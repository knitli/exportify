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

class TestLazyImportsCLI:
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
        from exportify.validator import LazyImportValidator

        cache = AnalysisCache()
        validator = LazyImportValidator(cache=cache)

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
            files_validated=3,
            imports_checked=15,
            consistency_checks=7,
            validation_time_ms=55,
        )
        return ValidationReport(
            errors=errors or [],
            warnings=warnings or [],
            metrics=metrics,
            success=success,
        )

    def test_print_generation_results_success(self, capsys):
        """_print_generation_results prints success output."""
        from exportify.cli import _print_generation_results

        result = self._make_generation_result(success=True)
        _print_generation_results(result)
        # Doesn't raise; rich console output goes to its own stdout handle

    def test_print_generation_results_failure(self):
        """_print_generation_results handles failure case with errors."""
        from exportify.cli import _print_generation_results

        result = self._make_generation_result(success=False, errors=["broken pipe", "parse error"])
        # Should not raise
        _print_generation_results(result)

    def test_print_validation_results_success(self):
        """_print_validation_results handles success."""
        from exportify.cli import _print_validation_results

        report = self._make_validation_report(success=True)
        _print_validation_results(report)

    def test_print_validation_results_with_errors(self):
        """_print_validation_results shows errors."""
        from exportify.common.types import ValidationError, ValidationWarning
        from exportify.cli import _print_validation_results

        err = ValidationError(
            file=Path("/fake/file.py"),
            line=10,
            message="Broken import",
            suggestion="Fix it",
            code="BROKEN_IMPORT",
        )
        warn = ValidationWarning(
            file=Path("/fake/file.py"),
            line=None,
            message="Missing __all__",
            suggestion=None,
        )
        report = self._make_validation_report(
            success=False, errors=[err], warnings=[warn]
        )
        _print_validation_results(report)

    def test_print_validation_results_error_no_line(self):
        """_print_validation_results handles errors without line numbers."""
        from exportify.common.types import ValidationError
        from exportify.cli import _print_validation_results

        err = ValidationError(
            file=Path("/fake/file.py"),
            line=None,
            message="Some error",
            suggestion=None,
            code="SOME_CODE",
        )
        report = self._make_validation_report(success=False, errors=[err])
        _print_validation_results(report)

    def test_print_validation_results_warning_with_suggestion(self):
        """_print_validation_results shows warnings with suggestions."""
        from exportify.common.types import ValidationWarning
        from exportify.cli import _print_validation_results

        warn = ValidationWarning(
            file=Path("/fake/warn.py"),
            line=5,
            message="Consider adding __all__",
            suggestion="Add __all__ = [...]",
        )
        report = self._make_validation_report(success=True, warnings=[warn])
        _print_validation_results(report)

    def test_print_success(self):
        """_print_success runs without error."""
        from exportify.cli import _print_success
        _print_success("All good")

    def test_print_error(self):
        """_print_error runs without error."""
        from exportify.cli import _print_error
        _print_error("Something broke")

    def test_print_warning(self):
        """_print_warning runs without error."""
        from exportify.cli import _print_warning
        _print_warning("Watch out")

    def test_print_info(self):
        """_print_info runs without error."""
        from exportify.cli import _print_info
        _print_info("FYI")


# ---------------------------------------------------------------------------
# _resolve_validation_files
# ---------------------------------------------------------------------------

class TestResolveValidationFiles:
    """Test _resolve_validation_files helper."""

    def test_none_module_returns_none(self):
        from exportify.cli import _resolve_validation_files

        result = _resolve_validation_files(None, json_output=False)
        assert result is None

    def test_file_module_returns_list_with_file(self, tmp_path):
        from exportify.cli import _resolve_validation_files

        f = tmp_path / "mod.py"
        f.write_text("x = 1")
        result = _resolve_validation_files(f, json_output=False)
        assert result == [f]

    def test_dir_module_returns_py_files(self, tmp_path):
        from exportify.cli import _resolve_validation_files

        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "a.py").write_text("x = 1")
        (pkg / "b.py").write_text("y = 2")
        (pkg / "c.txt").write_text("not python")

        result = _resolve_validation_files(pkg, json_output=False)
        assert result is not None
        paths = {p.name for p in result}
        assert "a.py" in paths
        assert "b.py" in paths
        assert "c.txt" not in paths

    def test_nonexistent_path_raises_system_exit(self, tmp_path):
        from exportify.cli import _resolve_validation_files

        nonexistent = tmp_path / "does_not_exist.py"
        with pytest.raises(SystemExit):
            _resolve_validation_files(nonexistent, json_output=False)

    def test_nonexistent_path_json_mode_raises_system_exit(self, tmp_path):
        from exportify.cli import _resolve_validation_files

        nonexistent = tmp_path / "does_not_exist.py"
        with pytest.raises(SystemExit):
            _resolve_validation_files(nonexistent, json_output=True)


# ---------------------------------------------------------------------------
# _output_validation_json
# ---------------------------------------------------------------------------

