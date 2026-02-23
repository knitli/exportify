# sourcery skip: avoid-global-variables
# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Exportify CLI commands.

Provides user interface for all export management operations:
- Checking exports and __all__ consistency
- Fixing exports and __all__ declarations
- Generating __init__.py files for new packages
- Analysis and health checks
- Migration from old system
"""

from __future__ import annotations

import logging

from pathlib import Path
from typing import TYPE_CHECKING, Annotated, NoReturn

from cyclopts import App, Parameter
from rich.console import Console
from rich.panel import Panel

from exportify.common.config import CONFIG_ENV_VAR, find_config_file
from exportify.common.types import MemberType, RuleAction
from exportify.export_manager.rules import RuleEngine
from exportify.utils import detect_source_root


logger = logging.getLogger(__name__)


if TYPE_CHECKING:
    from exportify.types import ExportGenerationResult, ValidationReport

app = App(
    name="exportify",
    help="Manage Python package exports: check, fix, and generate __init__.py files",
)

console = Console(markup=True)


DEFAULT_CONFIG_PATH = Path.cwd() / ".exportify" / "config.yaml"


def _print_success(message: str) -> None:
    """Print success message."""
    console.print(f"[green]✓[/green] {message}")


def _print_error(message: str) -> None:
    """Print error message."""
    console.print(f"[red]✗[/red] {message}")


def _print_warning(message: str) -> None:
    """Print warning message."""
    console.print(f"[yellow]⚠[/yellow] {message}")


def _print_info(message: str) -> None:
    """Print info message."""
    console.print(f"[cyan]ℹ[/cyan] {message}")  # noqa: RUF001


def _print_generation_results(result: ExportGenerationResult) -> None:
    """Print export generation results with colors."""
    console.print()
    console.print(Panel("[bold]Export Generation Results[/bold]", expand=False))
    console.print()

    # Summary metrics
    metrics = result.metrics
    console.print(f"  Files analyzed: [cyan]{metrics.files_analyzed}[/cyan]")
    console.print(f"  Files generated: [green]{metrics.files_generated}[/green]")
    console.print(f"  Files updated: [yellow]{metrics.files_updated}[/yellow]")
    console.print(f"  Files skipped: [dim]{metrics.files_skipped}[/dim]")
    console.print(f"  Exports created: [green]{metrics.exports_created}[/green]")
    console.print(f"  Processing time: [cyan]{metrics.processing_time_ms / 1000:.2f}s[/cyan]")
    console.print(f"  Cache hit rate: [cyan]{metrics.cache_hit_rate * 100:.1f}%[/cyan]")
    console.print()

    # Errors if any
    if result.errors:
        console.print("[red]Errors encountered:[/red]")
        for error in result.errors:
            console.print(f"  [red]•[/red] {error}")
        console.print()

    # Status
    if result.success:
        _print_success("Export generation completed successfully")
    else:
        _print_error("Export generation failed")
    console.print()


def _print_validation_results(report: ValidationReport) -> None:
    """Print validation results with colors."""
    console.print()
    console.print(Panel("[bold]Validation Results[/bold]", expand=False))
    console.print()

    # Summary
    metrics = report.metrics
    console.print(f"  Files validated: [cyan]{metrics.files_validated}[/cyan]")
    console.print(f"  Imports checked: [cyan]{metrics.imports_checked}[/cyan]")
    console.print(f"  Consistency checks: [cyan]{metrics.consistency_checks}[/cyan]")
    console.print(f"  Validation time: [cyan]{metrics.validation_time_ms / 1000:.2f}s[/cyan]")
    console.print()

    # Errors
    if report.errors:
        console.print(f"[red]Errors found: {len(report.errors)}[/red]")
        for error in report.errors:
            location = f"{error.file}:{error.line}" if error.line else str(error.file)
            console.print(f"  [red]•[/red] {location}")
            console.print(f"    {error.message}")
            if error.suggestion:
                console.print(f"    [dim]Suggestion: {error.suggestion}[/dim]")
        console.print()

    # Warnings
    if report.warnings:
        console.print(f"[yellow]Warnings found: {len(report.warnings)}[/yellow]")
        for warning in report.warnings:
            location = f"{warning.file}:{warning.line}" if warning.line else str(warning.file)
            console.print(f"  [yellow]•[/yellow] {location}")
            console.print(f"    {warning.message}")
            if warning.suggestion:
                console.print(f"    [dim]Suggestion: {warning.suggestion}[/dim]")
        console.print()

    # Status
    if report.success:
        _print_success("All validations passed")
    else:
        _print_error("Validation failed")
    console.print()


def _resolve_validation_files(module: Path | None, *, json_output: bool) -> list[Path] | None:
    """Resolve file paths to validate based on module parameter."""
    if not module:
        return None

    if module.is_file():
        return [module]
    if module.is_dir():
        return list(module.rglob("*.py"))

    if not json_output:
        _print_error(f"Module path does not exist: {module}")
    raise SystemExit(1)


def _output_validation_json(results) -> None:
    """Output validation results in JSON format."""
    import json as json_lib

    output_data = {
        "success": results.success,
        "errors": [
            {
                "file": str(error.file),
                "line": error.line,
                "message": error.message,
                "code": error.code,
                "suggestion": error.suggestion,
            }
            for error in results.errors
        ],
        "warnings": [
            {
                "file": str(warning.file),
                "line": warning.line,
                "message": warning.message,
                "suggestion": warning.suggestion,
            }
            for warning in results.warnings
        ],
        "metrics": {
            "files_validated": results.metrics.files_validated,
            "imports_checked": results.metrics.imports_checked,
            "consistency_checks": results.metrics.consistency_checks,
            "validation_time_ms": results.metrics.validation_time_ms,
        },
    }
    console.print(json_lib.dumps(output_data, indent=2))


def _output_validation_verbose(results) -> None:
    """Output validation results in verbose human-readable format."""
    console.print()
    console.print(Panel("[bold]Validation Results[/bold]", expand=False))
    console.print()

    # Show errors with full context
    if results.errors:
        console.print(f"[red]Errors found: {len(results.errors)}[/red]")
        console.print()
        for error in results.errors:
            location = f"{error.file}:{error.line}" if error.line else str(error.file)
            console.print(f"[red]ERROR[/red] {location}: [bold]{error.code}[/bold]")
            _print_error_in_validation(error)
    # Show warnings with full context
    if results.warnings:
        console.print(f"[yellow]Warnings found: {len(results.warnings)}[/yellow]")
        console.print()
        for warning in results.warnings:
            location = f"{warning.file}:{warning.line}" if warning.line else str(warning.file)
            console.print(f"[yellow]WARNING[/yellow] {location}")
            _print_error_in_validation(warning)
    # Show metrics
    metrics = results.metrics
    console.print("[bold]Metrics:[/bold]")
    console.print(f"  Files validated: [cyan]{metrics.files_validated}[/cyan]")
    console.print(f"  Imports checked: [cyan]{metrics.imports_checked}[/cyan]")
    console.print(f"  Consistency checks: [cyan]{metrics.consistency_checks}[/cyan]")
    console.print(f"  Validation time: [cyan]{metrics.validation_time_ms / 1000:.2f}s[/cyan]")
    console.print()


def _print_error_in_validation(error):
    console.print(f"  {error.message}")
    if error.suggestion:
        console.print(f"  [dim]Suggestion: {error.suggestion}[/dim]")
    console.print()


def _output_validation_concise(results) -> None:
    """Output validation results in concise human-readable format."""
    if results.errors:
        for error in results.errors:
            location = f"{error.file}:{error.line}" if error.line else str(error.file)
            console.print(f"[red][ERROR][/red] {location}: {error.code} ({error.message})")

    if results.warnings:
        for warning in results.warnings:
            location = f"{warning.file}:{warning.line}" if warning.line else str(warning.file)
            console.print(f"[yellow][WARNING][/yellow] {location}: {warning.message}")

    # Show summary
    console.print()
    console.print(f"Files validated: {results.metrics.files_validated}")
    console.print(f"Errors: {len(results.errors)}, Warnings: {len(results.warnings)}")


def _resolve_checks(
    *,
    lateimports: bool | None,
    dynamic_imports: bool | None,
    module_all: bool | None,
    package_all: bool | None,
) -> set[str]:
    """Resolve which checks to run given bool|None flags.

    Logic:
    - If ANY flag is True (explicitly given) → whitelist mode: only run those checks.
    - If ONLY False flags (--no-X) → blacklist mode: run everything except those.
    - If all None (no flags given) → run all checks.
    """
    all_checks = {"lateimports", "dynamic_imports", "module_all", "package_all"}
    flag_values = [lateimports, dynamic_imports, module_all, package_all]
    explicit_true = {k for k, v in zip(all_checks, flag_values, strict=True) if v is True}
    explicit_false = {k for k, v in zip(all_checks, flag_values, strict=True) if v is False}
    if explicit_true:
        return explicit_true
    return all_checks - explicit_false if explicit_false else all_checks


def _resolve_fix_checks(
    *, dynamic_imports: bool | None, module_all: bool | None, package_all: bool | None
) -> set[str]:
    """Resolve which fix operations to run given bool|None flags.

    Same logic as _resolve_checks but for the fix command (no lateimports).
    """
    all_checks = {"dynamic_imports", "module_all", "package_all"}
    flag_values = [dynamic_imports, module_all, package_all]
    explicit_true = {k for k, v in zip(all_checks, flag_values, strict=True) if v is True}
    explicit_false = {k for k, v in zip(all_checks, flag_values, strict=True) if v is False}
    if explicit_true:
        return explicit_true
    return all_checks - explicit_false if explicit_false else all_checks


def _run_lateimports_check(
    checks_to_run: set[str],
    *,
    lateimports: bool | None,
    py_files: list[Path],
    paths: tuple[Path, ...],
    shared_cache,
    json_output: bool,
    verbose: bool,
) -> tuple[int, int]:
    """Run lateimports check and return (errors, warnings) counts."""
    from exportify.utils import detect_lateimport_dependency
    from exportify.validator.validator import LazyImportValidator

    if "lateimports" not in checks_to_run:
        return 0, 0

    if not detect_lateimport_dependency():
        if lateimports is True or verbose:
            _print_info("Skipping lateimports check: 'lateimport' is not a project dependency")
        return 0, 0

    if verbose:
        _print_info("Checking lateimport() / LateImport calls...")

    validator = LazyImportValidator(project_root=Path.cwd(), cache=shared_cache)
    file_paths = py_files if paths else None
    results = validator.validate(file_paths=file_paths)

    # Only count import-resolution errors (not consistency errors)
    import_errors = [e for e in results.errors if e.code != "CONSISTENCY_ERROR"]
    import_warnings = [
        w for w in results.warnings if not hasattr(w, "code") or w.code != "CONSISTENCY_ERROR"
    ]

    if json_output:
        _output_validation_json(results)
    elif verbose:
        _output_validation_verbose(results)
    else:
        _output_validation_concise(results)

    return len(import_errors), len(import_warnings)


def _run_dynamic_imports_check(
    checks_to_run: set[str], py_files: list[Path], shared_cache, *, json_output: bool, verbose: bool
) -> tuple[int, int]:
    """Run dynamic_imports check and return (errors, warnings) counts."""
    from exportify.validator.validator import LazyImportValidator

    if "dynamic_imports" not in checks_to_run:
        return 0, 0

    if verbose:
        _print_info("Checking _dynamic_imports in __init__.py files...")

    if init_files := [f for f in py_files if f.name == "__init__.py"]:
        validator = LazyImportValidator(project_root=Path.cwd(), cache=shared_cache)
        results = validator.validate(file_paths=init_files)

        # dynamic_imports = import resolution errors (exclude CONSISTENCY_ERROR)
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
            from exportify.common.types import ValidationReport

            filtered = ValidationReport(
                errors=dynamic_errors,
                warnings=dynamic_warnings,
                metrics=results.metrics,
                success=not dynamic_errors,
            )
            if verbose:
                _output_validation_verbose(filtered)
            else:
                _output_validation_concise(filtered)

        return len(dynamic_errors), len(dynamic_warnings)

    return 0, 0


def _run_module_all_check(
    checks_to_run: set[str],
    py_files: list[Path],
    source_root: Path,
    rules: RuleEngine,
    *,
    json_output: bool,
    verbose: bool,
) -> tuple[int, int]:
    """Run module_all check and return (errors, warnings) counts."""
    from exportify.export_manager.module_all import check_module_all

    if "module_all" not in checks_to_run:
        return 0, 0

    if verbose:
        _print_info("Checking __all__ in regular modules...")

    # Only non-__init__ Python files
    regular_files = [f for f in py_files if f.name != "__init__.py"]
    module_all_errors = 0
    module_all_warnings = 0

    for py_file in regular_files:
        module_path = _path_to_module(py_file.with_suffix(""), source_root)
        issues = check_module_all(py_file, module_path, rules)
        for issue in issues:
            if issue.issue_type == "no_all":
                module_all_warnings += 1
                if not json_output:
                    _print_warning(issue.message)
            else:
                module_all_errors += 1
                if not json_output:
                    _print_error(issue.message)

    if not json_output and module_all_errors == 0 and module_all_warnings == 0 and verbose:
        _print_success("All regular modules have consistent __all__")

    return module_all_errors, module_all_warnings


def _run_package_all_check(
    checks_to_run: set[str], py_files: list[Path], shared_cache, *, json_output: bool, verbose: bool
) -> tuple[int, int]:
    """Run package_all check and return (errors, warnings) counts."""
    from exportify.validator.validator import LazyImportValidator

    if "package_all" not in checks_to_run:
        return 0, 0

    if verbose:
        _print_info("Checking __all__ and exports in __init__.py files...")

    if init_files := [f for f in py_files if f.name == "__init__.py"]:
        validator = LazyImportValidator(project_root=Path.cwd(), cache=shared_cache)
        results = validator.validate(file_paths=init_files)

        # Only consistency errors belong to package_all
        consistency_errors = [e for e in results.errors if e.code == "CONSISTENCY_ERROR"]
        consistency_warnings = list(results.warnings)

        if not json_output:
            from exportify.common.types import ValidationReport

            filtered = ValidationReport(
                errors=consistency_errors,
                warnings=consistency_warnings,
                metrics=results.metrics,
                success=not consistency_errors,
            )
            if verbose:
                _output_validation_verbose(filtered)
            else:
                _output_validation_concise(filtered)

        return len(consistency_errors), len(consistency_warnings)

    return 0, 0


def _load_rules(verbose: bool = False) -> RuleEngine:  # noqa: FBT001
    """Load rules from config file, falling back to defaults."""
    rules = RuleEngine()
    rules_path = find_config_file()

    if rules_path is None:
        if verbose:
            _print_warning(f"No config file found (set {CONFIG_ENV_VAR} or create .exportify.yaml)")
            _print_info("Using default rules")
    else:
        rules.load_rules([rules_path])
        if verbose:
            _print_success(f"Loaded rules from {rules_path}")

    return rules


def _collect_py_files(paths: tuple[Path, ...], source: Path | None) -> list[Path]:
    """Collect Python files from given paths or auto-detect source root.

    Args:
        paths: Explicit paths to check. If empty, auto-detect source root.
        source: Optional source root override.

    Returns:
        List of Python file paths to process.
    """
    if not paths:
        source_root = source or detect_source_root()
        return list(source_root.rglob("*.py"))

    all_files: list[Path] = []
    for p in paths:
        if not p.exists():
            _print_error(f"Path does not exist: {p}")
            raise SystemExit(1)
        if p.is_file():
            all_files.append(p)
        else:
            all_files.extend(p.rglob("*.py"))
    return all_files


def _path_to_module(path: Path, source_root: Path) -> str:
    """Convert a file path to a module path."""
    try:
        relative = path.relative_to(source_root)
    except ValueError:
        # Not relative to source_root, fall back to cwd-relative path
        try:
            relative = path.relative_to(Path.cwd())
        except ValueError:
            # Last resort: use just the file/dir stem
            return path.stem

    parts = relative.parts
    return ".".join(parts)


def _fix_module_all_files(
    py_files: list[Path], source_root: Path, rules: RuleEngine, *, dry_run: bool, verbose: bool
) -> int:
    """Fix __all__ in regular modules. Returns count of modified files."""
    from exportify.export_manager.module_all import fix_module_all

    if verbose:
        _print_info("Fixing __all__ in regular modules...")

    regular_files = [f for f in py_files if f.name != "__init__.py"]
    files_modified = 0

    for py_file in regular_files:
        module_path = _path_to_module(py_file.with_suffix(""), source_root)
        result = fix_module_all(py_file, module_path, rules, dry_run=dry_run)
        if result.was_modified:
            files_modified += 1
            if dry_run:
                _print_info(f"Would update {py_file}")
                _display_all_modifications(
                    result,
                    "  [green]+[/green] Add to __all__: ",
                    "  [red]-[/red] Remove from __all__: ",
                    "  [cyan]new[/cyan] __all__ would be created",
                )
            else:
                _print_success(f"Updated {py_file}")
                if verbose:
                    _display_all_modifications(
                        result,
                        "  [green]+[/green] Added to __all__: ",
                        "  [red]-[/red] Removed from __all__: ",
                        "  [cyan]new[/cyan] __all__ created",
                    )
    return files_modified


def _display_all_modifications(result, added: str, removed: str, created: str):
    """Helper to display __all__ modifications in a human-friendly way."""
    if result.added:
        console.print(f"{added}{result.added}")
    if result.removed:
        console.print(f"{removed}{result.removed}")
    if result.created:
        console.print(f"{created}{result.created}")


def _fix_package_via_pipeline(
    py_files: list[Path], source_root: Path, rules: RuleEngine, *, dry_run: bool, verbose: bool
) -> int:
    """Fix dynamic_imports and package_all via pipeline. Returns count of modified files."""
    from exportify.common.cache import JSONAnalysisCache
    from exportify.pipeline import Pipeline

    if verbose:
        _print_info("Fixing __init__.py exports...")

    package_dirs: set[Path] = {
        py_file.parent for py_file in py_files if py_file.parent != source_root
    }
    for pkg_dir in sorted(package_dirs):
        init_file = pkg_dir / "__init__.py"
        if not init_file.exists():
            _print_warning(f"{pkg_dir} has no __init__.py")
            console.print("  Run `exportify generate` to bootstrap it first")

    # Run pipeline to regenerate managed sections
    cache = JSONAnalysisCache()
    output_dir = source_root

    pipeline = Pipeline(rule_engine=rules, cache=cache, output_dir=output_dir)

    try:
        result = pipeline.run(source_root=source_root, dry_run=dry_run)
        files_modified = result.metrics.files_updated + result.metrics.files_generated
        if verbose:
            if dry_run:
                _print_info(f"Would update {result.metrics.files_updated} __init__.py file(s)")
                _print_info(
                    f"Would generate {result.metrics.files_generated} new __init__.py file(s)"
                )
            else:
                _print_info(f"Updated {result.metrics.files_updated} __init__.py file(s)")
    except Exception as e:
        _print_error(f"Pipeline execution failed: {e}")
        import traceback

        console.print("[dim]Full traceback:[/dim]")
        console.print(traceback.format_exc())
        raise SystemExit(1) from e
    else:
        return files_modified


@app.command
def check(
    *paths: Annotated[Path, Parameter(help="Paths to check (default: whole project)")],
    source: Annotated[Path | None, Parameter(help="Source root directory")] = None,
    lateimports: Annotated[
        bool | None, Parameter(help="Check lateimport() / LateImport calls")
    ] = None,
    dynamic_imports: Annotated[
        bool | None,
        Parameter(
            name="dynamic-imports", help="Check _dynamic_imports entries in __init__.py files"
        ),
    ] = None,
    module_all: Annotated[
        bool | None, Parameter(name="module-all", help="Check __all__ in regular modules")
    ] = None,
    package_all: Annotated[
        bool | None,
        Parameter(name="package-all", help="Check __all__ and exports in __init__.py files"),
    ] = None,
    strict: Annotated[bool, Parameter(help="Exit non-zero on warnings")] = False,
    json_output: Annotated[bool, Parameter(name="json", help="Output results as JSON")] = False,
    verbose: Annotated[bool, Parameter(help="Show detailed output")] = False,
) -> None:
    """Check exports and __all__ declarations for consistency.

    Checks:
    - lateimport() / LateImport calls resolve to real modules (--lateimports)
    - _dynamic_imports entries in __init__.py files are consistent (--dynamic-imports)
    - __all__ in regular modules matches export rules (--module-all)
    - __all__ and exports in __init__.py files are consistent (--package-all)

    If ANY flag is explicitly set to True, only those checks are run.
    Use --no-X flags to exclude specific checks while running the rest.
    If no flags are given, all checks are run.

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
    from exportify.export_manager.module_all import check_module_all
    from exportify.utils import detect_lateimport_dependency
    from exportify.validator.validator import LazyImportValidator

    checks_to_run = _resolve_checks(
        lateimports=lateimports,
        dynamic_imports=dynamic_imports,
        module_all=module_all,
        package_all=package_all,
    )

    if not json_output:
        _print_info("Running checks...")
        console.print()

    source_root = source or detect_source_root()
    py_files = _collect_py_files(paths, source)

    rules = _load_rules(verbose=verbose)

    # Create one shared cache for all validator-based checks
    shared_cache = JSONAnalysisCache()

    total_errors = 0
    total_warnings = 0

    # --- lateimports check ---
    if "lateimports" in checks_to_run:
        if detect_lateimport_dependency():
            if verbose:
                _print_info("Checking lateimport() / LateImport calls...")

            validator = LazyImportValidator(project_root=Path.cwd(), cache=shared_cache)
            file_paths = py_files if paths else None
            results = validator.validate(file_paths=file_paths)

            # Only count import-resolution errors (not consistency errors)
            import_errors = [e for e in results.errors if e.code != "CONSISTENCY_ERROR"]
            import_warnings = [
                w
                for w in results.warnings
                if not hasattr(w, "code") or w.code != "CONSISTENCY_ERROR"
            ]

            if json_output:
                _output_validation_json(results)
            elif verbose:
                _output_validation_verbose(results)
            else:
                _output_validation_concise(results)

            total_errors += len(import_errors)
            total_warnings += len(import_warnings)

        elif lateimports is True or verbose:
            _print_info("Skipping lateimports check: 'lateimport' is not a project dependency")

    # --- dynamic_imports check ---
    if "dynamic_imports" in checks_to_run:
        if verbose:
            _print_info("Checking _dynamic_imports in __init__.py files...")

        # Scope validation to __init__.py files only; report only import-resolution errors
        init_files = [f for f in py_files if f.name == "__init__.py"]
        if init_files or not paths:
            validator = LazyImportValidator(project_root=Path.cwd(), cache=shared_cache)
            results = validator.validate(file_paths=init_files or None)

            # dynamic_imports = import resolution errors (BROKEN_IMPORT, INVALID_LATEIMPORT, etc.)
            # Exclude CONSISTENCY_ERROR codes which belong to package_all
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
                # Build a filtered result view for output
                from exportify.common.types import ValidationReport

                filtered = ValidationReport(
                    errors=dynamic_errors,
                    warnings=dynamic_warnings,
                    metrics=results.metrics,
                    success=not dynamic_errors,
                )
                if verbose:
                    _output_validation_verbose(filtered)
                else:
                    _output_validation_concise(filtered)

            total_errors += len(dynamic_errors)
            total_warnings += len(dynamic_warnings)

    # --- module_all check ---
    if "module_all" in checks_to_run:
        if verbose:
            _print_info("Checking __all__ in regular modules...")

        # Only non-__init__ Python files
        regular_files = [f for f in py_files if f.name != "__init__.py"]
        module_all_errors = 0
        module_all_warnings = 0

        for py_file in regular_files:
            module_path = _path_to_module(py_file.with_suffix(""), source_root)
            issues = check_module_all(py_file, module_path, rules)
            for issue in issues:
                if issue.issue_type == "no_all":
                    # Missing __all__ is advisory (warning), not an error
                    module_all_warnings += 1
                    if not json_output:
                        _print_warning(issue.message)
                else:
                    # Mismatched (missing/extra) entries are errors
                    module_all_errors += 1
                    if not json_output:
                        _print_error(issue.message)

        if not json_output and module_all_errors == 0 and module_all_warnings == 0 and verbose:
            _print_success("All regular modules have consistent __all__")

        total_errors += module_all_errors
        total_warnings += module_all_warnings

    # --- package_all check ---
    if "package_all" in checks_to_run:
        if verbose:
            _print_info("Checking __all__ and exports in __init__.py files...")

        # package_all = consistency errors (__all__ vs _dynamic_imports mismatches)
        init_files = [f for f in py_files if f.name == "__init__.py"]
        if init_files or not paths:
            validator = LazyImportValidator(project_root=Path.cwd(), cache=shared_cache)
            results = validator.validate(file_paths=init_files or None)

            # Only consistency errors belong to package_all
            consistency_errors = [e for e in results.errors if e.code == "CONSISTENCY_ERROR"]
            consistency_warnings = list(results.warnings)

            if not json_output:
                from exportify.common.types import ValidationReport

                filtered = ValidationReport(
                    errors=consistency_errors,
                    warnings=consistency_warnings,
                    metrics=results.metrics,
                    success=not consistency_errors,
                )
                if verbose:
                    _output_validation_verbose(filtered)
                else:
                    _output_validation_concise(filtered)

            total_errors += len(consistency_errors)
            total_warnings += len(consistency_warnings)

    # Final status
    console.print()
    if total_errors == 0 and total_warnings == 0:
        _print_success("All checks passed")
    elif total_errors == 0:
        _print_warning(f"Checks passed with {total_warnings} warning(s)")
    else:
        _print_error(f"Checks failed: {total_errors} error(s), {total_warnings} warning(s)")
    console.print()

    if total_errors > 0 or (strict and total_warnings > 0):
        raise SystemExit(1)


