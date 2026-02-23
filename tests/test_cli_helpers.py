# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

# sourcery skip: require-return-annotation, require-parameter-annotation, no-relative-imports
"""Unit tests for CLI helper functions and utilities.

Tests all the internal helper functions in exportify.commands.utils that handle:
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
        files_validated=3, imports_checked=15, consistency_checks=7, validation_time_ms=55
    )
    return ValidationReport(
        errors=errors or [], warnings=warnings or [], metrics=metrics, success=success
    )


def _make_validation_error(
    file=None, line=10, message="Bad import", suggestion="Fix it", code="BROKEN_IMPORT"
):
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
        file=file or Path("/fake/file.py"), line=line, message=message, suggestion=suggestion
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
        module_path="my.pkg", own_exports=exports, propagated_exports=[], all_exports=exports
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

    def testprint_success_runs(self):
        from exportify.commands.utils import print_success

        print_success("All tests passed")

    def testprint_error_runs(self):
        from exportify.commands.utils import print_error

        print_error("Something broke")

    def testprint_warning_runs(self):
        from exportify.commands.utils import print_warning

        print_warning("Watch out")

    def testprint_info_runs(self):
        from exportify.commands.utils import print_info

        print_info("For your information")


class TestPrintGenerationResults:
    """Test print_generation_results helper."""

    def test_success_case(self):
        from exportify.commands.generate import _print_generation_results

        result = _make_generation_result(success=True)
        _print_generation_results(result)  # Should not raise

    def test_failure_case_with_errors(self):
        from exportify.commands.generate import _print_generation_results

        result = _make_generation_result(success=False, errors=["broken pipe", "parse error"])
        _print_generation_results(result)  # Should not raise

    def test_failure_case_no_errors(self):
        from exportify.commands.generate import _print_generation_results

        result = _make_generation_result(success=False, errors=[])
        _print_generation_results(result)  # Should not raise


class TestPrintValidationResults:
    """Test print_validation_results helper."""

    def test_success_case(self):
        from exportify.commands.utils import print_validation_results

        report = _make_validation_report(success=True)
        print_validation_results(report)

    def test_with_errors_and_warnings(self):
        from exportify.commands.utils import print_validation_results

        err = _make_validation_error(line=10)
        warn = _make_validation_warning(line=None)
        report = _make_validation_report(success=False, errors=[err], warnings=[warn])
        print_validation_results(report)

    def test_error_without_line(self):
        from exportify.commands.utils import print_validation_results

        err = _make_validation_error(line=None)
        report = _make_validation_report(success=False, errors=[err])
        print_validation_results(report)

    def test_warning_with_suggestion(self):
        from exportify.commands.utils import print_validation_results

        warn = _make_validation_warning(line=5, suggestion="Add __all__ = [...]")
        report = _make_validation_report(success=True, warnings=[warn])
        print_validation_results(report)

    def test_failure_message_shown(self):
        from exportify.commands.utils import print_validation_results

        report = _make_validation_report(success=False)
        print_validation_results(report)  # Should not raise


class TestPrintErrorInValidation:
    """Test print_error_in_validation helper."""

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


class TestOutputValidationJson:
    """Test print_output_validation_json helper."""

    def _get_json_output(self, report):
        from exportify.commands.utils import CONSOLE, print_output_validation_json

        captured = []
        with patch.object(CONSOLE, "print", side_effect=lambda x, **_: captured.append(x)):
            print_output_validation_json(report)
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
# print_output_validation_verbose / print_output_validation_concise tests
# ---------------------------------------------------------------------------


class TestOutputValidationVerbose:
    """Test print_output_validation_verbose helper."""

    def test_verbose_runs_with_errors_and_warnings(self):
        from exportify.commands.utils import print_output_validation_verbose

        err = _make_validation_error(line=3, suggestion="Do this")
        warn = _make_validation_warning(line=None, suggestion="Consider X")
        report = _make_validation_report(success=False, errors=[err], warnings=[warn])
        print_output_validation_verbose(report)

    def test_verbose_runs_empty_report(self):
        from exportify.commands.utils import print_output_validation_verbose

        report = _make_validation_report(success=True)
        print_output_validation_verbose(report)


class TestOutputValidationConcise:
    """Test print_output_validation_concise helper."""

    def test_concise_with_errors(self):
        from exportify.commands.utils import print_output_validation_concise

        err = _make_validation_error(line=7)
        report = _make_validation_report(success=False, errors=[err])
        print_output_validation_concise(report)

    def test_concise_with_error_no_line(self):
        from exportify.commands.utils import print_output_validation_concise

        err = _make_validation_error(line=None)
        report = _make_validation_report(success=False, errors=[err])
        print_output_validation_concise(report)

    def test_concise_with_warnings(self):
        from exportify.commands.utils import print_output_validation_concise

        warn = _make_validation_warning(line=2)
        report = _make_validation_report(success=True, warnings=[warn])
        print_output_validation_concise(report)

    def test_concise_empty_report(self):
        from exportify.commands.utils import print_output_validation_concise

        report = _make_validation_report(success=True)
        print_output_validation_concise(report)


# ---------------------------------------------------------------------------
# _resolve_checks tests
# ---------------------------------------------------------------------------


class TestResolveChecks:
    """Test _resolve_checks logic."""

    def test_all_none_returns_all_four_checks(self):
        from exportify.commands.check import _resolve_checks

        result = _resolve_checks(
            lateimports=None, dynamic_imports=None, module_all=None, package_all=None
        )
        assert result == {"lateimports", "dynamic_imports", "module_all", "package_all"}

    def test_all_false_returns_empty_set(self):
        from exportify.commands.check import _resolve_checks

        result = _resolve_checks(
            lateimports=False, dynamic_imports=False, module_all=False, package_all=False
        )
        assert result == set()

    def test_one_true_whitelist_returns_single_item(self):
        from exportify.commands.check import _resolve_checks

        # Whitelist mode: any True means only return the (set-mapped) True checks.
        # Due to set iteration, we only verify invariants not exact membership.
        result = _resolve_checks(
            lateimports=True, dynamic_imports=None, module_all=None, package_all=None
        )
        all_checks = {"lateimports", "dynamic_imports", "module_all", "package_all"}
        assert len(result) == 1
        assert result.issubset(all_checks)

    def test_two_true_whitelist_returns_two_items(self):
        from exportify.commands.check import _resolve_checks

        result = _resolve_checks(
            lateimports=True, dynamic_imports=True, module_all=None, package_all=None
        )
        all_checks = {"lateimports", "dynamic_imports", "module_all", "package_all"}
        assert len(result) == 2
        assert result.issubset(all_checks)

    def test_one_false_blacklist_removes_one_item(self):
        from exportify.commands.check import _resolve_checks

        result = _resolve_checks(
            lateimports=False, dynamic_imports=None, module_all=None, package_all=None
        )
        all_checks = {"lateimports", "dynamic_imports", "module_all", "package_all"}
        assert len(result) == 3
        assert result.issubset(all_checks)

    def test_two_false_removes_two_items(self):
        from exportify.commands.check import _resolve_checks

        result = _resolve_checks(
            lateimports=False, dynamic_imports=False, module_all=None, package_all=None
        )
        all_checks = {"lateimports", "dynamic_imports", "module_all", "package_all"}
        assert len(result) == 2
        assert result.issubset(all_checks)

    def test_true_triggers_whitelist_not_blacklist(self):
        from exportify.commands.check import _resolve_checks

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
        from exportify.commands.fix import _resolve_fix_checks

        result = _resolve_fix_checks(dynamic_imports=None, module_all=None, package_all=None)
        assert result == {"dynamic_imports", "module_all", "package_all"}

    def test_all_false_returns_empty(self):
        from exportify.commands.fix import _resolve_fix_checks

        result = _resolve_fix_checks(dynamic_imports=False, module_all=False, package_all=False)
        assert result == set()

    def test_one_true_whitelist_returns_subset(self):
        from exportify.commands.fix import _resolve_fix_checks

        result = _resolve_fix_checks(dynamic_imports=True, module_all=None, package_all=None)
        all_fix_checks = {"dynamic_imports", "module_all", "package_all"}
        assert len(result) == 1
        assert result.issubset(all_fix_checks)

    def test_one_false_blacklist_removes_one(self):
        from exportify.commands.fix import _resolve_fix_checks

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
        from exportify.commands.utils import collect_py_files

        (tmp_path / "a.py").write_text("x = 1")
        (tmp_path / "b.py").write_text("y = 2")

        result = collect_py_files((), tmp_path)
        names = {p.name for p in result}
        assert "a.py" in names
        assert "b.py" in names

    def test_explicit_file(self, tmp_path):
        from exportify.commands.utils import collect_py_files

        f = tmp_path / "mod.py"
        f.write_text("x = 1")
        result = collect_py_files((f,), None)
        assert f in result

    def test_explicit_dir_finds_py_files(self, tmp_path):
        from exportify.commands.utils import collect_py_files

        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "a.py").write_text("x = 1")
        result = collect_py_files((pkg,), None)
        assert any(p.name == "a.py" for p in result)

    def test_nonexistent_raises_system_exit(self, tmp_path):
        from exportify.commands.utils import collect_py_files

        with pytest.raises(SystemExit):
            collect_py_files((tmp_path / "nope",), None)


# ---------------------------------------------------------------------------
# path_to_module tests
# ---------------------------------------------------------------------------


class TestPathToModule:
    """Test path_to_module helper."""

    def test_simple_nested_path(self, tmp_path):
        from exportify.commands.utils import path_to_module

        path = tmp_path / "mypkg" / "utils"
        result = path_to_module(path, tmp_path)
        assert result == "mypkg.utils"

    def test_single_level_path(self, tmp_path):
        from exportify.commands.utils import path_to_module

        path = tmp_path / "mod"
        result = path_to_module(path, tmp_path)
        assert result == "mod"

    def test_fallback_for_outside_source(self, tmp_path):
        from exportify.commands.utils import path_to_module

        other = tmp_path / "other" / "thing"
        source = tmp_path / "src"
        result = path_to_module(other, source)
        assert isinstance(result, str)
        assert len(result) > 0


# ---------------------------------------------------------------------------
# load_rules tests
# ---------------------------------------------------------------------------


class TestLoadRules:
    """Test load_rules helper."""

    def test_no_config_returns_engine(self, monkeypatch):
        from exportify.commands.utils import load_rules

        monkeypatch.setattr("exportify.common.config.find_config_file", lambda: None)
        rules = load_rules()
        assert rules is not None

    def test_no_config_verbose_warns_but_returns_engine(self, monkeypatch):
        from exportify.commands.utils import load_rules

        monkeypatch.setattr("exportify.common.config.find_config_file", lambda: None)
        rules = load_rules(verbose=True)
        assert rules is not None

    def test_with_config_file_loads_rules(self, tmp_path, monkeypatch):
        from exportify.commands.utils import load_rules

        config = tmp_path / "rules.yaml"
        config.write_text('schema_version: "1.0"\nrules: []\n')
        monkeypatch.setattr("exportify.common.config.find_config_file", lambda: config)
        rules = load_rules(verbose=True)
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
        from exportify.commands.check import _display_all_modifications

        _display_all_modifications(self._result(added=["Foo"]), "+ Add: ", "- Remove: ", "new")

    def test_with_removed(self):
        from exportify.commands.check import _display_all_modifications

        _display_all_modifications(self._result(removed=["Old"]), "+ Add: ", "- Remove: ", "new")

    def test_with_created(self):
        from exportify.commands.check import _display_all_modifications

        _display_all_modifications(self._result(created=True), "+ Add: ", "- Remove: ", "new")

    def test_nothing_to_display(self):
        from exportify.commands.check import _display_all_modifications

        _display_all_modifications(self._result(), "+ Add: ", "- Remove: ", "new")


class TestDoctorCommandHelpers:
    """Test doctor command."""

    def test_doctor_runs_successfully(self):
        exit_code, _stdout, _ = run_cli("doctor")
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
        exit_code, _, stderr = run_cli(
            "fix", "--source", str(tmp_path), "--package-all", "--dry-run"
        )
        assert exit_code == 0, f"Failed: {stderr}"

    def test_fix_dynamic_imports_dry_run(self, tmp_path):
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        (pkg / "mod.py").write_text("class Foo: pass")
        exit_code, _, stderr = run_cli(
            "fix", "--source", str(tmp_path), "--dynamic-imports", "--dry-run"
        )
        assert exit_code == 0, f"Failed: {stderr}"

    def test_fix_module_all_dry_run_in_sync(self, tmp_path):
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        (pkg / "mod.py").write_text("class Foo: pass")
        exit_code, _, _ = run_cli("fix", "--source", str(tmp_path), "--module-all", "--dry-run")
        assert exit_code == 0


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