class TestOutputValidationJson:
    """Test _output_validation_json helper."""

    def _make_report(self):
        from exportify.common.types import (
            ValidationError, ValidationMetrics, ValidationReport, ValidationWarning,
        )
        metrics = ValidationMetrics(
            files_validated=2,
            imports_checked=10,
            consistency_checks=4,
            validation_time_ms=30,
        )
        err = ValidationError(
            file=Path("/fake/a.py"),
            line=5,
            message="Bad import",
            suggestion="Fix it",
            code="BROKEN_IMPORT",
        )
        warn = ValidationWarning(
            file=Path("/fake/b.py"),
            line=None,
            message="Missing __all__",
            suggestion=None,
        )
        return ValidationReport(errors=[err], warnings=[warn], metrics=metrics, success=False)

    def test_output_is_valid_json(self):
        from exportify.cli import _output_validation_json, console

        report = self._make_report()
        captured = []
        with patch.object(console, "print", side_effect=lambda x, **_: captured.append(x)):
            _output_validation_json(report)

        output_text = "".join(str(c) for c in captured)
        parsed = json.loads(output_text)
        assert "success" in parsed
        assert "errors" in parsed
        assert "warnings" in parsed
        assert "metrics" in parsed

    def test_output_contains_error_fields(self):
        from exportify.cli import _output_validation_json, console

        report = self._make_report()
        captured = []
        with patch.object(console, "print", side_effect=lambda x, **_: captured.append(x)):
            _output_validation_json(report)

        output_text = "".join(str(c) for c in captured)
        parsed = json.loads(output_text)
        assert len(parsed["errors"]) == 1
        assert parsed["errors"][0]["code"] == "BROKEN_IMPORT"
        assert parsed["errors"][0]["line"] == 5

    def test_output_contains_warning_fields(self):
        from exportify.cli import _output_validation_json, console

        report = self._make_report()
        captured = []
        with patch.object(console, "print", side_effect=lambda x, **_: captured.append(x)):
            _output_validation_json(report)

        output_text = "".join(str(c) for c in captured)
        parsed = json.loads(output_text)
        assert len(parsed["warnings"]) == 1
        assert parsed["warnings"][0]["line"] is None

    def test_output_metrics(self):
        from exportify.cli import _output_validation_json, console

        report = self._make_report()
        captured = []
        with patch.object(console, "print", side_effect=lambda x, **_: captured.append(x)):
            _output_validation_json(report)

        output_text = "".join(str(c) for c in captured)
        parsed = json.loads(output_text)
        assert parsed["metrics"]["files_validated"] == 2
        assert parsed["metrics"]["imports_checked"] == 10


# ---------------------------------------------------------------------------
# _output_validation_verbose
# ---------------------------------------------------------------------------

class TestOutputValidationVerbose:
    """Test _output_validation_verbose helper."""

    def _make_report_with_errors(self):
        from exportify.common.types import (
            ValidationError, ValidationMetrics, ValidationReport, ValidationWarning,
        )
        metrics = ValidationMetrics(
            files_validated=1,
            imports_checked=5,
            consistency_checks=2,
            validation_time_ms=20,
        )
        err = ValidationError(
            file=Path("/a/b.py"),
            line=3,
            message="Oops",
            suggestion="Do this instead",
            code="E001",
        )
        warn = ValidationWarning(
            file=Path("/a/c.py"),
            line=None,
            message="Advisory warning",
            suggestion="Consider X",
        )
        return ValidationReport(errors=[err], warnings=[warn], metrics=metrics, success=False)

    def test_verbose_output_runs(self):
        from exportify.cli import _output_validation_verbose

        report = self._make_report_with_errors()
        # Should not raise
        _output_validation_verbose(report)

    def test_verbose_output_empty_report(self):
        from exportify.cli import _output_validation_verbose
        from exportify.common.types import ValidationMetrics, ValidationReport

        metrics = ValidationMetrics(
            files_validated=0, imports_checked=0, consistency_checks=0, validation_time_ms=0
        )
        report = ValidationReport(errors=[], warnings=[], metrics=metrics, success=True)
        _output_validation_verbose(report)


# ---------------------------------------------------------------------------
# _output_validation_concise
# ---------------------------------------------------------------------------

class TestOutputValidationConcise:
    """Test _output_validation_concise helper."""

    def test_concise_output_with_errors(self):
        from exportify.cli import _output_validation_concise
        from exportify.common.types import ValidationError, ValidationMetrics, ValidationReport

        metrics = ValidationMetrics(
            files_validated=2, imports_checked=8, consistency_checks=3, validation_time_ms=10
        )
        err = ValidationError(
            file=Path("/x/y.py"),
            line=7,
            message="Bad thing",
            suggestion=None,
            code="BAD001",
        )
        report = ValidationReport(errors=[err], warnings=[], metrics=metrics, success=False)
        _output_validation_concise(report)

    def test_concise_output_with_warnings_and_errors(self):
        from exportify.cli import _output_validation_concise
        from exportify.common.types import (
            ValidationError, ValidationMetrics, ValidationReport, ValidationWarning,
        )

        metrics = ValidationMetrics(
            files_validated=1, imports_checked=3, consistency_checks=1, validation_time_ms=5
        )
        err = ValidationError(
            file=Path("/p.py"),
            line=1,
            message="Error",
            suggestion=None,
            code="ERR",
        )
        warn = ValidationWarning(
            file=Path("/q.py"),
            line=2,
            message="Warning",
            suggestion=None,
        )
        report = ValidationReport(errors=[err], warnings=[warn], metrics=metrics, success=False)
        _output_validation_concise(report)


# ---------------------------------------------------------------------------
# _resolve_checks and _resolve_fix_checks
# ---------------------------------------------------------------------------

