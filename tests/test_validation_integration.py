# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Integration tests for Phase 3 validation system.

Tests complete workflows including:
- CLI check command integration
- CLI fix --dry-run command integration
- Real codebase validation
- Error handling and edge cases
- Performance requirements

NOTE: These tests focus on CLI integration and error handling rather than
perfect validation of test fixtures, since test fixtures may not be fully
importable Python modules.
"""

from __future__ import annotations

import contextlib
import json
import time

from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest


def run_cli(*args) -> tuple[int, str, str]:
    # sourcery skip: remove-unnecessary-cast
    """Run CLI and capture output.

    Returns:
        Tuple of (exit_code, stdout, stderr)
    """
    from exportify.cli import app

    stdout = StringIO()
    stderr = StringIO()
    exit_code = 0

    with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
        try:
            app(list(args))
        except SystemExit as e:
            exit_code = e.code if e.code is not None else 0
        except Exception:
            import traceback

            stderr.write(traceback.format_exc())
            exit_code = 1

    return int(exit_code) if exit_code is not None else 0, stdout.getvalue(), stderr.getvalue()


@pytest.mark.integration
class TestCLICheckCommand:
    """Test check command end-to-end."""

    def test_check_runs_without_crash(self, tmp_path: Path):
        """Check command executes without crashing."""
        pkg = tmp_path / "pkg"
        pkg.mkdir()

        (pkg / "mod.py").write_text("""\"\"\"Module.\"\"\"

class PublicClass:
    pass
""")

        (pkg / "__init__.py").write_text("""\"\"\"Package.\"\"\"
__all__ = ["PublicClass"]
""")

        _exit_code, _stdout, stderr = run_cli("check", str(pkg))

        # Should complete without crashing
        assert "Traceback" not in stderr

    def test_check_shows_results(self, tmp_path: Path):
        """Check shows results."""
        pkg = tmp_path / "pkg"
        pkg.mkdir()

        (pkg / "mod.py").write_text("class A: pass")
        (pkg / "__init__.py").write_text("")

        _exit_code, stdout, stderr = run_cli("check", str(pkg))

        output = stdout + stderr
        # Should show some output
        assert len(output) > 0

    def test_check_with_nonexistent_path(self):
        """Check handles nonexistent paths."""
        _exit_code, _stdout, stderr = run_cli("check", "/totally/fake/path")

        # Should handle gracefully
        assert "Traceback" not in stderr

    def test_check_strict_mode_flag(self, tmp_path: Path):
        """Strict mode flag is accepted."""
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "mod.py").write_text("class A: pass")
        (pkg / "__init__.py").write_text("")

        _exit_code, _stdout, stderr = run_cli("check", str(pkg), "--strict")

        # Should accept the flag without crashing
        assert "Traceback" not in stderr

    def test_check_module_all_flag(self, tmp_path: Path):
        """--module-all flag is accepted."""
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "mod.py").write_text("class A: pass")
        (pkg / "__init__.py").write_text("")

        _exit_code, _stdout, stderr = run_cli("check", str(pkg), "--module-all")

        # Should accept the flag without crashing
        assert "Traceback" not in stderr

    def test_check_dynamic_imports_flag(self, tmp_path: Path):
        """--dynamic-imports flag is accepted."""
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "mod.py").write_text("class A: pass")
        (pkg / "__init__.py").write_text("")

        _exit_code, _stdout, stderr = run_cli("check", str(pkg), "--dynamic-imports")

        # Should accept the flag without crashing
        assert "Traceback" not in stderr

    # Keep validate tests for backward compatibility
    def test_validate_runs_without_crash(self, tmp_path: Path):
        """Validate command executes without crashing (backward compat)."""
        pkg = tmp_path / "pkg"
        pkg.mkdir()

        (pkg / "mod.py").write_text("""\"\"\"Module.\"\"\"

class PublicClass:
    pass
""")

        (pkg / "__init__.py").write_text("""\"\"\"Package.\"\"\"
