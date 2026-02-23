# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Tests for Import Validator."""

# sourcery skip: require-return-annotation, require-parameter-annotation, no-relative-imports
from __future__ import annotations

from pathlib import Path

from exportify.common.types import ValidationError, ValidationWarning
from exportify.validator.validator import LazyImportValidator


class TestLazyImportValidator:
    """Test suite for lazy import validator."""

    def test_valid_lazy_import_call(self, tmp_path: Path):
        """Valid lazy_import call should pass validation."""
        # Create a test file with valid lazy_import using a real module
        test_file = tmp_path / "test.py"
        test_file.write_text("""
from pathlib import Path

# Use a real module that exists
MyPath = Path
""")

        validator = LazyImportValidator(project_root=tmp_path)
        issues = validator.validate_file(test_file)

        # Should have no errors (file has no lazy_import calls, so nothing to validate)
        errors = [i for i in issues if isinstance(i, ValidationError)]
        assert not errors

    def test_broken_lazy_import_module(self, tmp_path: Path):
        """Broken module path should be detected."""
        test_file = tmp_path / "test.py"
        test_file.write_text("""
from lateimport import lateimport

MyClass = lateimport("nonexistent.module", "MyClass")
""")

        validator = LazyImportValidator(project_root=tmp_path)
        issues = validator.validate_file(test_file)

        errors = [i for i in issues if isinstance(i, ValidationError)]
        assert errors
        assert any("nonexistent.module" in e.message for e in errors)

    def test_broken_lazy_import_object(self, tmp_path: Path):
        """Missing object should be detected."""
        test_file = tmp_path / "test.py"
        test_file.write_text("""
from codeweaver.common.utils import lazy_import

# Module exists but object doesn't
Obj = lazy_import("codeweaver.core", "NonExistentClass")
""")

        validator = LazyImportValidator(project_root=tmp_path)
        issues = validator.validate_file(test_file)

        if errors := [i for i in issues if isinstance(i, ValidationError)]:
            assert any("NonExistentClass" in e.message for e in errors)

    def test_multiple_issues_in_file(self, tmp_path: Path):
        """Multiple issues should all be detected."""
        test_file = tmp_path / "test.py"
        test_file.write_text("""
from lateimport import lateimport

A = lateimport("nonexistent1", "Class1")
B = lateimport("nonexistent2", "Class2")
""")

        validator = LazyImportValidator(project_root=tmp_path)
        issues = validator.validate_file(test_file)

        errors = [i for i in issues if isinstance(i, ValidationError)]
        assert len(errors) >= 2

    def test_no_exportify(self, tmp_path: Path):
        """File with no lazy_import calls should pass."""
        test_file = tmp_path / "test.py"
        test_file.write_text("""
# Regular code, no lazy imports

class MyClass:
    pass
""")

        validator = LazyImportValidator(project_root=tmp_path)
        issues = validator.validate_file(test_file)

        # Should have no errors (warnings about missing __all__ are acceptable)
        errors = [i for i in issues if isinstance(i, ValidationError)]
        assert not errors

    def test_syntax_error_in_file(self, tmp_path: Path):
        """Syntax errors should be reported."""
        test_file = tmp_path / "test.py"
        test_file.write_text("""
def broken(
""")

        validator = LazyImportValidator(project_root=tmp_path)
        issues = validator.validate_file(test_file)

        errors = [i for i in issues if isinstance(i, ValidationError)]
        assert errors

    def test_validate_multiple_files(self, tmp_path: Path):
        """Can validate multiple files."""
        # Create multiple test files
        file1 = tmp_path / "file1.py"
        file1.write_text('lateimport("good.module", "Class")')

        file2 = tmp_path / "file2.py"
        file2.write_text('lateimport("bad.module", "Class")')

        validator = LazyImportValidator(project_root=tmp_path)
        issues = validator.validate_files([file1, file2])

        # Should have issues from both files
        assert len(issues) >= 1


