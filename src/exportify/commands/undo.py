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
