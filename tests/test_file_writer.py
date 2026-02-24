#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Tests for file_writer module."""

from __future__ import annotations

import tempfile

from pathlib import Path

import pytest

from exportify.export_manager.file_writer import FileWriter, WriteResult


class TestFileWriter:
    """Test FileWriter class."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for tests."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def writer(self):
        """Create a FileWriter instance."""
        return FileWriter()

    def test_write_new_file(self, writer, temp_dir):
        """Test writing to a new file."""
        target = temp_dir / "test.py"
        content = "# Test file\n__all__ = ['test']\n"

        result = writer.write_file(target, content)

        assert result.success
        assert result.file_path == target
        assert result.backup_path is None
        assert result.error is None
        assert target.exists()
        assert target.read_text() == content

    def test_write_invalid_syntax_fails(self, writer, temp_dir):
        """Test that invalid Python syntax is rejected."""
        target = temp_dir / "test.py"
        invalid_content = "def broken(\n"  # Missing closing paren

        result = writer.write_file(target, invalid_content)

        assert not result.success
        assert "syntax error" in result.error.lower()
        assert not target.exists()

    def test_custom_validator(self, temp_dir):
        """Test custom validation function."""

        def strict_validator(content: str) -> list[str]:
            return ["Content contains forbidden keyword"] if "forbidden" in content else []

        writer = FileWriter(validator=strict_validator)
        target = temp_dir / "test.py"

        # Should fail
        result = writer.write_file(target, "forbidden content")
        assert not result.success
        assert isinstance(result.error, str)
        assert "forbidden" in result.error.lower()

        # Should succeed
        result = writer.write_file(target, "allowed content")
        assert result.success

    def test_atomic_write_on_error(self, writer, temp_dir):
        """Test that atomic write preserves original on error."""
        target = temp_dir / "test.py"
        original = "# Original\n__all__ = []\n"
        invalid = "def broken(\n"  # Syntax error

        target.write_text(original)

        result = writer.write_file(target, invalid)

        assert not result.success
        # Original should be preserved
        assert target.read_text() == original

    def test_create_parent_directories(self, writer, temp_dir):
        """Test that parent directories are created."""
        target = temp_dir / "deep" / "nested" / "path" / "test.py"
        content = "# Test\n__all__ = []\n"

        result = writer.write_file(target, content)

        assert result.success
        assert target.exists()
        assert target.parent.exists()

    def test_write_result_success_helper(self):
        """Test WriteResult.success_result helper."""
        target = Path("/tmp/test.py")

        result = WriteResult.success_result(target)

        assert result.success
        assert result.file_path == target
        assert result.backup_path is None
        assert result.error is None

    def test_write_result_failure_helper(self):
        """Test WriteResult.failure_result helper."""
        target = Path("/tmp/test.py")
        error_msg = "Something went wrong"

        result = WriteResult.failure_result(target, error_msg)

        assert not result.success
        assert result.file_path == target
        assert result.backup_path is None
        assert result.error == error_msg


class TestFileWriterEdgeCases:
    """Additional tests for FileWriter edge cases and error paths."""

    @pytest.fixture
    def temp_dir(self, tmp_path):
        """Use pytest's tmp_path fixture."""
        return tmp_path

    @pytest.fixture
    def writer(self):
        """Create a FileWriter instance."""
        return FileWriter()

    # --- Lines 127-128: temp file creation failure ---

    def test_write_file_temp_file_creation_failure(self, temp_dir, monkeypatch):
        """Test write_file returns failure when temp file creation raises OSError."""
        import tempfile as tempfile_mod

        writer = FileWriter()
        target = temp_dir / "test.py"
        content = "# Valid\n__all__ = []\n"

        # Make tempfile.mkstemp raise OSError
        def failing_mkstemp(*args, **kwargs):
            raise OSError("No space left on device")

        monkeypatch.setattr(tempfile_mod, "mkstemp", failing_mkstemp)

        result = writer.write_file(target, content)

        assert not result.success
        assert isinstance(result.error, str)
        assert "Cannot create temp file" in result.error

    # --- Lines 137-140: temp file secondary validation failure ---

    def test_write_file_temp_validation_failure(self, temp_dir, monkeypatch):
        """Test write_file returns failure when temp file secondary validation fails."""
        # Use a validator that always passes on first call but fails on second
        call_count = [0]

        def flaky_validator(content: str) -> list[str]:
            call_count[0] += 1
            # Second call is temp file re-validation
            return ["Simulated temp validation failure"] if call_count[0] >= 2 else []

        writer = FileWriter(validator=flaky_validator)
        target = temp_dir / "test.py"
        content = "# Some content\n"

        result = writer.write_file(target, content)

        assert not result.success
        assert isinstance(result.error, str)
        assert "Temp file validation failed" in result.error

    # --- Lines 148-160: OSError during write with rollback ---

    def test_write_file_oserror_during_rename_triggers_rollback(self, temp_dir, monkeypatch):
        """Test write_file rolls back from backup when atomic rename raises OSError."""
        writer = FileWriter()
        target = temp_dir / "test.py"
        original_content = "# Original\n__all__ = []\n"
        new_content = "# Updated\n__all__ = []\n"
        target.write_text(original_content)

        # Monkeypatch Path.replace to raise OSError during atomic rename
        original_replace = Path.replace

        def patched_replace(self, other):
            # Only fail for the temp file rename (not backup operations)
            if "__init__" in self.name or (self.suffix == ".py" and "backup" not in self.name):
                raise OSError("Simulated rename failure")
            return original_replace(self, other)

        monkeypatch.setattr(Path, "replace", patched_replace)

        result = writer.write_file(target, new_content)

        assert not result.success
        assert isinstance(result.error, str)
        assert "Write failed" in result.error or "Permission denied" in result.error

    def test_write_file_permission_error_label(self, temp_dir, monkeypatch):
        """Test write_file labels PermissionError correctly."""
        writer = FileWriter()
        target = temp_dir / "test.py"
        content = "# Test\n__all__ = []\n"

        # Monkeypatch Path.replace to raise PermissionError
        def patched_replace(self, other):
            raise PermissionError("Permission denied")

        monkeypatch.setattr(Path, "replace", patched_replace)

        result = writer.write_file(target, content)

        assert not result.success
        assert isinstance(result.error, str)
        assert "Permission denied" in result.error
