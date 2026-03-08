# sourcery skip: avoid-global-variables
# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Exportify CLI entry point and command registration.

Registers the core commands and wires them to the ``exportify`` program:
- ``init``   — initialize project configuration
- ``sync``   — align project code with export rules
- ``check``  — validate exports and __all__ consistency
- ``doctor`` — run system and configuration health checks
- ``undo``   — restore files from the last sync run
- ``cache``  — manage analysis results and cache
"""

from __future__ import annotations

import logging

from cyclopts import App

from exportify import __version__
from exportify.commands.utils import CONSOLE


logger = logging.getLogger(__name__)

app = App(
    name="exportify",
    help="Manage Python package exports: generate \\_\\_init\\_\\_.py files, maintain \\_\\_all\\_\\_, and validate consistency",
    version=__version__,
    console=CONSOLE,
)


app.command(
    "exportify.commands.init:InitCommand", name="init", help="Initialize Exportify in a project"
)
app.command(
    "exportify.commands.sync:SyncCommand", name="sync", help="Synchronize project with export rules"
)
app.command(
    "exportify.commands.check:CheckCommand",
    name="check",
    help="Validate exports and \\_\\_all\\_\\_ consistency",
)
app.command(
    "exportify.commands.doctor:DoctorCommand", name="doctor", help="Run system health checks"
)
app.command(
    "exportify.commands.undo:UndoCommand", name="undo", help="Restore files from the last sync run"
)
app.command(
    "exportify.commands.cache:CacheCommand", name="cache", help="Manage analysis results and cache"
)


def main() -> None:
    """Main entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()

__all__ = ("main",)