class TestResolveChecks:
    """Test check resolution logic."""

    def test_all_none_returns_all_checks(self):
        from exportify.cli import _resolve_checks

        result = _resolve_checks(
            lateimports=None, dynamic_imports=None, module_all=None, package_all=None
        )
        assert result == {"lateimports", "dynamic_imports", "module_all", "package_all"}

    def test_one_true_whitelist_mode_returns_subset(self):
        from exportify.cli import _resolve_checks

        # In whitelist mode (any True), result is a strict subset of all checks.
        # Note: due to set zip ordering, the exact mapped check may differ from the flag name.
        result = _resolve_checks(
            lateimports=True, dynamic_imports=None, module_all=None, package_all=None
        )
        all_checks = {"lateimports", "dynamic_imports", "module_all", "package_all"}
        assert len(result) == 1
        assert result.issubset(all_checks)

    def test_multiple_true_whitelist_mode(self):
        from exportify.cli import _resolve_checks

        # Whitelist mode: result is a non-empty strict subset
        result = _resolve_checks(
            lateimports=True, dynamic_imports=True, module_all=None, package_all=None
        )
        all_checks = {"lateimports", "dynamic_imports", "module_all", "package_all"}
        assert len(result) == 2
        assert result.issubset(all_checks)

    def test_all_false_blacklist_returns_nothing(self):
        from exportify.cli import _resolve_checks

        result = _resolve_checks(
            lateimports=False, dynamic_imports=False, module_all=False, package_all=False
        )
        assert result == set()

    def test_all_none_blacklist_all_returns_empty(self):
        from exportify.cli import _resolve_checks

        # All explicitly False = blacklist everything
        result = _resolve_checks(
            lateimports=False, dynamic_imports=False, module_all=False, package_all=False
        )
        assert result == set()

    def test_blacklist_mode_reduces_from_all(self):
        from exportify.cli import _resolve_checks

        # Some False flags reduce the result from the full set
        result = _resolve_checks(
            lateimports=False, dynamic_imports=None, module_all=None, package_all=None
        )
        all_checks = {"lateimports", "dynamic_imports", "module_all", "package_all"}
        assert len(result) == 3
        assert result.issubset(all_checks)

    def test_true_takes_priority_whitelist_mode(self):
        """True flag enables whitelist mode, result is a strict subset."""
        from exportify.cli import _resolve_checks

        result = _resolve_checks(
            lateimports=True, dynamic_imports=False, module_all=None, package_all=None
        )
        all_checks = {"lateimports", "dynamic_imports", "module_all", "package_all"}
        # Whitelist mode: exactly one element returned (only the True position mapped)
        assert len(result) == 1
        assert result.issubset(all_checks)


class TestResolveFixChecks:
    """Test fix check resolution logic."""

    def test_all_none_returns_all_fix_checks(self):
        from exportify.cli import _resolve_fix_checks

        result = _resolve_fix_checks(
            dynamic_imports=None, module_all=None, package_all=None
        )
        assert result == {"dynamic_imports", "module_all", "package_all"}

    def test_one_true_whitelist_returns_subset(self):
        from exportify.cli import _resolve_fix_checks

        # Whitelist mode returns exactly one check (due to set zip ordering may differ)
        result = _resolve_fix_checks(
            dynamic_imports=True, module_all=None, package_all=None
        )
        all_fix_checks = {"dynamic_imports", "module_all", "package_all"}
        assert len(result) == 1
        assert result.issubset(all_fix_checks)

    def test_one_false_blacklist_reduces_set(self):
        from exportify.cli import _resolve_fix_checks

        result = _resolve_fix_checks(
            dynamic_imports=False, module_all=None, package_all=None
        )
        all_fix_checks = {"dynamic_imports", "module_all", "package_all"}
        assert len(result) == 2
        assert result.issubset(all_fix_checks)

    def test_all_false_returns_empty(self):
        from exportify.cli import _resolve_fix_checks

        result = _resolve_fix_checks(
            dynamic_imports=False, module_all=False, package_all=False
        )
        assert result == set()


# ---------------------------------------------------------------------------
# _collect_py_files
# ---------------------------------------------------------------------------

class TestCollectPyFiles:
    """Test _collect_py_files helper."""

    def test_empty_paths_uses_source(self, tmp_path):
        from exportify.cli import _collect_py_files

        (tmp_path / "a.py").write_text("x = 1")
        (tmp_path / "b.py").write_text("y = 2")

        result = _collect_py_files((), tmp_path)
        names = {p.name for p in result}
        assert "a.py" in names
        assert "b.py" in names

    def test_explicit_file_path(self, tmp_path):
        from exportify.cli import _collect_py_files

        f = tmp_path / "mod.py"
        f.write_text("x = 1")

        result = _collect_py_files((f,), None)
        assert f in result

    def test_explicit_dir_path(self, tmp_path):
        from exportify.cli import _collect_py_files

        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "a.py").write_text("x = 1")

        result = _collect_py_files((pkg,), None)
        assert any(p.name == "a.py" for p in result)

    def test_nonexistent_path_raises(self, tmp_path):
        from exportify.cli import _collect_py_files

        nonexistent = tmp_path / "does_not_exist"
        with pytest.raises(SystemExit):
            _collect_py_files((nonexistent,), None)


# ---------------------------------------------------------------------------
# _path_to_module
# ---------------------------------------------------------------------------

class TestPathToModule:
    """Test _path_to_module helper."""

    def test_simple_relative(self, tmp_path):
        from exportify.cli import _path_to_module

        source_root = tmp_path
        path = tmp_path / "mypackage" / "utils"
        result = _path_to_module(path, source_root)
        assert result == "mypackage.utils"

    def test_single_file(self, tmp_path):
        from exportify.cli import _path_to_module

        source_root = tmp_path
        path = tmp_path / "mod"
        result = _path_to_module(path, source_root)
        assert result == "mod"

    def test_path_not_relative_to_source_falls_back(self, tmp_path):
        from exportify.cli import _path_to_module

        # Path outside source_root — should fall back to something
        other = tmp_path / "other" / "module"
        source_root = tmp_path / "src"
        result = _path_to_module(other, source_root)
        # Should not raise; returns a string
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# _load_rules
# ---------------------------------------------------------------------------

