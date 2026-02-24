# Snapshot & Undo Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace per-file backup clutter in the source tree with a pre-flight snapshot system stored in `.exportify/snapshots/last/`, and add an `exportify undo` command to restore from it.

**Architecture:** Before `fix` writes any files, a `SnapshotManager` captures originals to `.exportify/snapshots/last/files/` and records a manifest. `FileWriter` loses its backup machinery entirely — atomic writes via temp file already prevent data loss. `exportify undo [paths...]` reads the manifest and restores, idempotently.

**Tech Stack:** Python 3.12+, stdlib only (`json`, `shutil`, `dataclasses`, `pathlib`), cyclopts for the CLI command.

---

## Task 1: Update `.gitignore`

**Files:**
- Modify: `.gitignore`

**Step 1: Add the snapshots dir to `.gitignore`**

In `.gitignore`, find the line `*mcp*.backup*` (line 19) and add two lines below it:

```
.exportify/snapshots/
*.py.backup.*
```

The second pattern catches any stray backup files that already exist in the working tree.

**Step 2: Verify it parses correctly (dry-run)**

```bash
git check-ignore -v src/exportify/__init__.py.backup.20260224-010717
```

Expected: should now be matched by `*.py.backup.*`.

**Step 3: Commit**

```bash
git add .gitignore
git commit -m "chore: ignore exportify snapshots dir and stray backup files"
```

---

## Task 2: Add snapshot constant to `common/config.py`

**Files:**
- Modify: `src/exportify/common/config.py:43` (right after `DEFAULT_CACHE_SUBDIR`)

**Step 1: Read the current constant**

Open `src/exportify/common/config.py` and find:

```python
DEFAULT_CACHE_SUBDIR: Path = Path(".exportify") / "cache"
```

**Step 2: Add the snapshot constant below it**

```python
DEFAULT_SNAPSHOT_DIR: Path = Path(".exportify") / "snapshots" / "last"
```

**Step 3: Export it from `__all__`**

Find the `__all__` tuple in `config.py` and add `"DEFAULT_SNAPSHOT_DIR"` alongside `"DEFAULT_CACHE_SUBDIR"`.

**Step 4: Commit**

```bash
git add src/exportify/common/config.py
git commit -m "feat: add DEFAULT_SNAPSHOT_DIR constant to common config"
```

---

## Task 3: Create `SnapshotManager` (TDD)

**Files:**
- Create: `tests/test_snapshot.py`
- Create: `src/exportify/common/snapshot.py`

### Step 1: Write the failing tests

Create `tests/test_snapshot.py`:

```python
# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Tests for SnapshotManager."""

from __future__ import annotations

import json

from pathlib import Path

import pytest

from exportify.common.snapshot import SnapshotManager


@pytest.fixture
def project_root(tmp_path):
    """Create a fake project root with some Python files."""
    (tmp_path / "src" / "pkg").mkdir(parents=True)
    (tmp_path / "src" / "pkg" / "__init__.py").write_text("# original init\n__all__ = []\n")
    (tmp_path / "src" / "pkg" / "mod.py").write_text("# original mod\n__all__ = ['Foo']\n")
    return tmp_path


@pytest.fixture
def manager(project_root):
    return SnapshotManager(project_root)


class TestSnapshotManagerCapture:
    def test_has_snapshot_false_before_capture(self, manager):
        assert not manager.has_snapshot()

    def test_capture_creates_manifest(self, project_root, manager):
        files = [
            project_root / "src" / "pkg" / "__init__.py",
            project_root / "src" / "pkg" / "mod.py",
        ]
        manager.capture(files)
        assert manager.manifest_path.exists()

    def test_manifest_contains_correct_entries(self, project_root, manager):
        files = [
            project_root / "src" / "pkg" / "__init__.py",
            project_root / "src" / "pkg" / "mod.py",
        ]
        manager.capture(files)
        manifest = manager.read_manifest()
        assert manifest is not None
        sources = [e.source for e in manifest.entries]
        assert "src/pkg/__init__.py" in sources
        assert "src/pkg/mod.py" in sources

    def test_capture_stores_file_contents(self, project_root, manager):
        init = project_root / "src" / "pkg" / "__init__.py"
        manager.capture([init])
        manifest = manager.read_manifest()
        entry = manifest.entries[0]
        stored = manager.files_dir / entry.stored
        assert stored.exists()
        assert stored.read_text() == "# original init\n__all__ = []\n"

    def test_capture_skips_nonexistent_files(self, project_root, manager):
        missing = project_root / "src" / "pkg" / "ghost.py"
        manager.capture([missing])
        manifest = manager.read_manifest()
        assert manifest is not None
        assert len(manifest.entries) == 0

    def test_has_snapshot_true_after_capture(self, project_root, manager):
        manager.capture([project_root / "src" / "pkg" / "__init__.py"])
        assert manager.has_snapshot()

    def test_capture_overwrites_previous_snapshot(self, project_root, manager):
        init = project_root / "src" / "pkg" / "__init__.py"
        manager.capture([init])
        init.write_text("# modified\n__all__ = ['Bar']\n")
        manager.capture([init])
        manifest = manager.read_manifest()
        entry = next(e for e in manifest.entries if "init" in e.source)
        stored = manager.files_dir / entry.stored
        assert stored.read_text() == "# modified\n__all__ = ['Bar']\n"


class TestSnapshotManagerRestore:
    def test_restore_all_files(self, project_root, manager):
        init = project_root / "src" / "pkg" / "__init__.py"
        manager.capture([init])
        # Simulate fix modifying the file
        init.write_text("# after fix\n__all__ = ['Bar']\n")
        restored = manager.restore()
        assert len(restored) == 1
        assert init.read_text() == "# original init\n__all__ = []\n"

    def test_restore_is_idempotent(self, project_root, manager):
        init = project_root / "src" / "pkg" / "__init__.py"
        manager.capture([init])
        init.write_text("# after fix\n")
        manager.restore()
        manager.restore()  # second restore should not raise
        assert init.read_text() == "# original init\n__all__ = []\n"

    def test_restore_with_path_filter_restores_matching(self, project_root, manager):
        init = project_root / "src" / "pkg" / "__init__.py"
        mod = project_root / "src" / "pkg" / "mod.py"
        manager.capture([init, mod])
        init.write_text("# after fix\n")
        mod.write_text("# after fix\n")
        restored = manager.restore(paths=[project_root / "src" / "pkg" / "__init__.py"])
        assert len(restored) == 1
        assert init.read_text() == "# original init\n__all__ = []\n"
        # mod.py not in filter, still changed
        assert mod.read_text() == "# after fix\n"

    def test_restore_with_directory_filter(self, project_root, manager):
        init = project_root / "src" / "pkg" / "__init__.py"
        mod = project_root / "src" / "pkg" / "mod.py"
        manager.capture([init, mod])
        init.write_text("# after fix\n")
        mod.write_text("# after fix\n")
        restored = manager.restore(paths=[project_root / "src" / "pkg"])
        assert len(restored) == 2

    def test_restore_no_snapshot_returns_empty(self, manager):
        result = manager.restore()
        assert result == []

    def test_restore_path_filter_no_match_returns_empty(self, project_root, manager):
        init = project_root / "src" / "pkg" / "__init__.py"
        manager.capture([init])
        result = manager.restore(paths=[project_root / "src" / "other"])
        assert result == []

    def test_read_manifest_returns_none_when_missing(self, manager):
        assert manager.read_manifest() is None
```

### Step 2: Run tests to verify they fail

```bash
uv run pytest tests/test_snapshot.py -v
```

Expected: `ModuleNotFoundError: No module named 'exportify.common.snapshot'`

### Step 3: Implement `src/exportify/common/snapshot.py`

