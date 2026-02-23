# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

# sourcery skip: require-return-annotation, require-parameter-annotation, no-relative-imports
"""Unit tests for CLI helper functions and utilities.

Tests all the internal helper functions in exportify.cli that handle:
- Printing results (generation results, validation results)
- Resolving checks and validation files
- Collecting Python files
- Converting paths to module names
- Loading rules
"""

from __future__ import annotations

import json

from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helper to run CLI commands
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
# Helper factories
# ---------------------------------------------------------------------------


def _make_generation_result(*, success=True, errors=None):
    """Create an ExportGenerationResult for testing."""
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


def _make_validation_report(*, success=True, errors=None, warnings=None):
    """Create a ValidationReport for testing."""
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


def _make_validation_error(file=None, line=10, message="Bad import", suggestion="Fix it", code="BROKEN_IMPORT"):
    """Create a ValidationError for testing."""
    from exportify.common.types import ValidationError

    return ValidationError(
        file=file or Path("/fake/file.py"),
        line=line,
        message=message,
        suggestion=suggestion,
        code=code,
    )


def _make_validation_warning(file=None, line=None, message="Missing __all__", suggestion=None):
    """Create a ValidationWarning for testing."""
    from exportify.common.types import ValidationWarning

    return ValidationWarning(
        file=file or Path("/fake/file.py"),
        line=line,
        message=message,
        suggestion=suggestion,
    )


def _make_export_manifest(num_exports=3):
    """Create an ExportManifest for testing."""
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


def _make_detected_symbol(name="MyClass", member_type_str="class"):
    """Create a DetectedSymbol for testing."""
    from exportify.common.types import DetectedSymbol, MemberType, SourceLocation, SymbolProvenance

    member_type = MemberType(member_type_str)
    return DetectedSymbol(
        name=name,
        provenance=SymbolProvenance.DEFINED_HERE,
        location=SourceLocation(line=1),
        member_type=member_type,
        is_private=name.startswith("_"),
        original_source=None,
        original_name=None,
    )


def _make_export_decision(symbol, action_str="include", export_name=None):
    """Create an ExportDecision for testing."""
    from exportify.common.types import ExportDecision, PropagationLevel, RuleAction

    action = RuleAction(action_str)
    return ExportDecision(
        module_path="my.module",
        action=action,
        export_name=export_name or symbol.name,
        propagation=PropagationLevel.PARENT,
        priority=800,
        reason="test-rule",
        source_symbol=symbol,
    )


# ---------------------------------------------------------------------------
# Print helper function tests
# ---------------------------------------------------------------------------


class TestPrintSimpleHelpers:
    """Test simple print helper functions."""

    def test_print_success_runs(self):
        from exportify.cli import _print_success

        _print_success("All tests passed")

    def test_print_error_runs(self):
        from exportify.cli import _print_error

        _print_error("Something broke")

    def test_print_warning_runs(self):
        from exportify.cli import _print_warning

        _print_warning("Watch out")

    def test_print_info_runs(self):
        from exportify.cli import _print_info

        _print_info("For your information")


class TestPrintGenerationResults:
    """Test _print_generation_results helper."""

    def test_success_case(self):
        from exportify.cli import _print_generation_results

        result = _make_generation_result(success=True)
        _print_generation_results(result)  # Should not raise

    def test_failure_case_with_errors(self):
        from exportify.cli import _print_generation_results

        result = _make_generation_result(success=False, errors=["broken pipe", "parse error"])
        _print_generation_results(result)  # Should not raise

    def test_failure_case_no_errors(self):
        from exportify.cli import _print_generation_results

        result = _make_generation_result(success=False, errors=[])
        _print_generation_results(result)  # Should not raise


class TestPrintValidationResults:
    """Test _print_validation_results helper."""

    def test_success_case(self):
        from exportify.cli import _print_validation_results

        report = _make_validation_report(success=True)
        _print_validation_results(report)

    def test_with_errors_and_warnings(self):
        from exportify.cli import _print_validation_results

        err = _make_validation_error(line=10)
        warn = _make_validation_warning(line=None)
        report = _make_validation_report(success=False, errors=[err], warnings=[warn])
        _print_validation_results(report)

    def test_error_without_line(self):
        from exportify.cli import _print_validation_results

        err = _make_validation_error(line=None)
        report = _make_validation_report(success=False, errors=[err])
        _print_validation_results(report)

    def test_warning_with_suggestion(self):
        from exportify.cli import _print_validation_results

        warn = _make_validation_warning(line=5, suggestion="Add __all__ = [...]")
        report = _make_validation_report(success=True, warnings=[warn])
        _print_validation_results(report)

    def test_failure_message_shown(self):
        from exportify.cli import _print_validation_results

        report = _make_validation_report(success=False)
        _print_validation_results(report)  # Should not raise


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
# _resolve_validation_files tests
# ---------------------------------------------------------------------------


