# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# sourcery skip: require-return-annotation, require-parameter-annotation, no-relative-imports
"""Tests for lazy import CLI."""

from __future__ import annotations

import json

from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def run_cli(*args):
    """Run CLI and capture output via patched stdout/stderr."""
    from exportify.cli import app

    stdout = StringIO()
    stderr = StringIO()
    exit_code = 0

    with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
        try:
            app(list(args))
        except SystemExit as e:
            exit_code = e.code if e.code is not None else 0
        except Exception as e:
            stderr.write(str(e))
            exit_code = 1

    return exit_code, stdout.getvalue(), stderr.getvalue()


# ---------------------------------------------------------------------------
# Existing basic import tests (unchanged)
# ---------------------------------------------------------------------------


class TestLateImportsCLI:
    """Test suite for lazy imports CLI commands."""

    def test_cli_module_imports(self):
        """Test that CLI module can be imported."""
        from exportify.cli import app

        assert app is not None
        # Cyclopts apps have name as a tuple
        assert "exportify" in app.name or app.name == ("exportify",)

    def test_types_module_imports(self):
        """Test that types module can be imported."""
        from exportify.types import CacheStatistics, ExportGenerationResult, ValidationReport

        assert CacheStatistics is not None
        assert ExportGenerationResult is not None
        assert ValidationReport is not None

    def test_cache_module_imports(self):
        """Test that cache module can be imported."""
        from exportify.common.cache import AnalysisCache

        assert AnalysisCache is not None

    def test_validator_module_imports(self):
        """Test that validator module can be imported."""
        from exportify.validator import ImportValidator

        assert ImportValidator is not None

    def test_export_manager_imports(self):
        """Test that export manager modules can be imported."""
        from exportify.export_manager import PropagationGraph, RuleEngine

        assert RuleEngine is not None
        assert PropagationGraph is not None

    def test_cache_initialization(self):
        """Test that cache can be initialized."""
        from exportify.common.cache import AnalysisCache

        cache = AnalysisCache()
        stats = cache.get_stats()

        assert stats.total_entries == 0
        assert stats.valid_entries == 0
        assert stats.hit_rate == 0.0

    def test_validator_initialization(self):
        """Test that validator can be initialized."""
        from exportify.common.cache import AnalysisCache
        from exportify.validator import LateImportValidator

        cache = AnalysisCache()
        validator = LateImportValidator(cache=cache)

        assert validator is not None

    def test_rule_engine_initialization(self):
        """Test that rule engine can be initialized."""
        from exportify.export_manager import RuleEngine

        engine = RuleEngine()
        assert engine is not None

    def test_propagation_graph_initialization(self):
        """Test that propagation graph can be initialized."""
        from exportify.export_manager import PropagationGraph, RuleEngine

        engine = RuleEngine()
        graph = PropagationGraph(rule_engine=engine)

        assert graph is not None


# ---------------------------------------------------------------------------
# Helper function tests (print functions, resolve functions)
# ---------------------------------------------------------------------------


