# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Centralized configuration file discovery for exportify.

Config file resolution order:
1. ``EXPORTIFY_CONFIG`` environment variable (any path)
2. ``.exportify/config.yaml`` in the current working directory
3. ``.exportify/config.yml`` in the current working directory
4. ``.exportify.yaml`` in the current working directory
5. ``.exportify.yml`` in the current working directory
6. ``exportify.yaml`` in the current working directory
7. ``exportify.yml`` in the current working directory
"""

from __future__ import annotations

import os

from pathlib import Path


CONFIG_ENV_VAR = "EXPORTIFY_CONFIG"
"""Environment variable for a custom config file path."""

DEFAULT_CONFIG_NAMES: list[str] = [
    ".exportify/config.yaml",
    ".exportify/config.yml",
    ".exportify.yaml",
    ".exportify.yml",
    "exportify.yaml",
    "exportify.yml",
]
"""Config file names searched in the working directory, in priority order."""

DEFAULT_CACHE_SUBDIR: Path = Path(".exportify") / "cache"
"""Default cache directory relative to the working directory."""


def find_config_file() -> Path | None:
    """Find the exportify config file.

    Checks, in order:

    1. ``EXPORTIFY_CONFIG`` environment variable — any valid path is accepted.
    2. ``.exportify/config.yaml`` / ``.exportify/config.yml`` in the current working directory.
    3. ``.exportify.yaml`` / ``.exportify.yml`` in the current working directory.
    4. ``exportify.yaml`` / ``exportify.yml`` in the current working directory.

    Returns:
        Path to the config file, or ``None`` if none is found.
    """
    # 1. Env var override
    if env_path := os.environ.get(CONFIG_ENV_VAR):
        p = Path(env_path).resolve()
        if p.exists():
            return p

    # 2. Search current working directory in priority order
    for name in DEFAULT_CONFIG_NAMES:
        p = (Path.cwd() / name).resolve()
        if p.exists():
            return p

    return None


__all__ = ["CONFIG_ENV_VAR", "DEFAULT_CACHE_SUBDIR", "DEFAULT_CONFIG_NAMES", "find_config_file"]