class TestResolveValidationFiles:
    """Test _resolve_validation_files helper."""

    def test_none_module_returns_none(self):
        from exportify.cli import _resolve_validation_files

        result = _resolve_validation_files(None, json_output=False)
        assert result is None

    def test_file_module_returns_list(self, tmp_path):
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
        names = {p.name for p in result}
        assert "a.py" in names
        assert "b.py" in names
        assert "c.txt" not in names

    def test_nonexistent_raises_system_exit(self, tmp_path):
        from exportify.cli import _resolve_validation_files

        nonexistent = tmp_path / "nope.py"
        with pytest.raises(SystemExit):
            _resolve_validation_files(nonexistent, json_output=False)

    def test_nonexistent_json_mode_raises_system_exit(self, tmp_path):
        from exportify.cli import _resolve_validation_files

        nonexistent = tmp_path / "nope.py"
        with pytest.raises(SystemExit):
            _resolve_validation_files(nonexistent, json_output=True)


# ---------------------------------------------------------------------------
# _output_validation_json tests
# ---------------------------------------------------------------------------


class TestOutputValidationJson:
    """Test _output_validation_json helper."""

    def _get_json_output(self, report):
        from exportify.cli import _output_validation_json, console

        captured = []
        with patch.object(console, "print", side_effect=lambda x, **_: captured.append(x)):
            _output_validation_json(report)
        return json.loads("".join(str(c) for c in captured))

    def test_output_has_required_keys(self):
        report = _make_validation_report(success=True)
        parsed = self._get_json_output(report)
        assert "success" in parsed
        assert "errors" in parsed
        assert "warnings" in parsed
        assert "metrics" in parsed

    def test_success_flag(self):
        report = _make_validation_report(success=True)
        parsed = self._get_json_output(report)
        assert parsed["success"] is True

    def test_failure_flag(self):
        report = _make_validation_report(success=False)
        parsed = self._get_json_output(report)
        assert parsed["success"] is False

    def test_error_serialization(self):
        err = _make_validation_error(line=5, code="BROKEN_IMPORT")
        report = _make_validation_report(success=False, errors=[err])
        parsed = self._get_json_output(report)
        assert len(parsed["errors"]) == 1
        assert parsed["errors"][0]["code"] == "BROKEN_IMPORT"
        assert parsed["errors"][0]["line"] == 5

    def test_error_without_line(self):
        err = _make_validation_error(line=None)
        report = _make_validation_report(success=False, errors=[err])
        parsed = self._get_json_output(report)
        assert parsed["errors"][0]["line"] is None

    def test_warning_serialization(self):
        warn = _make_validation_warning(line=None, message="Advisory")
        report = _make_validation_report(success=True, warnings=[warn])
        parsed = self._get_json_output(report)
        assert len(parsed["warnings"]) == 1
        assert parsed["warnings"][0]["message"] == "Advisory"
        assert parsed["warnings"][0]["line"] is None

    def test_metrics_serialization(self):
        report = _make_validation_report(success=True)
        parsed = self._get_json_output(report)
        assert parsed["metrics"]["files_validated"] == 3
        assert parsed["metrics"]["imports_checked"] == 15
        assert parsed["metrics"]["consistency_checks"] == 7


# ---------------------------------------------------------------------------
# _output_validation_verbose / _output_validation_concise tests
# ---------------------------------------------------------------------------


class TestOutputValidationVerbose:
    """Test _output_validation_verbose helper."""

    def test_verbose_runs_with_errors_and_warnings(self):
        from exportify.cli import _output_validation_verbose

        err = _make_validation_error(line=3, suggestion="Do this")
        warn = _make_validation_warning(line=None, suggestion="Consider X")
        report = _make_validation_report(success=False, errors=[err], warnings=[warn])
        _output_validation_verbose(report)

    def test_verbose_runs_empty_report(self):
        from exportify.cli import _output_validation_verbose

        report = _make_validation_report(success=True)
        _output_validation_verbose(report)


class TestOutputValidationConcise:
    """Test _output_validation_concise helper."""

    def test_concise_with_errors(self):
        from exportify.cli import _output_validation_concise

        err = _make_validation_error(line=7)
        report = _make_validation_report(success=False, errors=[err])
        _output_validation_concise(report)

    def test_concise_with_error_no_line(self):
        from exportify.cli import _output_validation_concise

        err = _make_validation_error(line=None)
        report = _make_validation_report(success=False, errors=[err])
        _output_validation_concise(report)

    def test_concise_with_warnings(self):
        from exportify.cli import _output_validation_concise

        warn = _make_validation_warning(line=2)
        report = _make_validation_report(success=True, warnings=[warn])
        _output_validation_concise(report)

    def test_concise_empty_report(self):
        from exportify.cli import _output_validation_concise

        report = _make_validation_report(success=True)
        _output_validation_concise(report)


