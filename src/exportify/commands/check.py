# sourcery skip: avoid-global-variables
# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Implementation of the ``check`` command for validating exports and ``__all__`` declarations."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from cyclopts import App, Parameter

from exportify.commands.utils import (
    CONSOLE,
    collect_py_files,
    get_all_source_roots,
    load_rules,
    path_to_module,
    print_error,
    print_info,
    print_output_validation_concise,
    print_output_validation_json,
    print_output_validation_verbose,
    print_success,
    print_warning,
    resolve_checks,
)
from exportify.utils import detect_source_root


CheckCommand = App(
    "check", help="Validate exports and \\_\\_all\\_\\_ consistency", console=CONSOLE
)


def _display_all_modifications(result, added: str, removed: str, created: str):
    """Helper to display __all__ modifications in a human-friendly way."""
    if result.added:
        CONSOLE.print(f"{added}{result.added}")
    if result.removed:
        CONSOLE.print(f"{removed}{result.removed}")
    if result.created:
        CONSOLE.print(f"{created}{result.created}")


def _run_lateimports_check(
    *,
    py_files: list[Path],
    paths: tuple[Path, ...],
    shared_cache,
    source_root: Path,
    lateimports: bool | None,
    json_output: bool,
    verbose: bool,
) -> tuple[int, int]:
    """Run the lateimports check and return (errors, warnings)."""
    from exportify.utils import detect_lateimport_dependency
    from exportify.validator.validator import LateImportValidator

    if not detect_lateimport_dependency(source_root):
        if lateimports is True or verbose:
            print_info("Skipping lateimports check: 'lateimport' is not a project dependency")
        return 0, 0

    if verbose:
        print_info("Checking lateimport() / LateImport calls...")

    validator = LateImportValidator(project_root=Path.cwd(), cache=shared_cache)
    file_paths = py_files if paths else None
    results = validator.validate(file_paths=file_paths)

    import_errors = [e for e in results.errors if e.code != "CONSISTENCY_ERROR"]
    import_warnings = [
        w for w in results.warnings if not hasattr(w, "code") or w.code != "CONSISTENCY_ERROR"
    ]

    if json_output:
        print_output_validation_json(results)
    elif verbose:
        print_output_validation_verbose(results)
    else:
        print_output_validation_concise(results)

    return len(import_errors), len(import_warnings)


def _run_dynamic_imports_check(
    *,
    py_files: list[Path],
    paths: tuple[Path, ...],
    shared_cache,
    source_root: Path,
    json_output: bool,
    verbose: bool,
) -> tuple[int, int]:
    """Run the dynamic_imports check and return (errors, warnings)."""
    from exportify.common.types import ValidationReport
    from exportify.validator.validator import LateImportValidator

    if verbose:
        print_info("Checking _dynamic_imports in __init__.py files...")

    init_files = [f for f in py_files if f.name == "__init__.py"]
    if not init_files and paths:
        return 0, 0

    validator = LateImportValidator(project_root=source_root, cache=shared_cache)
    results = validator.validate(file_paths=init_files or None)

    import_resolution_codes = {
        "BROKEN_IMPORT",
        "INVALID_LATEIMPORT",
        "NON_LITERAL_LATEIMPORT",
        "SYNTAX_ERROR",
        "VALIDATION_ERROR",
        "UNDEFINED_IN_ALL",
    }
    dynamic_errors = [e for e in results.errors if e.code in import_resolution_codes]
    dynamic_warnings = list(results.warnings)

    if not json_output:
        filtered = ValidationReport(
            errors=dynamic_errors,
            warnings=dynamic_warnings,
            metrics=results.metrics,
            success=not dynamic_errors,
        )
        if verbose:
            print_output_validation_verbose(filtered)
        else:
            print_output_validation_concise(filtered)

    return len(dynamic_errors), len(dynamic_warnings)


def _run_module_all_check(
    *, py_files: list[Path], source_root: Path, rules, json_output: bool, verbose: bool
) -> tuple[int, int]:
    """Run the module_all check and return (errors, warnings)."""
    from exportify.export_manager.module_all import check_module_all

    if verbose:
        print_info("Checking __all__ in regular modules...")

    regular_files = [f for f in py_files if f.name != "__init__.py"]
    module_all_errors = 0
    module_all_warnings = 0

    for py_file in regular_files:
        module_path = path_to_module(py_file.with_suffix(""), source_root)
        for issue in check_module_all(py_file, module_path, rules):
            if issue.issue_type == "no_all":
                module_all_warnings += 1
                if not json_output:
                    print_warning(issue.message)
            else:
                module_all_errors += 1
                if not json_output:
                    print_error(issue.message)

    if not json_output and module_all_errors == 0 and module_all_warnings == 0 and verbose:
        print_success("All regular modules have consistent __all__")

    return module_all_errors, module_all_warnings


def _run_package_all_check(
    *,
    py_files: list[Path],
    paths: tuple[Path, ...],
    shared_cache,
    source_root: Path,
    json_output: bool,
    verbose: bool,
) -> tuple[int, int]:
    """Run the package_all check and return (errors, warnings)."""
    from exportify.common.types import ValidationReport
    from exportify.validator.validator import LateImportValidator

    if verbose:
        print_info("Checking __all__ and exports in __init__.py files...")

    init_files = [f for f in py_files if f.name == "__init__.py"]
    if not init_files and paths:
        return 0, 0

    validator = LateImportValidator(project_root=source_root, cache=shared_cache)
    results = validator.validate(file_paths=init_files or None)

    consistency_errors = [e for e in results.errors if e.code == "CONSISTENCY_ERROR"]
    consistency_warnings = list(results.warnings)

    if not json_output:
        filtered = ValidationReport(
            errors=consistency_errors,
            warnings=consistency_warnings,
            metrics=results.metrics,
            success=not consistency_errors,
        )
        if verbose:
            print_output_validation_verbose(filtered)
        else:
            print_output_validation_concise(filtered)

    return len(consistency_errors), len(consistency_warnings)


