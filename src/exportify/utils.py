# SPDX-CopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# ruff: noqa: S603 --- IGNORE ---
"""Utility functions for exportify."""

import shutil
import tomllib

from pathlib import Path
from typing import Any


_common_python_files = {"pyproject.toml", "setup.py", "requirements.txt", "ruff.toml", "uv.lock"}


def _try_to_use_git_to_resolve_root() -> Path | None:
    """Try to use git to find the project root, if we're in a git repository."""
    import shutil
    import subprocess

    if (git := shutil.which("git")) is None:
        return None

    try:
        result = subprocess.run(
            [git, "rev-parse", "--show-toplevel"], capture_output=True, text=True, check=True
        )
    except Exception:
        return None
    else:
        return Path(result.stdout.strip())


def locate_project_root(base_path: Path | None = None) -> Path:
    """Locate the root of the git repository, if it exists."""

    def _check_for_markers(path: Path) -> bool:
        """Check if any project root markers exist in the given path."""
        return any((path / marker).exists() for marker in _common_python_files)

    current = base_path or Path.cwd()
    if _check_for_markers(current):
        return current
    if git_root := _try_to_use_git_to_resolve_root():
        return git_root
    # if our search fails, we return the closest parent with any of the markers, or the base_path / cwd and hope the user invoked the command from a reasonable location within the project
    return next(
        (parent for parent in current.parents if _check_for_markers(parent)),
        base_path or Path.cwd(),
    )


def _read_pyproject(base_path: Path | None = None) -> dict[str, Any]:
    """Read and parse pyproject.toml if it exists."""
    pyproject = (base_path or Path.cwd()) / "pyproject.toml"
    if (
        not pyproject.exists()
        and not (pyproject := locate_project_root(base_path) / "pyproject.toml").exists()
    ):
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


def detect_source_root(base_path: Path | None = None) -> Path:
    """Detect the Python source root for the current project.

    Resolution order:
    1. ``pyproject.toml`` -- common build-backend conventions (Hatch, Setuptools, Flit)
    2. ``src/`` directory exists → return ``Path("src")``
    3. Fall back to ``Path(".")`` (project root / flat layout)
    """
    if data := _read_pyproject(base_path):
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
    base_path = base_path or Path.cwd()
    # Conventional src/ layout fallback
    src = base_path / "src"
    if src.exists():
        return src
    # project_name / project_name layout (no intermediate src dir)
    if (name := base_path.name) and (base_path / name).exists():
        return base_path / name
    return base_path


def detect_lateimport_dependency(base_path: Path | None = None) -> bool:
    """Detect if the project has a dependency on late-import."""
    if data := _read_pyproject(base_path):
        if project_dependencies := (data.get("project", {}).get("dependencies", [])):
            return any("lateimport" in dep for dep in project_dependencies)
        # Handle Poetry weirdness
        if poetry_deps := data.get("tool", {}).get("poetry", {}).get("dependencies", {}):
            return any("lateimport" in dep for dep in poetry_deps)
    return False


def _has_ruff() -> bool:
    """Check if ruff is installed and available."""
    return shutil.which("ruff") is not None


def _has_isort() -> bool:
    """Check if isort is installed and available."""
    return shutil.which("isort") is not None


def _has_black() -> bool:
    """Check if black is installed and available."""
    return shutil.which("black") is not None


def formatting_tools_available() -> bool:
    """Check if any formatting tools are available."""
    return _has_ruff() or _has_isort() or _has_black()


def format_content(content: str, *, filename: Path | None = None, verbose: bool = False) -> str:
    """Format Python source code using the first available formatter via stdin.

    Pipes ``content`` to the formatter's stdin and returns the formatted
    result.  Passing ``filename`` lets the formatter discover project config
    (``ruff.toml``, ``pyproject.toml``, etc.) without the file needing to
    exist on disk.

    Falls back to returning ``content`` unchanged when no formatter is
    installed or when the formatter exits non-zero.

    Args:
        content: Python source code to format.
        filename: Optional path hint forwarded as ``--stdin-filename``.
        verbose: Whether to show formatter output.

    Returns:
        Formatted source code, or the original ``content`` if formatting
        is unavailable or fails.
    """
    import subprocess

    stdin_filename_args = ["--stdin-filename", str(filename)] if filename is not None else []

    if ruff_binary := shutil.which("ruff"):
        result = subprocess.run(
            [
                ruff_binary,
                "format",
                "--verbose" if verbose else "--quiet",
                *stdin_filename_args,
                "-",
            ],
            input=content,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            return result.stdout
    elif isort_binary := shutil.which("isort"):
        result = subprocess.run(
            [isort_binary, "-v" if verbose else "-q", *stdin_filename_args, "-"],
            input=content,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            return result.stdout
    elif black_binary := shutil.which("black"):
        result = subprocess.run(
            [black_binary, "--verbose" if verbose else "--quiet", *stdin_filename_args, "-"],
            input=content,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            return result.stdout
    elif uv_binary := shutil.which("uvx"):
        result = subprocess.run(
            [
                uv_binary,
                "ruff",
                "format",
                "--verbose" if verbose else "--quiet",
                *stdin_filename_args,
                "-",
            ],
            input=content,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            return result.stdout
    return content


def format_file(file_path: Path, *, verbose: bool = False) -> None:
    """Format a file in-place using the first available formatter tool.

    Reads the file, pipes content through :func:`format_content`, and
    writes the result back only when the content changes.  Silently does
    nothing if no formatter is installed.

    Args:
        file_path: Path to the Python file to format.
        verbose: Whether to show formatter output.
    """
    content = file_path.read_text(encoding="utf-8")
    formatted = format_content(content, filename=file_path, verbose=verbose)
    if formatted != content:
        file_path.write_text(formatted, encoding="utf-8")


def write_gitignore_patterns(exportify_dir: Path | None = None) -> None:
    """Write .gitignore file to exclude exportify's cache directory."""
    exportify_root = exportify_dir or (locate_project_root() / ".exportify")
    gitignore_patterns = ["cache/", "snapshots/"]
    gitignore_path = exportify_root / ".gitignore"
    if gitignore_path.exists():
        existing_patterns = set(gitignore_path.read_text().splitlines())
        if new_patterns := set(gitignore_patterns) - existing_patterns:
            gitignore_path.write_text("\n".join(existing_patterns | new_patterns) + "\n")
    else:
        gitignore_path.write_text("\n".join(gitignore_patterns) + "\n")


def find_project_name() -> str:
    """Find the project name from pyproject.toml or fallback to directory name."""
    if (data := _read_pyproject()) and (name := data.get("project", {}).get("name")):
        return name
    return locate_project_root().name


__all__ = (
    "detect_lateimport_dependency",
    "detect_source_root",
    "find_project_name",
    "format_content",
    "format_file",
    "formatting_tools_available",
    "locate_project_root",
    "write_gitignore_patterns",
)
