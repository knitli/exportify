#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Tests for file_writer module."""

from __future__ import annotations

import tempfile

from pathlib import Path

import pytest

from exportify.export_manager.file_writer import BackupPolicy, FileWriter, WriteResult


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
        return FileWriter(backup_policy=BackupPolicy.ALWAYS)

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

    def test_write_existing_file_creates_backup(self, writer, temp_dir):
        """Test that writing to existing file creates backup."""
        target = temp_dir / "test.py"
        original_content = "# Original\n__all__ = ['old']\n"
        new_content = "# Updated\n__all__ = ['new']\n"

        # Write original
        target.write_text(original_content)

        # Update
        result = writer.write_file(target, new_content)

        assert result.success
        assert target.read_text() == new_content
        # Backup should be cleaned up after successful write
        assert not (temp_dir / "test.py.bak").exists()

    def test_write_invalid_syntax_fails(self, writer, temp_dir):
        """Test that invalid Python syntax is rejected."""
        target = temp_dir / "test.py"
        invalid_content = "def broken(\n"  # Missing closing paren

        result = writer.write_file(target, invalid_content)

        assert not result.success
        assert "syntax error" in result.error.lower()
        assert not target.exists()

    def test_backup_policy_never(self, temp_dir):
        """Test NEVER backup policy."""
        writer = FileWriter(backup_policy=BackupPolicy.NEVER)
        target = temp_dir / "test.py"
        original = "# Original\n__all__ = []\n"
        updated = "# Updated\n__all__ = []\n"

        target.write_text(original)
        result = writer.write_file(target, updated)

        assert result.success
        assert result.backup_path is None
        assert not (temp_dir / "test.py.bak").exists()

    def test_backup_policy_on_change_no_change(self, temp_dir):
        """Test ON_CHANGE policy when content doesn't change."""
        writer = FileWriter(backup_policy=BackupPolicy.ON_CHANGE)
        target = temp_dir / "test.py"
        content = "# Same content\n__all__ = []\n"

        target.write_text(content)
        result = writer.write_file(target, content)

        assert result.success
        assert result.backup_path is None

    def test_backup_policy_on_change_with_change(self, temp_dir):
        """Test ON_CHANGE policy when content changes."""
        writer = FileWriter(backup_policy=BackupPolicy.ON_CHANGE)
        target = temp_dir / "test.py"
        original = "# Original\n__all__ = []\n"
        updated = "# Updated\n__all__ = []\n"

        target.write_text(original)
        result = writer.write_file(target, updated)

        assert result.success
        # Backup cleaned up after successful write
        assert not (temp_dir / "test.py.bak").exists()

    def test_restore_backup(self, writer, temp_dir):
        """Test backup restoration."""
        target = temp_dir / "test.py"
        # Use the timestamped backup format: <stem>.py.backup.<timestamp>
        backup_path = temp_dir / "test.py.backup.20260222-120000"

        backup_content = "# Backup content\n__all__ = []\n"
        backup_path.write_text(backup_content)

        result = writer.restore_backup(target)

        assert result.success
        assert target.exists()
        assert target.read_text() == backup_content

    def test_restore_backup_no_backup(self, writer, temp_dir):
        """Test restore_backup when no backup exists."""
        target = temp_dir / "test.py"

        result = writer.restore_backup(target)

        assert not result.success
        assert "no backup file" in result.error.lower()

    def test_cleanup_backups(self, writer, temp_dir):
        """Test backup cleanup."""
        import time

        # Create some backup files
        old_backup = temp_dir / "old.py.bak"
        new_backup = temp_dir / "new.py.bak"

        old_backup.write_text("old")
        new_backup.write_text("new")

        # Make old backup appear old
        old_time = time.time() - (10 * 86400)  # 10 days ago
        import os

        os.utime(old_backup, (old_time, old_time))

        # Clean up backups older than 7 days
        removed = writer.cleanup_backups(temp_dir, max_age_days=7)

        assert removed == 1
        assert not old_backup.exists()
        assert new_backup.exists()

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
        backup = Path("/tmp/test.py.bak")

        result = WriteResult.success_result(target, backup)

        assert result.success
        assert result.file_path == target
        assert result.backup_path == backup
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


class TestBackupPolicy:
    """Test BackupPolicy enum."""

    def test_policy_values(self):
        """Test that all policy values are defined."""
        assert BackupPolicy.ALWAYS.value == "always"
        assert BackupPolicy.NEVER.value == "never"
        assert BackupPolicy.ON_CHANGE.value == "on_change"

    def test_policy_membership(self):
        """Test policy enum membership."""
        assert BackupPolicy.ALWAYS in BackupPolicy
        assert BackupPolicy.NEVER in BackupPolicy
        assert BackupPolicy.ON_CHANGE in BackupPolicy


