# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Module for the `status` command."""

from __future__ import annotations

from typing import Annotated

from cyclopts import App, Parameter
from rich.panel import Panel

from exportify.commands.utils import CONSOLE
from exportify.common.config import find_config_file


StatusCommand = App(console=CONSOLE)


@StatusCommand.default
def status(
    *, verbose: Annotated[bool, Parameter(help="Show detailed information")] = False
) -> None:
    """Show current export/import health status.

    Displays:
    - Cache statistics
    - Validation status
    - Rule configuration status
    - Recent activity

    Examples:
        exportify status
        exportify status --verbose
    """
    CONSOLE.print()
    CONSOLE.print(Panel("[bold]Lazy Import System Status[/bold]", expand=False))
    CONSOLE.print()

    # Cache status
    from exportify.common.cache import AnalysisCache

    cache = AnalysisCache()
    stats = cache.get_stats()

    CONSOLE.print("[bold]Cache Status:[/bold]")
    CONSOLE.print(f"  Entries: [cyan]{stats.valid_entries}/{stats.total_entries}[/cyan] valid")
    CONSOLE.print(f"  Hit rate: [cyan]{stats.hit_rate * 100:.1f}%[/cyan]")
    CONSOLE.print()

    # Configuration status
    CONSOLE.print("[bold]Configuration:[/bold]")
    rules_path = find_config_file()

    if rules_path is not None:
        CONSOLE.print(f"  Rules: [green]✓[/green] {rules_path}")
    else:
        CONSOLE.print("  Rules: [yellow]–[/yellow] Not found (using defaults)")  # noqa: RUF001

    CONSOLE.print()

    # System status
    CONSOLE.print("[bold]System:[/bold]")
    CONSOLE.print("  Status: [green]Ready[/green]")
    CONSOLE.print()

    if verbose:
        CONSOLE.print("[bold]Detailed Information:[/bold]")
        CONSOLE.print(f"  Cache size: {stats.total_size_bytes / 1024:.1f}KB")
        CONSOLE.print(f"  Invalid entries: {stats.invalid_entries}")
        CONSOLE.print()


if __name__ == "__main__":
    StatusCommand()

__all__ = ("StatusCommand",)