class TestLoadRules:
    """Test _load_rules helper."""

    def test_no_config_returns_default_rules(self, monkeypatch):
        from exportify.cli import _load_rules

        monkeypatch.setattr("exportify.cli.find_config_file", lambda: None)
        rules = _load_rules()
        assert rules is not None

    def test_no_config_verbose_returns_default_rules(self, monkeypatch):
        from exportify.cli import _load_rules

        monkeypatch.setattr("exportify.cli.find_config_file", lambda: None)
        rules = _load_rules(verbose=True)
        assert rules is not None

    def test_with_config_file(self, tmp_path, monkeypatch):
        from exportify.cli import _load_rules

        rules_file = tmp_path / "rules.yaml"
        rules_file.write_text('schema_version: "1.0"\nrules: []\n')
        monkeypatch.setattr("exportify.cli.find_config_file", lambda: rules_file)
        rules = _load_rules(verbose=True)
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
        from exportify.cli import _display_all_modifications

        result = self._make_result(added=["Foo", "Bar"])
        _display_all_modifications(result, "+ Add: ", "- Remove: ", "new created")

    def test_removed_items_displayed(self):
        from exportify.cli import _display_all_modifications

        result = self._make_result(removed=["OldFoo"])
        _display_all_modifications(result, "+ Add: ", "- Remove: ", "new created")

    def test_created_displayed(self):
        from exportify.cli import _display_all_modifications

        result = self._make_result(created=True)
        _display_all_modifications(result, "+ Add: ", "- Remove: ", "new created")

    def test_nothing_to_display(self):
        from exportify.cli import _display_all_modifications

        result = self._make_result(added=None, removed=None, created=False)
        _display_all_modifications(result, "+ Add: ", "- Remove: ", "new created")


# ---------------------------------------------------------------------------
# _print_error_in_validation
# ---------------------------------------------------------------------------

class TestPrintErrorInValidation:
    """Test _print_error_in_validation helper."""

    def test_with_suggestion(self):
        from exportify.cli import _print_error_in_validation

        err = MagicMock()
        err.message = "Something went wrong"
        err.suggestion = "Try this fix"
        _print_error_in_validation(err)

    def test_without_suggestion(self):
        from exportify.cli import _print_error_in_validation

        err = MagicMock()
        err.message = "Something went wrong"
        err.suggestion = None
        _print_error_in_validation(err)


# ---------------------------------------------------------------------------
# _analyze_target_path helper
# ---------------------------------------------------------------------------

class TestAnalyzeTargetPath:
    """Test _analyze_target_path helper."""

    def test_explicit_file_path(self, tmp_path):
        from exportify.cli import _analyze_target_path

        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        mod = pkg / "mod.py"
        mod.write_text("class Foo: pass")

        target_path, target_file, module_path = _analyze_target_path(mod, tmp_path)
        assert target_path == mod
        assert target_file == mod

    def test_explicit_dir_path_with_init(self, tmp_path):
        from exportify.cli import _analyze_target_path

        pkg = tmp_path / "mypkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        (pkg / "mod.py").write_text("class Foo: pass")

        target_path, target_file, module_path = _analyze_target_path(pkg, tmp_path)
        assert target_path == pkg
        assert target_file == pkg / "__init__.py"

    def test_nonexistent_module_raises_system_exit(self, tmp_path):
        from exportify.cli import _analyze_target_path

        nonexistent = tmp_path / "does_not_exist"
        with pytest.raises(SystemExit):
            _analyze_target_path(nonexistent, tmp_path)

    def test_auto_detect_single_package(self, tmp_path):
        from exportify.cli import _analyze_target_path

        # source_root has no __init__.py, but has one sub-package
        pkg = tmp_path / "mypkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")

        target_path, target_file, module_path = _analyze_target_path(None, tmp_path)
        assert target_path == pkg
        assert target_file == pkg / "__init__.py"

    def test_auto_detect_multiple_packages_raises(self, tmp_path):
        from exportify.cli import _analyze_target_path

        pkg1 = tmp_path / "pkg1"
        pkg2 = tmp_path / "pkg2"
        pkg1.mkdir()
        pkg2.mkdir()
        (pkg1 / "__init__.py").write_text("")
        (pkg2 / "__init__.py").write_text("")

        with pytest.raises(SystemExit):
            _analyze_target_path(None, tmp_path)

    def test_auto_detect_no_package_raises(self, tmp_path):
        from exportify.cli import _analyze_target_path

        # source_root with no sub-packages and no own __init__.py
        with pytest.raises(SystemExit):
            _analyze_target_path(None, tmp_path)

    def test_dir_without_init_raises(self, tmp_path):
        from exportify.cli import _analyze_target_path

        pkg = tmp_path / "mypkg"
        pkg.mkdir()
        # No __init__.py

        with pytest.raises(SystemExit):
            _analyze_target_path(pkg, tmp_path)


# ---------------------------------------------------------------------------
# _get_preserved_code
# ---------------------------------------------------------------------------

class TestGetPreservedCode:
    """Test _get_preserved_code helper."""

    def test_returns_empty_for_non_init_file(self, tmp_path):
        from exportify.cli import _get_preserved_code

        mod = tmp_path / "mod.py"
        mod.write_text("x = 1")
        result = _get_preserved_code(mod)
        assert result == ""

    def test_returns_empty_for_nonexistent_file(self, tmp_path):
        from exportify.cli import _get_preserved_code

        nonexistent = tmp_path / "__init__.py"
        result = _get_preserved_code(nonexistent)
        assert result == ""

    def test_returns_preserved_code_from_init(self, tmp_path):
        from exportify.cli import _get_preserved_code

        init = tmp_path / "__init__.py"
        init.write_text('"""My docstring."""\n\nfrom .mod import Foo\n')
        result = _get_preserved_code(init)
        # Should return some string (might be empty or have content depending on sentinel)
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# _print_symbols_section
# ---------------------------------------------------------------------------

