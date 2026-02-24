# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Tests for the undo command."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from exportify.commands.undo import undo
from exportify.common.snapshot import SnapshotManager


@pytest.fixture
def project_root(tmp_path: Path):
    (tmp_path / "src" / "pkg").mkdir(parents=True)
    (tmp_path / "src" / "pkg" / "__init__.py").write_text("# fixed version\n__all__ = []\n")
    return tmp_path


class TestUndoFunction:
    def test_undo_no_snapshot_does_not_raise(self, project_root):
        """undo() should handle missing snapshot gracefully."""
        manager = SnapshotManager(project_root)
        assert not manager.has_snapshot()
        # Should complete without raising
        with patch("exportify.commands.undo.SnapshotManager", return_value=manager):
            undo()

    def test_undo_restores_all_files(self, project_root):
        init = project_root / "src" / "pkg" / "__init__.py"
        manager = SnapshotManager(project_root)
        manager.capture([init])
        # Simulate fix modifying the file
        init.write_text("# after fix\n__all__ = ['Bar']\n")

        with patch("exportify.commands.undo.SnapshotManager", return_value=manager):
            undo()

        assert init.read_text() == "# fixed version\n__all__ = []\n"

    def test_undo_with_path_filter(self, project_root):
        init = project_root / "src" / "pkg" / "__init__.py"
        manager = SnapshotManager(project_root)
        manager.capture([init])
        init.write_text("# after fix\n")

        with patch("exportify.commands.undo.SnapshotManager", return_value=manager):
            undo(init)

        assert init.read_text() == "# fixed version\n__all__ = []\n"

    def test_undo_is_idempotent(self, project_root):
        init = project_root / "src" / "pkg" / "__init__.py"
        manager = SnapshotManager(project_root)
        manager.capture([init])
        init.write_text("# after fix\n")

        with patch("exportify.commands.undo.SnapshotManager", return_value=manager):
            undo()
            assert init.read_text() == "# fixed version\n__all__ = []\n"

            # Dirty the file again to verify the second undo also restores
            init.write_text("# dirtied again\n")
            undo()

        assert init.read_text() == "# fixed version\n__all__ = []\n"

    def test_undo_path_filter_no_match_does_not_raise(self, project_root):
        init = project_root / "src" / "pkg" / "__init__.py"
        manager = SnapshotManager(project_root)
        manager.capture([init])

        nonexistent_path = project_root / "src" / "other"
        with patch("exportify.commands.undo.SnapshotManager", return_value=manager):
            undo(nonexistent_path)  # should not raise


class TestUndoCommandObject:
    def test_undo_command_is_cyclopts_app(self):
        from cyclopts import App

        from exportify.commands.undo import UndoCommand

        assert isinstance(UndoCommand, App)

    def test_undo_exported_from_module(self):
        from exportify.commands.undo import UndoCommand, undo

        assert callable(undo)
        assert UndoCommand is not None