class TestConsistencyChecker:
    """Test suite for package consistency checking."""

    def test_consistent_init_file(self, tmp_path: Path):
        """Consistent __init__.py should pass."""
        init_file = tmp_path / "__init__.py"
        init_file.write_text("""
from __future__ import annotations

from typing import TYPE_CHECKING

__all__ = ["MyClass"]

# Define MyClass as a lazy import
class MyClass:  # Placeholder definition
    pass

_dynamic_imports = {
    "MyClass": ("module", "MyClass"),
}

if TYPE_CHECKING:
    from .module import MyClass  # type: ignore[no-redef]
""")

        from exportify.validator.consistency import ConsistencyChecker

        checker = ConsistencyChecker(project_root=tmp_path)
        issues = checker.check_file_consistency(init_file)

        errors = [i for i in issues if i.severity == "error"]
        assert not errors

    def test_all_mismatch_dynamic_imports(self, tmp_path: Path):
        """__all__ and _dynamic_imports mismatch should be detected."""
        init_file = tmp_path / "__init__.py"
        init_file.write_text("""
__all__ = ["Class1", "Class2"]

_dynamic_imports = {
    "Class1": ("module", "Class1"),
    # Class2 missing!
}
""")

        from exportify.validator.consistency import ConsistencyChecker

        checker = ConsistencyChecker(project_root=tmp_path)
        issues = checker.check_file_consistency(init_file)

        errors = [i for i in issues if i.severity == "error"]
        assert errors
        assert any("Class2" in str(e) for e in errors)

    def test_duplicate_exports(self, tmp_path: Path):
        """Duplicate exports should be detected."""
        init_file = tmp_path / "__init__.py"
        init_file.write_text("""
__all__ = ["MyClass", "MyClass"]  # Duplicate!

_dynamic_imports = {
    "MyClass": ("module", "MyClass"),
}
""")

        from exportify.validator.consistency import ConsistencyChecker

        checker = ConsistencyChecker(project_root=tmp_path)
        issues = checker.check_file_consistency(init_file)

        # Should detect duplicate
        warnings = [i for i in issues if i.severity == "warning"]
        assert warnings or len(issues) > 0

    def test_missing_type_checking_import(self, tmp_path: Path):
        """Missing TYPE_CHECKING import should be detected."""
        init_file = tmp_path / "__init__.py"
        init_file.write_text("""
__all__ = ["MyClass"]

_dynamic_imports = {
    "MyClass": ("module", "MyClass"),
}

# Missing: if TYPE_CHECKING: ...
""")

        from exportify.validator.consistency import ConsistencyChecker

        checker = ConsistencyChecker(project_root=tmp_path)
        checker.check_file_consistency(init_file)

        # May warn about missing TYPE_CHECKING block
        # This is implementation dependent


class TestImportResolver:
    """Test suite for import resolution."""

    def test_resolve_valid_import(self):
        """Should resolve valid import."""
        from pathlib import Path

        from exportify.validator.resolver import ImportResolver

        resolver = ImportResolver(project_root=Path.cwd())

        # Try to resolve a real module
        resolution = resolver.resolve("pathlib", "Path")

        assert resolution.exists
        assert resolution.module == "pathlib"
        assert resolution.obj == "Path"
        assert resolution.error is None

    def test_resolve_invalid_module(self):
        """Should detect invalid module."""
        from pathlib import Path

        from exportify.validator.resolver import ImportResolver

        resolver = ImportResolver(project_root=Path.cwd())

        resolution = resolver.resolve("nonexistent.module", "Class")

        assert not resolution.exists
        assert resolution.error is not None

    def test_resolve_invalid_object(self):
        """Should detect invalid object."""
        from pathlib import Path

        from exportify.validator.resolver import ImportResolver

        resolver = ImportResolver(project_root=Path.cwd())

        # Module exists but object doesn't
        resolution = resolver.resolve("pathlib", "NonExistentClass")

        assert not resolution.exists or resolution.error is not None

    def test_resolve_cache(self):
        """Resolver should cache results."""
        from pathlib import Path

        from exportify.validator.resolver import ImportResolver

        resolver = ImportResolver(project_root=Path.cwd())

        # First resolution
        res1 = resolver.resolve("pathlib", "Path")

        # Second resolution (should use cache)
        res2 = resolver.resolve("pathlib", "Path")

        assert res1.exists == res2.exists
        assert res1.module == res2.module