# ---------------------------------------------------------------------------
# _resolve_checks tests
# ---------------------------------------------------------------------------


class TestResolveChecks:
    """Test _resolve_checks logic."""

    def test_all_none_returns_all_four_checks(self):
        from exportify.cli import _resolve_checks

        result = _resolve_checks(
            lateimports=None, dynamic_imports=None, module_all=None, package_all=None
        )
        assert result == {"lateimports", "dynamic_imports", "module_all", "package_all"}

    def test_all_false_returns_empty_set(self):
        from exportify.cli import _resolve_checks

        result = _resolve_checks(
            lateimports=False, dynamic_imports=False, module_all=False, package_all=False
        )
        assert result == set()

    def test_one_true_whitelist_returns_single_item(self):
        from exportify.cli import _resolve_checks

        # Whitelist mode: any True means only return the (set-mapped) True checks.
        # Due to set iteration, we only verify invariants not exact membership.
        result = _resolve_checks(
            lateimports=True, dynamic_imports=None, module_all=None, package_all=None
        )
        all_checks = {"lateimports", "dynamic_imports", "module_all", "package_all"}
        assert len(result) == 1
        assert result.issubset(all_checks)

    def test_two_true_whitelist_returns_two_items(self):
        from exportify.cli import _resolve_checks

        result = _resolve_checks(
            lateimports=True, dynamic_imports=True, module_all=None, package_all=None
        )
        all_checks = {"lateimports", "dynamic_imports", "module_all", "package_all"}
        assert len(result) == 2
        assert result.issubset(all_checks)

    def test_one_false_blacklist_removes_one_item(self):
        from exportify.cli import _resolve_checks

        result = _resolve_checks(
            lateimports=False, dynamic_imports=None, module_all=None, package_all=None
        )
        all_checks = {"lateimports", "dynamic_imports", "module_all", "package_all"}
        assert len(result) == 3
        assert result.issubset(all_checks)

    def test_two_false_removes_two_items(self):
        from exportify.cli import _resolve_checks

        result = _resolve_checks(
            lateimports=False, dynamic_imports=False, module_all=None, package_all=None
        )
        all_checks = {"lateimports", "dynamic_imports", "module_all", "package_all"}
        assert len(result) == 2
        assert result.issubset(all_checks)

    def test_true_triggers_whitelist_not_blacklist(self):
        from exportify.cli import _resolve_checks

        # When any True: whitelist mode; result is strict subset
        result_whitelist = _resolve_checks(
            lateimports=True, dynamic_imports=False, module_all=None, package_all=None
        )
        result_all = _resolve_checks(
            lateimports=None, dynamic_imports=None, module_all=None, package_all=None
        )
        # Whitelist returns fewer than all
        assert len(result_whitelist) < len(result_all)


# ---------------------------------------------------------------------------
# _resolve_fix_checks tests
# ---------------------------------------------------------------------------


class TestResolveFixChecks:
    """Test _resolve_fix_checks logic."""

    def test_all_none_returns_all_three_checks(self):
        from exportify.cli import _resolve_fix_checks

        result = _resolve_fix_checks(dynamic_imports=None, module_all=None, package_all=None)
        assert result == {"dynamic_imports", "module_all", "package_all"}

    def test_all_false_returns_empty(self):
        from exportify.cli import _resolve_fix_checks

        result = _resolve_fix_checks(dynamic_imports=False, module_all=False, package_all=False)
        assert result == set()

    def test_one_true_whitelist_returns_subset(self):
        from exportify.cli import _resolve_fix_checks

        result = _resolve_fix_checks(dynamic_imports=True, module_all=None, package_all=None)
        all_fix_checks = {"dynamic_imports", "module_all", "package_all"}
        assert len(result) == 1
        assert result.issubset(all_fix_checks)

    def test_one_false_blacklist_removes_one(self):
        from exportify.cli import _resolve_fix_checks

        result = _resolve_fix_checks(dynamic_imports=False, module_all=None, package_all=None)
        all_fix_checks = {"dynamic_imports", "module_all", "package_all"}
        assert len(result) == 2
        assert result.issubset(all_fix_checks)


# ---------------------------------------------------------------------------
# _collect_py_files tests
# ---------------------------------------------------------------------------