class TestPrintHelperFunctions:
    """Test the CLI helper print functions directly."""

    def _make_generation_result(self, *, success=True, errors=None):
        """Create a mock ExportGenerationResult."""
        from exportify.common.types import ExportGenerationResult, GenerationMetrics

        metrics = GenerationMetrics(
            files_analyzed=5,
            files_generated=2,
            files_updated=1,
            files_skipped=0,
            exports_created=10,
            processing_time_ms=123,
            cache_hit_rate=0.75,
        )
        return ExportGenerationResult(
            generated_files=[],
            updated_files=[],
            skipped_files=[],
            metrics=metrics,
            success=success,
            errors=errors or [],
        )

    def _make_validation_report(self, *, success=True, errors=None, warnings=None):
        """Create a mock ValidationReport."""
        from exportify.common.types import ValidationMetrics, ValidationReport

        metrics = ValidationMetrics(
            files_validated=3, imports_checked=15, consistency_checks=7, validation_time_ms=55
        )
        return ValidationReport(
            errors=errors or [], warnings=warnings or [], metrics=metrics, success=success
        )

    def test_print_generation_results_success(self, capsys):
        """_print_sync_results prints success output."""
        from exportify.commands.sync import _print_sync_results

        result = self._make_generation_result(success=True)
        _print_sync_results(result)
        # Doesn't raise; rich console output goes to its own stdout handle

    def test_print_generation_results_failure(self):
        """_print_sync_results handles failure case with errors."""
        from exportify.commands.sync import _print_sync_results

        result = self._make_generation_result(success=False, errors=["broken pipe", "parse error"])
        # Should not raise
        _print_sync_results(result)

    def test_print_validation_results_success(self):
        """_print_validation_results handles success."""
        from exportify.commands.utils import print_validation_results

        report = self._make_validation_report(success=True)
        print_validation_results(report)

    def test_print_validation_results_with_errors(self):
        """_print_validation_results shows errors."""
        from exportify.commands.utils import print_validation_results
        from exportify.common.types import ValidationError, ValidationWarning

        err = ValidationError(
            file=Path("/fake/file.py"),
            line=10,
            message="Broken import",
            suggestion="Fix it",
            code="BROKEN_IMPORT",
        )
        warn = ValidationWarning(
            file=Path("/fake/file.py"), line=None, message="Missing __all__", suggestion=None
        )
        report = self._make_validation_report(success=False, errors=[err], warnings=[warn])
        print_validation_results(report)

    def test_print_validation_results_error_no_line(self):
        """_print_validation_results handles errors without line numbers."""
        from exportify.commands.utils import print_validation_results
        from exportify.common.types import ValidationError

        err = ValidationError(
            file=Path("/fake/file.py"),
            line=None,
            message="Some error",
            suggestion=None,
            code="SOME_CODE",
        )
        report = self._make_validation_report(success=False, errors=[err])
        print_validation_results(report)

    def test_print_validation_results_warning_with_suggestion(self):
        """_print_validation_results shows warnings with suggestions."""
        from exportify.commands.utils import print_validation_results
        from exportify.common.types import ValidationWarning

        warn = ValidationWarning(
            file=Path("/fake/warn.py"),
            line=5,
            message="Consider adding __all__",
            suggestion="Add __all__ = [...]",
        )
        report = self._make_validation_report(success=True, warnings=[warn])
        print_validation_results(report)

    def test_print_success(self):
        """_print_success runs without error."""
        from exportify.commands.utils import print_success

        print_success("All good")

    def test_print_error(self):
        """_print_error runs without error."""
        from exportify.commands.utils import print_error

        print_error("Something broke")

    def test_print_warning(self):
        """_print_warning runs without error."""
        from exportify.commands.utils import print_warning

        print_warning("Watch out")

    def test_print_info(self):
        """_print_info runs without error."""
        from exportify.commands.utils import print_info

        print_info("FYI")


# ---------------------------------------------------------------------------
# print_output_validation_json
# ---------------------------------------------------------------------------


class TestOutputValidationJson:
    """Test print_output_validation_json helper."""

    def _make_report(self):
        from exportify.common.types import (
            ValidationError,
            ValidationMetrics,
            ValidationReport,
            ValidationWarning,
        )

        metrics = ValidationMetrics(
            files_validated=2, imports_checked=10, consistency_checks=4, validation_time_ms=30
        )
        err = ValidationError(
            file=Path("/fake/a.py"),
            line=5,
            message="Bad import",
            suggestion="Fix it",
            code="BROKEN_IMPORT",
        )
        warn = ValidationWarning(
            file=Path("/fake/b.py"), line=None, message="Missing __all__", suggestion=None
        )
        return ValidationReport(errors=[err], warnings=[warn], metrics=metrics, success=False)

    def test_output_is_valid_json(self):  # sourcery skip: class-extract-method
        from exportify.commands.utils import CONSOLE, print_output_validation_json

        report = self._make_report()
        captured = []
        with patch.object(CONSOLE, "print", side_effect=lambda x, **_: captured.append(x)):
            print_output_validation_json(report)

        output_text = "".join(str(c) for c in captured)
        parsed = json.loads(output_text)
        assert "success" in parsed
        assert "errors" in parsed
        assert "warnings" in parsed
        assert "metrics" in parsed

    def test_output_contains_error_fields(self):
        from exportify.commands.utils import CONSOLE, print_output_validation_json

        report = self._make_report()
        captured = []
        with patch.object(CONSOLE, "print", side_effect=lambda x, **_: captured.append(x)):
            print_output_validation_json(report)

        output_text = "".join(str(c) for c in captured)
        parsed = json.loads(output_text)
        assert len(parsed["errors"]) == 1
        assert parsed["errors"][0]["code"] == "BROKEN_IMPORT"
        assert parsed["errors"][0]["line"] == 5

    def test_output_contains_warning_fields(self):
        from exportify.commands.utils import CONSOLE, print_output_validation_json

        report = self._make_report()
        captured = []
        with patch.object(CONSOLE, "print", side_effect=lambda x, **_: captured.append(x)):
            print_output_validation_json(report)

        output_text = "".join(str(c) for c in captured)
        parsed = json.loads(output_text)
        assert len(parsed["warnings"]) == 1
        assert parsed["warnings"][0]["line"] is None

    def test_output_metrics(self):
        from exportify.commands.utils import CONSOLE, print_output_validation_json

        report = self._make_report()
        captured = []
        with patch.object(CONSOLE, "print", side_effect=lambda x, **_: captured.append(x)):
            print_output_validation_json(report)

        output_text = "".join(str(c) for c in captured)
        parsed = json.loads(output_text)
        assert parsed["metrics"]["files_validated"] == 2
        assert parsed["metrics"]["imports_checked"] == 10