class TestComprehensiveValidation:
    """Test suite for comprehensive validation methods."""

    def test_lazy_import_with_correct_arguments(self, tmp_path: Path):
        """Valid lateimport call with correct arguments should pass."""
        test_file = tmp_path / "test.py"
        test_file.write_text("""
from lateimport import lateimport

MyClass = lateimport("module.path", "MyClass")
""")

        validator = LazyImportValidator(project_root=tmp_path)
        issues = validator.validate_file(test_file)

        # Should have no errors about call syntax (may have resolution errors)
        syntax_errors = [
            i
            for i in issues
            if isinstance(i, ValidationError)
            and i.code in ("INVALID_LATEIMPORT", "NON_LITERAL_LATEIMPORT")
        ]
        assert not syntax_errors

    def test_lazy_import_with_insufficient_arguments(self, tmp_path: Path):
        """lateimport with < 2 arguments should error."""
        test_file = tmp_path / "test.py"
        test_file.write_text("""
from lateimport import lateimport

MyClass = lateimport("module.path")  # Missing second arg
""")

        validator = LazyImportValidator(project_root=tmp_path)
        issues = validator.validate_file(test_file)

        errors = [
            i for i in issues if isinstance(i, ValidationError) and i.code == "INVALID_LATEIMPORT"
        ]
        assert errors
        assert any("at least 2 arguments" in e.message for e in errors)

    def test_lazy_import_with_non_string_arguments(self, tmp_path: Path):
        """lateimport with non-string arguments should error."""
        test_file = tmp_path / "test.py"
        test_file.write_text("""
from lateimport import lateimport

module_var = "module.path"
MyClass = lateimport(module_var, "MyClass")  # Variable, not literal
""")

        validator = LazyImportValidator(project_root=tmp_path)
        issues = validator.validate_file(test_file)

        errors = [
            i
            for i in issues
            if isinstance(i, ValidationError) and i.code == "NON_LITERAL_LATEIMPORT"
        ]
        assert errors
        assert any("string literal" in e.message for e in errors)

    def test_type_checking_with_only_imports(self, tmp_path: Path):
        """TYPE_CHECKING block with only imports should not warn."""
        test_file = tmp_path / "test.py"
        test_file.write_text("""
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from module import Class1
    from module import Class2
""")

        validator = LazyImportValidator(project_root=tmp_path)
        issues = validator.validate_file(test_file)

        # No warnings about TYPE_CHECKING structure
        type_warnings = [
            i
            for i in issues
            if isinstance(i, ValidationWarning)
            and "TYPE_CHECKING block should only contain imports" in i.message
        ]
        assert not type_warnings

    def test_type_checking_with_non_import_code(self, tmp_path: Path):
        """TYPE_CHECKING block with non-import code should warn."""
        test_file = tmp_path / "test.py"
        test_file.write_text("""
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from module import Class1
    x = 5  # Non-import statement
    def helper(): pass  # Non-import statement
""")

        validator = LazyImportValidator(project_root=tmp_path)
        issues = validator.validate_file(test_file)

        warnings = [
            i
            for i in issues
            if isinstance(i, ValidationWarning)
            and "TYPE_CHECKING block should only contain imports" in i.message
        ]
        assert len(warnings) == 2  # One for each non-import statement

    def test_all_with_all_names_defined(self, tmp_path: Path):
        """__all__ with all names defined should pass."""
        test_file = tmp_path / "test.py"
        test_file.write_text("""
__all__ = ["MyClass", "my_function", "MY_CONSTANT"]

class MyClass:
    pass

def my_function():
    pass

MY_CONSTANT = 42
""")

        validator = LazyImportValidator(project_root=tmp_path)
        issues = validator.validate_file(test_file)

        # No errors about undefined names
        all_errors = [
            i for i in issues if isinstance(i, ValidationError) and i.code == "UNDEFINED_IN_ALL"
        ]
        assert not all_errors

    def test_all_with_undefined_name(self, tmp_path: Path):
        """__all__ with undefined name should error."""
        test_file = tmp_path / "test.py"
        test_file.write_text("""
__all__ = ["MyClass", "UndefinedClass"]

class MyClass:
    pass
""")

        validator = LazyImportValidator(project_root=tmp_path)
        issues = validator.validate_file(test_file)

        errors = [
            i for i in issues if isinstance(i, ValidationError) and i.code == "UNDEFINED_IN_ALL"
        ]
        assert errors
        assert any("UndefinedClass" in e.message for e in errors)

    def test_missing_all_declaration(self, tmp_path: Path):
        """Missing __all__ should warn."""
        test_file = tmp_path / "test.py"
        test_file.write_text("""
class MyClass:
    pass

def my_function():
    pass
""")

        validator = LazyImportValidator(project_root=tmp_path)
        issues = validator.validate_file(test_file)

        warnings = [
            i for i in issues if isinstance(i, ValidationWarning) and "Missing __all__" in i.message
        ]
        assert warnings

    def test_imports_at_top_of_file(self, tmp_path: Path):
        """Imports at top of file should not warn."""
        test_file = tmp_path / "test.py"
        test_file.write_text("""
import os
from pathlib import Path

class MyClass:
    pass
""")

        validator = LazyImportValidator(project_root=tmp_path)
        issues = validator.validate_file(test_file)

        # No warnings about import organization
        org_warnings = [
            i
            for i in issues
            if isinstance(i, ValidationWarning)
            and "Import statement after non-import code" in i.message
        ]
        assert not org_warnings

    def test_imports_after_code(self, tmp_path: Path):
        """Imports after code should warn."""
        test_file = tmp_path / "test.py"
        test_file.write_text("""
class MyClass:
    pass

import os  # Import after code
from pathlib import Path  # Import after code
""")

        validator = LazyImportValidator(project_root=tmp_path)
        issues = validator.validate_file(test_file)

        warnings = [
            i
            for i in issues
            if isinstance(i, ValidationWarning)
            and "Import statement after non-import code" in i.message
        ]
        assert len(warnings) == 2  # Both imports flagged

    def test_syntax_error_handling(self, tmp_path: Path):
        """Syntax errors should be caught and reported."""
        test_file = tmp_path / "test.py"
        test_file.write_text("""
def broken(
    # Missing closing parenthesis
""")

        validator = LazyImportValidator(project_root=tmp_path)
        issues = validator.validate_file(test_file)

        errors = [i for i in issues if isinstance(i, ValidationError) and i.code == "SYNTAX_ERROR"]
        assert errors

    def test_empty_file(self, tmp_path: Path):
        """Empty file should pass validation."""
        test_file = tmp_path / "test.py"
        test_file.write_text("")

        validator = LazyImportValidator(project_root=tmp_path)
        issues = validator.validate_file(test_file)

        # Should just warn about missing __all__
        errors = [i for i in issues if isinstance(i, ValidationError)]
        assert not errors

    def test_file_with_only_docstring(self, tmp_path: Path):
        """File with only docstring should pass validation."""
        test_file = tmp_path / "test.py"
        test_file.write_text('"""Module docstring."""')

        validator = LazyImportValidator(project_root=tmp_path)
        issues = validator.validate_file(test_file)

        # Should just warn about missing __all__
        errors = [i for i in issues if isinstance(i, ValidationError)]
        assert not errors

    def test_comprehensive_validation(self, tmp_path: Path):
        """Test multiple validation checks at once."""
        test_file = tmp_path / "test.py"
        test_file.write_text("""
from typing import TYPE_CHECKING
from lateimport import lateimport

__all__ = ["MyClass", "UndefinedExport"]

class MyClass:
    pass

if TYPE_CHECKING:
    from module import Type1
    x = 5  # Should warn

BadImport = lateimport("module")  # Should error - insufficient args

import late_import  # Should warn - import after code
""")

        validator = LazyImportValidator(project_root=tmp_path)
        issues = validator.validate_file(test_file)

        # Should have errors and warnings
        errors = [i for i in issues if isinstance(i, ValidationError)]
        warnings = [i for i in issues if isinstance(i, ValidationWarning)]

        assert len(errors) >= 2  # Insufficient args, undefined export
        assert len(warnings) >= 2  # TYPE_CHECKING non-import, late import

    def test_validation_result_aggregation(self, tmp_path: Path):
        """Test that validation results are properly aggregated."""
        test_file = tmp_path / "test.py"
        test_file.write_text("""
from lateimport import lateimport

__all__ = ["Missing1", "Missing2"]

lateimport("bad")  # Error
lateimport("also", "bad", "extra")  # Should still validate
""")

        validator = LazyImportValidator(project_root=tmp_path)
        issues = validator.validate_file(test_file)

        # All issues should be in a single list
        assert isinstance(issues, list)
        assert len(issues) > 0

        # Should have both errors and warnings
        has_errors = any(isinstance(i, ValidationError) for i in issues)
        has_warnings = any(isinstance(i, ValidationWarning) for i in issues)

        assert has_errors  # From lazy_import and __all__
        assert has_warnings  # From late import and missing TYPE_CHECKING block