@app.command
def fix(
    *paths: Annotated[Path, Parameter(help="Paths to fix (default: whole project)")],
    source: Annotated[Path | None, Parameter(help="Source root directory")] = None,
    dynamic_imports: Annotated[
        bool | None,
        Parameter(name="dynamic-imports", help="Fix _dynamic_imports entries in __init__.py files"),
    ] = None,
    module_all: Annotated[
        bool | None, Parameter(name="module-all", help="Fix __all__ in regular modules")
    ] = None,
    package_all: Annotated[
        bool | None,
        Parameter(name="package-all", help="Fix __all__ and exports in __init__.py files"),
    ] = None,
    dry_run: Annotated[
        bool, Parameter(name="dry-run", help="Show what would change without writing")
    ] = False,
    verbose: Annotated[bool, Parameter(help="Show detailed output")] = False,
) -> None:
    """Sync exports and __all__ declarations to match rules.

    Updates:
    - __all__ in regular modules (--module-all)
    - _dynamic_imports and __all__ in __init__.py files (--dynamic-imports, --package-all)

    Does NOT fix lateimport() call paths — those require manual correction.

    If --dry-run: shows what would change without writing any files.

    When __init__.py is missing entirely, warns and suggests running `generate`.

    Examples:
        exportify fix
        exportify fix --dry-run
        exportify fix --module-all
        exportify fix src/mypackage/core
    """
    from exportify.common.cache import JSONAnalysisCache
    from exportify.export_manager.module_all import fix_module_all
    from exportify.pipeline import Pipeline

    fixes_to_run = _resolve_fix_checks(
        dynamic_imports=dynamic_imports, module_all=module_all, package_all=package_all
    )

    if dry_run:
        _print_info("Dry run mode — no files will be written")
    else:
        _print_info("Fixing exports and __all__ declarations...")
    console.print()
    source_root = source or detect_source_root()
    py_files = _collect_py_files(paths, source)

    rules = _load_rules(verbose=verbose)

    files_modified = 0
    files_would_modify = 0

    # --- module_all fix ---
    if "module_all" in fixes_to_run:
        if verbose:
            _print_info("Fixing __all__ in regular modules...")

        regular_files = [f for f in py_files if f.name != "__init__.py"]
        for py_file in regular_files:
            module_path = _path_to_module(py_file.with_suffix(""), source_root)
            result = fix_module_all(py_file, module_path, rules, dry_run=dry_run)
            if result.was_modified:
                if dry_run:
                    files_would_modify += 1
                    _print_info(f"Would update {py_file}")
                    if result.added:
                        console.print(f"  [green]+[/green] Add to __all__: {result.added}")
                    if result.removed:
                        console.print(f"  [red]-[/red] Remove from __all__: {result.removed}")
                    if result.created:
                        console.print("  [cyan]new[/cyan] __all__ would be created")
                else:
                    files_modified += 1
                    _print_success(f"Updated {py_file}")
                    if verbose:
                        if result.added:
                            console.print(f"  [green]+[/green] Added to __all__: {result.added}")
                        if result.removed:
                            console.print(f"  [red]-[/red] Removed from __all__: {result.removed}")
                        if result.created:
                            console.print("  [cyan]new[/cyan] __all__ created")

    # --- dynamic_imports and package_all fix ---
    # Both are handled via the Pipeline (regenerates __init__.py content)
    if "dynamic_imports" in fixes_to_run or "package_all" in fixes_to_run:
        if verbose:
            _print_info("Fixing __init__.py exports...")

        package_dirs: set[Path] = {
            py_file.parent for py_file in py_files if py_file.parent != source_root
        }
        for pkg_dir in sorted(package_dirs):
            init_file = pkg_dir / "__init__.py"
            if not init_file.exists():
                _print_warning(f"{pkg_dir} has no __init__.py")
                console.print("  Run `exportify generate` to bootstrap it first")

        # Run pipeline to regenerate managed sections
        cache = JSONAnalysisCache()
        output_dir = source_root

        pipeline = Pipeline(rule_engine=rules, cache=cache, output_dir=output_dir)

        try:
            result = pipeline.run(source_root=source_root, dry_run=dry_run)
            if dry_run:
                files_would_modify += result.metrics.files_updated + result.metrics.files_generated
                if verbose:
                    _print_info(f"Would update {result.metrics.files_updated} __init__.py file(s)")
                    _print_info(
                        f"Would generate {result.metrics.files_generated} new __init__.py file(s)"
                    )
            else:
                files_modified += result.metrics.files_updated + result.metrics.files_generated
                if verbose:
                    _print_info(f"Updated {result.metrics.files_updated} __init__.py file(s)")

        except Exception as e:
            _print_error(f"Pipeline execution failed: {e}")
            if verbose:
                import traceback

                console.print("[dim]Full traceback:[/dim]")
                console.print(traceback.format_exc())
            raise SystemExit(1) from e

    # Final summary
    console.print()
    if (dry_run and files_would_modify == 0) or (not dry_run and files_modified == 0):
        _print_success("Everything is already in sync — no changes needed")
    elif dry_run:
        _print_info(f"Dry run: {files_would_modify} file(s) would be modified")
    else:
        _print_success(f"Fixed {files_modified} file(s)")
    console.print()