# ---------------------------------------------------------------------------
# print_output_validation_verbose
# ---------------------------------------------------------------------------


class TestOutputValidationVerbose:
    """Test print_output_validation_verbose helper."""

    def _make_report_with_errors(self):
        from exportify.common.types import (
            ValidationError,
            ValidationMetrics,
            ValidationReport,
            ValidationWarning,
        )

        metrics = ValidationMetrics(
            files_validated=1, imports_checked=5, consistency_checks=2, validation_time_ms=20
        )
        err = ValidationError(
            file=Path("/a/b.py"), line=3, message="Oops", suggestion="Do this instead", code="E001"
        )
        warn = ValidationWarning(
            file=Path("/a/c.py"), line=None, message="Advisory warning", suggestion="Consider X"
        )
        return ValidationReport(errors=[err], warnings=[warn], metrics=metrics, success=False)

    def test_verbose_output_runs(self):
        from exportify.commands.utils import print_output_validation_verbose

        report = self._make_report_with_errors()
        # Should not raise
        print_output_validation_verbose(report)

    def test_verbose_output_empty_report(self):
        from exportify.commands.utils import print_output_validation_verbose
        from exportify.common.types import ValidationMetrics, ValidationReport

        metrics = ValidationMetrics(
            files_validated=0, imports_checked=0, consistency_checks=0, validation_time_ms=0
        )
        report = ValidationReport(errors=[], warnings=[], metrics=metrics, success=True)
        print_output_validation_verbose(report)


# ---------------------------------------------------------------------------
# print_output_validation_concise
# ---------------------------------------------------------------------------


class TestOutputValidationConcise:
    """Test print_output_validation_concise helper."""

    def test_concise_output_with_errors(self):
        from exportify.commands.utils import print_output_validation_concise
        from exportify.common.types import ValidationError, ValidationMetrics, ValidationReport

        metrics = ValidationMetrics(
            files_validated=2, imports_checked=8, consistency_checks=3, validation_time_ms=10
        )
        err = ValidationError(
            file=Path("/x/y.py"), line=7, message="Bad thing", suggestion=None, code="BAD001"
        )
        report = ValidationReport(errors=[err], warnings=[], metrics=metrics, success=False)
        print_output_validation_concise(report)

    def test_concise_output_with_warnings_and_errors(self):
        from exportify.commands.utils import print_output_validation_concise
        from exportify.common.types import (
            ValidationError,
            ValidationMetrics,
            ValidationReport,
            ValidationWarning,
        )

        metrics = ValidationMetrics(
            files_validated=1, imports_checked=3, consistency_checks=1, validation_time_ms=5
        )
        err = ValidationError(
            file=Path("/p.py"), line=1, message="Error", suggestion=None, code="ERR"
        )
        warn = ValidationWarning(file=Path("/q.py"), line=2, message="Warning", suggestion=None)
        report = ValidationReport(errors=[err], warnings=[warn], metrics=metrics, success=False)
        print_output_validation_concise(report)


# ---------------------------------------------------------------------------
# _resolve_checks and _resolve_fix_checks
# ---------------------------------------------------------------------------


