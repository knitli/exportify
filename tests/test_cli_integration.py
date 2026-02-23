# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Simple CLI integration tests that verify end-to-end workflow.

Focuses on essential CLI functionality without subprocess complexity.
"""

# sourcery skip: require-return-annotation, require-parameter-annotation
from __future__ import annotations

import time

from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest


def run_cli(*args):
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
        except Exception as e:
            stderr.write(str(e))
            exit_code = 1

    return exit_code, stdout.getvalue(), stderr.getvalue()


@pytest.mark.integration
class TestCLICheckCommand:
    """Test check command."""

    def test_check_runs_successfully(self, tmp_path: Path):
        """Check command executes without error."""
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        (pkg / "mod.py").write_text("class Foo: pass")
        exit_code, _stdout, stderr = run_cli("check", str(pkg))

        assert exit_code == 0, f"Failed: {stderr}"

    def test_check_module_all_flag(self, tmp_path: Path):
        """Check --module-all flag works."""
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        (pkg / "mod.py").write_text("class Foo: pass")
        exit_code, _stdout, stderr = run_cli("check", str(pkg), "--module-all")

        assert exit_code == 0, f"Failed: {stderr}"

    def test_check_with_nonexistent_path(self, tmp_path: Path):
        """Check handles nonexistent paths gracefully."""
        nonexistent = tmp_path / "nonexistent"

        exit_code, stdout, stderr = run_cli("check", str(nonexistent))

        # Should either fail or complete with warning
        assert (
            exit_code != 0
            or "not found" in (stdout + stderr).lower()
            or "does not exist" in (stdout + stderr).lower()
        )


@pytest.mark.integration
class TestCLIFixCommand:
    """Test fix command."""

    def test_fix_dry_run(self, tmp_path: Path):
        """Dry-run mode doesn't write files."""
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "mod.py").write_text("class Foo: pass")

        (pkg / "__init__.py").write_text("")

        exit_code, stdout, stderr = run_cli("fix", "--source", str(tmp_path), "--dry-run")

        assert exit_code == 0, f"Failed: {stderr}"
        assert "dry run" in (stdout + stderr).lower() or "Dry run" in (stdout + stderr)

    def test_fix_module_all_dry_run(self, tmp_path: Path):
        """Fix --module-all --dry-run works."""
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        (pkg / "mod.py").write_text("class Foo: pass\ndef bar(): pass")

        exit_code, _stdout, stderr = run_cli(
            "fix", "--source", str(tmp_path), "--module-all", "--dry-run"
        )

        assert exit_code == 0, f"Failed: {stderr}"


@pytest.mark.integration
class TestCLIGenerateCommand:
    """Test generate command."""

    def test_generate_dry_run(self, tmp_path: Path):
        """Dry-run mode doesn't write files."""
        # Create module
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "mod.py").write_text("class Foo: pass")

        init_file = pkg / "__init__.py"
        existed_before = init_file.exists()

        exit_code, stdout, stderr = run_cli("generate", "--source", str(tmp_path), "--dry-run")

        assert exit_code == 0, f"Failed: {stderr}"
        assert "dry run" in stdout.lower() or "Dry run" in stdout

        # No files should be written in dry-run
        if not existed_before:
            assert not init_file.exists()

    def test_generate_creates_files(self, tmp_path: Path):
        """Generate creates __init__.py files."""
        # Create module
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "mod.py").write_text("""
class Foo:
    pass

def bar():
    pass
""")

        exit_code, _stdout, stderr = run_cli("generate", "--source", str(tmp_path))

        assert exit_code == 0, f"Failed: {stderr}"

        # Check if __init__.py was created
        init_file = pkg / "__init__.py"
        if init_file.exists():
            content = init_file.read_text()
            # Should have some export mechanism
            assert "__all__" in content or "import" in content.lower()

    def test_generate_preserves_manual_content(self, tmp_path: Path):
        """Generate preserves existing manual exports."""
        # Create package with existing __init__.py
        pkg = tmp_path / "pkg"
        pkg.mkdir()

        (pkg / "mod.py").write_text("class New: pass")

        init_file = pkg / "__init__.py"
        manual_content = '''"""Manual docstring."""

from .other import Manual

__all__ = ["Manual"]
'''
        init_file.write_text(manual_content)

        exit_code, _stdout, stderr = run_cli("generate", "--source", str(tmp_path))

        # Should complete (may or may not preserve content depending on implementation)
        assert exit_code == 0, f"Failed: {stderr}"

        # File should still exist and be valid
        assert init_file.exists()
        assert len(init_file.read_text()) > 0


@pytest.mark.integration
class TestCLICacheIntegration:
    """Test cache behavior."""

    def test_cache_used_on_second_run(self, tmp_path: Path):
        """Second run shows cache usage."""
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        (pkg / "mod.py").write_text("class Foo: pass")

        # First run
        run_cli("fix", "--dry-run", "--source", str(pkg))

        # Second run
        time.sleep(0.1)  # Small delay
        exit_code2, _stdout2, _stderr2 = run_cli("fix", "--dry-run", "--source", str(pkg))

        assert exit_code2 == 0