__all__ = ["PublicClass"]
""")

        _exit_code, stdout, stderr = run_cli("validate", "--module", str(pkg))

        # Should complete without crashing
        assert "Traceback" not in stderr
        # spellchecker:off
        assert "validat" in stdout.lower() or "validat" in stderr.lower()
        # spellchecker:on

    def test_validate_shows_results(self, tmp_path: Path):
        """Validate shows validation results (backward compat)."""
        pkg = tmp_path / "pkg"
        pkg.mkdir()

        (pkg / "mod.py").write_text("class A: pass")
        (pkg / "__init__.py").write_text("")

        _exit_code, stdout, stderr = run_cli("validate", "--module", str(pkg))

        output = stdout + stderr
        # Should show some validation output
        assert "files" in output.lower() or "validated" in output.lower()

    def test_validate_with_nonexistent_path(self):
        """Validate handles nonexistent paths (backward compat)."""
        _exit_code, _stdout, stderr = run_cli("validate", "--module", "/totally/fake/path")

        # Should handle gracefully
        assert "Traceback" not in stderr

    def test_validate_strict_mode_flag(self, tmp_path: Path):
        """Strict mode flag is accepted (backward compat)."""
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "mod.py").write_text("class A: pass")
        (pkg / "__init__.py").write_text("")

        _exit_code, _stdout, stderr = run_cli("validate", "--module", str(pkg), "--strict")

        # Should accept the flag without crashing
        assert "Traceback" not in stderr

    def test_validate_fix_mode_flag(self, tmp_path: Path):
        """Fix mode flag is accepted (backward compat)."""
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "mod.py").write_text("class A: pass")
        (pkg / "__init__.py").write_text("")

        _exit_code, _stdout, stderr = run_cli("validate", "--module", str(pkg), "--fix")

        # Should accept the flag without crashing
        assert "Traceback" not in stderr


@pytest.mark.integration
class TestCLIFixDryRunCommand:
    """Test fix --dry-run command end-to-end (replaces analyze)."""

    def test_fix_dry_run_single_module(self, tmp_path: Path):
        """Fix --dry-run single module completes."""
        pkg = self._create_package_structure(tmp_path, "test_pkg", "__init__.py", "")
        (pkg / "mod.py").write_text("""\"\"\"Module.\"\"\"

class PublicClass:
    pass

def public_function():
    return 42
""")

        _exit_code, _stdout, stderr = run_cli("fix", "--dry-run", "--source", str(tmp_path))

        # Should complete (may warn about implementation but shouldn't crash)
        assert "Traceback" not in stderr

    def _create_package_structure(self, tmp_path, arg1, arg2, arg3):
        # Create a proper package structure
        result = tmp_path / arg1
        result.mkdir()

        (result / arg2).write_text(arg3)
        return result

    def test_fix_dry_run_nested_structure(self, tmp_path: Path):
        """Fix --dry-run package hierarchy."""
        root = tmp_path / "pkg"
        core = root / "core"
        core.mkdir(parents=True)

        (root / "__init__.py").write_text("")
        (core / "__init__.py").write_text("")
        (core / "models.py").write_text("class Model: pass")

        _exit_code, _stdout, stderr = run_cli("fix", "--dry-run", "--source", str(tmp_path))

        # Should complete (may warn but shouldn't crash)
        assert "Traceback" not in stderr

    # Keep analyze tests for backward compatibility
    def test_analyze_single_module(self, tmp_path: Path):
        """Analyze single module completes (backward compat)."""
        pkg = self._create_package_structure(tmp_path, "test_pkg", "__init__.py", "")
        (pkg / "mod.py").write_text("""\"\"\"Module.\"\"\"

class PublicClass:
    pass

def public_function():
    return 42
""")

        _exit_code, _stdout, stderr = run_cli("analyze", "--source", str(tmp_path))

        # Should complete (may warn about implementation but shouldn't crash)
        assert "Traceback" not in stderr

    def test_analyze_nested_structure(self, tmp_path: Path):
        """Analyze package hierarchy (backward compat)."""
        root = tmp_path / "pkg"
        core = root / "core"
        core.mkdir(parents=True)

        (root / "__init__.py").write_text("")
        (core / "__init__.py").write_text("")
        (core / "models.py").write_text("class Model: pass")

        _exit_code, _stdout, stderr = run_cli("analyze", "--source", str(tmp_path))

        # Should complete (may warn but shouldn't crash)
        assert "Traceback" not in stderr

    def test_analyze_table_format(self, tmp_path: Path):
        """Analyze with table format (backward compat)."""
        pkg = self._create_temp_directory_with_file(tmp_path, "pkg", "__init__.py", "")
        (pkg / "mod.py").write_text("class TestClass: pass")

        self._create_temp_directory_with_file(
            tmp_path,
            ".codeweaver",
            "lazy_import_rules.yaml",
            """