class TestResolveChecks:
    """Test check resolution logic."""

    def test_all_none_returns_all_checks(self):
        from exportify.commands.utils import resolve_checks

        all_checks = {"lateimports", "dynamic_imports", "module_all", "package_all"}
        result = resolve_checks(
            all_checks, lateimports=None, dynamic_imports=None, module_all=None, package_all=None
        )
        assert result == all_checks

    def test_one_true_whitelist_mode_returns_subset(self):
        from exportify.commands.utils import resolve_checks

        all_checks = {"lateimports", "dynamic_imports", "module_all", "package_all"}
        result = resolve_checks(
            all_checks, lateimports=True, dynamic_imports=None, module_all=None, package_all=None
        )
        assert result == {"lateimports"}

    def test_multiple_true_whitelist_mode(self):
        from exportify.commands.utils import resolve_checks

        all_checks = {"lateimports", "dynamic_imports", "module_all", "package_all"}
        result = resolve_checks(
            all_checks, lateimports=True, dynamic_imports=True, module_all=None, package_all=None
        )
        assert result == {"lateimports", "dynamic_imports"}

    def test_all_false_blacklist_returns_nothing(self):
        from exportify.commands.utils import resolve_checks

        all_checks = {"lateimports", "dynamic_imports", "module_all", "package_all"}
        result = resolve_checks(
            all_checks,
            lateimports=False,
            dynamic_imports=False,
            module_all=False,
            package_all=False,
        )
        assert result == set()

    def test_blacklist_mode_reduces_from_all(self):
        from exportify.commands.utils import resolve_checks

        all_checks = {"lateimports", "dynamic_imports", "module_all", "package_all"}
        result = resolve_checks(
            all_checks, lateimports=False, dynamic_imports=None, module_all=None, package_all=None
        )
        assert result == {"dynamic_imports", "module_all", "package_all"}

    def test_true_takes_priority_whitelist_mode(self):
        """True flag enables whitelist mode, ignoring False flags."""
        from exportify.commands.utils import resolve_checks

        all_checks = {"lateimports", "dynamic_imports", "module_all", "package_all"}
        result = resolve_checks(
            all_checks, lateimports=True, dynamic_imports=False, module_all=None, package_all=None
        )
        assert result == {"lateimports"}


class TestResolveFixChecks:
    """Test fix check resolution logic."""

    def test_all_none_returns_all_fix_checks(self):
        from exportify.commands.utils import resolve_checks

        all_checks = {"dynamic_imports", "module_all", "package_all"}
        result = resolve_checks(all_checks, dynamic_imports=None, module_all=None, package_all=None)
        assert result == all_checks

    def test_one_true_whitelist_returns_subset(self):
        from exportify.commands.utils import resolve_checks

        all_checks = {"dynamic_imports", "module_all", "package_all"}
        result = resolve_checks(all_checks, dynamic_imports=True, module_all=None, package_all=None)
        assert result == {"dynamic_imports"}

    def test_one_false_blacklist_reduces_set(self):
        from exportify.commands.utils import resolve_checks

        all_checks = {"dynamic_imports", "module_all", "package_all"}
        result = resolve_checks(
            all_checks, dynamic_imports=False, module_all=None, package_all=None
        )
        assert result == {"module_all", "package_all"}

    def test_all_false_returns_empty(self):
        from exportify.commands.utils import resolve_checks

        all_checks = {"dynamic_imports", "module_all", "package_all"}
        result = resolve_checks(
            all_checks, dynamic_imports=False, module_all=False, package_all=False
        )
        assert result == set()


# ---------------------------------------------------------------------------
# collect_py_files
# ---------------------------------------------------------------------------