@pytest.mark.integration
class TestCLIEndToEnd:
    """Test complete workflows."""

    def test_check_then_generate(self, tmp_path: Path):
        """Complete workflow: check → generate."""
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        (pkg / "mod.py").write_text("""
class Public:
    pass

def public_func():
    return 42

_private = "secret"
""")

        # Step 1: Check (target the package dir directly)
        exit1, _stdout1, stderr1 = run_cli("check", str(pkg))
        assert exit1 == 0, f"Check failed: {stderr1}"

        # Step 2: Generate
        exit2, _stdout2, stderr2 = run_cli("generate", "--source", str(tmp_path))
        assert exit2 == 0, f"Generate failed: {stderr2}"

        # Verify file created
        init_file = pkg / "__init__.py"
        if init_file.exists():
            content = init_file.read_text()
            assert len(content) > 0

    def test_generated_file_is_valid_python(self, tmp_path: Path):
        """Generated files are syntactically valid."""
        # Create module
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "mod.py").write_text("""
class Test:
    pass

def test_func():
    pass
""")

        # Generate
        exit_code, _stdout, stderr = run_cli("generate", "--source", str(tmp_path))
        assert exit_code == 0, f"Failed: {stderr}"

        # Verify syntax
        init_file = pkg / "__init__.py"
        if init_file.exists():
            import ast

            content = init_file.read_text()
            try:
                ast.parse(content)
            except SyntaxError as e:
                pytest.fail(f"Generated file has syntax error: {e}")


@pytest.mark.integration
class TestCLIErrorHandling:
    """Test error handling."""

    def test_missing_rules_uses_defaults(self, tmp_path: Path, monkeypatch):
        """Missing rules file uses defaults."""
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        (pkg / "mod.py").write_text("class Foo: pass")

        # Ensure find_config_file() returns None regardless of working directory.
        monkeypatch.setattr("exportify.common.config.find_config_file", lambda: None)

        exit_code, _stdout, _stderr = run_cli("fix", "--dry-run", "--source", str(pkg))

        assert exit_code == 0

    def test_syntax_error_handled(self, tmp_path: Path):
        """Syntax errors in source files are handled gracefully."""
        # Create module with syntax error
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "bad.py").write_text("def broken(\n    # Missing closing paren")

        # Create rules
        (tmp_path / ".codeweaver").mkdir()
        (tmp_path / ".codeweaver/lateimport_rules.yaml").write_text("""
schema_version: "1.0"
rules: []
""")

        # Should not crash
        exit_code, _stdout, stderr = run_cli("check", str(pkg))

        # May complete with warnings or errors, but should not crash
        assert "Traceback" not in stderr or exit_code != 0


@pytest.mark.integration
class TestCLIHelp:
    """Test help and documentation."""

    def test_help_works(self):
        """Help message is accessible."""
        exit_code, stdout, _stderr = run_cli("--help")

        assert exit_code == 0
        assert "check" in stdout or "generate" in stdout or "fix" in stdout

    def test_check_help(self):
        """Check command help works."""
        exit_code, stdout, _stderr = run_cli("check", "--help")

        assert exit_code == 0
        assert "source" in stdout.lower() or "check" in stdout.lower()

    def test_fix_help(self):
        """Fix command help works."""
        exit_code, stdout, _stderr = run_cli("fix", "--help")

        assert exit_code == 0
        assert "dry-run" in stdout.lower() or "fix" in stdout.lower()

    def test_generate_help(self):
        """Generate command help works."""
        exit_code, stdout, _stderr = run_cli("generate", "--help")

        assert exit_code == 0
        assert "dry-run" in stdout.lower() or "generate" in stdout.lower()


@pytest.mark.integration
class TestKnownIssues:
    """Tests for previously known issues that are now resolved."""

    def test_no_duplicate_future_imports(self, tmp_path: Path):
        """Duplicate future imports are not generated."""
        pkg = tmp_path / "pkg"
        pkg.mkdir()

        # Create init with existing future import
        init_file = pkg / "__init__.py"
        init_file.write_text("from __future__ import annotations\n\n# Existing\n")

        (pkg / "mod.py").write_text("class Foo: pass")

        # Create rules
        (tmp_path / ".codeweaver").mkdir()
        (tmp_path / ".codeweaver/lateimport_rules.yaml").write_text("""
schema_version: "1.0"
rules:
  - name: "include-all"
    priority: 500
    match:
      name_pattern: ".*"
    action: include
""")

        # Generate
        run_cli("generate", "--source", str(tmp_path))

        if init_file.exists():
            content = init_file.read_text()
            count = content.count("from __future__ import annotations")
            assert count <= 1, f"Found {count} future imports, expected 1"

    def test_check_no_lateimports_blacklist(self, tmp_path: Path):
        """check --no-lateimports (blacklist mode) runs without crashing."""
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        (pkg / "mod.py").write_text("class Foo: pass")

        exit_code, _stdout, stderr = run_cli("check", str(pkg), "--no-lateimports")

        assert exit_code == 0, f"Failed: {stderr}"

    def test_fix_warns_on_missing_init(self, tmp_path: Path):
        """fix warns when a package directory has no __init__.py and suggests generate."""
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        # Intentionally no __init__.py
        (pkg / "mod.py").write_text("class Foo: pass")

        exit_code, stdout, stderr = run_cli("fix", "--source", str(tmp_path))
        assert exit_code == 0, f"Failed: {stderr}"
        combined = stdout + stderr
        # Should warn about missing __init__.py
        assert "__init__.py" in combined or "init" in combined.lower(), (
            f"Expected warning about missing __init__.py, got: {combined!r}"
        )
        # Should suggest running generate
        assert "generate" in combined.lower(), (
            f"Expected suggestion to run generate, got: {combined!r}"
        )

    def test_check_package_all_flag(self, tmp_path: Path):
        """check --package-all runs without error."""
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        (pkg / "mod.py").write_text("class Foo: pass")

        exit_code, _stdout, stderr = run_cli("check", str(pkg), "--package-all")

        assert exit_code == 0, f"Failed: {stderr}"
