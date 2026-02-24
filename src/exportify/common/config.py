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
import tomllib

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from exportify.common.types import OutputStyle


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

DEFAULT_SNAPSHOT_DIR: Path = Path(".exportify") / "snapshots" / "last"
"""Default snapshot directory relative to the working directory."""


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


@dataclass
class ExportifyConfig:
    """Parsed exportify configuration."""

    output_style: OutputStyle = OutputStyle.LAZY
    """Default output style for all generated __init__.py files."""

    package_styles: dict[str, OutputStyle] = field(default_factory=dict)
    """Per-package overrides: maps package path (e.g. "mypackage.compat") to its OutputStyle."""

    def get_output_style(self, module_path: str) -> OutputStyle:
        """Get output style for a module, inheriting from the nearest matching ancestor.

        Walks up the dotted path from most-specific to least-specific, returning
        the first matching per-package override.  Falls back to the global default
        when no ancestor (including the module itself) has an explicit override.

        Args:
            module_path: Dotted module path (e.g. "mypackage.core.models").

        Returns:
            The :class:`OutputStyle` for this module — the most specific per-package
            override found when walking up the package hierarchy, or the global default.
        """
        parts = module_path.split(".")
        for i in range(len(parts), 0, -1):
            candidate = ".".join(parts[:i])
            if candidate in self.package_styles:
                return self.package_styles[candidate]
        return self.output_style


def load_config(path: Path) -> ExportifyConfig:
    """Load an exportify configuration from a YAML file.

    Reads the file at *path* and populates an :class:`ExportifyConfig`.  Only
    the ``output_style`` and ``overrides`` sections are relevant to this
    function; all other YAML keys (e.g. ``schema_version``, ``rules``) are
    silently ignored.

    YAML schema understood by this function::

        output_style: lazy  # or "barrel"; default "lazy"

        overrides:
          "mypackage.compat":
            output_style: barrel

    Args:
        path: Path to the YAML config file.

    Returns:
        A populated :class:`ExportifyConfig`.

    Raises:
        ValueError: If ``output_style`` (top-level or in an override) contains
            an unrecognized value.
    """
    with path.open() as fh:
        data: dict = yaml.safe_load(fh) or {}

    # --- top-level output_style ---
    raw_style = data.get("output_style", OutputStyle.LAZY.value)
    try:
        global_style = OutputStyle(raw_style)
    except ValueError:
        valid = [s.value for s in OutputStyle]
        raise ValueError(
            f"Unrecognized output_style {raw_style!r} in {path}. Valid values: {valid}"
        ) from None

    # --- per-package overrides ---
    package_styles: dict[str, OutputStyle] = {}
    overrides_section = data.get("overrides", {}) or {}
    for pkg_path, pkg_cfg in overrides_section.items():
        if not isinstance(pkg_cfg, dict):
            continue
        raw_pkg_style = pkg_cfg.get("output_style")
        if raw_pkg_style is None:
            continue
        try:
            package_styles[pkg_path] = OutputStyle(raw_pkg_style)
        except ValueError:
            valid = [s.value for s in OutputStyle]
            raise ValueError(
                f"Unrecognized output_style {raw_pkg_style!r} for package {pkg_path!r} "
                f"in {path}. Valid values: {valid}"
            ) from None

    return ExportifyConfig(output_style=global_style, package_styles=package_styles)


def detect_lateimport_dependency() -> bool:
    """Return True if 'lateimport' is listed as a project dependency in pyproject.toml.

    Checks both ``project.dependencies`` (runtime) and every list under
    ``dependency-groups`` (e.g. dev dependencies added via ``uv add --dev``).

    ``pyproject.toml`` is looked up relative to the current working directory
    (``Path.cwd() / "pyproject.toml"``), consistent with the behavior of
    :func:`find_config_file`.

    Returns:
        ``True`` if any dependency entry starting with ``"lateimport"`` is
        found; ``False`` otherwise (including when ``pyproject.toml`` is absent
        or cannot be parsed).
    """
    pyproject_path = Path.cwd() / "pyproject.toml"
    if not pyproject_path.exists():
        return False

    try:
        with pyproject_path.open("rb") as fh:
            data = tomllib.load(fh)
    except (OSError, tomllib.TOMLDecodeError):
        return False

    # Check project.dependencies
    project_deps: list[str] = data.get("project", {}).get("dependencies", []) or []
    if any(dep.startswith("lateimport") for dep in project_deps):
        return True

    # Check dependency-groups.* (each value is a list of deps or dicts)
    dep_groups: dict[str, list] = data.get("dependency-groups", {}) or {}
    for group_deps in dep_groups.values():
        if not isinstance(group_deps, list):
            continue
        for entry in group_deps:
            # Entries can be plain strings or dicts (e.g. {include-group = "..."})
            if isinstance(entry, str) and entry.startswith("lateimport"):
                return True

    return False


__all__ = [
    "CONFIG_ENV_VAR",
    "DEFAULT_CACHE_SUBDIR",
    "DEFAULT_CONFIG_NAMES",
    "DEFAULT_SNAPSHOT_DIR",
    "ExportifyConfig",
    "detect_lateimport_dependency",
    "find_config_file",
    "load_config",
]
