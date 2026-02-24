# sourcery skip: avoid-global-variables
# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Implements the ``doctor`` command: cache and configuration health checks."""

from __future__ import annotations

from cyclopts import App
from rich.panel import Panel

from exportify.commands.utils import CONSOLE, print_info, print_success, print_warning
from exportify.common.cache import AnalysisCache
from exportify.common.config import CONFIG_ENV_VAR, find_config_file


DoctorCommand = App(console=CONSOLE)


@DoctorCommand.default
def doctor() -> None:
    """Check Exportify cache and configuration health.

    Checks:
    - Cache entries (total, valid, invalid, size, hit rate)
    - Rule configuration (config file present or missing)

    Warns if more than 10% of cache entries are invalid and
    recommends running ``exportify clear-cache``.

    Examples:
        exportify doctor
    """
    CONSOLE.print()
    CONSOLE.print(Panel("[bold]Lazy Import System Health Check[/bold]", expand=False))
    CONSOLE.print()

    # Check cache
    print_info("Checking analysis cache...")

    cache = AnalysisCache()
    stats = cache.get_stats()

    CONSOLE.print(f"  Total entries: [cyan]{stats.total_entries}[/cyan]")
    CONSOLE.print(f"  Valid entries: [green]{stats.valid_entries}[/green]")
    CONSOLE.print(f"  Invalid entries: [red]{stats.invalid_entries}[/red]")
    CONSOLE.print(f"  Cache size: [cyan]{stats.total_size_bytes / 1024:.1f}KB[/cyan]")
    CONSOLE.print(f"  Hit rate: [cyan]{stats.hit_rate * 100:.1f}%[/cyan]")
    CONSOLE.print()

    # Check rules
    print_info("Checking rule configuration...")
    rules_path = find_config_file()

    if rules_path is not None:
        print_success(f"Rules file found: {rules_path}")
    else:
        print_warning("No config file found")
        CONSOLE.print(
            f"  [dim]Recommendation: Create .exportify.yaml or set {CONFIG_ENV_VAR}[/dim]"
        )

    CONSOLE.print()

    # Overall status
    if stats.invalid_entries > stats.total_entries * 0.1:  # More than 10% invalid
        print_warning("High invalid cache rate - consider clearing cache")
        CONSOLE.print("  [dim]Run: exportify clear-cache[/dim]")
    else:
        print_success("System health looks good")

    CONSOLE.print()


if __name__ == "__main__":
    DoctorCommand()

__all__ = (
    "DoctorCommand",
    "doctor",
)