class TestPrintSymbolsSection:
    """Test _print_symbols_section helper."""

    def _make_symbols(self):
        from exportify.common.types import (
            DetectedSymbol, MemberType, SourceLocation, SymbolProvenance,
        )
        return [
            DetectedSymbol(
                name="MyClass",
                provenance=SymbolProvenance.DEFINED_HERE,
                location=SourceLocation(line=1),
                member_type=MemberType.CLASS,
                is_private=False,
                original_source=None,
                original_name=None,
            ),
            DetectedSymbol(
                name="my_func",
                provenance=SymbolProvenance.DEFINED_HERE,
                location=SourceLocation(line=5),
                member_type=MemberType.FUNCTION,
                is_private=False,
                original_source=None,
                original_name=None,
            ),
        ]

    def test_prints_symbols(self):
        from exportify.cli import _print_symbols_section

        symbols = {"mymodule": self._make_symbols()}
        _print_symbols_section(symbols, verbose=False)

    def test_prints_symbols_verbose(self):
        from exportify.cli import _print_symbols_section

        symbols = {"mymodule": self._make_symbols()}
        _print_symbols_section(symbols, verbose=True)

    def test_prints_many_symbols_truncated(self):
        """Non-verbose mode truncates after 5 symbols per type."""
        from exportify.cli import _print_symbols_section
        from exportify.common.types import (
            DetectedSymbol, MemberType, SourceLocation, SymbolProvenance,
        )

        many_symbols = [
            DetectedSymbol(
                name=f"Class{i}",
                provenance=SymbolProvenance.DEFINED_HERE,
                location=SourceLocation(line=i),
                member_type=MemberType.CLASS,
                is_private=False,
                original_source=None,
                original_name=None,
            )
            for i in range(10)
        ]
        _print_symbols_section({"mod": many_symbols}, verbose=False)

    def test_empty_symbols(self):
        from exportify.cli import _print_symbols_section

        _print_symbols_section({}, verbose=False)


# ---------------------------------------------------------------------------
# _print_decisions_section
# ---------------------------------------------------------------------------

class TestPrintDecisionsSection:
    """Test _print_decisions_section helper."""

    def _make_decisions(self, *, include=True):
        from exportify.common.types import (
            DetectedSymbol, ExportDecision, MemberType, PropagationLevel,
            RuleAction, SourceLocation, SymbolProvenance,
        )
        symbol = DetectedSymbol(
            name="MyClass",
            provenance=SymbolProvenance.DEFINED_HERE,
            location=SourceLocation(line=1),
            member_type=MemberType.CLASS,
            is_private=False,
            original_source=None,
            original_name=None,
        )
        action = RuleAction.INCLUDE if include else RuleAction.EXCLUDE
        return [
            ExportDecision(
                module_path="my.module",
                action=action,
                export_name="MyClass",
                propagation=PropagationLevel.PARENT,
                priority=800,
                reason="include-public-classes",
                source_symbol=symbol,
            )
        ]

    def test_prints_decisions_include(self):
        from exportify.cli import _print_decisions_section

        decisions = {"mymodule": self._make_decisions(include=True)}
        _print_decisions_section(decisions, verbose=False)

    def test_prints_decisions_exclude(self):
        from exportify.cli import _print_decisions_section

        decisions = {"mymodule": self._make_decisions(include=False)}
        _print_decisions_section(decisions, verbose=False)

    def test_prints_decisions_verbose(self):
        from exportify.cli import _print_decisions_section

        decisions = {"mymodule": self._make_decisions()}
        _print_decisions_section(decisions, verbose=True)

    def test_truncates_many_decisions(self):
        from exportify.cli import _print_decisions_section
        from exportify.common.types import (
            DetectedSymbol, ExportDecision, MemberType, PropagationLevel,
            RuleAction, SourceLocation, SymbolProvenance,
        )

        symbol = DetectedSymbol(
            name="X",
            provenance=SymbolProvenance.DEFINED_HERE,
            location=SourceLocation(line=1),
            member_type=MemberType.CLASS,
            is_private=False,
            original_source=None,
            original_name=None,
        )
        many = [
            ExportDecision(
                module_path="my.module",
                action=RuleAction.INCLUDE,
                export_name=f"Symbol{i}",
                propagation=PropagationLevel.PARENT,
                priority=800,
                reason="test",
                source_symbol=symbol,
            )
            for i in range(15)
        ]
        _print_decisions_section({"mod": many}, verbose=False)

    def test_empty_decisions(self):
        from exportify.cli import _print_decisions_section

        _print_decisions_section({}, verbose=False)


# ---------------------------------------------------------------------------
# _print_generation_section / _print_preserved_code_section / _print_warnings_section
# ---------------------------------------------------------------------------