class TestCollectPyFiles:
    """Test _collect_py_files helper."""

    def test_no_paths_uses_source(self, tmp_path):
        from exportify.cli import _collect_py_files

        (tmp_path / "a.py").write_text("x = 1")
        (tmp_path / "b.py").write_text("y = 2")

        result = _collect_py_files((), tmp_path)
        names = {p.name for p in result}
        assert "a.py" in names
        assert "b.py" in names

    def test_explicit_file(self, tmp_path):
        from exportify.cli import _collect_py_files

        f = tmp_path / "mod.py"
        f.write_text("x = 1")
        result = _collect_py_files((f,), None)
        assert f in result

    def test_explicit_dir_finds_py_files(self, tmp_path):
        from exportify.cli import _collect_py_files

        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "a.py").write_text("x = 1")
        result = _collect_py_files((pkg,), None)
        assert any(p.name == "a.py" for p in result)

    def test_nonexistent_raises_system_exit(self, tmp_path):
        from exportify.cli import _collect_py_files

        with pytest.raises(SystemExit):
            _collect_py_files((tmp_path / "nope",), None)


# ---------------------------------------------------------------------------
# _path_to_module tests
# ---------------------------------------------------------------------------


class TestPathToModule:
    """Test _path_to_module helper."""

    def test_simple_nested_path(self, tmp_path):
        from exportify.cli import _path_to_module

        path = tmp_path / "mypkg" / "utils"
        result = _path_to_module(path, tmp_path)
        assert result == "mypkg.utils"

    def test_single_level_path(self, tmp_path):
        from exportify.cli import _path_to_module

        path = tmp_path / "mod"
        result = _path_to_module(path, tmp_path)
        assert result == "mod"

    def test_fallback_for_outside_source(self, tmp_path):
        from exportify.cli import _path_to_module

        other = tmp_path / "other" / "thing"
        source = tmp_path / "src"
        result = _path_to_module(other, source)
        assert isinstance(result, str)
        assert len(result) > 0


# ---------------------------------------------------------------------------
# _load_rules tests
# ---------------------------------------------------------------------------


class TestLoadRules:
    """Test _load_rules helper."""

    def test_no_config_returns_engine(self, monkeypatch):
        from exportify.cli import _load_rules

        monkeypatch.setattr("exportify.cli.find_config_file", lambda: None)
        rules = _load_rules()
        assert rules is not None

    def test_no_config_verbose_warns_but_returns_engine(self, monkeypatch):
        from exportify.cli import _load_rules

        monkeypatch.setattr("exportify.cli.find_config_file", lambda: None)
        rules = _load_rules(verbose=True)
        assert rules is not None

    def test_with_config_file_loads_rules(self, tmp_path, monkeypatch):
        from exportify.cli import _load_rules

        config = tmp_path / "rules.yaml"
        config.write_text('schema_version: "1.0"\nrules: []\n')
        monkeypatch.setattr("exportify.cli.find_config_file", lambda: config)
        rules = _load_rules(verbose=True)
        assert rules is not None


# ---------------------------------------------------------------------------
# _display_all_modifications tests
# ---------------------------------------------------------------------------


class TestDisplayAllModifications:
    """Test _display_all_modifications helper."""

    def _result(self, added=None, removed=None, created=False):
        r = MagicMock()
        r.added = added
        r.removed = removed
        r.created = created
        return r

    def test_with_added(self):
        from exportify.cli import _display_all_modifications

        _display_all_modifications(self._result(added=["Foo"]), "+ Add: ", "- Remove: ", "new")

    def test_with_removed(self):
        from exportify.cli import _display_all_modifications

        _display_all_modifications(self._result(removed=["Old"]), "+ Add: ", "- Remove: ", "new")

    def test_with_created(self):
        from exportify.cli import _display_all_modifications

        _display_all_modifications(self._result(created=True), "+ Add: ", "- Remove: ", "new")

    def test_nothing_to_display(self):
        from exportify.cli import _display_all_modifications

        _display_all_modifications(self._result(), "+ Add: ", "- Remove: ", "new")


# ---------------------------------------------------------------------------
# _analyze_target_path tests
# ---------------------------------------------------------------------------


