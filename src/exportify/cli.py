# sourcery skip: avoid-global-variables
# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Exportify CLI entry point and command registration.

Registers all eight commands and wires them to the ``exportify`` program:
- ``check``       — validate exports and ``__all__`` consistency
- ``fix``         — repair exports and ``__all__`` declarations
- ``generate``    — create ``__init__.py`` files with lazy imports
- ``status``      — show a quick cache and configuration snapshot
- ``doctor``      — run cache and configuration health checks
- ``init``        — initialize Exportify in a project
- ``clear-cache`` — delete all cached analysis results
- ``undo``        — restore files modified by the last fix run
"""

from __future__ import annotations

import logging

from cyclopts import App

from exportify import __version__
from exportify.commands.utils import CONSOLE


logger = logging.getLogger(__name__)

app = App(
    name="exportify",
    help="Generate, validate, and fix Python package exports and __init__.py files",
    version=__version__,
    console=CONSOLE,
)

app.command("exportify.commands.check:CheckCommand", name="check")
app.command("exportify.commands.fix:FixCommand", name="fix")
app.command("exportify.commands.generate:GenerateCommand", name="generate")
app.command("exportify.commands.status:StatusCommand", name="status")
app.command("exportify.commands.doctor:DoctorCommand", name="doctor")
app.command("exportify.commands.init:InitCommand", name="init")
app.command("exportify.commands.clear_cache:ClearCacheCommand", name="clear-cache")
app.command("exportify.commands.undo:UndoCommand", name="undo")


def main() -> None:
    """Main entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()

__all__ = ("main",)