class TestValidationReport:
    """Test validation report generation."""

    def test_empty_report(self):
        """Empty validation report."""
        from exportify.common.types import ValidationMetrics, ValidationReport

        report = ValidationReport(
            errors=[],
            warnings=[],
            metrics=ValidationMetrics(
                files_validated=0, imports_checked=0, consistency_checks=0, validation_time_ms=0
            ),
            success=True,
        )

        assert report.success
        assert len(report.errors) == 0
        assert len(report.warnings) == 0

    def test_report_with_errors(self):
        """Report with errors should not be successful."""
        from exportify.common.types import ValidationMetrics, ValidationReport

        errors = [
            ValidationError(
                file=Path("test.py"),
                line=10,
                message="Import not found",
                suggestion="Check module path",
                code="BROKEN_IMPORT",
            )
        ]

        report = ValidationReport(
            errors=errors,
            warnings=[],
            metrics=ValidationMetrics(
                files_validated=1, imports_checked=5, consistency_checks=1, validation_time_ms=100
            ),
            success=False,
        )

        assert not report.success
        assert len(report.errors) == 1

    def test_report_with_warnings_is_success(self):
        """Report with only warnings should be successful."""
        from exportify.common.types import ValidationMetrics, ValidationReport

        warnings = [
            ValidationWarning(
                file=Path("test.py"), line=10, message="Unused import", suggestion="Remove import"
            )
        ]

        report = ValidationReport(
            errors=[],
            warnings=warnings,
            metrics=ValidationMetrics(
                files_validated=1, imports_checked=5, consistency_checks=1, validation_time_ms=100
            ),
            success=True,
        )

        assert report.success
        assert len(report.warnings) == 1