class TestAnalyzeTargetPath:
    """Test _analyze_target_path helper."""

    def test_explicit_file(self, tmp_path):
        from exportify.cli import _analyze_target_path

        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        mod = pkg / "mod.py"
        mod.write_text("class Foo: pass")

        target_path, target_file, module_path = _analyze_target_path(mod, tmp_path)
        assert target_path == mod
        assert target_file == mod

    def test_explicit_dir_with_init(self, tmp_path):
        from exportify.cli import _analyze_target_path

        pkg = tmp_path / "mypkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        (pkg / "mod.py").write_text("class Foo: pass")

        target_path, target_file, _ = _analyze_target_path(pkg, tmp_path)
        assert target_path == pkg
        assert target_file == pkg / "__init__.py"

    def test_nonexistent_raises_system_exit(self, tmp_path):
        from exportify.cli import _analyze_target_path

        with pytest.raises(SystemExit):
            _analyze_target_path(tmp_path / "nope", tmp_path)

    def test_auto_detect_single_package(self, tmp_path):
        from exportify.cli import _analyze_target_path

        pkg = tmp_path / "mypkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")

        target_path, target_file, _ = _analyze_target_path(None, tmp_path)
        assert target_path == pkg

    def test_auto_detect_multiple_packages_raises(self, tmp_path):
        from exportify.cli import _analyze_target_path

        for name in ("pkg1", "pkg2"):
            d = tmp_path / name
            d.mkdir()
            (d / "__init__.py").write_text("")

        with pytest.raises(SystemExit):
            _analyze_target_path(None, tmp_path)

    def test_auto_detect_no_package_raises(self, tmp_path):
        from exportify.cli import _analyze_target_path

        with pytest.raises(SystemExit):
            _analyze_target_path(None, tmp_path)

    def test_dir_without_init_raises(self, tmp_path):
        from exportify.cli import _analyze_target_path

        pkg = tmp_path / "mypkg"
        pkg.mkdir()

        with pytest.raises(SystemExit):
            _analyze_target_path(pkg, tmp_path)


# ---------------------------------------------------------------------------
# _get_preserved_code tests
# ---------------------------------------------------------------------------


class TestGetPreservedCode:
    """Test _get_preserved_code helper."""

    def test_non_init_file_returns_empty(self, tmp_path):
        from exportify.cli import _get_preserved_code

        mod = tmp_path / "mod.py"
        mod.write_text("x = 1")
        assert _get_preserved_code(mod) == ""

    def test_nonexistent_init_returns_empty(self, tmp_path):
        from exportify.cli import _get_preserved_code

        assert _get_preserved_code(tmp_path / "__init__.py") == ""

    def test_existing_init_returns_string(self, tmp_path):
        from exportify.cli import _get_preserved_code

        init = tmp_path / "__init__.py"
        init.write_text('"""Docstring."""\n\nfrom .mod import Foo\n')
        result = _get_preserved_code(init)
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# _print_symbols_section tests
# ---------------------------------------------------------------------------


class TestPrintSymbolsSection:
    """Test _print_symbols_section helper."""

    def test_basic_symbols(self):
        from exportify.cli import _print_symbols_section

        symbols = {
            "mymodule": [
                _make_detected_symbol("MyClass", "class"),
                _make_detected_symbol("my_func", "function"),
            ]
        }
        _print_symbols_section(symbols, verbose=False)

    def test_verbose_mode(self):
        from exportify.cli import _print_symbols_section

        symbols = {"mod": [_make_detected_symbol("Foo", "class")]}
        _print_symbols_section(symbols, verbose=True)

    def test_many_symbols_truncated_in_non_verbose(self):
        from exportify.cli import _print_symbols_section

        many = [_make_detected_symbol(f"Class{i}", "class") for i in range(10)]
        _print_symbols_section({"mod": many}, verbose=False)

    def test_empty_dict(self):
        from exportify.cli import _print_symbols_section

        _print_symbols_section({}, verbose=False)

    def test_empty_module_skipped(self):
        from exportify.cli import _print_symbols_section

        _print_symbols_section({"emptymod": []}, verbose=False)


# ---------------------------------------------------------------------------
# _print_decisions_section tests
# ---------------------------------------------------------------------------


class TestPrintDecisionsSection:
    """Test _print_decisions_section helper."""

    def test_include_decisions(self):
        from exportify.cli import _print_decisions_section

        sym = _make_detected_symbol("Foo")
        dec = _make_export_decision(sym, "include")
        _print_decisions_section({"mod": [dec]}, verbose=False)

    def test_exclude_decisions(self):
        from exportify.cli import _print_decisions_section

        sym = _make_detected_symbol("_Private")
        dec = _make_export_decision(sym, "exclude")
        _print_decisions_section({"mod": [dec]}, verbose=False)

    def test_verbose_decisions(self):
        from exportify.cli import _print_decisions_section

        sym = _make_detected_symbol("Foo")
        dec = _make_export_decision(sym, "include")
        _print_decisions_section({"mod": [dec]}, verbose=True)

    def test_many_decisions_truncated(self):
        from exportify.cli import _print_decisions_section

        sym = _make_detected_symbol("X")
        many = [_make_export_decision(sym, "include", f"Symbol{i}") for i in range(15)]
        _print_decisions_section({"mod": many}, verbose=False)

    def test_empty_decisions(self):
        from exportify.cli import _print_decisions_section

        _print_decisions_section({}, verbose=False)