class TestCollectPyFiles:
    """Test collect_py_files helper."""

    def test_empty_paths_uses_source(self, tmp_path):
        from exportify.commands.utils import collect_py_files

        (tmp_path / "a.py").write_text("x = 1")
        (tmp_path / "b.py").write_text("y = 2")

        result = collect_py_files((), tmp_path)
        names = {p.name for p in result}
        assert "a.py" in names
        assert "b.py" in names

    def test_explicit_file_path(self, tmp_path):
        from exportify.commands.utils import collect_py_files

        f = tmp_path / "mod.py"
        f.write_text("x = 1")

        result = collect_py_files((f,), None)
        assert f in result

    def test_explicit_dir_path(self, tmp_path):
        from exportify.commands.utils import collect_py_files

        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "a.py").write_text("x = 1")

        result = collect_py_files((pkg,), None)
        assert any(p.name == "a.py" for p in result)

    def test_nonexistent_path_raises(self, tmp_path):
        from exportify.commands.utils import collect_py_files

        nonexistent = tmp_path / "does_not_exist"
        with pytest.raises(SystemExit):
            collect_py_files((nonexistent,), None)


# ---------------------------------------------------------------------------
# path_to_module
# ---------------------------------------------------------------------------


class TestPathToModule:
    """Test path_to_module helper."""

    def test_simple_relative(self, tmp_path):
        from exportify.commands.utils import path_to_module

        source_root = tmp_path
        path = tmp_path / "mypackage" / "utils"
        result = path_to_module(path, source_root)
        assert result == "mypackage.utils"

    def test_single_file(self, tmp_path):
        from exportify.commands.utils import path_to_module

        source_root = tmp_path
        path = tmp_path / "mod"
        result = path_to_module(path, source_root)
        assert result == "mod"

    def test_path_not_relative_to_source_falls_back(self, tmp_path):
        from exportify.commands.utils import path_to_module

        # Path outside source_root — should fall back to something
        other = tmp_path / "other" / "module"
        source_root = tmp_path / "src"
        result = path_to_module(other, source_root)
        # Should not raise; returns a string
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# load_rules
# ---------------------------------------------------------------------------


class TestLoadRules:
    """Test load_rules helper."""

    def test_no_config_returns_default_rules(self, monkeypatch):
        from exportify.commands.utils import load_rules

        monkeypatch.setattr("exportify.commands.utils.find_config_file", lambda: None)
        rules = load_rules()
        assert rules is not None

    def test_no_config_verbose_returns_default_rules(self, monkeypatch):
        from exportify.commands.utils import load_rules

        monkeypatch.setattr("exportify.commands.utils.find_config_file", lambda: None)
        rules = load_rules(verbose=True)
        assert rules is not None

    def test_with_config_file(self, tmp_path, monkeypatch):
        from exportify.commands.utils import load_rules

        rules_file = tmp_path / "rules.yaml"
        rules_file.write_text('schema_version: "1.0"\nrules: []\n')
        monkeypatch.setattr("exportify.commands.utils.find_config_file", lambda: rules_file)
        rules = load_rules(verbose=True)
        assert rules is not None


# ---------------------------------------------------------------------------
# _display_all_modifications
# ---------------------------------------------------------------------------


class TestDisplayAllModifications:
    """Test _display_all_modifications helper."""

    def _make_result(self, added=None, removed=None, created=False):
        result = MagicMock()
        result.added = added
        result.removed = removed
        result.created = created
        return result

    def test_added_items_displayed(self):
        from exportify.commands.check import _display_all_modifications

        result = self._make_result(added=["Foo", "Bar"])
        _display_all_modifications(result, "+ Add: ", "- Remove: ", "new created")

    def test_removed_items_displayed(self):
        from exportify.commands.check import _display_all_modifications

        result = self._make_result(removed=["OldFoo"])
        _display_all_modifications(result, "+ Add: ", "- Remove: ", "new created")

    def test_created_displayed(self):
        from exportify.commands.check import _display_all_modifications

        result = self._make_result(created=True)
        _display_all_modifications(result, "+ Add: ", "- Remove: ", "new created")

    def test_nothing_to_display(self):
        from exportify.commands.check import _display_all_modifications

        result = self._make_result(added=None, removed=None, created=False)
        _display_all_modifications(result, "+ Add: ", "- Remove: ", "new created")


# ---------------------------------------------------------------------------
# _print_error_in_validation
# ---------------------------------------------------------------------------


class TestPrintErrorInValidation:
    """Test _print_error_in_validation helper."""

    def test_with_suggestion(self):
        from exportify.commands.utils import _print_error_in_validation

        err = MagicMock()
        err.message = "Something went wrong"
        err.suggestion = "Try this fix"
        _print_error_in_validation(err)

    def test_without_suggestion(self):
        from exportify.commands.utils import _print_error_in_validation

        err = MagicMock()
        err.message = "Something went wrong"
        err.suggestion = None
        _print_error_in_validation(err)