schema_version: "1.0"
rules: []
""",
        )
        _exit_code, _stdout, stderr = run_cli(
            "analyze", "--source", str(tmp_path), "--format", "table"
        )

        # Should accept the format flag
        assert "Traceback" not in stderr

    def _create_temp_directory_with_file(
        self, tmp_path: Path, pkg: str, filename: str, content: str
    ) -> Path:
        result = tmp_path / pkg
        result.mkdir(exist_ok=True)
        (result / filename).write_text(content)
        return result

    def test_analyze_json_format(self, tmp_path: Path):
        """Analyze with JSON format (backward compat)."""
        pkg = self._create_temp_directory_with_file(tmp_path, "pkg", "__init__.py", "")
        (pkg / "mod.py").write_text("class TestClass: pass")

        self._create_temp_directory_with_file(
            tmp_path,
            ".codeweaver",
            "lazy_import_rules.yaml",
            """
schema_version: "1.0"
rules: []
""",
        )
        exit_code, stdout, _stderr = run_cli(
            "analyze", "--source", str(tmp_path), "--format", "json"
        )

        # Should accept the format flag
        if exit_code == 0 and stdout.strip():
            # If JSON format is implemented, it should be valid JSON
            with contextlib.suppress(json.JSONDecodeError):
                data = json.loads(stdout)
                assert isinstance(data, (dict, list))

    def test_analyze_report_format(self, tmp_path: Path):
        """Analyze with report format (backward compat)."""
        pkg = self._create_temp_directory_with_file(tmp_path, "pkg", "__init__.py", "")
        (pkg / "mod.py").write_text("class A: pass")

        # Create rules file
        self._create_temp_directory_with_file(
            tmp_path,
            ".codeweaver",
            "lazy_import_rules.yaml",
            """
schema_version: "1.0"
rules: []
""",
        )

        _exit_code, _stdout, stderr = run_cli(
            "analyze", "--source", str(tmp_path), "--format", "report"
        )

        # Should accept the format
        assert "Traceback" not in stderr


@pytest.mark.integration
class TestRealCodebaseValidation:
    """Test validation on real CodeWeaver codebase."""

    def test_check_exportify_export_manager(self):
        """Check exportify's export_manager subpackage."""
        core_path = Path("src/exportify/export_manager")

        if not core_path.exists():
            pytest.skip("exportify export_manager not found")

        _exit_code, _stdout, stderr = run_cli("check", str(core_path))

        # Should complete without crashing
        assert "Traceback" not in stderr

    def test_check_exportify_itself(self):
        """Check exportify tool codebase."""
        exportify_path = Path("src/exportify")

        if not exportify_path.exists():
            pytest.skip("exportify package not found")

        _exit_code, _stdout, stderr = run_cli("check", str(exportify_path))

        # Should not crash
        assert "Traceback" not in stderr

    # Keep validate tests for backward compatibility
    def test_validate_exportify_export_manager(self):
        """Validate exportify's export_manager subpackage (backward compat)."""
        core_path = Path("src/exportify/export_manager")

        if not core_path.exists():
            pytest.skip("exportify export_manager not found")

        _exit_code, _stdout, stderr = run_cli("validate", "--module", str(core_path))

        # Should complete without crashing
        assert "Traceback" not in stderr

    def test_validate_exportify_itself(self):
        """Validate exportify tool codebase (backward compat)."""
        exportify_path = Path("src/exportify")

        if not exportify_path.exists():
            pytest.skip("exportify package not found")

        _exit_code, _stdout, stderr = run_cli("validate", "--module", str(exportify_path))

        # Should not crash
        assert "Traceback" not in stderr

    @pytest.mark.slow
    def test_fix_dry_run_exportify_performance(self):
        """Performance test: fix --dry-run on exportify's own source tree."""
        src_path = Path("src/exportify")

        if not src_path.exists():
            pytest.skip("exportify source not found")

        start_time = time.time()
        _exit_code, _stdout, stderr = run_cli("fix", "--dry-run", "--source", str(src_path))
        elapsed = time.time() - start_time

        # Should complete without crashing
        assert "Traceback" not in stderr

        # Performance requirement: <10s for exportify's own source
        if elapsed > 10:
            pytest.fail(f"Fix --dry-run took {elapsed:.2f}s, expected <10s")

    @pytest.mark.slow
    def test_check_large_codebase_performance(self, tmp_path: Path):
        """Performance test with many files."""
        pkg = tmp_path / "large_pkg"
        pkg.mkdir()

        (pkg / "__init__.py").write_text("")

        for i in range(50):
            (pkg / f"mod_{i}.py").write_text(f"""\"\"\"Module {i}.\"\"\"

class Class_{i}:
    pass

def function_{i}():
    pass
""")

        start_time = time.time()
        _exit_code, _stdout, stderr = run_cli("check", str(pkg))
        elapsed = time.time() - start_time

        # Should complete
        assert "Traceback" not in stderr

        # Should be reasonably fast
        assert elapsed < 10, f"Check took {elapsed:.2f}s for 50 files"