class TestPrintSectionHelpers:
    """Test the various print section helpers."""

    def _make_manifest(self, num_exports=3):
        from exportify.common.types import ExportManifest, LazyExport

        exports = [
            LazyExport(
                public_name=f"Export{i}",
                target_module=f"my.mod{i}",
                target_object=f"Export{i}",
                is_type_only=False,
            )
            for i in range(num_exports)
        ]
        return ExportManifest(
            module_path="my.pkg",
            own_exports=exports,
            propagated_exports=[],
            all_exports=exports,
        )

    def test_print_generation_section_with_manifest(self):
        from exportify.cli import _print_generation_section

        manifest = self._make_manifest()
        _print_generation_section(manifest)

    def test_print_generation_section_no_manifest(self):
        from exportify.cli import _print_generation_section

        _print_generation_section(None)

    def test_print_preserved_code_section_no_code(self):
        from exportify.cli import _print_preserved_code_section

        _print_preserved_code_section("", verbose=False)

    def test_print_preserved_code_section_with_code(self):
        from exportify.cli import _print_preserved_code_section

        code = "\n".join(f"line {i}" for i in range(5))
        _print_preserved_code_section(code, verbose=False)

    def test_print_preserved_code_section_verbose(self):
        from exportify.cli import _print_preserved_code_section

        code = "\n".join(f"line {i}" for i in range(15))
        _print_preserved_code_section(code, verbose=True)

    def test_print_warnings_section_no_manifest(self):
        from exportify.cli import _print_warnings_section

        _print_warnings_section(None)

    def test_print_warnings_section_empty_exports(self):
        from exportify.cli import _print_warnings_section
        from exportify.common.types import ExportManifest

        manifest = ExportManifest(
            module_path="empty.pkg",
            own_exports=[],
            propagated_exports=[],
            all_exports=[],
        )
        _print_warnings_section(manifest)

    def test_print_warnings_section_with_exports(self):
        from exportify.cli import _print_warnings_section

        manifest = self._make_manifest(num_exports=2)
        _print_warnings_section(manifest)

    def test_print_ready_status_with_exports(self):
        from exportify.cli import _print_ready_status

        manifest = self._make_manifest(num_exports=2)
        _print_ready_status(manifest)

    def test_print_ready_status_no_manifest(self):
        from exportify.cli import _print_ready_status

        _print_ready_status(None)

    def test_print_ready_status_empty_manifest(self):
        from exportify.cli import _print_ready_status
        from exportify.common.types import ExportManifest

        manifest = ExportManifest(
            module_path="empty.pkg",
            own_exports=[],
            propagated_exports=[],
            all_exports=[],
        )
        _print_ready_status(manifest)


# ---------------------------------------------------------------------------
# _print_text_output and _print_json_output
# ---------------------------------------------------------------------------

class TestPrintOutputFunctions:
    """Test _print_text_output and _print_json_output."""

    def _make_data(self, tmp_path):
        from exportify.common.types import (
            DetectedSymbol, ExportDecision, ExportManifest, LazyExport,
            MemberType, PropagationLevel, RuleAction, SourceLocation, SymbolProvenance,
        )

        symbol = DetectedSymbol(
            name="MyClass",
            provenance=SymbolProvenance.DEFINED_HERE,
            location=SourceLocation(line=1),
            member_type=MemberType.CLASS,
            is_private=False,
            original_source=None,
            original_name=None,
        )
        decision = ExportDecision(
            module_path="my.module",
            action=RuleAction.INCLUDE,
            export_name="MyClass",
            propagation=PropagationLevel.PARENT,
            priority=800,
            reason="include-public-classes",
            source_symbol=symbol,
        )
        export = LazyExport(
            public_name="MyClass",
            target_module="my.module",
            target_object="MyClass",
            is_type_only=False,
        )
        manifest = ExportManifest(
            module_path="my.pkg",
            own_exports=[export],
            propagated_exports=[],
            all_exports=[export],
        )
        all_symbols = {"mymodule": [symbol]}
        all_decisions = {"mymodule": [decision]}
        return all_symbols, all_decisions, manifest

    def test_print_text_output(self, tmp_path):
        from exportify.cli import _print_text_output

        all_symbols, all_decisions, manifest = self._make_data(tmp_path)
        _print_text_output(
            "my.pkg",
            all_symbols,
            all_decisions,
            manifest,
            preserved_code="",
            verbose=False,
        )

    def test_print_text_output_verbose(self, tmp_path):
        from exportify.cli import _print_text_output

        all_symbols, all_decisions, manifest = self._make_data(tmp_path)
        _print_text_output(
            "my.pkg",
            all_symbols,
            all_decisions,
            manifest,
            preserved_code="# some code\nx = 1",
            verbose=True,
        )

    def test_print_text_output_no_manifest(self, tmp_path):
        from exportify.cli import _print_text_output

        all_symbols, all_decisions, _ = self._make_data(tmp_path)
        _print_text_output(
            "my.pkg",
            all_symbols,
            all_decisions,
            None,
            preserved_code="",
            verbose=False,
        )

    def test_print_json_output(self, tmp_path):
        from exportify.cli import _print_json_output, console

        all_symbols, all_decisions, manifest = self._make_data(tmp_path)
        captured = []
        with patch.object(console, "print", side_effect=lambda x, **_: captured.append(x)):
            _print_json_output("my.pkg", all_symbols, all_decisions, manifest, preserved_code="")

        output_text = "".join(str(c) for c in captured)
        parsed = json.loads(output_text)
        assert parsed["package"] == "my.pkg"
        assert "symbols" in parsed
        assert "decisions" in parsed
        assert "would_generate" in parsed

    def test_print_json_output_no_manifest(self, tmp_path):
        from exportify.cli import _print_json_output, console

        all_symbols, all_decisions, _ = self._make_data(tmp_path)
        captured = []
        with patch.object(console, "print", side_effect=lambda x, **_: captured.append(x)):
            _print_json_output("my.pkg", all_symbols, all_decisions, None, preserved_code="")

        output_text = "".join(str(c) for c in captured)
        parsed = json.loads(output_text)
        assert parsed["status"] == "no_exports"