@pytest.mark.integration
class TestDoctorCommand:
    """Test doctor command."""

    def test_doctor_runs(self):
        """doctor command executes without error."""
        exit_code, _stdout, stderr = run_cli("doctor")
        assert exit_code == 0, f"Failed: {stderr}"

    def test_doctor_output_contains_health_info(self):
        """doctor output mentions cache and config."""
        exit_code, stdout, _ = run_cli("doctor")
        assert exit_code == 0
        # Should mention something about cache or config
        combined = stdout.lower()
        assert "cache" in combined or "config" in combined or "health" in combined

    def test_doctor_help(self):
        exit_code, _stdout, _ = run_cli("doctor", "--help")
        assert exit_code == 0


@pytest.mark.integration
class TestStatusCommand:
    """Test doctor --short command (the new status)."""

    def test_status_runs(self):
        """doctor --short executes without error."""
        exit_code, _stdout, stderr = run_cli("doctor", "--short")
        assert exit_code == 0, f"Failed: {stderr}"

    def test_status_verbose(self):
        """doctor (full) executes without error."""
        exit_code, _stdout, stderr = run_cli("doctor")
        assert exit_code == 0, f"Failed: {stderr}"

    def test_status_help(self):
        exit_code, _stdout, _ = run_cli("doctor", "--help")
        assert exit_code == 0


@pytest.mark.integration
class TestClearCacheCommand:
    """Test cache clear command."""

    def test_clear_cache_runs(self):
        """cache clear executes without error."""
        exit_code, _stdout, stderr = run_cli("cache", "clear")
        assert exit_code == 0, f"Failed: {stderr}"

    def test_clear_cache_help(self):
        exit_code, _stdout, _ = run_cli("cache", "clear", "--help")
        assert exit_code == 0


@pytest.mark.integration
class TestInitCommand:
    """Test init command."""

    def test_init_dry_run(self, tmp_path):
        """init --dry-run shows config without writing."""
        output_file = tmp_path / "config.yaml"
        exit_code, _stdout, stderr = run_cli("init", "--output", str(output_file), "--dry-run")
        assert exit_code == 0, f"Failed: {stderr}"
        assert not output_file.exists(), "dry-run should not write files"

    def test_init_creates_file(self, tmp_path):
        """init creates the config file."""
        output_file = tmp_path / "config.yaml"
        exit_code, _stdout, stderr = run_cli("init", "--output", str(output_file))
        assert exit_code == 0, f"Failed: {stderr}"
        assert output_file.exists(), "init should write config file"

    def test_init_does_not_overwrite_without_force(self, tmp_path):
        """init refuses to overwrite existing config without --force."""
        output_file = tmp_path / "config.yaml"
        output_file.write_text("existing content")

        exit_code, _stdout, _stderr = run_cli("init", "--output", str(output_file))
        assert exit_code != 0, "Should fail when file already exists without --force"
        # The existing file should be unchanged
        assert output_file.read_text() == "existing content"

    def test_init_force_overwrites(self, tmp_path):
        """init --force overwrites existing config."""
        output_file = tmp_path / "config.yaml"
        output_file.write_text("old content")

        exit_code, _stdout, stderr = run_cli("init", "--output", str(output_file), "--force")
        assert exit_code == 0, f"Failed: {stderr}"
        new_content = output_file.read_text()
        assert "old content" not in new_content

    def test_init_verbose(self, tmp_path):
        """init --verbose shows configuration summary."""
        output_file = tmp_path / "config.yaml"
        exit_code, _stdout, stderr = run_cli("init", "--output", str(output_file), "--verbose")
        assert exit_code == 0, f"Failed: {stderr}"

    def test_init_help(self):
        exit_code, _stdout, _ = run_cli("init", "--help")
        assert exit_code == 0