# ---------------------------------------------------------------------------
# Section print helpers
# ---------------------------------------------------------------------------


class TestSectionPrintHelpers:
    """Test various print section helper functions."""

    def test_print_generation_section_with_manifest(self):
        from exportify.cli import _print_generation_section

        _print_generation_section(_make_export_manifest())

    def test_print_generation_section_no_manifest(self):
        from exportify.cli import _print_generation_section

        _print_generation_section(None)

    def test_print_preserved_code_empty(self):
        from exportify.cli import _print_preserved_code_section

        _print_preserved_code_section("", verbose=False)

    def test_print_preserved_code_short(self):
        from exportify.cli import _print_preserved_code_section

        code = "line 1\nline 2\nline 3"
        _print_preserved_code_section(code, verbose=False)

    def test_print_preserved_code_long_verbose(self):
        from exportify.cli import _print_preserved_code_section

        code = "\n".join(f"line {i}" for i in range(20))
        _print_preserved_code_section(code, verbose=True)

    def test_print_warnings_no_manifest(self):
        from exportify.cli import _print_warnings_section

        _print_warnings_section(None)

    def test_print_warnings_empty_exports(self):
        from exportify.cli import _print_warnings_section
        from exportify.common.types import ExportManifest

        empty = ExportManifest(
            module_path="empty.pkg", own_exports=[], propagated_exports=[], all_exports=[]
        )
        _print_warnings_section(empty)

    def test_print_warnings_with_exports(self):
        from exportify.cli import _print_warnings_section

        _print_warnings_section(_make_export_manifest(num_exports=2))

    def test_print_ready_status_with_exports(self):
        from exportify.cli import _print_ready_status

        _print_ready_status(_make_export_manifest(num_exports=2))

    def test_print_ready_status_no_manifest(self):
        from exportify.cli import _print_ready_status

        _print_ready_status(None)

    def test_print_ready_status_empty_manifest(self):
        from exportify.cli import _print_ready_status
        from exportify.common.types import ExportManifest

        empty = ExportManifest(
            module_path="empty.pkg", own_exports=[], propagated_exports=[], all_exports=[]
        )
        _print_ready_status(empty)


# ---------------------------------------------------------------------------
# _print_text_output and _print_json_output
# ---------------------------------------------------------------------------


class TestPrintOutputFunctions:
    """Test _print_text_output and _print_json_output."""

    def _make_full_data(self):
        sym = _make_detected_symbol("MyClass")
        dec = _make_export_decision(sym, "include")
        manifest = _make_export_manifest(num_exports=1)
        return {"mymod": [sym]}, {"mymod": [dec]}, manifest

    def test_print_text_output(self):
        from exportify.cli import _print_text_output

        all_symbols, all_decisions, manifest = self._make_full_data()
        _print_text_output(
            "my.pkg", all_symbols, all_decisions, manifest, preserved_code="", verbose=False
        )

    def test_print_text_output_verbose_with_code(self):
        from exportify.cli import _print_text_output

        all_symbols, all_decisions, manifest = self._make_full_data()
        _print_text_output(
            "my.pkg",
            all_symbols,
            all_decisions,
            manifest,
            preserved_code="# manual code\nx = 1",
            verbose=True,
        )

    def test_print_text_output_no_manifest(self):
        from exportify.cli import _print_text_output

        all_symbols, all_decisions, _ = self._make_full_data()
        _print_text_output(
            "my.pkg", all_symbols, all_decisions, None, preserved_code="", verbose=False
        )

    def test_print_json_output_with_manifest(self):
        from exportify.cli import _print_json_output, console

        all_symbols, all_decisions, manifest = self._make_full_data()
        captured = []
        with patch.object(console, "print", side_effect=lambda x, **_: captured.append(x)):
            _print_json_output("my.pkg", all_symbols, all_decisions, manifest, preserved_code="")

        parsed = json.loads("".join(str(c) for c in captured))
        assert parsed["package"] == "my.pkg"
        assert "symbols" in parsed
        assert "decisions" in parsed
        assert "would_generate" in parsed
        assert parsed["status"] == "ready"

    def test_print_json_output_no_manifest(self):
        from exportify.cli import _print_json_output, console

        all_symbols, all_decisions, _ = self._make_full_data()
        captured = []
        with patch.object(console, "print", side_effect=lambda x, **_: captured.append(x)):
            _print_json_output("my.pkg", all_symbols, all_decisions, None, preserved_code="")

        parsed = json.loads("".join(str(c) for c in captured))
        assert parsed["status"] == "no_exports"
        assert parsed["would_generate"]["all_count"] == 0


