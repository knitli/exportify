# sourcery skip: avoid-global-variables
# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Implements the ``clear-cache`` command: wipes all cached analysis results."""

from __future__ import annotations

from cyclopts import App

from exportify.commands.utils import CONSOLE, print_info, print_success
from exportify.common.cache import AnalysisCache


ClearCacheCommand = App(console=CONSOLE)


@ClearCacheCommand.default
def clear_cache() -> None:
    """Delete all cached analysis results.

    Removes every entry from the analysis cache. Exportify rebuilds
    the cache automatically on the next ``validate`` or ``generate`` run.

    Use this when:
    - The cache is corrupted
    - You upgrade Exportify and the cache schema changes
    - Stale cache entries cause unexpected behavior

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

__all__ = (
    "ClearCacheCommand",
    "clear_cache",
)
