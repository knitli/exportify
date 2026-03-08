# sourcery skip: avoid-global-variables
# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Implements the ``cache`` command group for managing analysis results."""

from __future__ import annotations

from cyclopts import App

from exportify.commands.utils import CONSOLE, print_info, print_success
from exportify.common.cache import AnalysisCache


CacheCommand = App("cache", help="Manage analysis results and cache", console=CONSOLE)


@CacheCommand.command(name="clear")
def clear() -> None:
    """Delete all cached analysis results.

    Removes every entry from the analysis cache. Exportify rebuilds
    the cache automatically on the next `check` or `sync` run.

    Examples:
        exportify cache clear
    """
    print_info("Clearing analysis cache...")
    CONSOLE.print()

    cache = AnalysisCache()
    cache.clear()

    print_success("Cache cleared successfully")
    CONSOLE.print()


@CacheCommand.command(name="stats")
def stats() -> None:
    """Show detailed cache statistics.

    Displays:
    - Total, valid, and invalid entries
    - Cache size on disk
    - Hit rate across all sessions

    Examples:
        exportify cache stats
    """
    from rich.table import Table

    cache = AnalysisCache()
    stats_data = cache.get_stats()

    table = Table(title="Analysis Cache Statistics")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Valid Entries", str(stats_data.valid_entries))
    table.add_row("Invalid Entries", str(stats_data.invalid_entries))
    table.add_row("Total Entries", str(stats_data.total_entries))
    table.add_row("Cache Size", f"{stats_data.total_size_bytes / 1024:.1f} KB")
    table.add_row("Hit Rate", f"{stats_data.hit_rate * 100:.1f}%")

    CONSOLE.print()
    CONSOLE.print(table)
    CONSOLE.print()


if __name__ == "__main__":
    CacheCommand()

__all__ = ("CacheCommand",)