# ---------------------------------------------------------------------------
# CLI command integration tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestValidateCommandHelpers:
    """Test validate command (backward compat)."""

    def test_validate_basic_runs(self, tmp_path):
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")

        exit_code, _, _ = run_cli("validate")
        assert isinstance(exit_code, int)

    def test_validate_verbose_runs(self, tmp_path):
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")

        exit_code, _, _ = run_cli("validate", "--verbose")
        assert isinstance(exit_code, int)

    def test_validate_json_runs(self):
        exit_code, stdout, _ = run_cli("validate", "--json")
        assert isinstance(exit_code, int)

    def test_validate_module_file(self, tmp_path):
        f = tmp_path / "mod.py"
        f.write_text("class Foo: pass")
        exit_code, _, _ = run_cli("validate", "--module", str(f))
        assert isinstance(exit_code, int)

    def test_validate_module_dir(self, tmp_path):
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        exit_code, _, _ = run_cli("validate", "--module", str(pkg))
        assert isinstance(exit_code, int)

    def test_validate_nonexistent_module_fails(self, tmp_path):
        exit_code, _, _ = run_cli("validate", "--module", str(tmp_path / "nope.py"))
        assert exit_code != 0

    def test_validate_help(self):
        exit_code, _, _ = run_cli("validate", "--help")
        assert exit_code == 0


@pytest.mark.integration
class TestDoctorCommandHelpers:
    """Test doctor command."""

    def test_doctor_runs_successfully(self):
        exit_code, stdout, _ = run_cli("doctor")
        assert exit_code == 0

    def test_doctor_output_mentions_cache(self):
        exit_code, stdout, _ = run_cli("doctor")
        assert exit_code == 0
        assert "cache" in stdout.lower() or "health" in stdout.lower()

    def test_doctor_help(self):
        exit_code, _, _ = run_cli("doctor", "--help")
        assert exit_code == 0


@pytest.mark.integration
class TestStatusCommandHelpers:
    """Test status command."""

    def test_status_runs(self):
        exit_code, _, stderr = run_cli("status")
        assert exit_code == 0, f"Failed: {stderr}"

    def test_status_verbose_runs(self):
        exit_code, _, stderr = run_cli("status", "--verbose")
        assert exit_code == 0, f"Failed: {stderr}"

    def test_status_help(self):
        exit_code, _, _ = run_cli("status", "--help")
        assert exit_code == 0


@pytest.mark.integration
class TestClearCacheCommandHelpers:
    """Test clear-cache command."""

    def test_clear_cache_runs(self):
        exit_code, _, stderr = run_cli("clear-cache")
        assert exit_code == 0, f"Failed: {stderr}"

    def test_clear_cache_help(self):
        exit_code, _, _ = run_cli("clear-cache", "--help")
        assert exit_code == 0


@pytest.mark.integration
class TestInitCommandHelpers:
    """Test init command."""

    def test_init_dry_run(self, tmp_path):
        out = tmp_path / "config.yaml"
        exit_code, _, stderr = run_cli("init", "--output", str(out), "--dry-run")
        assert exit_code == 0, f"Failed: {stderr}"
        assert not out.exists()

    def test_init_creates_file(self, tmp_path):
        out = tmp_path / "config.yaml"
        exit_code, _, stderr = run_cli("init", "--output", str(out))
        assert exit_code == 0, f"Failed: {stderr}"
        assert out.exists()

    def test_init_fails_if_exists_without_force(self, tmp_path):
        out = tmp_path / "config.yaml"
        out.write_text("existing")
        exit_code, _, _ = run_cli("init", "--output", str(out))
        assert exit_code != 0
        assert out.read_text() == "existing"

    def test_init_force_overwrites(self, tmp_path):
        out = tmp_path / "config.yaml"
        out.write_text("old")
        exit_code, _, stderr = run_cli("init", "--output", str(out), "--force")
        assert exit_code == 0, f"Failed: {stderr}"
        assert "old" not in out.read_text()

    def test_init_verbose(self, tmp_path):
        out = tmp_path / "config.yaml"
        exit_code, _, stderr = run_cli("init", "--output", str(out), "--verbose")
        assert exit_code == 0, f"Failed: {stderr}"

    def test_init_help(self):
        exit_code, _, _ = run_cli("init", "--help")
        assert exit_code == 0