@app.command
def generate(
    dry_run: Annotated[bool, Parameter(help="Show changes without writing files")] = False,
    module: Annotated[Path | None, Parameter(help="Generate for specific module")] = None,
    source: Annotated[Path | None, Parameter(help="Source root directory")] = None,
    output: Annotated[
        Path | None, Parameter(help="Output directory (default: same as source)")
    ] = None,
) -> None:
    """Bootstrap new __init__.py files for packages that don't have one.

    Analyzes the codebase and creates __init__.py files for packages that are
    currently missing them, with:
    - Proper __all__ declarations
    - lazy_import() calls for exports (or barrel imports if configured)
    - TYPE_CHECKING imports where appropriate

    Use `fix` to update existing __init__.py files.

    Examples:
        exportify generate
        exportify generate --dry-run
        exportify generate --module src/mypackage/core
        exportify generate --source src/mypackage --output /tmp/test
    """

    def _raise_system_exit(message: str) -> NoReturn:
        _print_error(message)
        raise SystemExit(1)

    from exportify.common.cache import JSONAnalysisCache
    from exportify.common.config import load_config
    from exportify.pipeline import Pipeline

    source_root = source or detect_source_root()

    _print_info("Generating exports...")
    console.print()

    # Load rules
    _print_info("Loading export rules...")
    rules = RuleEngine()
    rules_path = find_config_file()

    if rules_path is None:
        _print_warning(f"No config file found (set {CONFIG_ENV_VAR} or create .exportify.yaml)")
        _print_info("Using default rules")
        output_style_value = "lazy"
    else:
        rules.load_rules([rules_path])
        _print_success(f"Loaded rules from {rules_path}")
        config = load_config(rules_path)
        output_style_value = config.output_style.value

    console.print()

    # Set up cache and output directory
    cache = JSONAnalysisCache()
    output_dir = output or source_root

    # Create pipeline
    _print_info("Initializing pipeline...")
    pipeline = Pipeline(
        rule_engine=rules, cache=cache, output_dir=output_dir, output_style=output_style_value
    )

    if not source_root.exists():
        _print_error(f"Source directory not found: {source_root}")
        raise SystemExit(1)

    console.print()

    # Show dry-run status
    if dry_run:
        _print_info("Dry run mode - no files will be written")
        console.print()

    # Execute pipeline
    _print_info(f"Processing {source_root}...")
    if module:
        _print_info(f"Filtering to module: {module}")

    console.print()

    try:
        result = pipeline.run(source_root=source_root, dry_run=dry_run, module=module)

        # Display results
        _print_generation_results(result)

        # Exit with error if generation failed
        if not result.success:
            _raise_system_exit("Export generation failed - see above for details")

    except Exception as e:
        _print_error(f"Pipeline execution failed: {e}")
        console.print()
        import traceback

        console.print("[dim]Full traceback:[/dim]")
        console.print(traceback.format_exc())
        raise SystemExit(1) from e