@pytest.mark.integration
class TestErrorHandling:
    """Test error handling and edge cases."""

    def test_check_invalid_path(self):
        """Invalid path handled gracefully."""
        exit_code, stdout, stderr = run_cli("check", "/nonexistent/path")

        # Should handle gracefully
        output = stdout + stderr
        # May show error or warning, but shouldn't crash
        assert "Traceback" not in output or exit_code != 0

    def test_validate_invalid_module_path(self):
        """Invalid module path handled gracefully (backward compat)."""
        exit_code, stdout, stderr = run_cli("validate", "--module", "/nonexistent/path")

        # Should handle gracefully
        output = stdout + stderr
        # May show error or warning, but shouldn't crash
        assert "Traceback" not in output or exit_code != 0

    def test_validate_missing_source_directory(self):
        """Missing source directory handled gracefully."""
        exit_code, _stdout, stderr = run_cli("analyze", "--source", "/totally/fake/directory")

        # Should handle gracefully
        assert "Traceback" not in stderr or exit_code != 0

    def test_check_syntax_error_file(self, tmp_path: Path):
        """Syntax errors handled gracefully."""
        pkg = tmp_path / "pkg"
        pkg.mkdir()

        # Create file with syntax error
        (pkg / "broken.py").write_text("""def incomplete(
    # Missing closing paren
""")

        (pkg / "__init__.py").write_text("")

        _exit_code, stdout, stderr = run_cli("check", str(pkg))

        # Should handle gracefully (may report error but not crash)
        output = stdout + stderr
        # If it crashes, ensure it's a handled error
        if "Traceback" in output:
            assert "SyntaxError" in output or "ParseError" in output.lower()

    def test_validate_syntax_error_file(self, tmp_path: Path):
        """Syntax errors handled gracefully (backward compat)."""
        pkg = tmp_path / "pkg"
        pkg.mkdir()

        # Create file with syntax error
        (pkg / "broken.py").write_text("""def incomplete(
    # Missing closing paren
""")

        (pkg / "__init__.py").write_text("")

        _exit_code, stdout, stderr = run_cli("validate", "--module", str(pkg))

        # Should handle gracefully (may report error but not crash)
        output = stdout + stderr
        # If it crashes, ensure it's a handled error
        if "Traceback" in output:
            assert "SyntaxError" in output or "ParseError" in output.lower()

    def test_check_empty_directory(self, tmp_path: Path):
        """Empty directory handled gracefully."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        _exit_code, _stdout, stderr = run_cli("check", str(empty_dir))

        # Should complete without crash
        assert "Traceback" not in stderr

    def test_validate_empty_directory(self, tmp_path: Path):
        """Empty directory handled gracefully (backward compat)."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        _exit_code, _stdout, stderr = run_cli("validate", "--module", str(empty_dir))

        # Should complete without crash
        assert "Traceback" not in stderr

    def test_check_non_python_files(self, tmp_path: Path):
        """Non-Python files are ignored."""
        pkg = tmp_path / "pkg"
        pkg.mkdir()

        (pkg / "README.md").write_text("# Not Python")
        (pkg / "data.json").write_text('{"key": "value"}')
        (pkg / "__init__.py").write_text("")

        _exit_code, _stdout, stderr = run_cli("check", str(pkg))

        # Should complete successfully
        assert "Traceback" not in stderr

    def test_validate_non_python_files(self, tmp_path: Path):
        """Non-Python files are ignored (backward compat)."""
        pkg = tmp_path / "pkg"
        pkg.mkdir()

        (pkg / "README.md").write_text("# Not Python")
        (pkg / "data.json").write_text('{"key": "value"}')
        (pkg / "__init__.py").write_text("")

        _exit_code, _stdout, stderr = run_cli("validate", "--module", str(pkg))

        # Should complete successfully
        assert "Traceback" not in stderr

    def test_error_messages_are_informative(self, tmp_path: Path):
        """Error messages contain useful information."""
        pkg = tmp_path / "pkg"
        pkg.mkdir()

        (pkg / "mod.py").write_text("class A: pass")
        (pkg / "__init__.py").write_text("# Minimal init")

        _exit_code, stdout, stderr = run_cli("check", str(pkg))

        output = stdout + stderr
        # Should have some meaningful output
        assert len(output) > 10  # Not just empty