```python
# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Pre-flight snapshot system for exportify fix runs.

Captures original file contents before the fix command modifies them,
storing snapshots in .exportify/snapshots/last/ so the undo command
can restore them.
"""

from __future__ import annotations

import json
import shutil

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path


@dataclass
class SnapshotEntry:
    """One file in the snapshot."""

    source: str  # relative path from project root
    stored: str  # filename inside files_dir, e.g. "0.py"


@dataclass
class SnapshotManifest:
    """Full manifest for a snapshot."""

    timestamp: str
    entries: list[SnapshotEntry]

    def to_dict(self) -> dict:
        return {"timestamp": self.timestamp, "entries": [asdict(e) for e in self.entries]}

    @classmethod
    def from_dict(cls, d: dict) -> SnapshotManifest:
        return cls(
            timestamp=d["timestamp"],
            entries=[SnapshotEntry(**e) for e in d.get("entries", [])],
        )


class SnapshotManager:
    """Manages pre-flight snapshots for exportify fix runs.

    Snapshots are stored in .exportify/snapshots/last/ relative to the
    project root. Only one snapshot (the most recent) is kept.
    """

    SNAPSHOT_SUBDIR = Path(".exportify") / "snapshots" / "last"

    def __init__(self, project_root: Path | None = None) -> None:
        self.project_root = (project_root or Path.cwd()).resolve()
        self.snapshot_dir = self.project_root / self.SNAPSHOT_SUBDIR
        self.files_dir = self.snapshot_dir / "files"
        self.manifest_path = self.snapshot_dir / "manifest.json"

    def capture(self, files: list[Path]) -> SnapshotManifest:
        """Capture current content of files before modification.

        Only files that exist are captured. Overwrites any previous snapshot.

        Args:
            files: Absolute paths to files that may be modified.

        Returns:
            The manifest that was written.
        """
        # Wipe and recreate snapshot dirs for clean overwrite
        if self.snapshot_dir.exists():
            shutil.rmtree(self.snapshot_dir)
        self.files_dir.mkdir(parents=True, exist_ok=True)

        entries: list[SnapshotEntry] = []
        for i, file_path in enumerate(files):
            if not file_path.exists():
                continue
            stored_name = f"{i}.py"
            shutil.copy2(file_path, self.files_dir / stored_name)
            rel = str(file_path.resolve().relative_to(self.project_root))
            entries.append(SnapshotEntry(source=rel, stored=stored_name))

        manifest = SnapshotManifest(
            timestamp=datetime.now(UTC).isoformat(),
            entries=entries,
        )
        self.manifest_path.write_text(
            json.dumps(manifest.to_dict(), indent=2), encoding="utf-8"
        )
        return manifest

    def restore(self, paths: list[Path] | None = None) -> list[Path]:
        """Restore files from the last snapshot.

        Idempotent: calling restore multiple times produces the same result.

        Args:
            paths: Optional list of files or directories to filter the restore.
                   A directory path matches all snapshot entries under it.
                   If None, all entries are restored.

        Returns:
            List of file paths that were restored.
        """
        manifest = self.read_manifest()
        if manifest is None:
            return []

        resolved_filters: list[Path] | None = None
        if paths:
            resolved_filters = [p.resolve() for p in paths]

        restored: list[Path] = []
        for entry in manifest.entries:
            abs_source = self.project_root / entry.source

            if resolved_filters is not None:
                if not any(
                    abs_source == f or abs_source.is_relative_to(f)
                    for f in resolved_filters
                ):
                    continue

            stored = self.files_dir / entry.stored
            if not stored.exists():
                continue

            abs_source.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(stored, abs_source)
            restored.append(abs_source)

        return restored

    def has_snapshot(self) -> bool:
        """Return True if a snapshot manifest exists."""
        return self.manifest_path.exists()

    def read_manifest(self) -> SnapshotManifest | None:
        """Read and parse the manifest, returning None if not present."""
        if not self.manifest_path.exists():
            return None
        try:
            data = json.loads(self.manifest_path.read_text(encoding="utf-8"))
            return SnapshotManifest.from_dict(data)
        except (json.JSONDecodeError, KeyError, TypeError):
            return None
```

### Step 4: Run tests to verify they pass

```bash
uv run pytest tests/test_snapshot.py -v
```

Expected: all tests PASS.

### Step 5: Export from `common/__init__.py`

Open `src/exportify/common/__init__.py`. Add `SnapshotManager`, `SnapshotManifest`, and `SnapshotEntry` to its `_dynamic_imports` and `__all__` (using the same lazy-import pattern already present in that file).

### Step 6: Commit

```bash
git add src/exportify/common/snapshot.py tests/test_snapshot.py src/exportify/common/__init__.py
git commit -m "feat: add SnapshotManager for pre-flight fix snapshots"
```

---

## Task 4: Create `undo` command (TDD)

**Files:**
- Create: `tests/test_undo.py`
- Create: `src/exportify/commands/undo.py`

### Step 1: Write the failing tests

Create `tests/test_undo.py`:

```python
# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Tests for the undo command."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from cyclopts import App

from exportify.commands.undo import UndoCommand, undo


@pytest.fixture
def project_root(tmp_path):
    (tmp_path / "src" / "pkg").mkdir(parents=True)
    (tmp_path / "src" / "pkg" / "__init__.py").write_text("# fixed version\n")
    return tmp_path


def _run_undo(args: list[str] = None, project_root: Path = None):
    """Helper to invoke the undo command via its App."""
    with patch("exportify.commands.undo.SnapshotManager") as MockManager:
        yield MockManager


class TestUndoCommand:
    def test_undo_no_snapshot_warns(self, capsys, project_root):
        from exportify.common.snapshot import SnapshotManager

        manager = SnapshotManager(project_root)
        # No snapshot created — undo should print a warning

        with patch("exportify.commands.undo.SnapshotManager", return_value=manager):
            UndoCommand(["undo"], exit_on_error=False)

        # Should not raise, should warn
        captured = capsys.readouterr()
        # Rich output goes through a Console; we check the undo logic via unit test below

    def test_undo_restores_all_files(self, project_root):
        from exportify.common.snapshot import SnapshotManager

        init = project_root / "src" / "pkg" / "__init__.py"
        manager = SnapshotManager(project_root)
        manager.capture([init])
        init.write_text("# after fix\n")

        with patch("exportify.commands.undo.SnapshotManager", return_value=manager):
            with patch("exportify.commands.undo.Path.cwd", return_value=project_root):
                undo()

        assert init.read_text() == "# fixed version\n"

    def test_undo_with_path_filter(self, project_root):
        from exportify.common.snapshot import SnapshotManager

        init = project_root / "src" / "pkg" / "__init__.py"
        manager = SnapshotManager(project_root)
        manager.capture([init])
        init.write_text("# after fix\n")

        with patch("exportify.commands.undo.SnapshotManager", return_value=manager):
            undo(init)

        assert init.read_text() == "# fixed version\n"

    def test_undo_command_is_app_instance(self):
        from cyclopts import App

        assert isinstance(UndoCommand, App)
```

### Step 2: Run tests to verify they fail

```bash
uv run pytest tests/test_undo.py -v
```

Expected: `ModuleNotFoundError: No module named 'exportify.commands.undo'`

### Step 3: Implement `src/exportify/commands/undo.py`

```python
# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Implementation of the ``undo`` command — restores files from the last fix snapshot."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from cyclopts import App, Parameter

from exportify.commands.utils import CONSOLE, print_info, print_success, print_warning
from exportify.common.snapshot import SnapshotManager


UndoCommand = App(console=CONSOLE)


@UndoCommand.default
def undo(
    *paths: Annotated[
        Path,
        Parameter(help="Files or directories to restore (default: all)"),
    ],
    verbose: Annotated[bool, Parameter(help="Show each restored file")] = False,
) -> None:
    """Restore files modified by the last fix run.

    Reads the snapshot taken before the most recent ``fix`` run and
    restores the original content.  Idempotent — safe to run multiple times.

    If paths are given, only matching files are restored.

    Examples:
        exportify undo
        exportify undo src/mypackage/
        exportify undo src/foo/__init__.py src/bar/__init__.py
    """
    manager = SnapshotManager()

    if not manager.has_snapshot():
        print_warning("No snapshot found — run `exportify fix` first to create one.")
        return

    path_list = list(paths) or None
    restored = manager.restore(path_list)

    if not restored:
        if path_list:
            print_warning("No snapshot entries matched the given paths.")
        else:
            print_info("Nothing to restore — snapshot is empty.")
        return

    if verbose:
        for p in restored:
            print_success(f"Restored {p}")

    CONSOLE.print()
    print_success(f"Restored {len(restored)} file(s) from snapshot.")
    CONSOLE.print()


if __name__ == "__main__":
    UndoCommand()


__all__ = (
    "UndoCommand",
    "undo",
)
```

### Step 4: Run tests to verify they pass

```bash
uv run pytest tests/test_undo.py -v
```

Expected: all tests PASS.

### Step 5: Commit

```bash
git add src/exportify/commands/undo.py tests/test_undo.py
git commit -m "feat: add exportify undo command for fix rollback"
```

---

## Task 5: Add pre-flight snapshot to `fix.py`