class TestFileWriterEdgeCases:
    """Additional tests for FileWriter edge cases and error paths."""

    @pytest.fixture
    def temp_dir(self, tmp_path):
        """Use pytest's tmp_path fixture."""
        return tmp_path

    @pytest.fixture
    def writer(self):
        """Create a FileWriter instance with ALWAYS backup policy."""
        return FileWriter(backup_policy=BackupPolicy.ALWAYS)

    # --- Line 117: backup creation failure returns WriteResult.failure_result ---

    def test_write_file_backup_failure_returns_error(self, temp_dir, monkeypatch):
        """Test write_file returns failure when backup creation itself fails."""
        writer = FileWriter(backup_policy=BackupPolicy.ALWAYS)
        target = temp_dir / "test.py"
        original_content = "# Original\n__all__ = []\n"
        new_content = "# New\n__all__ = []\n"
        target.write_text(original_content)

        # Make _create_timestamped_backup return None to simulate backup failure
        monkeypatch.setattr(writer, "_create_timestamped_backup", lambda t: None)

        result = writer.write_file(target, new_content)

        assert not result.success
        assert isinstance(result.error, str)
        assert "Cannot create backup" in result.error

    # --- Lines 127-128: temp file creation failure ---

    def test_write_file_temp_file_creation_failure(self, temp_dir, monkeypatch):
        """Test write_file returns failure when temp file creation raises OSError."""
        import tempfile as tempfile_mod

        writer = FileWriter(backup_policy=BackupPolicy.NEVER)
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

        writer = FileWriter(backup_policy=BackupPolicy.NEVER, validator=flaky_validator)
        target = temp_dir / "test.py"
        content = "# Some content\n"

        result = writer.write_file(target, content)

        assert not result.success
        assert isinstance(result.error, str)
        assert "Temp file validation failed" in result.error

    # --- Lines 148-160: OSError during write with rollback ---

    def test_write_file_oserror_during_rename_triggers_rollback(self, temp_dir, monkeypatch):
        """Test write_file rolls back from backup when atomic rename raises OSError."""
        writer = FileWriter(backup_policy=BackupPolicy.ALWAYS)
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
        writer = FileWriter(backup_policy=BackupPolicy.NEVER)
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

    # --- Line 179: restore_backup with specific backup path not found ---

    def test_restore_backup_specific_path_not_found(self, temp_dir):
        """Test restore_backup fails with helpful message when specific backup path missing."""
        writer = FileWriter()
        target = temp_dir / "test.py"
        missing_backup = temp_dir / "test.py.backup.20260101-000000"

        result = writer.restore_backup(target, backup_path=missing_backup)

        assert not result.success
        assert isinstance(result.error, str)
        assert "Backup file not found" in result.error

    # --- Lines 184-185: restore_backup OSError ---

    def test_restore_backup_oserror(self, temp_dir, monkeypatch):
        """Test restore_backup returns failure when shutil.copy2 raises OSError."""
        import shutil

        writer = FileWriter()
        target = temp_dir / "test.py"
        backup = temp_dir / "test.py.backup.20260101-000000"
        backup.write_text("# Backup\n")

        def failing_copy2(src, dst):
            raise OSError("Disk error")

        monkeypatch.setattr(shutil, "copy2", failing_copy2)

        result = writer.restore_backup(target, backup_path=backup)

        assert not result.success
        assert isinstance(result.error, str)
        assert "Failed to restore backup" in result.error

    # --- Lines 201-202: _create_timestamped_backup OSError returns None ---

    def test_create_timestamped_backup_oserror_returns_none(self, temp_dir, monkeypatch):
        """Test _create_timestamped_backup returns None when shutil.copy2 fails."""
        import shutil

        writer = FileWriter()
        target = temp_dir / "test.py"
        target.write_text("# content\n")

        def failing_copy2(src, dst):
            raise OSError("Simulated copy failure")

        monkeypatch.setattr(shutil, "copy2", failing_copy2)

        result = writer._create_timestamped_backup(target)
        assert result is None

    # --- Lines 226-231: _cleanup_old_backups OSError on unlink ---

    def test_cleanup_old_backups_handles_oserror_on_unlink(self, temp_dir, monkeypatch):
        """Test _cleanup_old_backups continues when unlink raises OSError."""
        writer = FileWriter(max_backups=0)  # Force removal of all backups
        target = temp_dir / "__init__.py"
        target.write_text("# content\n")

        # Create a backup file
        backup = temp_dir / "__init__.py.backup.20260101-000000"
        backup.write_text("# backup\n")

        # Make unlink raise OSError
        original_unlink = Path.unlink

        def patched_unlink(self, *args, **kwargs):
            if "backup" in self.name:
                raise OSError("Cannot delete")
            return original_unlink(self, *args, **kwargs)

        monkeypatch.setattr(Path, "unlink", patched_unlink)

        # Should not raise, should handle gracefully
        removed = writer._cleanup_old_backups(target)
        assert removed == 0  # Nothing removed due to OSError

    # --- Line 264: cleanup_backups with non-existent directory ---

    def test_cleanup_backups_nonexistent_directory(self, temp_dir):
        """Test cleanup_backups returns 0 when directory doesn't exist."""
        writer = FileWriter()
        missing_dir = temp_dir / "does_not_exist"

        removed = writer.cleanup_backups(missing_dir, max_age_days=1)

        assert removed == 0

    # --- Lines 274-276: cleanup_backups OSError when stat() fails ---

    def test_cleanup_backups_oserror_on_stat(self, temp_dir, monkeypatch):
        """Test cleanup_backups handles OSError when stat() fails on a backup file."""
        writer = FileWriter()
        backup = temp_dir / "test.py.bak"
        backup.write_text("# old backup\n")

        original_stat = Path.stat

        def patched_stat(self, *args, **kwargs):
            if self == backup:
                raise OSError("Permission denied")
            return original_stat(self, *args, **kwargs)

        monkeypatch.setattr(Path, "stat", patched_stat)

        # Should not raise, should skip the problematic file
        removed = writer.cleanup_backups(temp_dir, max_age_days=0)
        assert removed == 0

    # --- Lines 297, 301-303: _should_backup with ON_CHANGE policy ---

    def test_should_backup_on_change_file_not_exists(self, temp_dir):
        """Test _should_backup returns False for ON_CHANGE when file doesn't exist."""
        writer = FileWriter(backup_policy=BackupPolicy.ON_CHANGE)
        target = temp_dir / "nonexistent.py"

        result = writer._should_backup(target, "some content")
        assert result is False

    def test_should_backup_on_change_oserror_reading_existing(self, temp_dir, monkeypatch):
        """Test _should_backup returns True for ON_CHANGE when existing file can't be read."""
        writer = FileWriter(backup_policy=BackupPolicy.ON_CHANGE)
        target = temp_dir / "test.py"
        target.write_text("# existing content\n")

        original_read_text = Path.read_text

        def patched_read_text(self, *args, **kwargs):
            if self == target:
                raise OSError("Cannot read")
            return original_read_text(self, *args, **kwargs)

        monkeypatch.setattr(Path, "read_text", patched_read_text)

        result = writer._should_backup(target, "some content")
        # When read fails, play it safe and backup
        assert result is True

    def test_should_backup_on_change_same_content(self, temp_dir):
        """Test _should_backup returns False for ON_CHANGE when content is identical."""
        writer = FileWriter(backup_policy=BackupPolicy.ON_CHANGE)
        target = temp_dir / "test.py"
        content = "# Same content\n__all__ = []\n"
        target.write_text(content)

        result = writer._should_backup(target, content)
        assert result is False

    def test_should_backup_on_change_different_content(self, temp_dir):
        """Test _should_backup returns True for ON_CHANGE when content differs."""
        writer = FileWriter(backup_policy=BackupPolicy.ON_CHANGE)
        target = temp_dir / "test.py"
        target.write_text("# Original\n")

        result = writer._should_backup(target, "# Updated\n")
        assert result is True

    # --- Ensure cleanup_backups actually removes old files (lines 269-276) ---

    def test_cleanup_backups_removes_old_bak_files(self, temp_dir):
        """Test cleanup_backups removes .py.bak files older than max_age_days."""
        import os
        import time

        writer = FileWriter()

        old_backup = temp_dir / "old.py.bak"
        old_backup.write_text("# old")
        old_time = time.time() - (10 * 86400)  # 10 days ago
        os.utime(old_backup, (old_time, old_time))

        recent_backup = temp_dir / "recent.py.bak"
        recent_backup.write_text("# recent")

        removed = writer.cleanup_backups(temp_dir, max_age_days=7)

        assert removed == 1
        assert not old_backup.exists()
        assert recent_backup.exists()

    # --- Timestamped backup is created and retained on successful write ---

    def test_write_file_creates_timestamped_backup_retained(self, temp_dir):
        """Test that a timestamped backup is created and kept after a successful write."""
        writer = FileWriter(backup_policy=BackupPolicy.ALWAYS)
        target = temp_dir / "test.py"
        original = "# Original\n__all__ = []\n"
        updated = "# Updated\n__all__ = []\n"

        target.write_text(original)
        result = writer.write_file(target, updated)

        assert result.success
        # The backup_path returned should exist
        assert result.backup_path is not None
        assert result.backup_path.exists()
        # Backup should have the timestamped format
        assert "backup" in result.backup_path.name

    # --- _cleanup_old_backups actually removes excess backups ---

    def test_cleanup_old_backups_removes_excess(self, temp_dir):
        """Test _cleanup_old_backups removes backups beyond max_backups."""
        import time

        writer = FileWriter(max_backups=2)
        target = temp_dir / "__init__.py"
        target.write_text("# content\n")

        # Create 4 backup files with different timestamps
        backups = []
        for i in range(4):
            backup = temp_dir / f"__init__.py.backup.2026010{i + 1}-000000"
            backup.write_text(f"# backup {i}\n")
            backups.append(backup)
            # Set modification time so sorting works correctly
            t = time.time() - (3 - i) * 3600  # newer = higher index
            import os

            os.utime(backup, (t, t))

        removed = writer._cleanup_old_backups(target)
        assert removed == 2  # 4 backups - max_backups(2) = 2 removed