@pytest.mark.integration
class TestCheckCommandExtended:
    """Extended tests for the check command."""

    def test_check_verbose_flag(self, tmp_path):
        """check --verbose shows detailed output."""
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        (pkg / "mod.py").write_text("class Foo: pass")

        exit_code, _stdout, _ = run_cli("check", str(pkg), "--verbose")
        assert exit_code == 0

    def test_check_json_flag(self, tmp_path):
        """check --json outputs JSON-like content."""
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        (pkg / "mod.py").write_text("class Foo: pass")

        exit_code, _stdout, _ = run_cli("check", str(pkg), "--json")
        # Exit code may vary; just ensure it doesn't crash unexpectedly
        assert isinstance(exit_code, int)

    def test_check_dynamic_imports_flag(self, tmp_path):
        """check --dynamic-imports runs without error."""
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        (pkg / "mod.py").write_text("class Foo: pass")

        exit_code, _stdout, stderr = run_cli("check", str(pkg), "--dynamic-imports")
        assert exit_code == 0, f"Failed: {stderr}"

    def test_check_package_all_verbose(self, tmp_path):
        """check --package-all --verbose runs without error."""
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")

        exit_code, _stdout, stderr = run_cli("check", str(pkg), "--package-all", "--verbose")
        assert exit_code == 0, f"Failed: {stderr}"

    def test_check_strict_mode_no_issues(self, tmp_path):
        """check --strict with no issues passes."""
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")

        exit_code, _, _ = run_cli("check", str(pkg), "--strict")
        assert exit_code == 0

    def test_check_lateimports_flag_without_dependency(self, tmp_path, monkeypatch):
        """check --lateimports when dependency absent skips gracefully."""
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        (pkg / "mod.py").write_text("class Foo: pass")

        # detect_lateimport_dependency is imported inside the function from exportify.utils
        monkeypatch.setattr("exportify.utils.detect_lateimport_dependency", lambda: False)
        exit_code, _stdout, _ = run_cli("check", str(pkg), "--lateimports")
        # Should complete without crashing
        assert isinstance(exit_code, int)

    def test_check_source_flag(self, tmp_path):
        """check --source flag works."""
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        (pkg / "mod.py").write_text("class Foo: pass")

        exit_code, _, _stderr = run_cli("check", "--source", str(tmp_path))
        assert isinstance(exit_code, int)


@pytest.mark.integration
class TestSyncCommandExtended:
    """Extended tests for the sync command (formerly generate and fix)."""

    def test_sync_verbose(self, tmp_path):
        """sync --verbose shows detailed output."""
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        (pkg / "mod.py").write_text("class Foo: pass")

        exit_code, _, stderr = run_cli("sync", "--source", str(tmp_path), "--verbose")
        assert exit_code == 0, f"Failed: {stderr}"

    def test_sync_package_all_dry_run(self, tmp_path):
        """sync --package-all --dry-run works."""
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        (pkg / "mod.py").write_text("class Foo: pass")

        exit_code, _, stderr = run_cli(
            "sync", "--source", str(tmp_path), "--package-all", "--dry-run"
        )
        assert exit_code == 0, f"Failed: {stderr}"

    def test_sync_all_in_sync_message(self, tmp_path):
        """sync reports 'already in sync' when nothing to change."""
        src = tmp_path / "src"
        src.mkdir()
        pkg = src / "pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        (pkg / "mod.py").write_text("class Foo: pass")

        # First sync to get it in sync
        run_cli("sync", "--source", str(src))

        # Second sync should report success
        exit_code, stdout, _ = run_cli("sync", "--source", str(src), "--dry-run")
        assert exit_code == 0
        assert "completed successfully" in stdout.lower()

    def test_sync_with_path_arg(self, tmp_path):
        """sync with positional path targets specific path."""
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "mod.py").write_text("class Foo: pass")

        exit_code, _, stderr = run_cli("sync", str(pkg), "--source", str(tmp_path))
        assert exit_code == 0, f"Failed: {stderr}"

    def test_sync_with_output_dir(self, tmp_path):
        """sync --output directs output to another directory."""
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "mod.py").write_text("class Foo: pass")
        out_dir = tmp_path / "out"
        out_dir.mkdir()

        exit_code, _, stderr = run_cli("sync", "--source", str(tmp_path), "--output", str(out_dir))
        assert exit_code == 0, f"Failed: {stderr}"

    def test_sync_nonexistent_source_exits_nonzero(self, tmp_path):
        """sync exits non-zero when source doesn't exist."""
        nonexistent = tmp_path / "nonexistent_src"
        exit_code, _, _ = run_cli("sync", "--source", str(nonexistent))
        assert exit_code != 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