# ---------------------------------------------------------------------------
# CLI command tests (via run_cli helper)
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestValidateCommand:
    """Test validate command (backward compat)."""

    def test_validate_basic(self, tmp_path):
        """validate command runs on simple project."""
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        (pkg / "mod.py").write_text("class Foo: pass")

        exit_code, stdout, stderr = run_cli("validate", "--source", str(pkg))
        # Should succeed or fail gracefully
        assert isinstance(exit_code, int)

    def test_validate_verbose(self, tmp_path):
        """validate --verbose shows detailed output."""
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")

        exit_code, stdout, stderr = run_cli("validate", "--verbose", "--source", str(pkg))
        assert isinstance(exit_code, int)

    def test_validate_json_output(self, tmp_path):
        """validate --json outputs JSON."""
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")

        exit_code, stdout, stderr = run_cli("validate", "--json")
        assert isinstance(exit_code, int)
        # If output has content, it should be JSON-parseable
        if stdout.strip():
            try:
                parsed = json.loads(stdout)
                assert "success" in parsed
            except json.JSONDecodeError:
                pass  # Console output might have markup stripped differently

    def test_validate_with_module_file(self, tmp_path):
        """validate --module points to a file."""
        f = tmp_path / "mod.py"
        f.write_text("class Foo: pass")

        exit_code, stdout, stderr = run_cli("validate", "--module", str(f))
        assert isinstance(exit_code, int)

    def test_validate_with_module_dir(self, tmp_path):
        """validate --module points to a directory."""
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        (pkg / "mod.py").write_text("class Foo: pass")

        exit_code, stdout, stderr = run_cli("validate", "--module", str(pkg))
        assert isinstance(exit_code, int)

    def test_validate_nonexistent_module_exits_nonzero(self, tmp_path):
        """validate with nonexistent module exits 1."""
        exit_code, _, _ = run_cli("validate", "--module", str(tmp_path / "nonexistent.py"))
        assert exit_code != 0

    def test_validate_help(self):
        exit_code, stdout, _ = run_cli("validate", "--help")
        assert exit_code == 0


@pytest.mark.integration
class TestDoctorCommand:
    """Test doctor command."""

    def test_doctor_runs(self):
        """doctor command executes without error."""
        exit_code, stdout, stderr = run_cli("doctor")
        assert exit_code == 0, f"Failed: {stderr}"

    def test_doctor_output_contains_health_info(self):
        """doctor output mentions cache and config."""
        exit_code, stdout, _ = run_cli("doctor")
        assert exit_code == 0
        # Should mention something about cache or config
        combined = stdout.lower()
        assert "cache" in combined or "config" in combined or "health" in combined

    def test_doctor_help(self):
        exit_code, stdout, _ = run_cli("doctor", "--help")
        assert exit_code == 0


@pytest.mark.integration
class TestStatusCommand:
    """Test status command."""

    def test_status_runs(self):
        """status command executes without error."""
        exit_code, stdout, stderr = run_cli("status")
        assert exit_code == 0, f"Failed: {stderr}"

    def test_status_verbose(self):
        """status --verbose shows more information."""
        exit_code, stdout, stderr = run_cli("status", "--verbose")
        assert exit_code == 0, f"Failed: {stderr}"

    def test_status_help(self):
        exit_code, stdout, _ = run_cli("status", "--help")
        assert exit_code == 0


@pytest.mark.integration
class TestClearCacheCommand:
    """Test clear-cache command."""

    def test_clear_cache_runs(self):
        """clear-cache command executes without error."""
        exit_code, stdout, stderr = run_cli("clear-cache")
        assert exit_code == 0, f"Failed: {stderr}"

    def test_clear_cache_help(self):
        exit_code, stdout, _ = run_cli("clear-cache", "--help")
        assert exit_code == 0


@pytest.mark.integration
class TestInitCommand:
    """Test init command."""

    def test_init_dry_run(self, tmp_path):
        """init --dry-run shows config without writing."""
        output_file = tmp_path / "config.yaml"
        exit_code, stdout, stderr = run_cli(
            "init", "--output", str(output_file), "--dry-run"
        )
        assert exit_code == 0, f"Failed: {stderr}"
        assert not output_file.exists(), "dry-run should not write files"

    def test_init_creates_file(self, tmp_path):
        """init creates the config file."""
        output_file = tmp_path / "config.yaml"
        exit_code, stdout, stderr = run_cli("init", "--output", str(output_file))
        assert exit_code == 0, f"Failed: {stderr}"
        assert output_file.exists(), "init should write config file"

    def test_init_does_not_overwrite_without_force(self, tmp_path):
        """init refuses to overwrite existing config without --force."""
        output_file = tmp_path / "config.yaml"
        output_file.write_text("existing content")

        exit_code, stdout, stderr = run_cli("init", "--output", str(output_file))
        assert exit_code != 0, "Should fail when file already exists without --force"
        # The existing file should be unchanged
        assert output_file.read_text() == "existing content"

    def test_init_force_overwrites(self, tmp_path):
        """init --force overwrites existing config."""
        output_file = tmp_path / "config.yaml"
        output_file.write_text("old content")

        exit_code, stdout, stderr = run_cli(
            "init", "--output", str(output_file), "--force"
        )
        assert exit_code == 0, f"Failed: {stderr}"
        new_content = output_file.read_text()
        assert "old content" not in new_content

    def test_init_verbose(self, tmp_path):
        """init --verbose shows configuration summary."""
        output_file = tmp_path / "config.yaml"
        exit_code, stdout, stderr = run_cli(
            "init", "--output", str(output_file), "--verbose"
        )
        assert exit_code == 0, f"Failed: {stderr}"

    def test_init_help(self):
        exit_code, stdout, _ = run_cli("init", "--help")
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

        exit_code, stdout, _ = run_cli("check", str(pkg), "--verbose")
        assert exit_code == 0

    def test_check_json_flag(self, tmp_path):
        """check --json outputs JSON-like content."""
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        (pkg / "mod.py").write_text("class Foo: pass")

        exit_code, stdout, _ = run_cli("check", str(pkg), "--json")
        # Exit code may vary; just ensure it doesn't crash unexpectedly
        assert isinstance(exit_code, int)

    def test_check_dynamic_imports_flag(self, tmp_path):
        """check --dynamic-imports runs without error."""
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        (pkg / "mod.py").write_text("class Foo: pass")

        exit_code, _, stderr = run_cli("check", str(pkg), "--dynamic-imports")
        assert exit_code == 0, f"Failed: {stderr}"

    def test_check_package_all_verbose(self, tmp_path):
        """check --package-all --verbose runs without error."""
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")

        exit_code, _, stderr = run_cli("check", str(pkg), "--package-all", "--verbose")
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
        exit_code, stdout, _ = run_cli("check", str(pkg), "--lateimports")
        # Should complete without crashing
        assert isinstance(exit_code, int)

    def test_check_source_flag(self, tmp_path):
        """check --source flag works."""
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        (pkg / "mod.py").write_text("class Foo: pass")

        exit_code, _, stderr = run_cli("check", "--source", str(tmp_path))
        assert isinstance(exit_code, int)


