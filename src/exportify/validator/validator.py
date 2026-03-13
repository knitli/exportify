# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Main validator for lazy imports.

Validates lateimport calls and Python module structure.
"""

from __future__ import annotations

import ast
import contextlib

from pathlib import Path
from typing import TYPE_CHECKING, Any

from exportify.common.types import ValidationError, ValidationWarning


if TYPE_CHECKING:
    from exportify.common.types import ValidationReport

from exportify.validator.consistency import ConsistencyChecker
from exportify.validator.resolver import ImportResolver


class LateImportValidator:
    """Validates lazy import usage and module structure.

    Checks:
    - lateimport() call syntax and arguments
    - Import resolution (module and object exist)
    - __all__ declarations match definitions
    - TYPE_CHECKING block structure
    - Import organization
    """

    def __init__(
        self,
        project_root: Path | None = None,
        cache: Any | None = None,  # JSONAnalysisCache type, but avoiding import
    ) -> None:
        """Initialize validator.

        Args:
            project_root: Root directory of the project
            cache: Optional cache for analysis results (not currently used but accepted for compatibility)
        """
        self.project_root = project_root or Path.cwd()
        self.cache = cache  # Store for future use
        self.resolver = ImportResolver(project_root=self.project_root)
        self.consistency_checker = ConsistencyChecker(project_root=self.project_root)

    def validate_file(self, file_path: Path) -> list[ValidationError | ValidationWarning]:
        """Validate a single Python file.

        Args:
            file_path: Path to Python file to validate

        Returns:
            List of validation errors and warnings
        """
        issues, _, _ = self._validate_file_with_metrics(file_path)
        return issues

    def _validate_file_with_metrics(
        self, file_path: Path
    ) -> tuple[list[ValidationError | ValidationWarning], int, ast.AST | None]:
        """Validate a single Python file and count lateimport calls.

        Args:
            file_path: Path to Python file to validate

        Returns:
            Tuple of (list of issues, count of lateimport calls, parsed AST tree or None)
        """
        try:
            content = file_path.read_text()
            tree = ast.parse(content)
        except SyntaxError as e:
            return (
                [
                    ValidationError(
                        file=file_path,
                        line=e.lineno,
                        message=f"Syntax error: {e.msg}",
                        suggestion="Fix syntax error",
                        code="SYNTAX_ERROR",
                    )
                ],
                0,
                None,
            )
        except Exception as e:
            return (
                [
                    ValidationError(
                        file=file_path,
                        line=None,
                        message=f"Validation failed: {e}",
                        suggestion="Check file for errors",
                        code="VALIDATION_ERROR",
                    )
                ],
                0,
                None,
            )

        # Count lateimport calls checked
        imports_checked = content.count("lateimport(")

        issues: list[ValidationError | ValidationWarning] = []
        has_all_declaration = self._collect_all_declaration_issues(file_path, tree, issues)
        has_type_checking_block, has_lateimport_calls = self._check_structure_and_imports(
            file_path, tree, issues
        )
        issues.extend(
            self._finalize_warnings(
                file_path,
                tree,
                has_all_declaration=has_all_declaration,
                has_type_checking_block=has_type_checking_block,
                has_lateimport_calls=has_lateimport_calls,
            )
        )
        return issues, imports_checked, tree

    def _collect_all_declaration_issues(
        self, file_path: Path, tree: ast.AST, issues: list[ValidationError | ValidationWarning]
    ) -> bool:
        """Check for __all__ declaration and validate it."""
        has_all_declaration = False
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign):
                continue
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "__all__":
                    has_all_declaration = True
                    issues.extend(self._validate_all_declaration(file_path, node, tree))
        return has_all_declaration

    def _check_structure_and_imports(
        self, file_path: Path, tree: ast.AST, issues: list[ValidationError | ValidationWarning]
    ) -> tuple[bool, bool]:
        """Check import organization and collect lateimport issues."""
        seen_code = False
        has_type_checking_block = False
        has_lateimport_calls = False

        if not isinstance(tree, ast.Module):
            return has_type_checking_block, has_lateimport_calls

        for node in tree.body:
            is_import = isinstance(node, (ast.Import, ast.ImportFrom))
            is_code = self._is_code_statement(node, is_import=is_import)

            if is_import and seen_code and not self._is_type_checking_block():
                issues.append(
                    ValidationWarning(
                        file=file_path,
                        line=node.lineno,
                        message="Import statement after non-import code",
                        suggestion="Move imports to the top of the file",
                    )
                )

            if is_code:
                seen_code = True

            if isinstance(node, ast.If) and self._is_type_checking_guard(node):
                has_type_checking_block = True
                issues.extend(self._validate_type_checking_block(file_path, node))

            has_lateimport_calls |= self._collect_lateimport_issues(file_path, node, issues)

        return has_type_checking_block, has_lateimport_calls

    def _is_code_statement(self, node: ast.stmt, *, is_import: bool) -> bool:
        """Check if a statement is considered "code" (not import or docstring)."""
        if is_import:
            return False
        if isinstance(node, ast.Expr):
            return not isinstance(node.value, ast.Constant)
        return not isinstance(node, ast.Pass)

    def _collect_lateimport_issues(
        self, file_path: Path, node: ast.stmt, issues: list[ValidationError | ValidationWarning]
    ) -> bool:
        if isinstance(node, ast.Assign):
            return self._collect_lateimport_calls_from_value(file_path, node.value, issues)
        if (
            isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Call)
            and self._is_lateimport_call(node.value)
        ):
            issues.extend(self._validate_lateimport_call(file_path, node.value))
            return True
        return False

    def _collect_lateimport_calls_from_value(
        self, file_path: Path, value: ast.AST, issues: list[ValidationError | ValidationWarning]
    ) -> bool:
        found = False
        for item in ast.walk(value):
            if isinstance(item, ast.Call) and self._is_lateimport_call(item):
                found = True
                issues.extend(self._validate_lateimport_call(file_path, item))
        return found

    def _finalize_warnings(
        self,
        file_path: Path,
        tree: ast.AST,
        *,
        has_all_declaration: bool,
        has_type_checking_block: bool,
        has_lateimport_calls: bool,
    ) -> list[ValidationError | ValidationWarning]:
        issues: list[ValidationError | ValidationWarning] = []

        if not has_all_declaration and self._has_exports(tree):
            issues.append(
                ValidationWarning(
                    file=file_path,
                    line=1,
                    message="Missing __all__ declaration",
                    suggestion="Add __all__ to explicitly declare public API",
                )
            )

        if has_lateimport_calls and not has_type_checking_block:
            issues.append(
                ValidationWarning(
                    file=file_path,
                    line=1,
                    message="File uses lateimport but has no TYPE_CHECKING block",
                    suggestion="Add TYPE_CHECKING block with type imports for better type checking",
                )
            )

        return issues

    def validate_files(self, file_paths: list[Path]) -> list[ValidationError | ValidationWarning]:
        """Validate multiple files.

        Args:
            file_paths: List of file paths to validate

        Returns:
            Combined list of all validation issues
        """
        all_issues: list[ValidationError | ValidationWarning] = []
        for file_path in file_paths:
            issues = self.validate_file(file_path)
            all_issues.extend(issues)
        return all_issues

    def validate(self, file_paths: list[Path] | None = None) -> ValidationReport:
        """Validate project files for lazy import compliance.

        Validates all Python files in the project (or provided list) and aggregates results.

        Args:
            file_paths: Optional list of files to validate. If None, validates all Python files
                       in project_root.

        Returns:
            ValidationReport with aggregated errors, warnings, and metrics
        """
        import time

        from exportify.common.types import ValidationMetrics, ValidationReport

        start_time = time.time()

        # Determine files to validate
        if file_paths is None:
            # Find all Python files in project
            file_paths = list(self.project_root.rglob("*.py"))

        # Validate all files
        all_errors: list[ValidationError] = []
        all_warnings: list[ValidationWarning] = []
        imports_checked = 0
        parsed_trees: dict[Path, ast.AST] = {}

        for file_path in file_paths:
            results, count, tree = self._validate_file_with_metrics(file_path)

            # Separate errors and warnings
            errors = [r for r in results if isinstance(r, ValidationError)]
            warnings = [r for r in results if isinstance(r, ValidationWarning)]

            all_errors.extend(errors)
            all_warnings.extend(warnings)

            # Store trees for __init__.py files to reuse in consistency checks
            if tree and file_path.name == "__init__.py":
                parsed_trees[file_path] = tree

            # Add to metrics
            imports_checked += count

        # Run consistency checks on __init__.py files
        init_files = [f for f in file_paths if f.name == "__init__.py"]
        consistency_checks = 0

        for init_file in init_files:
            tree = parsed_trees.get(init_file)
            consistency_issues = self.consistency_checker.check_file_consistency(
                init_file, tree=tree
            )
            consistency_checks += len(consistency_issues)

            # Convert ConsistencyIssue to ValidationError/Warning
            for issue in consistency_issues:
                if issue.severity == "error":
                    all_errors.append(
                        ValidationError(
                            file=issue.location,
                            line=issue.line,
                            message=issue.message,
                            suggestion="Check __all__ and _dynamic_imports consistency",
                            code="CONSISTENCY_ERROR",
                        )
                    )
                else:
                    all_warnings.append(
                        ValidationWarning(
                            file=issue.location,
                            line=issue.line,
                            message=issue.message,
                            suggestion="Review module exports",
                        )
                    )

        end_time = time.time()
        validation_time_ms = int((end_time - start_time) * 1000)

        return ValidationReport(
            errors=all_errors,
            warnings=all_warnings,
            metrics=ValidationMetrics(
                files_validated=len(file_paths),
                imports_checked=imports_checked,
                consistency_checks=consistency_checks,
                validation_time_ms=validation_time_ms,
            ),
            success=not all_errors,
        )

    def _is_lateimport_call(self, node: ast.Call) -> bool:
        """Check if node is a lateimport() call.

        Args:
            node: AST Call node

        Returns:
            True if this is a lateimport call
        """
        if isinstance(node.func, ast.Name) and node.func.id == "lateimport":
            return True
        return isinstance(node.func, ast.Attribute) and node.func.attr == "lateimport"

    def _validate_lateimport_call(
        self, file_path: Path, node: ast.Call
    ) -> list[ValidationError | ValidationWarning]:
        """Validate a lateimport() call.

        Args:
            file_path: Path to file containing the call
            node: AST Call node for lateimport call

        Returns:
            List of validation issues
        """
        issues: list[ValidationError | ValidationWarning] = []

        # Check argument count
        if len(node.args) < 2:
            issues.append(
                ValidationError(
                    file=file_path,
                    line=node.lineno,
                    message="lateimport() requires at least 2 arguments (module, object)",
                    suggestion="Add missing arguments",
                    code="INVALID_LATEIMPORT",
                )
            )
            return issues

        # Check that arguments are string literals
        module_arg = node.args[0]
        obj_arg = node.args[1]

        if not isinstance(module_arg, ast.Constant) or not isinstance(module_arg.value, str):
            issues.append(
                ValidationError(
                    file=file_path,
                    line=node.lineno,
                    message="lateimport() module argument must be a string literal",
                    suggestion="Use a string literal instead of a variable",
                    code="NON_LITERAL_LATEIMPORT",
                )
            )
            return issues

        if not isinstance(obj_arg, ast.Constant) or not isinstance(obj_arg.value, str):
            issues.append(
                ValidationError(
                    file=file_path,
                    line=node.lineno,
                    message="lateimport() object argument must be a string literal",
                    suggestion="Use a string literal instead of a variable",
                    code="NON_LITERAL_LATEIMPORT",
                )
            )
            return issues

        # Resolve the import
        module = module_arg.value
        obj = obj_arg.value

        resolution = self.resolver.resolve(module, obj)

        if not resolution.exists:
            issues.append(
                ValidationError(
                    file=file_path,
                    line=node.lineno,
                    message=resolution.error or f"Failed to resolve {module}.{obj}",
                    suggestion="Check module and object names",
                    code="BROKEN_IMPORT",
                )
            )

        return issues

    def _validate_type_checking_block(
        self, file_path: Path, node: ast.If
    ) -> list[ValidationError | ValidationWarning]:
        """Validate TYPE_CHECKING block structure.

        Args:
            file_path: Path to file
            node: If node for TYPE_CHECKING block

        Returns:
            List of validation issues
        """
        issues: list[ValidationError | ValidationWarning] = []

        # Check that block only contains imports
        issues.extend(
            ValidationWarning(
                file=file_path,
                line=stmt.lineno,
                message="TYPE_CHECKING block should only contain imports",
                suggestion="Move non-import code outside TYPE_CHECKING block",
            )
            for stmt in node.body
            if not isinstance(stmt, (ast.Import, ast.ImportFrom))
        )
        return issues

    def _validate_all_declaration(
        self, file_path: Path, node: ast.Assign, tree: ast.AST
    ) -> list[ValidationError | ValidationWarning]:
        """Validate __all__ declaration.

        Args:
            file_path: Path to file
            node: Assignment node for __all__
            tree: Parsed AST tree for the file

        Returns:
            List of validation issues
        """
        issues: list[ValidationError | ValidationWarning] = []

        if not isinstance(node.value, ast.List):
            return issues

        # Get all names in __all__
        all_names = []
        all_names.extend(
            elt.value
            for elt in node.value.elts
            if isinstance(elt, ast.Constant) and isinstance(elt.value, str)
        )
        # Use provided tree to find defined names
        with contextlib.suppress(Exception):
            # Collect defined names
            defined_names = set()
            for node_item in ast.walk(tree):
                if isinstance(node_item, (ast.FunctionDef, ast.ClassDef)):
                    defined_names.add(node_item.name)
                elif isinstance(node_item, ast.Assign):
                    for target in node_item.targets:
                        if isinstance(target, ast.Name):
                            defined_names.add(target.id)

            # Check for undefined names in __all__
            issues.extend(
                ValidationError(
                    file=file_path,
                    line=node.lineno,
                    message=f"Name '{name}' in __all__ is not defined in module",
                    suggestion=f"Define '{name}' or remove from __all__",
                    code="UNDEFINED_IN_ALL",
                )
                for name in all_names
                if name not in defined_names and name != "__all__"
            )
        return issues

    def _is_type_checking_guard(self, node: ast.If) -> bool:
        """Check if node is a TYPE_CHECKING guard.

        Args:
            node: If statement node

        Returns:
            True if this is a TYPE_CHECKING guard
        """
        return isinstance(node.test, ast.Name) and node.test.id == "TYPE_CHECKING"

    def _is_type_checking_block(self) -> bool:
        """Check if we're currently in a TYPE_CHECKING block.

        This is a simplified check - it just looks for any TYPE_CHECKING if in the nodes.
        More sophisticated tracking would be needed for nested structures.

        Returns:
            True if there's a TYPE_CHECKING block in the nodes (simplified)
        """
        # For now, just return False - this is too simplistic
        # The real check needs to track nesting depth and current scope
        return False

    def _has_exports(self, tree: ast.AST) -> bool:
        """Check if module has any exports (classes, functions, etc.).

        Args:
            tree: Parsed AST

        Returns:
            True if module has exportable items
        """
        return any(
            isinstance(node, (ast.FunctionDef, ast.ClassDef)) and not node.name.startswith("_")
            for node in ast.walk(tree)
        )


__all__ = ["LateImportValidator"]
