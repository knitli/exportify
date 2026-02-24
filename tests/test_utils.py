# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

# sourcery skip: no-relative-imports
"""Tests for exportify.utils module."""

from __future__ import annotations

from pathlib import Path

from exportify.utils import (
    _detect_flit_module,
    _detect_hatch_packages,
    _detect_pdm_packages,
    _detect_poetry_packages,
    _detect_setuptools_package_dir,
    _read_pyproject,
    detect_lateimport_dependency,
    detect_source_root,
)


class TestReadPyproject:
    """Tests for _read_pyproject."""

    def test_returns_empty_dict_when_no_pyproject(self, tmp_path: Path, monkeypatch):
        """Returns empty dict when pyproject.toml doesn't exist."""
        monkeypatch.chdir(tmp_path)
        result = _read_pyproject()
        assert result == {}

    def test_returns_parsed_data_when_pyproject_exists(self, tmp_path: Path, monkeypatch):
        """Returns parsed TOML data from pyproject.toml."""
        monkeypatch.chdir(tmp_path)
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "mypackage"\nversion = "1.0"\n')

        result = _read_pyproject()
        assert result["project"]["name"] == "mypackage"
        assert result["project"]["version"] == "1.0"

    def test_returns_empty_dict_on_invalid_toml(self, tmp_path: Path, monkeypatch):
        """Returns empty dict when pyproject.toml has invalid TOML content."""
        monkeypatch.chdir(tmp_path)
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("this is not: valid: toml: [\n")

        result = _read_pyproject()
        assert result == {}


class TestDetectPoetryPackages:
    """Tests for _detect_poetry_packages.

    Note: The function signature takes the full pyproject data dict and
    navigates via data.get("tool", {}).get("poetry", ...).
    """

    def test_returns_none_when_no_tool_key(self):
        """Returns None when data has no 'tool' key."""
        result = _detect_poetry_packages({})
        assert result is None

    def test_returns_none_when_no_poetry_config(self):
        """Returns None when no poetry configuration under tool."""
        result = _detect_poetry_packages({"tool": {}})
        assert result is None

    def test_returns_none_when_packages_empty(self):
        """Returns None when poetry packages list is empty."""
        data = {"tool": {"poetry": {"packages": []}}}
        result = _detect_poetry_packages(data)
        assert result is None

    def test_returns_none_when_from_is_dot(self):
        """Returns None when poetry 'from' is '.' (current dir)."""
        data = {"tool": {"poetry": {"packages": [{"include": "mypackage", "from": "."}]}}}
        result = _detect_poetry_packages(data)
        assert result is None

    def test_returns_path_when_from_dir_exists(self, tmp_path: Path):
        """Returns candidate path when poetry 'from' directory exists."""
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        data = {"tool": {"poetry": {"packages": [{"include": "mypackage", "from": str(src_dir)}]}}}
        result = _detect_poetry_packages(data)
        assert result == src_dir

    def test_returns_none_when_from_dir_not_exists(self):
        """Returns None when poetry 'from' dir doesn't exist on filesystem."""
        data = {
            "tool": {"poetry": {"packages": [{"include": "mypackage", "from": "/nonexistent_x9z"}]}}
        }
        result = _detect_poetry_packages(data)
        assert result is None


class TestDetectFlitModule:
    """Tests for _detect_flit_module.

    Note: The function takes the full pyproject data dict and navigates
    via data.get("tool", {}).get("flit", {}).get("module", "").
    """

    def test_returns_none_when_no_tool_key(self):
        """Returns None when data has no 'tool' key."""
        result = _detect_flit_module({})
        assert result is None

    def test_returns_none_when_no_flit_config(self):
        """Returns None when no flit configuration under tool."""
        result = _detect_flit_module({"tool": {}})
        assert result is None

    def test_returns_none_when_flit_module_not_exists(self):
        """Returns None when flit module path doesn't exist on filesystem."""
        data = {"tool": {"flit": {"module": "/nonexistent_module_x9z"}}}
        result = _detect_flit_module(data)
        assert result is None

    def test_returns_path_when_flit_module_exists(self, tmp_path: Path):
        """Returns path when flit module directory exists."""
        module_dir = tmp_path / "mypackage"
        module_dir.mkdir()
        data = {"tool": {"flit": {"module": str(module_dir)}}}
        result = _detect_flit_module(data)
        assert result == module_dir

    def test_returns_none_when_flit_module_empty_string(self):
        """Returns None when flit module is an empty string (falsy)."""
        data = {"tool": {"flit": {"module": ""}}}
        result = _detect_flit_module(data)
        assert result is None


