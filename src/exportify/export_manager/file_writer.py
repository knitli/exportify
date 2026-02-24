# sourcery skip: do-not-use-staticmethod
# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""File writing operations with atomic writes and validation.

This module implements safe file writing for generated __init__.py files:
- Atomic writes via temp file + rename (no data loss on failure)
- Validation before commit
- Temp file cleanup on error
"""

from __future__ import annotations

import ast
import os
import tempfile

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from collections.abc import Callable


@dataclass(frozen=True)
class WriteResult:
    """Result of a file write operation."""

    success: bool
    file_path: Path
    backup_path: Path | None  # always None; kept for API compatibility
    error: str | None

    @classmethod
    def success_result(cls, file_path: Path, backup_path: Path | None = None) -> WriteResult:
        """Create a success result."""
        return cls(success=True, file_path=file_path, backup_path=None, error=None)

    @classmethod
    def failure_result(cls, file_path: Path, error: str) -> WriteResult:
        """Create a failure result."""
        return cls(success=False, file_path=file_path, backup_path=None, error=error)


class FileWriter:
    """Handles atomic file writes with validation.

    Writes are performed via a temp file + atomic rename, so the target
    file is never left in a partial state.  Pre-run snapshots (see
    SnapshotManager) provide user-facing rollback instead of per-file backups.
    """

    def __init__(self, validator: Callable[[str], list[str]] | None = None) -> None:
        """Initialize file writer.

        Args:
            validator: Optional validation function returning a list of errors.
                       Defaults to Python syntax checking.
        """
        self.validator = validator or self._default_validator

    def write_file(self, target: Path, content: str) -> WriteResult:
        """Write file atomically.

        Algorithm:
        1. Validate content (AST parse)
        2. Write to temp file in target's directory
        3. Validate temp file content
        4. Atomic rename to target
        5. Return result

        Args:
            target: Target file path
            content: File content to write

        Returns:
            WriteResult with success status
        """
        # 1. Validate content first
        if validation_errors := self.validator(content):
            error_msg = "Generated code has syntax errors:\n" + "\n".join(
                f"  - {err}" for err in validation_errors
            )
            return WriteResult.failure_result(target, error_msg)

        # Ensure parent directory exists
        target.parent.mkdir(parents=True, exist_ok=True)

        # 2. Write to temp file
        try:
            _temp_fd, temp_filepath = tempfile.mkstemp(
                suffix=".py", prefix="__init__", dir=target.parent, text=True
            )
            os.close(_temp_fd)
            temp_path = Path(temp_filepath)
        except OSError as e:
            return WriteResult.failure_result(target, f"Cannot create temp file: {e}")

        try:
            with temp_path.open("w", encoding="utf-8") as f:
                f.write(content)

            # 3. Validate temp file (belt-and-suspenders)
            temp_content = temp_path.read_text(encoding="utf-8")
            if validation_errors := self.validator(temp_content):
                temp_path.unlink(missing_ok=True)
                error_msg = "Temp file validation failed:\n" + "\n".join(
                    f"  - {err}" for err in validation_errors
                )
                return WriteResult.failure_result(target, error_msg)

            # 4. Atomic rename
            temp_path.replace(target)
            return WriteResult.success_result(target)

        except OSError as e:
            if temp_path.exists():
                temp_path.unlink()
            error_type = "Permission denied" if isinstance(e, PermissionError) else "Write failed"
            return WriteResult.failure_result(target, f"{error_type}: {e}")

    @staticmethod
    def _default_validator(content: str) -> list[str]:
        """Default validation: check Python syntax.

        Args:
            content: Python source code

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []
        try:
            ast.parse(content)
        except SyntaxError as e:
            errors.append(f"Syntax error at line {e.lineno}: {e.msg}")
        return errors


__all__ = ["FileWriter", "WriteResult"]