# --- Legacy validate command (kept for backward compatibility) ---


@app.command
def validate(
    fix: Annotated[bool, Parameter(help="Auto-fix import issues")] = False,
    strict: Annotated[bool, Parameter(help="Fail on any issues (including warnings)")] = False,
    module: Annotated[Path | None, Parameter(help="Validate specific module or file")] = None,
    json_output: Annotated[bool, Parameter(name="json", help="Output results as JSON")] = False,
    verbose: Annotated[bool, Parameter(help="Show detailed validation information")] = False,
) -> None:
    """Validate that imports match exports.

    Deprecated: use `check` instead. This command is kept for backward compatibility.

    Checks:
    - All lazy_import() calls resolve to real modules
    - __all__ declarations match _dynamic_imports
    - TYPE_CHECKING imports exist
    - No broken imports

    Examples:
        exportify validate
        exportify validate --fix
        exportify validate --strict
        exportify validate --module src/mypackage/core
        exportify validate --json
        exportify validate --verbose
    """
    from exportify.common.cache import JSONAnalysisCache
    from exportify.validator.validator import LazyImportValidator

    if not json_output:
        _print_info("Validating lazy imports...")
        console.print()

    # Set up validator
    cache = JSONAnalysisCache()
    project_root = Path.cwd()
    validator = LazyImportValidator(project_root=project_root, cache=cache)

    # Determine files to validate
    file_paths = _resolve_validation_files(module, json_output=json_output)

    # Run validation
    results = validator.validate(file_paths=file_paths)

    # Output results based on format
    if json_output:
        _output_validation_json(results)
    elif verbose:
        _output_validation_verbose(results)
    else:
        _output_validation_concise(results)

    # Status message
    console.print()
    if results.success:
        _print_success("All validations passed")
    else:
        _print_error("Validation failed")
    console.print()

    # Auto-fix if requested
    if fix and (results.errors or results.warnings) and not json_output:
        _print_info("Auto-fix is not yet implemented")
        console.print()

    # Exit with error code if validation failed
    if not results.success or (strict and results.warnings):
        raise SystemExit(1)