class TestDetectPdmPackages:
    """Tests for _detect_pdm_packages.

    Note: The function takes the full pyproject data dict and navigates
    via data.get("tool", {}).get("pdm", {}).get("build", {}).
    """

    def test_returns_none_when_no_tool_key(self):
        """Returns None when data has no 'tool' key."""
        result = _detect_pdm_packages({})
        assert result is None

    def test_returns_none_when_no_pdm_config(self):
        """Returns None when no PDM configuration under tool."""
        result = _detect_pdm_packages({"tool": {}})
        assert result is None

    def test_returns_none_when_candidate_parent_is_dot(self):
        """Returns None when packages list yields a parent path of '.'."""
        data = {"tool": {"pdm": {"build": {"packages": ["mypackage"]}}}}
        result = _detect_pdm_packages(data)
        assert result is None

    def test_returns_path_when_package_parent_exists(self, tmp_path: Path):
        """Returns parent of the first package path when it exists."""
        self._get_package_dir_from_data(tmp_path, "packages")

    def test_returns_none_when_parent_not_exists(self):
        """Returns None when the resolved parent path doesn't exist."""
        data = {"tool": {"pdm": {"build": {"packages": ["/nonexistent_x9z/package"]}}}}
        result = _detect_pdm_packages(data)
        assert result is None

    def test_uses_package_dir_key_when_packages_absent(self, tmp_path: Path):
        """Falls through to package-dir key when packages key is absent."""
        self._get_package_dir_from_data(tmp_path, "package-dir")

    # TODO Rename this here and in `test_returns_path_when_package_parent_exists` and `test_uses_package_dir_key_when_packages_absent`
    def _get_package_dir_from_data(self, tmp_path, arg1):
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        package_path = str(src_dir / "mypackage")
        data = {"tool": {"pdm": {"build": {arg1: [package_path]}}}}
        result = _detect_pdm_packages(data)
        assert result == src_dir


class TestDetectSetuptoolsPackageDir:
    """Tests for _detect_setuptools_package_dir.

    Note: The function takes the full pyproject data dict and navigates
    via data.get("tool", {}).get("setuptools", {}).get("package-dir", {}).get("", "").
    """

    def test_returns_none_when_no_tool_key(self):
        """Returns None when data has no 'tool' key."""
        result = _detect_setuptools_package_dir({})
        assert result is None

    def test_returns_none_when_no_setuptools_config(self):
        """Returns None when no setuptools configuration under tool."""
        result = _detect_setuptools_package_dir({"tool": {}})
        assert result is None

    def test_returns_none_when_root_key_empty_string(self):
        """Returns None when the '' root key maps to empty string."""
        data = {"tool": {"setuptools": {"package-dir": {"": ""}}}}
        result = _detect_setuptools_package_dir(data)
        assert result is None

    def test_returns_path_when_dir_exists(self, tmp_path: Path):
        """Returns candidate path when setuptools package-dir root exists."""
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        data = {"tool": {"setuptools": {"package-dir": {"": str(src_dir)}}}}
        result = _detect_setuptools_package_dir(data)
        assert result == src_dir

    def test_returns_none_when_dir_not_exists(self):
        """Returns None when setuptools package-dir root doesn't exist."""
        data = {"tool": {"setuptools": {"package-dir": {"": "/nonexistent_x9z"}}}}
        result = _detect_setuptools_package_dir(data)
        assert result is None


class TestDetectHatchPackages:
    """Tests for _detect_hatch_packages.

    Note: The function takes the full pyproject data dict and navigates
    via data.get("tool", {}).get("hatch", {}).get("build", {}).get("targets", {})
              .get("wheel", {}).get("packages", []).
    """

    def test_returns_none_when_no_tool_key(self):
        """Returns None when data has no 'tool' key."""
        result = _detect_hatch_packages({})
        assert result is None

    def test_returns_none_when_no_hatch_config(self):
        """Returns None when no hatch configuration under tool."""
        result = _detect_hatch_packages({"tool": {}})
        assert result is None

    def test_returns_none_when_hatch_packages_empty(self):
        """Returns None when hatch wheel packages list is empty."""
        data = {"tool": {"hatch": {"build": {"targets": {"wheel": {"packages": []}}}}}}
        result = _detect_hatch_packages(data)
        assert result is None

    def test_returns_none_when_parent_is_dot(self):
        """Returns None when parent of the first hatch package is '.'."""
        data = {"tool": {"hatch": {"build": {"targets": {"wheel": {"packages": ["mypackage"]}}}}}}
        result = _detect_hatch_packages(data)
        assert result is None

    def test_returns_path_when_parent_exists(self, tmp_path: Path):
        """Returns parent path when hatch package's parent directory exists."""
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        package_path = str(src_dir / "mypackage")
        data = {"tool": {"hatch": {"build": {"targets": {"wheel": {"packages": [package_path]}}}}}}
        result = _detect_hatch_packages(data)
        assert result == src_dir

    def test_returns_none_when_parent_not_exists(self):
        """Returns None when hatch package's parent path doesn't exist."""
        data = {
            "tool": {
                "hatch": {"build": {"targets": {"wheel": {"packages": ["/nonexistent_x9z/pkg"]}}}}
            }
        }
        result = _detect_hatch_packages(data)
        assert result is None


