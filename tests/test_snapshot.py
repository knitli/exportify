# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Tests for SnapshotManager."""

from __future__ import annotations

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

    def test_read_manifest_returns_none_on_invalid_json(self, manager):
        manager.snapshot_dir.mkdir(parents=True, exist_ok=True)
        manager.manifest_path.write_text("{ invalid json", encoding="utf-8")
        assert manager.read_manifest() is None

    def test_read_manifest_returns_none_on_missing_keys(self, manager):
        manager.snapshot_dir.mkdir(parents=True, exist_ok=True)
        # Missing "timestamp"
        manager.manifest_path.write_text('{"entries": []}', encoding="utf-8")
        assert manager.read_manifest() is None

    def test_read_manifest_returns_none_on_invalid_types(self, manager):
        manager.snapshot_dir.mkdir(parents=True, exist_ok=True)
        # Should be a dict, not a list
        manager.manifest_path.write_text("[]", encoding="utf-8")
        assert manager.read_manifest() is None