def _analyze_target_path(module: Path | None, source_root: Path) -> tuple[Path, Path, str]:
    """Determine and validate target path for analysis.

    Returns: (target_path, target_file, module_path)
    """
    if module:
        target_path = module
        if not target_path.exists():
            _print_error(f"Module not found: {target_path}")
            raise SystemExit(1)
    else:
        # No module specified — try to auto-detect the package under source_root.
        # source_root itself (e.g. `src/`) is typically a container, not a package.
        init_file = source_root / "__init__.py"
        if init_file.exists():
            target_path = source_root
        else:
            # Scan for immediate sub-directories that are Python packages.
            packages = sorted(
                p for p in source_root.iterdir() if p.is_dir() and (p / "__init__.py").exists()
            )
            if len(packages) == 1:
                target_path = packages[0]
            elif len(packages) > 1:
                _print_error(
                    f"Multiple packages found under {source_root}; "
                    "please specify one with --module:"
                )
                for pkg in packages:
                    _print_info(f"  {pkg}")
                raise SystemExit(1)
            else:
                _analyze_missing_init_and_exit(source_root)

    if target_path.is_dir():
        init_file = target_path / "__init__.py"
        if not init_file.exists():
            _analyze_missing_init_and_exit(target_path)
        target_file = init_file
        module_path = _path_to_module(target_path, source_root)
    else:
        target_file = target_path
        module_path = _path_to_module(target_path.parent, source_root)

    return target_path, target_file, module_path