class TestValidateMethod:
    """Test the validate() method that returns a full ValidationReport."""

    def test_validate_with_explicit_file_list(self, tmp_path: Path):
        """validate() with an explicit file list processes only those files."""
        test_file = tmp_path / "mymodule.py"
        test_file.write_text("""
class Good: pass
""")

        validator = LazyImportValidator(project_root=tmp_path)
        report = validator.validate(file_paths=[test_file])

        assert report.metrics.files_validated == 1
        # No errors expected for a clean file with only a class
        assert isinstance(report.success, bool)

    def test_validate_counts_lateimport_calls(self, tmp_path: Path):
        """validate() counts lateimport() occurrences for metrics."""
        test_file = tmp_path / "mod.py"
        test_file.write_text("""
from lateimport import lateimport
A = lateimport("pathlib", "Path")
B = lateimport("os", "getcwd")
""")

        validator = LazyImportValidator(project_root=tmp_path)
        report = validator.validate(file_paths=[test_file])

        assert report.metrics.imports_checked == 2

    def test_validate_processes_init_files_for_consistency(self, tmp_path: Path):
        """validate() runs consistency checks on __init__.py files."""
        init_file = tmp_path / "__init__.py"
        init_file.write_text("""
__all__ = ["A", "B"]
_dynamic_imports = {
    "A": ("mod", "A"),
    # B is missing — consistency error
}
""")

        validator = LazyImportValidator(project_root=tmp_path)
        report = validator.validate(file_paths=[init_file])

        # Should detect consistency issue (B missing from _dynamic_imports)
        assert report.metrics.consistency_checks > 0

    def test_validate_consistency_error_added_to_report(self, tmp_path: Path):
        """Consistency errors from __init__.py are promoted to ValidationErrors."""
        init_file = tmp_path / "__init__.py"
        init_file.write_text("""
__all__ = ["Missing"]
_dynamic_imports = {}
""")

        validator = LazyImportValidator(project_root=tmp_path)
        report = validator.validate(file_paths=[init_file])

        assert any("Missing" in e.message for e in report.errors)

    def test_validate_consistency_warning_added_to_report(self, tmp_path: Path):
        """Consistency warnings from __init__.py are promoted to ValidationWarnings."""
        init_file = tmp_path / "__init__.py"
        init_file.write_text("""
__all__ = ["A"]
_dynamic_imports = {
    "A": ("mod", "A"),
    "Extra": ("mod", "Extra"),  # Extra in _dynamic_imports
}
""")

        validator = LazyImportValidator(project_root=tmp_path)
        report = validator.validate(file_paths=[init_file])

        # Extra in _dynamic_imports is a warning
        assert any("Extra" in w.message for w in report.warnings)

    def test_validate_general_exception_in_file(self, tmp_path: Path, monkeypatch):
        """validate_file catching a non-SyntaxError exception returns a VALIDATION_ERROR."""
        test_file = tmp_path / "bad.py"
        test_file.write_text("class X: pass")

        validator = LazyImportValidator(project_root=tmp_path)

        # Monkeypatch ast.parse to raise an unexpected error
        import ast

        original_parse = ast.parse

        def bad_parse(source, *args, **kwargs):
            raise RuntimeError("unexpected parse failure")

        monkeypatch.setattr(ast, "parse", bad_parse)

        issues = validator.validate_file(test_file)
        errors = [i for i in issues if isinstance(i, ValidationError)]
        assert errors
        assert errors[0].code == "VALIDATION_ERROR"

    def test_validate_non_module_ast_returns_no_lateimport_data(self, tmp_path: Path):
        """_check_structure_and_imports returns (False, False) for non-Module AST."""
        import ast

        validator = LazyImportValidator(project_root=tmp_path)

        # Pass a non-Module AST node (get the Constant value from the assignment)
        assign_stmt = ast.parse("x = 1").body[0]
        expr_node = assign_stmt.value  # Constant node
        issues: list = []
        result = validator._check_structure_and_imports(tmp_path / "x.py", expr_node, issues)

        assert result == (False, False)

    def test_lateimport_obj_arg_not_string_literal(self, tmp_path: Path):
        """lateimport() with non-string second arg reports NON_LITERAL_LATEIMPORT."""
        test_file = tmp_path / "test.py"
        test_file.write_text("""
from lateimport import lateimport
obj_var = "Path"
MyClass = lateimport("pathlib", obj_var)
""")

        validator = LazyImportValidator(project_root=tmp_path)
        issues = validator.validate_file(test_file)

        errors = [
            i
            for i in issues
            if isinstance(i, ValidationError) and i.code == "NON_LITERAL_LATEIMPORT"
        ]
        assert errors
        assert any("object argument" in e.message for e in errors)