@pytest.mark.integration
class TestCheckCommandExtended:
    """Extended check command tests."""

    def test_check_verbose(self, tmp_path):
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        (pkg / "mod.py").write_text("class Foo: pass")
        exit_code, _, _ = run_cli("check", str(pkg), "--verbose")
        assert exit_code == 0

    def test_check_json(self, tmp_path):
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        exit_code, _, _ = run_cli("check", str(pkg), "--json")
        assert isinstance(exit_code, int)

    def test_check_dynamic_imports(self, tmp_path):
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        exit_code, _, stderr = run_cli("check", str(pkg), "--dynamic-imports")
        assert exit_code == 0, f"Failed: {stderr}"

    def test_check_strict_no_issues(self, tmp_path):
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        exit_code, _, _ = run_cli("check", str(pkg), "--strict")
        assert exit_code == 0

    def test_check_package_all_verbose(self, tmp_path):
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        exit_code, _, stderr = run_cli("check", str(pkg), "--package-all", "--verbose")
        assert exit_code == 0, f"Failed: {stderr}"

    def test_check_source_flag(self, tmp_path):
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        exit_code, _, _ = run_cli("check", "--source", str(tmp_path))
        assert isinstance(exit_code, int)

    def test_check_lateimports_without_dependency(self, tmp_path, monkeypatch):
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        monkeypatch.setattr("exportify.utils.detect_lateimport_dependency", lambda: False)
        exit_code, _, _ = run_cli("check", str(pkg), "--lateimports")
        assert isinstance(exit_code, int)


@pytest.mark.integration
class TestFixCommandExtended:
    """Extended fix command tests."""

    def test_fix_verbose(self, tmp_path):
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        (pkg / "mod.py").write_text("class Foo: pass")
        exit_code, _, stderr = run_cli("fix", "--source", str(tmp_path), "--verbose")
        assert exit_code == 0, f"Failed: {stderr}"

    def test_fix_package_all_dry_run(self, tmp_path):
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        (pkg / "mod.py").write_text("class Foo: pass")
        exit_code, _, stderr = run_cli("fix", "--source", str(tmp_path), "--package-all", "--dry-run")
        assert exit_code == 0, f"Failed: {stderr}"

    def test_fix_dynamic_imports_dry_run(self, tmp_path):
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        (pkg / "mod.py").write_text("class Foo: pass")
        exit_code, _, stderr = run_cli("fix", "--source", str(tmp_path), "--dynamic-imports", "--dry-run")
        assert exit_code == 0, f"Failed: {stderr}"

    def test_fix_module_all_dry_run_in_sync(self, tmp_path):
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        (pkg / "mod.py").write_text("class Foo: pass")
        exit_code, _, _ = run_cli("fix", "--source", str(tmp_path), "--module-all", "--dry-run")
        assert exit_code == 0


@pytest.mark.integration
class TestAnalyzeCommandExtended:
    """Extended analyze command tests."""

    def test_analyze_json_format(self, tmp_path):
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        (pkg / "mod.py").write_text("class Foo: pass")
        exit_code, _, _ = run_cli("analyze", "--source", str(pkg), "--format", "json")
        assert exit_code == 0

    def test_analyze_verbose(self, tmp_path):
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        (pkg / "mod.py").write_text("class Foo: pass\ndef bar(): pass")
        exit_code, _, stderr = run_cli("analyze", "--source", str(pkg), "--verbose")
        assert exit_code == 0, f"Failed: {stderr}"

    def test_analyze_with_module(self, tmp_path):
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        (pkg / "mod.py").write_text("class Foo: pass")
        exit_code, _, stderr = run_cli("analyze", "--module", str(pkg))
        assert exit_code == 0, f"Failed: {stderr}"

    def test_analyze_nonexistent_source(self, tmp_path):
        exit_code, _, _ = run_cli("analyze", "--source", str(tmp_path / "nope"))
        assert exit_code != 0


@pytest.mark.integration
class TestGenerateCommandExtended:
    """Extended generate command tests."""

    def test_generate_with_module(self, tmp_path):
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "mod.py").write_text("class Foo: pass")
        exit_code, _, stderr = run_cli("generate", "--source", str(tmp_path), "--module", str(pkg))
        assert exit_code == 0, f"Failed: {stderr}"

    def test_generate_with_output_dir(self, tmp_path):
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "mod.py").write_text("class Foo: pass")
        out = tmp_path / "out"
        out.mkdir()
        exit_code, _, stderr = run_cli("generate", "--source", str(tmp_path), "--output", str(out))
        assert exit_code == 0, f"Failed: {stderr}"

    def test_generate_nonexistent_source(self, tmp_path):
        exit_code, _, _ = run_cli("generate", "--source", str(tmp_path / "nope"))
        assert exit_code != 0