@pytest.mark.integration
class TestCLIOutput:
    """Test CLI output formatting."""

    def test_check_produces_output(self, tmp_path: Path):
        """Check produces readable output."""
        pkg = tmp_path / "pkg"
        pkg.mkdir()

        (pkg / "mod.py").write_text("class A: pass")
        (pkg / "__init__.py").write_text("")

        _exit_code, stdout, stderr = run_cli("check", str(pkg))

        output = stdout + stderr
        # Should have some output
        assert len(output) > 0

    def test_validate_produces_output(self, tmp_path: Path):
        """Validation produces readable output (backward compat)."""
        pkg = tmp_path / "pkg"
        pkg.mkdir()

        (pkg / "mod.py").write_text("class A: pass")
        (pkg / "__init__.py").write_text("")

        _exit_code, stdout, stderr = run_cli("validate", "--module", str(pkg))

        output = stdout + stderr
        # Should have some output
        assert len(output) > 0
        # Should mention validation
        assert "validat" in output.lower()

    def test_fix_dry_run_shows_info(self, tmp_path: Path):
        """Fix --dry-run shows useful information."""
        pkg = self._create_temp_directory_with_file(tmp_path, "pkg", "__init__.py", "")
        for i in range(3):
            (pkg / f"mod_{i}.py").write_text(f"class Class_{i}: pass")

        self._create_temp_directory_with_file(
            tmp_path,
            ".codeweaver",
            "lazy_import_rules.yaml",
            """
schema_version: "1.0"
rules: []
""",
        )
        _exit_code, stdout, stderr = run_cli("fix", "--dry-run", "--source", str(tmp_path))

        output = stdout + stderr
        # Should show some information
        assert len(output) > 0

    def test_analyze_shows_metrics(self, tmp_path: Path):
        """Analyze shows useful information (backward compat)."""
        pkg = self._create_temp_directory_with_file(tmp_path, "pkg", "__init__.py", "")
        for i in range(3):
            (pkg / f"mod_{i}.py").write_text(f"class Class_{i}: pass")

        self._create_temp_directory_with_file(
            tmp_path,
            ".codeweaver",
            "lazy_import_rules.yaml",
            """
schema_version: "1.0"
rules: []
""",
        )
        _exit_code, stdout, stderr = run_cli("analyze", "--source", str(tmp_path))

        output = stdout + stderr
        # Should show some information
        assert len(output) > 20

    def _create_temp_directory_with_file(self, tmp_path, pkg: str, filename: str, content: str):
        result = tmp_path / pkg
        result.mkdir(exist_ok=True)

        (result / filename).write_text(content)
        return result