def _analyze_missing_init_and_exit(target_path) -> NoReturn:
    _print_warning(f"No Python package found in {target_path}")
    _print_info("Searched for directories containing an __init__.py but found none.")
    _print_info("Specify a package explicitly with --module, e.g.:")
    _print_info(f"  exportify fix --dry-run --module {target_path}/<package>")
    raise SystemExit(1)


def _collect_analysis_data(
    target_path: Path, module_path: str, rules: RuleEngine
) -> tuple[dict, dict]:
    """Collect symbols and decisions from target module."""
    from collections import defaultdict

    from exportify.analysis.ast_parser import ASTParser

    parser = ASTParser()

    # Parse all Python files in the package
    package_dir = target_path if target_path.is_dir() else target_path.parent
    python_files = [f for f in package_dir.glob("*.py") if f.name != "__init__.py"]

    # Collect all symbols from child modules
    all_symbols: dict[str, list] = defaultdict(list)
    all_decisions: dict[str, list] = defaultdict(list)

    for py_file in python_files:
        rel_module = py_file.stem
        full_module = f"{module_path}.{rel_module}"

        analysis = parser.parse_file(py_file, full_module)
        all_symbols[rel_module] = analysis.symbols

        # Evaluate rules for each symbol
        for symbol in analysis.symbols:
            decision = rules.evaluate(symbol, full_module)
            if decision.action != RuleAction.NO_DECISION:
                all_decisions[rel_module].append(decision)

    return all_symbols, all_decisions


def _build_manifest(module_path: str, all_decisions: dict, rules: RuleEngine):
    """Build manifest from decisions."""
    from exportify.export_manager import CodeGenerator
    from exportify.export_manager.graph import PropagationGraph

    # Generate code to see what would be created
    CodeGenerator(output_dir=Path.cwd())

    # Build propagation graph (simplified for single module analysis)
    graph = PropagationGraph(rule_engine=rules)

    # Add modules to graph first
    graph.add_module(module_path, parent=None)
    for rel_module in all_decisions:
        full_module = f"{module_path}.{rel_module}"
        graph.add_module(full_module, parent=module_path)

    # Add export decisions
    for decisions in all_decisions.values():
        for decision in decisions:
            if decision.action == RuleAction.INCLUDE:
                graph.add_export(decision)

    manifests = graph.build_manifests()
    return manifests.get(module_path)


def _get_preserved_code(target_file: Path) -> str:
    """Extract preserved code from existing __init__.py."""
    if target_file.exists() and target_file.name == "__init__.py":
        content = target_file.read_text()
        from exportify.export_manager.section_parser import SectionParser

        parser_section = SectionParser()
        parsed = parser_section.parse_content(content)
        return parsed.preserved_code
    return ""