def _print_final_status(total_errors: int, total_warnings: int, *, strict: bool) -> None:
    """Print final check status and exit if needed."""
    CONSOLE.print()
    if total_errors == 0 and total_warnings == 0:
        print_success("All checks passed")
    elif total_errors == 0:
        print_warning(f"Checks passed with {total_warnings} warning(s)")
    else:
        print_error(f"Checks failed: {total_errors} error(s), {total_warnings} warning(s)")
    CONSOLE.print()

    if total_errors > 0 or (strict and total_warnings > 0):
        raise SystemExit(1)


@CheckCommand.default
def check(
    *paths: Annotated[Path, Parameter(help="Files or directories to check")],
    source: Annotated[Path | None, Parameter(help="Source root directory")] = None,
    lateimports: Annotated[
        bool | None, Parameter(help="Validate lateimport() / LateImport call targets")
    ] = None,
    dynamic_imports: Annotated[
        bool | None,
        Parameter(
            name="dynamic-imports",
            help="Check \\_dynamic\\_imports entries resolve and match \\_\\_all\\_\\_",
        ),
    ] = None,
    module_all: Annotated[
        bool | None,
        Parameter(name="module-all", help="Check \\_\\_all\\_\\_ against export rules in modules"),
    ] = None,
    package_all: Annotated[
        bool | None,
        Parameter(
            name="package-all",
            help="Check \\_\\_all\\_\\_ and exports in \\_\\_init\\_\\_.py files",
        ),
    ] = None,
    strict: Annotated[bool, Parameter(help="Exit non-zero on warnings")] = False,
    json_output: Annotated[bool, Parameter(name="json", help="Output results as JSON")] = False,
    verbose: Annotated[bool, Parameter(help="Show detailed output")] = False,
) -> None:
    """Validate exports and __all__ declarations for consistency.

    Checks:
    - lateimport() / LateImport calls resolve to real modules (--lateimports)
    - _dynamic_imports entries in __init__.py files resolve correctly and match __all__ (--dynamic-imports)
    - __all__ in regular modules matches configured export rules (--module-all)
    - __all__ and exports in __init__.py files are consistent with each other (--package-all)

    Pass one or more flags explicitly to run only those checks.
    Use --no-X flags to skip specific checks while running the rest.
    Omit all flags to run every check.

    Note: The lateimports check is automatically skipped if 'lateimport' is not
    listed as a project dependency (it's an opt-in library).

    Examples:
        exportify check
        exportify check --module-all
        exportify check --no-lateimports
        exportify check --strict
        exportify check src/mypackage/core
        exportify check --json
    """
    from exportify.common.cache import JSONAnalysisCache

    checks_to_run = resolve_checks(
        {"lateimports", "dynamic_imports", "module_all", "package_all"},
        lateimports=lateimports,
        dynamic_imports=dynamic_imports,
        module_all=module_all,
        package_all=package_all,
    )

    if not json_output:
        print_info("Running checks...")
        CONSOLE.print()

    source_root = source or detect_source_root()
    rules = load_rules(verbose=verbose)
    shared_cache = JSONAnalysisCache()

    all_source_roots = get_all_source_roots(source)

    # Collect explicit files once (when user specified paths)
    explicit_py_files = collect_py_files(paths, source) if paths else []

    results: list[tuple[int, int]] = []

    for root in all_source_roots:
        if root != source_root and not json_output:
            CONSOLE.print()
            print_info(f"Checking additional source: {root}...")
            CONSOLE.print()

        root_py_files = (
            [f for f in explicit_py_files if f.is_relative_to(root)]
            if paths
            else collect_py_files((), root)
        )

        if "lateimports" in checks_to_run:
            results.append(
                _run_lateimports_check(
                    py_files=root_py_files,
                    paths=paths,
                    shared_cache=shared_cache,
                    source_root=root,
                    lateimports=lateimports,
                    json_output=json_output,
                    verbose=verbose,
                )
            )

        if "dynamic_imports" in checks_to_run:
            results.append(
                _run_dynamic_imports_check(
                    py_files=root_py_files,
                    paths=paths,
                    source_root=root,
                    shared_cache=shared_cache,
                    json_output=json_output,
                    verbose=verbose,
                )
            )

        if "module_all" in checks_to_run:
            results.append(
                _run_module_all_check(
                    py_files=root_py_files,
                    source_root=root,
                    rules=rules,
                    json_output=json_output,
                    verbose=verbose,
                )
            )

        if "package_all" in checks_to_run:
            results.append(
                _run_package_all_check(
                    py_files=root_py_files,
                    paths=paths,
                    shared_cache=shared_cache,
                    source_root=root,
                    json_output=json_output,
                    verbose=verbose,
                )
            )

    total_errors = sum(e for e, _ in results)
    total_warnings = sum(w for _, w in results)

    _print_final_status(total_errors, total_warnings, strict=strict)


if __name__ == "__main__":
    CheckCommand()


__all__ = ("CheckCommand",)