class TestDetectSourceRoot:
    """Tests for detect_source_root.

    This function reads pyproject.toml from cwd, then passes tool dict to helpers.
    Note: Due to the implementation passing 'tool' sub-dict to helpers (not full data),
    the helpers get {'hatch': ..., 'setuptools': ...} instead of {'tool': {...}}.
    This means the helpers' data.get('tool', {}) always returns {} from detect_source_root.
    The pyproject-based detection requires mocking the helpers to test those branches.
    """

    def test_falls_back_to_src_when_exists(self, tmp_path: Path, monkeypatch):
        """Falls back to 'src' directory when it exists and no pyproject.toml."""
        monkeypatch.chdir(tmp_path)
        self._check_fallback_to_src_directory(tmp_path)

    def test_falls_back_to_cwd_when_no_src_and_no_pyproject(self, tmp_path: Path, monkeypatch):
        """Falls back to cwd when no src/ directory and no pyproject.toml."""
        monkeypatch.chdir(tmp_path)

        result = detect_source_root()
        assert result == tmp_path

    def test_falls_back_to_project_name_dir(self, tmp_path: Path, monkeypatch):
        """Falls back to project_name/ dir when it matches cwd name and no src/."""
        # Create a dir named after the parent directory (cwd name)
        project_dir = tmp_path / tmp_path.name
        project_dir.mkdir()
        monkeypatch.chdir(tmp_path)

        result = detect_source_root()
        assert result == tmp_path / tmp_path.name

    def test_pyproject_read_failure_falls_back_to_src(self, tmp_path: Path, monkeypatch):
        """When pyproject.toml is invalid, falls back to src/ if it exists."""
        monkeypatch.chdir(tmp_path)
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("this is not: valid [ toml")
        self._check_fallback_to_src_directory(tmp_path)

    def _check_fallback_to_src_directory(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        result = detect_source_root()
        assert result == tmp_path / "src"

    def test_pyproject_read_failure_falls_back_to_cwd(self, tmp_path: Path, monkeypatch):
        """When pyproject.toml is invalid and no src/, falls back to cwd."""
        monkeypatch.chdir(tmp_path)
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("this is not: valid [ toml")

        result = detect_source_root()
        assert result == tmp_path

    def test_detects_src_layout_from_pyproject(self, tmp_path: Path, monkeypatch):
        """Detects 'src' layout via pyproject.toml with src/ directory present."""
        monkeypatch.chdir(tmp_path)
        src = tmp_path / "src"
        src.mkdir()
        # Write a pyproject.toml that has no build-backend detection info
        # so it falls through to the src/ directory fallback
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "mypackage"\n')

        result = detect_source_root()
        assert result == tmp_path / "src"

    def test_returns_path_when_no_fallback_matches(self, tmp_path: Path, monkeypatch):
        """Returns cwd when neither pyproject nor src/ nor project-name dir exist."""
        # Use a tmp dir whose name doesn't match any subdirectory
        unique_tmp = tmp_path / "unique_project"
        unique_tmp.mkdir()
        monkeypatch.chdir(unique_tmp)

        result = detect_source_root()
        # No src/ and no subdir named "unique_project", so returns cwd
        assert result == unique_tmp

    def test_uses_hatch_detection_when_helper_returns_path(self, tmp_path: Path, monkeypatch):
        """Uses hatch helper result when it returns a truthy path."""
        from unittest.mock import patch

        monkeypatch.chdir(tmp_path)
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "mypackage"\n')
        expected = tmp_path / "src"

        with patch("exportify.utils._detect_hatch_packages", return_value=expected):
            result = detect_source_root()
        assert result == expected

    def test_uses_setuptools_detection_when_hatch_returns_none(self, tmp_path: Path, monkeypatch):
        """Uses setuptools helper result when hatch returns None."""
        from unittest.mock import patch

        monkeypatch.chdir(tmp_path)
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "mypackage"\n')
        expected = tmp_path / "src"

        with (
            patch("exportify.utils._detect_hatch_packages", return_value=None),
            patch("exportify.utils._detect_setuptools_package_dir", return_value=expected),
        ):
            result = detect_source_root()
        assert result == expected

    def test_uses_flit_detection_when_prior_helpers_return_none(self, tmp_path: Path, monkeypatch):
        """Uses flit helper result when hatch and setuptools both return None."""
        from unittest.mock import patch

        monkeypatch.chdir(tmp_path)
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "mypackage"\n')
        expected = tmp_path / "mypackage"

        with (
            patch("exportify.utils._detect_hatch_packages", return_value=None),
            patch("exportify.utils._detect_setuptools_package_dir", return_value=None),
            patch("exportify.utils._detect_flit_module", return_value=expected),
        ):
            result = detect_source_root()
        assert result == expected

    def test_uses_pdm_detection_when_prior_helpers_return_none(self, tmp_path: Path, monkeypatch):
        """Uses PDM helper result when hatch, setuptools, and flit all return None."""
        from unittest.mock import patch

        monkeypatch.chdir(tmp_path)
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "mypackage"\n')
        expected = tmp_path / "src"

        with (
            patch("exportify.utils._detect_hatch_packages", return_value=None),
            patch("exportify.utils._detect_setuptools_package_dir", return_value=None),
            patch("exportify.utils._detect_flit_module", return_value=None),
            patch("exportify.utils._detect_pdm_packages", return_value=expected),
        ):
            result = detect_source_root()
        assert result == expected

    def test_uses_poetry_detection_when_all_other_helpers_return_none(
        self, tmp_path: Path, monkeypatch
    ):
        """Uses poetry helper result when all other helpers return None."""
        from unittest.mock import patch

        monkeypatch.chdir(tmp_path)
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "mypackage"\n')
        expected = tmp_path / "src"

        with (
            patch("exportify.utils._detect_hatch_packages", return_value=None),
            patch("exportify.utils._detect_setuptools_package_dir", return_value=None),
            patch("exportify.utils._detect_flit_module", return_value=None),
            patch("exportify.utils._detect_pdm_packages", return_value=None),
            patch("exportify.utils._detect_poetry_packages", return_value=expected),
        ):
            result = detect_source_root()
        assert result == expected


class TestDetectLateimportDependency:
    """Tests for detect_lateimport_dependency."""

    def test_returns_false_when_no_pyproject(self, tmp_path: Path, monkeypatch):
        """Returns False when no pyproject.toml exists."""
        monkeypatch.chdir(tmp_path)
        result = detect_lateimport_dependency()
        assert result is False

    def test_returns_true_when_lateimport_in_project_dependencies(
        self, tmp_path: Path, monkeypatch
    ):
        """Returns True when lateimport is in project.dependencies list."""
        monkeypatch.chdir(tmp_path)
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('[project]\ndependencies = ["lateimport>=0.1.0", "click>=8.0"]\n')

        result = detect_lateimport_dependency()
        assert result is True

    def test_returns_false_when_lateimport_not_in_dependencies(self, tmp_path: Path, monkeypatch):
        """Returns False when lateimport is not among project dependencies."""
        monkeypatch.chdir(tmp_path)
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('[project]\ndependencies = ["click>=8.0", "pydantic>=2.0"]\n')

        result = detect_lateimport_dependency()
        assert result is False

    def test_returns_false_when_project_dependencies_empty(self, tmp_path: Path, monkeypatch):
        """Returns False when project dependencies list is empty."""
        monkeypatch.chdir(tmp_path)
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[project]\ndependencies = []\n")

        result = detect_lateimport_dependency()
        assert result is False

    def test_returns_true_when_lateimport_in_poetry_dependencies(self, tmp_path: Path, monkeypatch):
        """Returns True when lateimport is in tool.poetry.dependencies."""
        monkeypatch.chdir(tmp_path)
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            '[tool.poetry.dependencies]\npython = "^3.12"\nlateimport = ">=0.1.0"\n'
        )

        result = detect_lateimport_dependency()
        assert result is True

    def test_returns_false_when_pyproject_has_no_dependencies_key(
        self, tmp_path: Path, monkeypatch
    ):
        """Returns False when pyproject.toml has project section but no dependencies."""
        monkeypatch.chdir(tmp_path)
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "mypackage"\n')

        result = detect_lateimport_dependency()
        assert result is False

    def test_returns_false_when_pyproject_has_no_project_section(self, tmp_path: Path, monkeypatch):
        """Returns False when pyproject.toml has no project section at all."""
        monkeypatch.chdir(tmp_path)
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('[build-system]\nrequires = ["setuptools"]\n')

        result = detect_lateimport_dependency()
        assert result is False