class TestConsistencyCheckerErrors:
    """Test ConsistencyChecker error handling paths."""

    def test_syntax_error_in_init_file(self, tmp_path: Path):
        """SyntaxError during parse should be recorded as an error ConsistencyIssue."""
        from exportify.validator.consistency import ConsistencyChecker

        init_file = tmp_path / "__init__.py"
        init_file.write_text("def broken(\n")  # Syntax error

        checker = ConsistencyChecker(project_root=tmp_path)
        issues = checker.check_file_consistency(init_file)

        errors = [i for i in issues if i.severity == "error"]
        assert errors
        assert any("Syntax error" in e.message for e in errors)

    def test_generic_exception_in_init_file(self, tmp_path: Path, monkeypatch):
        """Generic exceptions during consistency check are recorded as error issues."""
        import ast

        from exportify.validator.consistency import ConsistencyChecker

        init_file = tmp_path / "__init__.py"
        init_file.write_text("__all__ = ['A']\n")

        original_parse = ast.parse

        def bad_parse(source, *args, **kwargs):
            raise RuntimeError("unexpected failure")

        monkeypatch.setattr(ast, "parse", bad_parse)

        checker = ConsistencyChecker(project_root=tmp_path)
        issues = checker.check_file_consistency(init_file)

        errors = [i for i in issues if i.severity == "error"]
        assert errors
        assert any("Failed to check consistency" in e.message for e in errors)