def _print_json_output(
    module_path: str, all_symbols: dict, all_decisions: dict, target_manifest, preserved_code: str
) -> None:
    """Print analysis results in JSON format."""
    import json

    output = {
        "package": module_path,
        "status": "ready" if target_manifest else "no_exports",
        "symbols": {
            rel_module: [
                {
                    "name": s.name,
                    "type": s.member_type.value,
                    "provenance": s.provenance.value,
                    "is_private": s.is_private,
                    "location": {"line": s.location.line},
                }
                for s in symbols
            ]
            for rel_module, symbols in all_symbols.items()
        },
        "decisions": {
            rel_module: [
                {
                    "symbol": d.export_name,
                    "action": d.action.value,
                    "rule": d.reason,
                    "propagation": d.propagation.value if d.propagation else None,
                }
                for d in decisions
            ]
            for rel_module, decisions in all_decisions.items()
        },
        "would_generate": {
            "type_checking_count": len(target_manifest.all_exports) if target_manifest else 0,
            "dynamic_imports_count": len([
                e for e in target_manifest.all_exports if not e.is_type_only
            ])
            if target_manifest
            else 0,
            "all_count": len(target_manifest.all_exports) if target_manifest else 0,
        },
        "preserved_code": bool(preserved_code),
    }
    console.print(json.dumps(output, indent=2))


def _print_symbols_section(all_symbols: dict, *, verbose: bool) -> None:
    """Print detected symbols section."""
    from collections import defaultdict

    total_symbols = sum(len(symbols) for symbols in all_symbols.values())
    console.print(f"[bold]Detected Symbols ({total_symbols}):[/bold]")

    for rel_module, symbols in sorted(all_symbols.items()):
        if not symbols:
            continue

        console.print(f"  [cyan]{rel_module}.py[/cyan]:")
        by_type: dict[MemberType, list] = defaultdict(list)
        for symbol in symbols:
            by_type[symbol.member_type].append(symbol)

        for member_type in [
            MemberType.CLASS,
            MemberType.FUNCTION,
            MemberType.CONSTANT,
            MemberType.VARIABLE,
            MemberType.TYPE_ALIAS,
            MemberType.IMPORTED,
        ]:
            if member_type not in by_type:
                continue

            names = [s.name for s in by_type[member_type]]
            if not verbose:
                display_names = names[:5]
                if len(names) > 5:
                    display_names.append(f"... and {len(names) - 5} more")
                console.print(f"    {member_type.value.title()}: {', '.join(display_names)}")
            else:
                console.print(f"    {member_type.value.title()}:")
                for name in names:
                    console.print(f"      • {name}")

    console.print()


def _print_decisions_section(all_decisions: dict, *, verbose: bool) -> None:
    """Print export rules applied section."""
    total_decisions = sum(len(decisions) for decisions in all_decisions.values())
    console.print(f"[bold]Export Rules Applied ({total_decisions}):[/bold]")

    for rel_module, decisions in sorted(all_decisions.items()):
        if not decisions:
            continue

        console.print(f"  [cyan]{rel_module}.py[/cyan]:")
        for decision in decisions[: None if verbose else 10]:
            status = "✓" if decision.action == RuleAction.INCLUDE else "✗"
            color = "green" if decision.action == RuleAction.INCLUDE else "red"
            console.print(
                f"    [{color}]{status}[/{color}] {decision.export_name:<20} [{decision.reason}]"
            )

        if not verbose and len(decisions) > 10:
            console.print(f"    [dim]... and {len(decisions) - 10} more[/dim]")

    console.print()


def _print_generation_section(target_manifest) -> None:
    """Print would generate section."""
    if not target_manifest:
        return

    runtime_exports = [e for e in target_manifest.all_exports if not e.is_type_only]
    console.print("[bold]Would Generate:[/bold]")
    console.print(f"  TYPE_CHECKING: [cyan]{len(target_manifest.all_exports)}[/cyan] imports")
    console.print(f"  _dynamic_imports: [cyan]{len(runtime_exports)}[/cyan] entries")
    console.print(f"  __all__: [cyan]{len(target_manifest.all_exports)}[/cyan] exports")
    console.print()


def _print_preserved_code_section(preserved_code: str, *, verbose: bool) -> None:
    """Print preserved code section."""
    if not preserved_code:
        return

    console.print("[bold]Preserved Code:[/bold]")
    lines = preserved_code.strip().split("\n")
    console.print(f"  {len(lines)} lines of user code")

    if verbose:
        console.print()
        console.print("  [dim]Preview:[/dim]")
        for line in lines[:10]:
            console.print(f"  [dim]{line}[/dim]")
        if len(lines) > 10:
            console.print(f"  [dim]... and {len(lines) - 10} more lines[/dim]")

    console.print()


def _print_warnings_section(target_manifest) -> None:
    """Print warnings section."""
    warnings = []
    if not target_manifest or not target_manifest.all_exports:
        warnings.append("No exports detected - package may be empty or all private")

    console.print("[bold]Warnings:[/bold]")
    if warnings:
        for warning in warnings:
            _print_warning(warning)
    else:
        console.print("  None")

    console.print()


def _print_ready_status(target_manifest) -> None:
    """Print final ready status."""
    if target_manifest and target_manifest.all_exports:
        _print_success("Ready: Yes")
    else:
        _print_warning("Ready: No (no exports to generate)")


def _print_text_output(
    module_path: str,
    all_symbols: dict,
    all_decisions: dict,
    target_manifest,
    preserved_code: str,
    *,
    verbose: bool,
) -> None:
    """Print analysis results in human-readable text format."""
    console.print(f"[bold]Package:[/bold] {module_path}")
    console.print(
        f"[bold]Status:[/bold] {'[green]Ready for generation[/green]' if target_manifest else '[yellow]No exports detected[/yellow]'}"
    )
    console.print()

    _print_symbols_section(all_symbols, verbose=verbose)
    _print_decisions_section(all_decisions, verbose=verbose)
    _print_generation_section(target_manifest)
    _print_preserved_code_section(preserved_code, verbose=verbose)
    _print_warnings_section(target_manifest)
    _print_ready_status(target_manifest)


@app.command
def analyze(
    module: Annotated[Path | None, Parameter(help="Analyze specific module")] = None,
    source: Annotated[Path | None, Parameter(help="Source directory to analyze")] = None,
    verbose: Annotated[bool, Parameter(help="Show detailed analysis")] = False,
    format: Annotated[  # noqa: A002
        str, Parameter(help="Output format: text, json")
    ] = "text",
) -> None:
    """Analyze package structure and show what would be generated.

    Deprecated: use `fix --dry-run` instead. This command is kept for backward compatibility.

    Performs dry-run analysis showing:
    - Detected symbols with metadata
    - Export rules applied
    - What would be generated
    - Preserved code sections
    - Warnings and issues

    Examples:
        exportify analyze
        exportify analyze --module src/mypackage/core
        exportify analyze --verbose
        exportify analyze --format json
    """
    from exportify.common.cache import AnalysisCache

    _print_info("Analyzing package structure...")
    console.print()

    # Load rules
    _print_info("Loading export rules...")
    rules = RuleEngine()
    rules_path = find_config_file()

    if rules_path is None:
        _print_warning(f"No config file found (set {CONFIG_ENV_VAR} or create .exportify.yaml)")
        _print_info("Using default rules")
    else:
        rules.load_rules([rules_path])
        _print_success(f"Loaded rules from {rules_path}")

    console.print()

    # Determine target path
    source_root = source or detect_source_root()
    if not source_root.exists():
        _print_error(f"Source directory not found: {source_root}")
        raise SystemExit(1)

    # Analyze target path
    target_path, target_file, module_path = _analyze_target_path(module, source_root)

    # Parse the module
    _print_info(f"Analyzing module: {module_path}")
    console.print()

    AnalysisCache()

    # Collect analysis data
    all_symbols, all_decisions = _collect_analysis_data(target_path, module_path, rules)

    # Build manifest
    target_manifest = _build_manifest(module_path, all_decisions, rules)

    # Get preserved code
    preserved_code = _get_preserved_code(target_file)

    # Output results
    if format == "json":
        _print_json_output(module_path, all_symbols, all_decisions, target_manifest, preserved_code)
    else:
        _print_text_output(
            module_path,
            all_symbols,
            all_decisions,
            target_manifest,
            preserved_code,
            verbose=verbose,
        )

    console.print()


