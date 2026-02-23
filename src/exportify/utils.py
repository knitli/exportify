# SPDX-CopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Utility functions for exportify."""

import tomllib

from pathlib import Path
from typing import Any


def _read_pyproject() -> dict[str, Any]:
    """Read and parse pyproject.toml if it exists."""
    pyproject = Path.cwd() / "pyproject.toml"
    if not pyproject.exists():
        return {}
    try:
        return tomllib.loads(pyproject.read_text())
    except Exception:
        return {}


def _detect_poetry_packages(data: dict) -> Path | None:
    """Detect source root from Poetry's pyproject.toml configuration."""
    if poetry_pkgs := (data.get("tool", {}).get("poetry", {}).get("packages", [])):
        candidate = Path(poetry_pkgs[0].get("from", "."))
        if str(candidate) != "." and candidate.exists():
            return candidate
    return None


def _detect_flit_module(data: dict) -> Path | None:
    """Detect source root from Flit's pyproject.toml configuration."""
    if flit_mod := (data.get("tool", {}).get("flit", {}).get("module", "")):
        candidate = Path(flit_mod)
        if candidate.exists():
            return candidate
    return None


def _detect_pdm_packages(data: dict) -> Path | None:
    """Detect source root from PDM's pyproject.toml configuration."""
    if pdm_pkgs := (
        data.get("tool", {}).get("pdm", {}).get("build", {}).get("package-dir")
        or data.get("tool", {}).get("pdm", {}).get("build", {}).get("packages", [])
    ):
        candidate = Path(pdm_pkgs[0]).parent
        if str(candidate) != "." and candidate.exists():
            return candidate
    return None


def _detect_setuptools_package_dir(data: dict) -> Path | None:
    """Detect source root from Setuptools' package-dir configuration."""
    if pkg_dir_root := (
        data.get("tool", {}).get("setuptools", {}).get("package-dir", {}).get("", "")
    ):
        candidate = Path(pkg_dir_root)
        if candidate.exists():
            return candidate
    return None


def _detect_hatch_packages(data: dict) -> Path | None:
    """Detect source root from Hatch's pyproject.toml configuration."""
    if hatch_pkgs := (
        data
        .get("tool", {})
        .get("hatch", {})
        .get("build", {})
        .get("targets", {})
        .get("wheel", {})
        .get("packages", [])
    ):
        candidate = Path(hatch_pkgs[0]).parent
        if str(candidate) != "." and candidate.exists():
            return candidate
    return None


def detect_source_root() -> Path:
    """Detect the Python source root for the current project.

    Resolution order:
    1. ``pyproject.toml`` -- common build-backend conventions (Hatch, Setuptools, Flit)
    2. ``src/`` directory exists → return ``Path("src")``
    3. Fall back to ``Path(".")`` (project root / flat layout)
    """
    if data := _read_pyproject():
        tool = data.get("tool", {})

        if hatch_pkgs := _detect_hatch_packages(tool):
            return hatch_pkgs

        if setuptools_pkg_dir := _detect_setuptools_package_dir(tool):
            return setuptools_pkg_dir

        if flit_module := _detect_flit_module(tool):
            return flit_module

        if pdm_pkgs := _detect_pdm_packages(tool):
            return pdm_pkgs

        if poetry_pkgs := _detect_poetry_packages(tool):
            return poetry_pkgs

    # Conventional src/ layout fallback
    src = Path("src")
    if src.exists():
        return src
    # project_name / project_name layout (no intermediate src dir)
    if (name := Path.cwd().name) and (Path.cwd() / name).exists():
        return Path(name)
    return Path.cwd()


def detect_lateimport_dependency() -> bool:
    """Detect if the project has a dependency on late-import."""
    if data := _read_pyproject():
        if project_dependencies := (data.get("project", {}).get("dependencies", [])):
            return any("lateimport" in dep for dep in project_dependencies)
        # Handle Poetry weirdness
        if poetry_deps := data.get("tool", {}).get("poetry", {}).get("dependencies", {}):
            return any("lateimport" in dep for dep in poetry_deps)
    return False


__all__ = ("detect_lateimport_dependency", "detect_source_root")