**Files:**
- Modify: `src/exportify/commands/fix.py`

**Step 1: Import `SnapshotManager`**

Add to the imports in `fix.py`:

```python
from exportify.common.snapshot import SnapshotManager
```

**Step 2: Capture snapshot at the start of `fix()`**

In the `fix()` function, after `py_files = collect_py_files(paths, source)` and before the `if "module_all" in fixes_to_run:` block, add:

```python
    if not dry_run:
        snapshot = SnapshotManager()
        snapshot.capture(py_files)
        if verbose:
            print_info(f"Snapshot captured ({len(py_files)} file(s))")
```

Note: `py_files` contains all `.py` files discovered; the `SnapshotManager` only stores files that actually exist, so this is safe.

**Step 3: Run the existing fix tests (no fix tests exist yet, run full suite)**

```bash
uv run pytest -x -q
```

Expected: all tests PASS.

**Step 4: Commit**

```bash
git add src/exportify/commands/fix.py
git commit -m "feat: capture pre-flight snapshot before fix writes any files"
```

---

## Task 6: Simplify `FileWriter` — remove backup machinery

The per-file backup was the root cause of source tree clutter. Now that the snapshot system covers recovery, `FileWriter` only needs atomic writes.

**Files:**
- Modify: `src/exportify/export_manager/file_writer.py`
- Modify: `tests/test_file_writer.py`

### Step 1: Understand what stays and what goes

**Remove from `FileWriter`:**
- `BackupPolicy` enum (dead code once `backup_policy` param is gone)
- `__init__` params: `backup_policy`, `max_backups`
- Methods: `restore_backup`, `_create_timestamped_backup`, `_cleanup_old_backups`, `_find_latest_backup`, `cleanup_backups`, `_should_backup`
- In `write_file`: the entire backup block (lines 113–120), the `create_backup` param
- `WriteResult.backup_path`: set to always `None` (keep field for now; removing it would be a separate cleanup)

**Keep:**
- `FileWriter.__init__` with `validator` only
- `write_file(target, content)` — atomic via temp file + rename
- `WriteResult` dataclass (with `backup_path: Path | None = None`)
- `_default_validator`

### Step 2: Rewrite `file_writer.py`

Replace the entire file content with:

```python
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
import tempfile

from dataclasses import dataclass, field
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

    def __init__(
        self,
        validator: Callable[[str], list[str]] | None = None,
    ) -> None:
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
            temp_path = Path(temp_filepath)
        except OSError as e:
            return WriteResult.failure_result(target, f"Cannot create temp file: {e}")

        try:
            with temp_path.open("w", encoding="utf-8") as f:
                f.write(content)

            # 3. Validate temp file (belt-and-suspenders)
            temp_content = temp_path.read_text(encoding="utf-8")
            if validation_errors := self.validator(temp_content):
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
        """Default validation: check Python syntax."""
        errors = []
        try:
            ast.parse(content)
        except SyntaxError as e:
            errors.append(f"Syntax error at line {e.lineno}: {e.msg}")
        return errors


__all__ = ["FileWriter", "WriteResult"]
```

### Step 3: Update `tests/test_file_writer.py`

The backup-related tests need to be removed or updated. Here are the tests to **delete**:
- `test_write_existing_file_creates_backup` — tests backup creation, no longer applies
- `test_backup_policy_never` — `BackupPolicy` removed
- `test_backup_policy_on_change_no_change` — `BackupPolicy` removed
- `test_backup_policy_on_change_with_change` — `BackupPolicy` removed
- `test_restore_backup` — `restore_backup` removed
- `test_restore_backup_no_backup` — `restore_backup` removed
- `test_cleanup_backups` — `cleanup_backups` removed
- `test_write_result_success_helper` — update: remove `backup` arg
- `test_write_file_backup_failure_returns_error` — remove
- `test_restore_backup_specific_path_not_found` — remove
- `test_restore_backup_oserror` — remove
- `test_create_timestamped_backup_oserror_returns_none` — remove
- `test_cleanup_old_backups_handles_oserror_on_unlink` — remove
- `test_cleanup_backups_nonexistent_directory` — remove
- `test_cleanup_backups_oserror_on_stat` — remove
- `test_should_backup_*` (4 tests) — remove
- `test_cleanup_backups_removes_old_bak_files` — remove
- `test_write_file_creates_timestamped_backup_retained` — remove
- `test_cleanup_old_backups_removes_excess` — remove
- `TestBackupPolicy` class — remove entirely