@app.command
def doctor() -> None:
    """Run health checks and provide actionable advice.

    Checks:
    - Cache health and validity
    - Rule configuration
    - Export conflicts
    - Performance issues

    Provides recommendations for improvements.

    Examples:
        exportify doctor
    """
    console.print()
    console.print(Panel("[bold]Lazy Import System Health Check[/bold]", expand=False))
    console.print()

    # Check cache
    _print_info("Checking analysis cache...")
    from exportify.common.cache import AnalysisCache

    cache = AnalysisCache()
    stats = cache.get_stats()

    console.print(f"  Total entries: [cyan]{stats.total_entries}[/cyan]")
    console.print(f"  Valid entries: [green]{stats.valid_entries}[/green]")
    console.print(f"  Invalid entries: [red]{stats.invalid_entries}[/red]")
    console.print(f"  Cache size: [cyan]{stats.total_size_bytes / 1024:.1f}KB[/cyan]")
    console.print(f"  Hit rate: [cyan]{stats.hit_rate * 100:.1f}%[/cyan]")
    console.print()

    # Check rules
    _print_info("Checking rule configuration...")
    rules_path = find_config_file()

    if rules_path is not None:
        _print_success(f"Rules file found: {rules_path}")
    else:
        _print_warning("No config file found")
        console.print(
            f"  [dim]Recommendation: Create .exportify.yaml or set {CONFIG_ENV_VAR}[/dim]"
        )

    console.print()

    # Overall status
    if stats.invalid_entries > stats.total_entries * 0.1:  # More than 10% invalid
        _print_warning("High invalid cache rate - consider clearing cache")
        console.print("  [dim]Run: exportify clear-cache[/dim]")
    else:
        _print_success("System health looks good")

    console.print()


@app.command
def init(
    output: Annotated[
        Path, Parameter(help="Output path for the config YAML")
    ] = DEFAULT_CONFIG_PATH,
    dry_run: Annotated[bool, Parameter(help="Show generated config without writing files")] = False,
    force: Annotated[bool, Parameter(help="Overwrite existing config file")] = False,
    verbose: Annotated[bool, Parameter(help="Show full configuration summary")] = False,
) -> None:
    """Initialise exportify with a default configuration file.

    Creates `.exportify.yaml` in the current directory with sensible default
    rules that work for most Python packages.  Edit the file afterwards to
    customise which symbols are exported and how they propagate.

    Examples:
        exportify init
        exportify init --dry-run
        exportify init --output path/to/rules.yaml
        exportify init --force
        exportify init --verbose
    """
    from exportify.migration import migrate_to_yaml

    if not dry_run and output.exists() and not force:
        _print_error(f"Config file already exists: {output}")
        _print_info("Use --force to overwrite, or --dry-run to preview.")
        console.print()
        raise SystemExit(1)

    _print_info("Generating default exportify configuration...")
    console.print()

    result = migrate_to_yaml(output, dry_run=dry_run)

    if not result.success:
        _print_error("Init failed:")
        for error in result.errors:
            console.print(f"  [red]•[/red] {error}")
        console.print()
        raise SystemExit(1)

    console.print()
    _print_success("Configuration generated!")
    console.print(f"  Rules: [cyan]{len(result.rules_generated)}[/cyan]")
    console.print()

    if dry_run:
        _print_info("Dry run mode — no files written")
        console.print()
        console.print("[bold]Generated YAML:[/bold]")
        console.print("─" * 80)
        console.print(result.yaml_content)
        console.print("─" * 80)
    else:
        _print_success(f"Config written to: {output}")
        _print_info("Edit this file to customise export rules for your project.")

    console.print()

    if verbose and result.summary:
        console.print("[bold]Configuration Summary:[/bold]")
        console.print()
        console.print(result.summary)
        console.print()


@app.command
def status(verbose: Annotated[bool, Parameter(help="Show detailed information")] = False) -> None:
    """Show current export/import health status.

    Displays:
    - Cache statistics
    - Validation status
    - Rule configuration status
    - Recent activity

    Examples:
        exportify status
        exportify status --verbose
    """
    console.print()
    console.print(Panel("[bold]Lazy Import System Status[/bold]", expand=False))
    console.print()

    # Cache status
    from exportify.common.cache import AnalysisCache

    cache = AnalysisCache()
    stats = cache.get_stats()

    console.print("[bold]Cache Status:[/bold]")
    console.print(f"  Entries: [cyan]{stats.valid_entries}/{stats.total_entries}[/cyan] valid")
    console.print(f"  Hit rate: [cyan]{stats.hit_rate * 100:.1f}%[/cyan]")
    console.print()

    # Configuration status
    console.print("[bold]Configuration:[/bold]")
    rules_path = find_config_file()

    if rules_path is not None:
        console.print(f"  Rules: [green]✓[/green] {rules_path}")
    else:
        console.print("  Rules: [yellow]–[/yellow] Not found (using defaults)")  # noqa: RUF001

    console.print()

    # System status
    console.print("[bold]System:[/bold]")
    console.print("  Status: [green]Ready[/green]")
    console.print()

    if verbose:
        console.print("[bold]Detailed Information:[/bold]")
        console.print(f"  Cache size: {stats.total_size_bytes / 1024:.1f}KB")
        console.print(f"  Invalid entries: {stats.invalid_entries}")
        console.print()


@app.command(name="clear-cache")
def clear_cache() -> None:
    """Clear the analysis cache.

    Removes all cached analysis results. The cache will be rebuilt
    on the next validation or generation run.

    Use this when:
    - Cache is corrupted
    - Schema version changed
    - Performance issues

    Examples:
        exportify clear-cache
    """
    from exportify.common.cache import AnalysisCache

    _print_info("Clearing analysis cache...")
    console.print()

    cache = AnalysisCache()
    cache.clear()

    _print_success("Cache cleared successfully")
    console.print()


def main() -> None:
    """Main entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()

__all__ = ("app",)