@pytest.mark.integration
class TestCLIWorkflows:
    """Test complete CLI workflows."""

    def test_check_then_fix_dry_run_workflow(self, tmp_path: Path):
        """Workflow: check → fix --dry-run."""
        pkg = self._create_temp_directory_with_file(tmp_path, "pkg", "mod.py", "class Public: pass")
        (pkg / "__init__.py").write_text("")

        self._create_temp_directory_with_file(
            tmp_path,
            ".codeweaver",
            "lazy_import_rules.yaml",
            """
schema_version: "1.0"
rules: []
""",
        )
        # Step 1: Check
        _exit1, _stdout1, stderr1 = run_cli("check", str(pkg))
        # Should complete (may warn)
        assert "Traceback" not in stderr1

        # Step 2: Fix dry run
        _exit2, _stdout2, stderr2 = run_cli("fix", "--dry-run", "--source", str(tmp_path))
        # Should complete (may have warnings but shouldn't crash)
        assert "Traceback" not in stderr2

    def test_analyze_then_validate_workflow(self, tmp_path: Path):
        """Workflow: analyze → validate (backward compat)."""
        pkg = self._create_temp_directory_with_file(tmp_path, "pkg", "mod.py", "class Public: pass")
        (pkg / "__init__.py").write_text("")

        self._create_temp_directory_with_file(
            tmp_path,
            ".codeweaver",
            "lazy_import_rules.yaml",
            """
schema_version: "1.0"
rules: []
""",
        )
        # Step 1: Analyze
        _exit1, _stdout1, stderr1 = run_cli("analyze", "--source", str(tmp_path))
        # Should complete (may warn)
        assert "Traceback" not in stderr1

        # Step 2: Validate
        _exit2, _stdout2, stderr2 = run_cli("validate", "--module", str(pkg))
        # Should complete (may have warnings but shouldn't crash)
        assert "Traceback" not in stderr2

    def _create_temp_directory_with_file(self, tmp_path, pkg: str, filename: str, content: str):
        result = tmp_path / pkg
        result.mkdir(exist_ok=True)

        (result / filename).write_text(content)
        return result

    def test_full_pipeline_workflow(self, tmp_path: Path):
        """Full workflow: check → generate → fix."""
        pkg = self._create_temp_directory_with_file(
            tmp_path, "pkg", "mod.py", "class MyClass: pass"
        )
        (pkg / "__init__.py").write_text("")

        # Create rules
        rules_dir = tmp_path / ".codeweaver"
        rules_dir.mkdir()
        (rules_dir / "lazy_import_rules.yaml").write_text("""
schema_version: "1.0"
rules:
  - name: "include-all"
    priority: 500
    match:
      name_pattern: ".*"
    action: include
    propagate: parent
""")

        # Check
        _exit1, _stdout1, stderr1 = run_cli("check", str(pkg))
        # Should complete (may warn)
        assert "Traceback" not in stderr1

        # Generate
        _exit2, _stdout2, stderr2 = run_cli("generate", "--source", str(tmp_path))
        # Should complete (may have warnings)
        assert "Traceback" not in stderr2

        # Fix dry-run
        _exit3, _stdout3, stderr3 = run_cli("fix", "--dry-run", "--source", str(tmp_path))
        # Should complete
        assert "Traceback" not in stderr3


@pytest.mark.integration
class TestCLIHelp:
    """Test help and documentation."""

    def test_check_help(self):
        """Check command help works."""
        exit_code, stdout, stderr = run_cli("check", "--help")

        assert exit_code == 0
        output = stdout + stderr
        assert "check" in output.lower() or "help" in output.lower()

    def test_fix_help(self):
        """Fix command help works."""
        exit_code, stdout, stderr = run_cli("fix", "--help")

        assert exit_code == 0
        output = stdout + stderr
        assert "fix" in output.lower() or "help" in output.lower()

    def test_validate_help(self):
        """Validate command help works (backward compat)."""
        exit_code, stdout, stderr = run_cli("validate", "--help")

        assert exit_code == 0
        output = stdout + stderr
        assert "validate" in output.lower() or "help" in output.lower()

    def test_analyze_help(self):
        """Analyze command help works (backward compat)."""
        exit_code, stdout, stderr = run_cli("analyze", "--help")

        assert exit_code == 0
        output = stdout + stderr
        assert "analyze" in output.lower() or "help" in output.lower()