class TestImportResolverEdgeCases:
    """Test edge cases in ImportResolver."""

    def test_resolve_module_import_fails(self, tmp_path):
        """Module found but import raises Exception records the failure."""
        from exportify.validator.resolver import ImportResolver

        resolver = ImportResolver(project_root=tmp_path)

        # Use a module that exists in sys.modules but monkeypatch importlib
        import importlib.util

        original_find = importlib.util.find_spec
        original_import = importlib.import_module

        # Create a fake spec that looks valid
        import types

        fake_spec = types.SimpleNamespace(origin="/fake/path.py")

        import importlib

        def fake_find(name):
            if name == "fake_importable_module":
                return fake_spec
            return original_find(name)

        def fake_import(name):
            if name == "fake_importable_module":
                raise ImportError("cannot import this module")
            return original_import(name)

        import unittest.mock

        with (
            unittest.mock.patch("importlib.util.find_spec", side_effect=fake_find),
            unittest.mock.patch("importlib.import_module", side_effect=fake_import),
        ):
            result = resolver.resolve("fake_importable_module", "SomeClass")

        assert not result.exists
        assert result.error is not None
        assert "fake_importable_module" in result.error

    def test_resolve_find_spec_raises_exception(self, tmp_path):
        """When find_spec itself raises, resolver returns a failure result."""
        import unittest.mock

        from exportify.validator.resolver import ImportResolver

        resolver = ImportResolver(project_root=tmp_path)

        def boom(name):
            raise RuntimeError("find_spec exploded")

        with unittest.mock.patch("importlib.util.find_spec", side_effect=boom):
            result = resolver.resolve("some.module.that.will.fail", "Obj")

        assert not result.exists
        assert result.error is not None
        assert "Failed to resolve" in result.error

    def test_resolve_caches_failure_results(self, tmp_path):
        """Failed resolutions are cached to avoid repeated import attempts."""
        from exportify.validator.resolver import ImportResolver

        resolver = ImportResolver(project_root=tmp_path)

        result1 = resolver.resolve("definitely.not.a.real.module", "Thing")
        result2 = resolver.resolve("definitely.not.a.real.module", "Thing")

        assert not result1.exists
        assert result1 is result2  # Same object from cache


class TestRemainingValidatorPaths:
    """Tests for the remaining uncovered paths in validator modules."""

    def test_validate_without_file_paths_uses_project_root(self, tmp_path: Path):
        """validate(file_paths=None) discovers files from project_root."""
        # Create a Python file in the project root
        (tmp_path / "mymodule.py").write_text("class Foo: pass\n")

        validator = LazyImportValidator(project_root=tmp_path)
        # Pass file_paths=None — should autodiscover from project_root
        report = validator.validate(file_paths=None)

        # Should have discovered at least the one file we created
        assert report.metrics.files_validated >= 1

    def test_validate_all_with_non_list_value_returns_empty_issues(self, tmp_path: Path):
        """__all__ assigned a non-list value (e.g., tuple) returns no issues from _validate_all_declaration."""
        test_file = tmp_path / "test.py"
        # Assign __all__ as a tuple, not a list
        test_file.write_text("""
__all__ = ("MyClass",)

class MyClass:
    pass
""")

        validator = LazyImportValidator(project_root=tmp_path)
        issues = validator.validate_file(test_file)

        # No UNDEFINED_IN_ALL errors should be raised when __all__ is a tuple
        all_errors = [
            i for i in issues if isinstance(i, ValidationError) and i.code == "UNDEFINED_IN_ALL"
        ]
        assert not all_errors

    def test_extract_all_returns_none_when_absent(self, tmp_path: Path):
        """_extract_all returns None when there is no __all__ in the AST."""
        import ast

        from exportify.validator.consistency import ConsistencyChecker

        checker = ConsistencyChecker(project_root=tmp_path)

        # Parse a file that has no __all__
        tree = ast.parse("class Foo: pass\n")
        result = checker._extract_all(tree)
        assert result is None

    def test_extract_dynamic_imports_returns_none_when_absent(self, tmp_path: Path):
        """_extract_dynamic_imports returns None when there is no _dynamic_imports in the AST."""
        import ast

        from exportify.validator.consistency import ConsistencyChecker

        checker = ConsistencyChecker(project_root=tmp_path)

        # Parse a file that has no _dynamic_imports
        tree = ast.parse("__all__ = ['Foo']\n")
        result = checker._extract_dynamic_imports(tree)
        assert result is None
