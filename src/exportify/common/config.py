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
from typing import Any

import yaml

from exportify import detect_source_root, locate_project_root
from exportify.common.types import OutputStyle
from exportify.utils import find_project_name


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


@dataclass(frozen=True)
class ProjectConfig:
    """Basic configuration information for an exportify project, derived from the config file and other sources."""

    project_name: str = field(default_factory=find_project_name)
    """The project name, derived from pyproject.toml or the current directory name if not provided."""
    project_path: Path = field(default_factory=locate_project_root)
    """The project root path, derived from pyproject.toml or the current working directory if not found."""
    source_path: Path = field(default_factory=detect_source_root)
    """The source root path (i.e. the directory containing the top-level package, such as project_path / "src" ), auto-detected by looking for __init__.py files."""
    additional_source_paths: list[Path] = field(default_factory=list)
    """Additional source paths to include when searching for modules, specified in the config file."""

    def __init__(
        self,
        project_name: str | None = None,
        project_path: str | Path | None = None,
        source_path: str | Path | None = None,
        additional_source_paths: list[str] | list[Path] | None = None,
        **kwargs: Any,
    ):
        """Initialize ProjectConfig, ignoring any extra kwargs from the config file."""
        object.__setattr__(self, "project_name", project_name or find_project_name())
        object.__setattr__(
            self,
            "project_path",
            Path(project_path).resolve() if project_path else locate_project_root(),
        )
        object.__setattr__(
            self,
            "source_path",
            Path(source_path).resolve() if source_path else detect_source_root(),
        )
        if additional_paths := [Path(p).resolve() for p in (additional_source_paths or [])]:
            object.__setattr__(self, "additional_source_paths", additional_paths)
        elif (packages_dir := self.project_path / "packages").is_dir():
            # Monorepo: auto-detect packages/ subdirectories that are standalone projects,
            # resolving each to its actual source root.
            additional_paths = [
                detect_source_root(base_path=p)
                for p in packages_dir.iterdir()
                if p.is_dir() and (p / "pyproject.toml").is_file()
            ]
            object.__setattr__(self, "additional_source_paths", additional_paths)
        else:
            object.__setattr__(self, "additional_source_paths", [])


# the spdx generation logic causes reuse to error when scanned
# REUSE-IgnoreStart
@dataclass(frozen=True)
class SpdxConfig:
    """SPDX license header configuration for generated __init__.py files."""

    enabled: bool = False
    """Whether to add SPDX comment headers to generated files. Default: False."""

    copyright: str = ""
    """SPDX-FileCopyrightText value (e.g. '2026 Acme Corp.')."""

    license: str = ""
    """SPDX-License-Identifier value (e.g. 'MIT' or 'Apache-2.0')."""

    def build_header(self) -> str | None:
        """Return the SPDX comment block, or None if disabled or nothing to emit."""
        if not self.enabled:
            return None
        parts = []
        if self.copyright:
            parts.append(f"# SPDX-FileCopyrightText: {self.copyright}")
        if self.license:
            parts.append(f"# SPDX-License-Identifier: {self.license}")
        return "\n#\n".join(parts) if parts else None


# REUSE-IgnoreEnd


@dataclass(frozen=True)
class ExportifyConfig:
    """Parsed exportify configuration."""

    output_style: OutputStyle = OutputStyle.LAZY
    """Default output style for all generated __init__.py files."""

    package_styles: dict[str, OutputStyle] = field(default_factory=dict)
    """Per-package overrides: maps package path (e.g. "mypackage.compat") to its OutputStyle."""

    project: ProjectConfig = field(default_factory=ProjectConfig)
    """Basic project configuration derived from the config file and other sources."""

    spdx: SpdxConfig = field(default_factory=SpdxConfig)
    """SPDX header configuration for generated files."""

    exclude_paths: list[str] = field(default_factory=list)
    """Glob patterns for paths to exclude from processing (relative to each source root).

    Supports ``**`` for recursive matching.  Examples::

        exclude_paths:
          - "**/_vendor/**"
          - "**/tests/**"
          - "mypackage/legacy/**"
    """

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
    the ``output_style``, ``overrides``, ``spdx``, ``project``, and
    ``exclude_paths`` sections are relevant to this function; all other YAML
    keys (e.g. ``schema_version``, ``rules``) are silently ignored.

    YAML schema understood by this function::

        output_style: lazy  # or "barrel"; default "lazy"

        overrides:
          "mypackage.compat":
            output_style: barrel

        exclude_paths:
          - "**/_vendor/**"
          - "**/tests/**"

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

    # --- spdx config ---
    spdx_data = data.get("spdx") or {}
    spdx = SpdxConfig(
        enabled=bool(spdx_data.get("enabled", False)),
        copyright=spdx_data.get("copyright", "") or "",
        license=spdx_data.get("license", "") or "",
    )

    # --- project config ---
    project_data = {
        k: v for k, v in data.get("project", {}).items() if v
    }  # Only "name" is relevant to our ProjectConfig
    project = ProjectConfig(**project_data)

    # --- exclude_paths ---
    exclude_paths: list[str] = data.get("exclude_paths", []) or []

    return ExportifyConfig(
        output_style=global_style,
        project=project,
        package_styles=package_styles,
        spdx=spdx,
        exclude_paths=exclude_paths,
    )


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
    "ProjectConfig",
    "SpdxConfig",
    "detect_lateimport_dependency",
    "find_config_file",
    "load_config",
]