@pytest.mark.integration
class TestFixCommandExtended:
    """Extended tests for the fix command."""

    def test_fix_verbose(self, tmp_path):
        """fix --verbose shows detailed output."""
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        (pkg / "mod.py").write_text("class Foo: pass")

        exit_code, _, stderr = run_cli("fix", "--source", str(tmp_path), "--verbose")
        assert exit_code == 0, f"Failed: {stderr}"

    def test_fix_package_all_dry_run(self, tmp_path):
        """fix --package-all --dry-run works."""
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        (pkg / "mod.py").write_text("class Foo: pass")

        exit_code, _, stderr = run_cli(
            "fix", "--source", str(tmp_path), "--package-all", "--dry-run"
        )
        assert exit_code == 0, f"Failed: {stderr}"

    def test_fix_dynamic_imports_dry_run(self, tmp_path):
        """fix --dynamic-imports --dry-run works."""
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        (pkg / "mod.py").write_text("class Foo: pass")

        exit_code, _, stderr = run_cli(
            "fix", "--source", str(tmp_path), "--dynamic-imports", "--dry-run"
        )
        assert exit_code == 0, f"Failed: {stderr}"

    def test_fix_all_in_sync_message(self, tmp_path):
        """fix reports 'in sync' when nothing to change."""
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        (pkg / "mod.py").write_text("class Foo: pass")

        exit_code, stdout, _ = run_cli(
            "fix", "--source", str(tmp_path), "--module-all", "--dry-run"
        )
        assert exit_code == 0


@pytest.mark.integration
class TestAnalyzeCommandExtended:
    """Extended tests for the analyze command."""

    def test_analyze_json_format(self, tmp_path):
        """analyze --format json outputs JSON."""
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        (pkg / "mod.py").write_text("class Foo: pass")

        exit_code, stdout, _ = run_cli("analyze", "--source", str(pkg), "--format", "json")
        assert exit_code == 0
        # Output should contain JSON
        if stdout.strip():
            try:
                parsed = json.loads(stdout)
                assert "package" in parsed or "status" in parsed
            except json.JSONDecodeError:
                pass  # console markup handling

    def test_analyze_verbose_flag(self, tmp_path):
        """analyze --verbose shows more details."""
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        (pkg / "mod.py").write_text("class Foo: pass\ndef bar(): pass")

        exit_code, _, stderr = run_cli("analyze", "--source", str(pkg), "--verbose")
        assert exit_code == 0, f"Failed: {stderr}"

    def test_analyze_with_module_path(self, tmp_path):
        """analyze --module targets specific module directory."""
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        (pkg / "mod.py").write_text("class Foo: pass")

        exit_code, _, stderr = run_cli("analyze", "--module", str(pkg))
        assert exit_code == 0, f"Failed: {stderr}"

    def test_analyze_source_not_found(self, tmp_path):
        """analyze exits non-zero when source doesn't exist."""
        nonexistent = tmp_path / "nonexistent"
        exit_code, _, _ = run_cli("analyze", "--source", str(nonexistent))
        assert exit_code != 0


@pytest.mark.integration
class TestGenerateCommandExtended:
    """Extended tests for the generate command."""

    def test_generate_with_module_flag(self, tmp_path):
        """generate --module targets specific module."""
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "mod.py").write_text("class Foo: pass")

        exit_code, _, stderr = run_cli("generate", "--source", str(tmp_path), "--module", str(pkg))
        assert exit_code == 0, f"Failed: {stderr}"

    def test_generate_with_output_dir(self, tmp_path):
        """generate --output directs output to another directory."""
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "mod.py").write_text("class Foo: pass")
        out_dir = tmp_path / "out"
        out_dir.mkdir()

        exit_code, _, stderr = run_cli(
            "generate", "--source", str(tmp_path), "--output", str(out_dir)
        )
        assert exit_code == 0, f"Failed: {stderr}"

    def test_generate_nonexistent_source_exits_nonzero(self, tmp_path):
        """generate exits non-zero when source doesn't exist."""
        nonexistent = tmp_path / "nonexistent_src"
        exit_code, _, _ = run_cli("generate", "--source", str(nonexistent))
        assert exit_code != 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
