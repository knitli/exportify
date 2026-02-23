# sourcery skip: avoid-global-variables
# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Module for the `clear_cache` command."""

from __future__ import annotations

from cyclopts import App

from exportify.commands.utils import CONSOLE, print_info, print_success
from exportify.common.cache import AnalysisCache


ClearCacheCommand = App(console=CONSOLE)


@ClearCacheCommand.default
def clear_cache() -> None:
    """Clear the analysis cache.

    Removes all cached analysis results. The cache will be rebuilt
    on the next validation or generation run.

    Use this when:
    - Cache is corrupted
    - Schema version changed
    - Performance issues

    Examples:
        exportify clear-cache
    """
    print_info("Clearing analysis cache...")
    CONSOLE.print()

    cache = AnalysisCache()
    cache.clear()

    print_success("Cache cleared successfully")
    CONSOLE.print()


if __name__ == "__main__":
    ClearCacheCommand()

__all__ = ("ClearCacheCommand",)
