# sourcery skip: avoid-global-variables
# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Exportify CLI commands.

Provides user interface for all export management operations:
- Checking exports and __all__ consistency
- Fixing exports and __all__ declarations
- Generating __init__.py files for new packages
- Analysis and health checks
- Migration from old system
"""

from __future__ import annotations

import logging

from cyclopts import App

from exportify import __version__
from exportify.commands.utils import CONSOLE


logger = logging.getLogger(__name__)

app = App(
    name="exportify",
    help="Manage Python package exports: check, fix, and generate __init__.py files",
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


def main() -> None:
    """Main entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()

__all__ = ("app",)
