# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Tests for exportify.common.config and exportify.utils."""

from __future__ import annotations

import tomllib

from pathlib import Path

import pytest
import yaml


# ---------------------------------------------------------------------------
# config.py tests
# ---------------------------------------------------------------------------


class TestFindConfigFile:
    def test_returns_none_when_no_config(self, tmp_path: Path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("EXPORTIFY_CONFIG", raising=False)
        from exportify.common.config import find_config_file

        assert find_config_file() is None

    def test_finds_dotexportify_config_yaml(self, tmp_path: Path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("EXPORTIFY_CONFIG", raising=False)
        cfg = tmp_path / ".exportify" / "config.yaml"
        cfg.parent.mkdir()
        cfg.write_text("schema_version: '1.0'\n")
        from importlib import reload

        from exportify.common import config as cfg_mod

        reload(cfg_mod)
        from exportify.common.config import find_config_file

        assert find_config_file() == cfg.resolve()

    def test_env_var_takes_priority(self, tmp_path: Path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        env_cfg = tmp_path / "custom.yaml"
        env_cfg.write_text("schema_version: '1.0'\n")
        monkeypatch.setenv("EXPORTIFY_CONFIG", str(env_cfg))
        from exportify.common.config import find_config_file

        assert find_config_file() == env_cfg.resolve()

    def test_env_var_nonexistent_path_falls_through(self, tmp_path: Path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("EXPORTIFY_CONFIG", str(tmp_path / "missing.yaml"))
        from exportify.common.config import find_config_file

        # No fallback files either → None
        assert find_config_file() is None

    def test_finds_exportify_yaml_in_cwd(self, tmp_path: Path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("EXPORTIFY_CONFIG", raising=False)
        cfg = tmp_path / "exportify.yaml"
        cfg.write_text("schema_version: '1.0'\n")
        from exportify.common.config import find_config_file

        assert find_config_file() == cfg.resolve()


class TestExportifyConfigGetOutputStyle:
    def test_default_style_returned_when_no_overrides(self):
        from exportify.common.config import ExportifyConfig
        from exportify.common.types import OutputStyle

        cfg = ExportifyConfig(output_style=OutputStyle.BARREL)
        assert cfg.get_output_style("mypackage.core") == OutputStyle.BARREL

    def test_exact_package_match(self):
        from exportify.common.config import ExportifyConfig
        from exportify.common.types import OutputStyle

        cfg = ExportifyConfig(
            output_style=OutputStyle.LAZY,
            package_styles={"mypackage.compat": OutputStyle.BARREL},
        )
        assert cfg.get_output_style("mypackage.compat") == OutputStyle.BARREL

    def test_parent_package_match(self):
        from exportify.common.config import ExportifyConfig
        from exportify.common.types import OutputStyle

        cfg = ExportifyConfig(
            output_style=OutputStyle.LAZY,
            package_styles={"mypackage.compat": OutputStyle.BARREL},
        )
        # sub-module inherits parent override
        assert cfg.get_output_style("mypackage.compat.models") == OutputStyle.BARREL

    def test_most_specific_match_wins(self):
        from exportify.common.config import ExportifyConfig
        from exportify.common.types import OutputStyle

        cfg = ExportifyConfig(
            output_style=OutputStyle.LAZY,
            package_styles={
                "mypackage": OutputStyle.BARREL,
                "mypackage.core": OutputStyle.LAZY,
            },
        )
        assert cfg.get_output_style("mypackage.core.models") == OutputStyle.LAZY

    def test_falls_back_to_global_default(self):
        from exportify.common.config import ExportifyConfig
        from exportify.common.types import OutputStyle

        cfg = ExportifyConfig(
            output_style=OutputStyle.BARREL,
            package_styles={"other_pkg": OutputStyle.LAZY},
        )
        assert cfg.get_output_style("mypackage.core") == OutputStyle.BARREL


class TestLoadConfig:
    def test_load_lazy_style(self, tmp_path: Path):
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text("schema_version: '1.0'\noutput_style: lazy\n")
        from exportify.common.config import load_config
        from exportify.common.types import OutputStyle

        result = load_config(cfg_file)
        assert result.output_style == OutputStyle.LAZY

    def test_load_barrel_style(self, tmp_path: Path):
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text("schema_version: '1.0'\noutput_style: barrel\n")
        from exportify.common.config import load_config
        from exportify.common.types import OutputStyle

        result = load_config(cfg_file)
        assert result.output_style == OutputStyle.BARREL

    def test_default_style_when_not_specified(self, tmp_path: Path):
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text("schema_version: '1.0'\n")
        from exportify.common.config import load_config
        from exportify.common.types import OutputStyle

        result = load_config(cfg_file)
        assert result.output_style == OutputStyle.LAZY

    def test_invalid_top_level_style_raises(self, tmp_path: Path):
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text("output_style: turbo\n")
        from exportify.common.config import load_config

        with pytest.raises(ValueError, match="turbo"):
            load_config(cfg_file)

    def test_load_overrides_section(self, tmp_path: Path):
        cfg_file = tmp_path / "config.yaml"
        data = {
            "output_style": "lazy",
            "overrides": {"mypackage.compat": {"output_style": "barrel"}},
        }
        cfg_file.write_text(yaml.dump(data))
        from exportify.common.config import load_config
        from exportify.common.types import OutputStyle

        result = load_config(cfg_file)
        assert result.package_styles["mypackage.compat"] == OutputStyle.BARREL

    def test_invalid_override_style_raises(self, tmp_path: Path):
        cfg_file = tmp_path / "config.yaml"
        data = {
            "output_style": "lazy",
            "overrides": {"mypackage.compat": {"output_style": "bad"}},
        }
        cfg_file.write_text(yaml.dump(data))
        from exportify.common.config import load_config

        with pytest.raises(ValueError, match="bad"):
            load_config(cfg_file)

    def test_override_without_output_style_skipped(self, tmp_path: Path):
        cfg_file = tmp_path / "config.yaml"
        data = {
            "output_style": "lazy",
            "overrides": {"mypackage.compat": {"other_key": "value"}},
        }
        cfg_file.write_text(yaml.dump(data))
        from exportify.common.config import load_config

        result = load_config(cfg_file)
        assert "mypackage.compat" not in result.package_styles

    def test_non_dict_override_skipped(self, tmp_path: Path):
        cfg_file = tmp_path / "config.yaml"
        # Write raw YAML where override value is a string, not a dict
        cfg_file.write_text(
            "output_style: lazy\noverrides:\n  mypackage.compat: not_a_dict\n"
        )
        from exportify.common.config import load_config

        result = load_config(cfg_file)
        assert "mypackage.compat" not in result.package_styles


class TestDetectLateimportDependency:
    def test_no_pyproject_returns_false(self, tmp_path: Path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        from exportify.common.config import detect_lateimport_dependency

        assert detect_lateimport_dependency() is False

    def test_lateimport_in_project_dependencies(self, tmp_path: Path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_bytes(
            b'[project]\ndependencies = ["lateimport>=0.1.0", "pyyaml"]\n'
        )
        from exportify.common.config import detect_lateimport_dependency

        assert detect_lateimport_dependency() is True

    def test_no_lateimport_in_project_dependencies(self, tmp_path: Path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_bytes(b'[project]\ndependencies = ["pyyaml", "click"]\n')
        from exportify.common.config import detect_lateimport_dependency

        assert detect_lateimport_dependency() is False

    def test_lateimport_in_dependency_groups(self, tmp_path: Path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_bytes(
            b'[dependency-groups]\ndev = ["lateimport>=0.1.0", "pytest"]\n'
        )
        from exportify.common.config import detect_lateimport_dependency

        assert detect_lateimport_dependency() is True

    def test_lateimport_not_in_dependency_groups(self, tmp_path: Path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_bytes(b'[dependency-groups]\ndev = ["pytest", "black"]\n')
        from exportify.common.config import detect_lateimport_dependency

        assert detect_lateimport_dependency() is False

    def test_dict_entry_in_dependency_group_skipped(self, tmp_path: Path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        pyproject = tmp_path / "pyproject.toml"
        # Dict entries like {include-group = "..."} should be skipped gracefully
        pyproject.write_bytes(
            b'[dependency-groups]\ndev = [{include-group = "extras"}, "pytest"]\n'
        )
        from exportify.common.config import detect_lateimport_dependency

        assert detect_lateimport_dependency() is False

    def test_corrupt_pyproject_returns_false(self, tmp_path: Path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_bytes(b"not valid toml [[[[\n")
        from exportify.common.config import detect_lateimport_dependency

        assert detect_lateimport_dependency() is False

    def test_non_list_dependency_group_value_skipped(self, tmp_path: Path, monkeypatch):
        """A dep-group whose value is not a list (e.g. a dict) must be skipped gracefully."""
        monkeypatch.chdir(tmp_path)
        pyproject = tmp_path / "pyproject.toml"
        # dependency-groups value is a string, not a list — should be skipped
        pyproject.write_bytes(b'[dependency-groups]\ndev = "not-a-list"\n')
        from exportify.common.config import detect_lateimport_dependency

        assert detect_lateimport_dependency() is False


# ---------------------------------------------------------------------------
# utils.py tests
# ---------------------------------------------------------------------------


class TestDetectSourceRoot:
    def test_returns_src_when_exists(self, tmp_path: Path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "src").mkdir()
        from exportify.utils import detect_source_root

        assert detect_source_root() == tmp_path / "src"

    def test_falls_back_to_cwd_when_no_src(self, tmp_path: Path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        from exportify.utils import detect_source_root

        assert detect_source_root() == tmp_path

    def test_reads_setuptools_package_dir(self, tmp_path: Path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        src = tmp_path / "src"
        src.mkdir()
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_bytes(
            b'[tool.setuptools.package-dir]\n"" = "src"\n'
        )
        from exportify.utils import detect_source_root

        assert detect_source_root() == tmp_path / "src"

    def test_reads_hatch_packages(self, tmp_path: Path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        src = tmp_path / "src"
        src.mkdir()
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_bytes(
            b"[tool.hatch.build.targets.wheel]\npackages = [\"src/mypkg\"]\n"
        )
        from exportify.utils import detect_source_root

        # hatch packages[0] = "src/mypkg", parent = "src"
        assert detect_source_root() == tmp_path / "src"


class TestDetectLateimportDependencyUtils:
    def test_no_pyproject_returns_false(self, tmp_path: Path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        from exportify.utils import detect_lateimport_dependency

        assert detect_lateimport_dependency() is False

    def test_lateimport_found_in_project_deps(self, tmp_path: Path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "pyproject.toml").write_text(
            '[project]\ndependencies = ["lateimport>=0.1"]\n'
        )
        from exportify.utils import detect_lateimport_dependency

        assert detect_lateimport_dependency() is True

    def test_lateimport_found_in_poetry_deps(self, tmp_path: Path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "pyproject.toml").write_text(
            '[tool.poetry.dependencies]\nlateimport = "^0.1"\n'
        )
        from exportify.utils import detect_lateimport_dependency

        assert detect_lateimport_dependency() is True

    def test_not_found_returns_false(self, tmp_path: Path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "pyproject.toml").write_text('[project]\ndependencies = ["rich"]\n')
        from exportify.utils import detect_lateimport_dependency

        assert detect_lateimport_dependency() is False

    def test_corrupt_pyproject_returns_false(self, tmp_path: Path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "pyproject.toml").write_text("not valid toml [[[[")
        from exportify.utils import detect_lateimport_dependency

        assert detect_lateimport_dependency() is False