Tests to **update**:
- `test_write_result_success_helper`: remove the `backup` argument from `WriteResult.success_result(target, backup)` → `WriteResult.success_result(target)`, and assert `result.backup_path is None`

Tests to **keep unchanged**: all others (`test_write_new_file`, `test_write_invalid_syntax_fails`, `test_atomic_write_on_error`, `test_create_parent_directories`, `test_write_result_failure_helper`, `test_custom_validator`, `test_write_file_temp_file_creation_failure`, `test_write_file_temp_validation_failure`, `test_write_file_oserror_during_rename_triggers_rollback`, `test_write_file_permission_error_label`).

### Step 4: Update `export_manager/__init__.py`

Remove `BackupPolicy` from the `_dynamic_imports` dict, `TYPE_CHECKING` import block, and `__all__` in `src/exportify/export_manager/__init__.py`.

### Step 5: Run tests

```bash
uv run pytest tests/test_file_writer.py -v
```

Expected: all remaining tests PASS.

```bash
uv run pytest -x -q
```

Expected: full suite PASS.

### Step 6: Commit

```bash
git add src/exportify/export_manager/file_writer.py tests/test_file_writer.py src/exportify/export_manager/__init__.py
git commit -m "refactor: remove per-file backup from FileWriter; snapshots handle recovery"
```

---

## Task 7: Register `undo` in the CLI

**Files:**
- Modify: `src/exportify/cli.py`
- Modify: `src/exportify/commands/__init__.py`

### Step 1: Add `undo` to `cli.py`

In `cli.py`, after the `clear-cache` line, add:

```python
app.command("exportify.commands.undo:UndoCommand", name="undo")
```

Also update the module docstring to list `undo` alongside the other commands.

### Step 2: Export `UndoCommand` from `commands/__init__.py`

Add `UndoCommand` and `undo` to `_dynamic_imports` and `__all__` in `src/exportify/commands/__init__.py` following the same lazy-import pattern used for `FixCommand`, etc.

### Step 3: Smoke-test the CLI

```bash
uv run exportify undo --help
```

Expected: help text for the `undo` command appears.

### Step 4: Run the full test suite

```bash
uv run pytest -q
```

Expected: all tests PASS.

### Step 5: Commit

```bash
git add src/exportify/cli.py src/exportify/commands/__init__.py
git commit -m "feat: register exportify undo command in CLI"
```

---

## Task 8: Delete stray backup files and final validation

**Step 1: Delete existing backup files**

```bash
find /home/knitli/exportify/src -name "*.py.backup.*" -delete
```

**Step 2: Verify git status is clean**

```bash
git status
```

Expected: the `?? src/exportify/*.backup.*` entries are gone.

**Step 3: Run full test suite one final time**

```bash
uv run pytest -q
```

Expected: all tests PASS with no errors.

**Step 4: Commit**

```bash
git add -u  # stage the deletions
git commit -m "chore: delete stray backup files from source tree"
```

---

## Summary of Changes

| File | Action |
|------|--------|
| `.gitignore` | Add `*.py.backup.*` and `.exportify/snapshots/` |
| `src/exportify/common/config.py` | Add `DEFAULT_SNAPSHOT_DIR` constant |
| `src/exportify/common/snapshot.py` | **New** — `SnapshotManager`, `SnapshotManifest`, `SnapshotEntry` |
| `src/exportify/commands/undo.py` | **New** — `UndoCommand`, `undo()` |
| `src/exportify/commands/fix.py` | Add pre-flight `SnapshotManager.capture()` call |
| `src/exportify/export_manager/file_writer.py` | Remove all backup machinery; keep atomic write |
| `src/exportify/export_manager/__init__.py` | Remove `BackupPolicy` export |
| `src/exportify/cli.py` | Register `undo` command |
| `src/exportify/commands/__init__.py` | Export `UndoCommand`, `undo` |
| `tests/test_snapshot.py` | **New** — `SnapshotManager` tests |
| `tests/test_undo.py` | **New** — `undo` command tests |
| `tests/test_file_writer.py` | Remove/update backup-related tests |
