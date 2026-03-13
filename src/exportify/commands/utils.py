# sourcery skip: avoid-global-variables
# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Utility functions for commands."""

import logging

from pathlib import Path

from rich.console import Console
from rich.panel import Panel

from exportify.common.config import CONFIG_ENV_VAR, ExportifyConfig, find_config_file, load_config
from exportify.export_manager import RuleEngine
from exportify.types import ValidationReport
from exportify.utils import detect_source_root, display_path, locate_project_root


logger = logging.getLogger(__name__)


CONSOLE = Console(markup=True)


DEFAULT_CONFIG_PATH = locate_project_root() / ".exportify" / "config.yaml"


def resolve_checks(all_checks: set[str], **flags: bool | None) -> set[str]:
    """Resolve which checks to run given bool|None flags.

    Logic:
    - If ANY flag is True (explicitly given) → whitelist mode: only run those checks.
    - If ONLY False flags (--no-X) → blacklist mode: run everything except those.
    - If all None (no flags given) → run all checks.
    """
    explicit_true = {k for k, v in flags.items() if v is True}
    explicit_false = {k for k, v in flags.items() if v is False}

    if explicit_true:
        return explicit_true

    return all_checks - explicit_false if explicit_false else all_checks


def get_all_source_roots(source_override: Path | None = None) -> list[Path]:
    """Get all source roots: primary (detected or overridden) + additional from config."""
    source_root = (source_override or detect_source_root()).resolve()
    additional_source_roots: list[Path] = []

    if config_path := find_config_file():
        config = load_config(config_path)
        additional_source_roots = [
            Path(p).resolve() for p in config.project.additional_source_paths
        ]

    return [source_root, *additional_source_roots]


def load_config_and_rules(*, verbose: bool = False) -> tuple[RuleEngine, ExportifyConfig | None]:
    """Load config and rules, falling back to defaults if not found."""
    rules = RuleEngine()
    config_path = find_config_file()
    config: ExportifyConfig | None = None

    if config_path is None:
        if verbose:
            print_warning(f"No config file found (set {CONFIG_ENV_VAR} or create .exportify.yaml)")
            print_info("Using built-in default rules")

        # Load bundled default rules
        try:
            import importlib.resources as pkg_resources

            from exportify import rules as rules_pkg

            with pkg_resources.as_file(
                pkg_resources.files(rules_pkg) / "default_rules.yaml"
            ) as default_rules_path:
                rules.load_rules([default_rules_path])
        except Exception as e:
            if verbose:
                print_error(f"Failed to load built-in default rules: {e}")
    else:
        rules.load_rules([config_path])
        config = load_config(config_path)
        if verbose:
            print_success(f"Loaded rules from {config_path}")

    return rules, config


def print_success(message: str) -> None:
    """Print success message."""
    CONSOLE.print(f"[green]✓[/green] {message}")


def print_error(message: str) -> None:
    """Print error message."""
    CONSOLE.print(f"[red]✗[/red] {message}")


def print_warning(message: str) -> None:
    """Print warning message."""
    CONSOLE.print(f"[yellow]⚠[/yellow] {message}")


def print_info(message: str) -> None:
    """Print info message."""
    CONSOLE.print(f"[cyan]ℹ[/cyan] {message}")  # noqa: RUF001


def print_validation_results(report: ValidationReport) -> None:
    """Print validation results with colors."""
    CONSOLE.print()
    CONSOLE.print(Panel("[bold]Validation Results[/bold]", expand=False))
    CONSOLE.print()

    # Summary
    metrics = report.metrics
    CONSOLE.print(f"  Files validated: [cyan]{metrics.files_validated}[/cyan]")
    CONSOLE.print(f"  Imports checked: [cyan]{metrics.imports_checked}[/cyan]")
    CONSOLE.print(f"  Consistency checks: [cyan]{metrics.consistency_checks}[/cyan]")
    CONSOLE.print(f"  Validation time: [cyan]{metrics.validation_time_ms / 1000:.2f}s[/cyan]")
    CONSOLE.print()

    # Errors
    if report.errors:
        CONSOLE.print(f"[red]Errors found: {len(report.errors)}[/red]")
        for error in report.errors:
            location = f"{error.file}:{error.line}" if error.line else str(error.file)
            CONSOLE.print(f"  [red]•[/red] {location}")
            CONSOLE.print(f"    {error.message}")
            if error.suggestion:
                CONSOLE.print(f"    [dim]Suggestion: {error.suggestion}[/dim]")
        CONSOLE.print()

    # Warnings
    if report.warnings:
        CONSOLE.print(f"[yellow]Warnings found: {len(report.warnings)}[/yellow]")
        for warning in report.warnings:
            location = f"{warning.file}:{warning.line}" if warning.line else str(warning.file)
            CONSOLE.print(f"  [yellow]•[/yellow] {location}")
            CONSOLE.print(f"    {warning.message}")
            if warning.suggestion:
                CONSOLE.print(f"    [dim]Suggestion: {warning.suggestion}[/dim]")
        CONSOLE.print()

    # Status
    if report.success:
        print_success("All validations passed")
    else:
        print_error("Validation failed")
    CONSOLE.print()


def print_output_validation_json(results: ValidationReport) -> None:
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
    CONSOLE.print(json_lib.dumps(output_data, indent=2))


def _print_error_in_validation(error):
    CONSOLE.print(f"  {error.message}")
    if error.suggestion:
        CONSOLE.print(f"  [dim]Suggestion: {error.suggestion}[/dim]")
    CONSOLE.print()


def print_output_validation_verbose(results: ValidationReport) -> None:
    """Output validation results in verbose human-readable format."""
    CONSOLE.print()
    CONSOLE.print(Panel("[bold]Validation Results[/bold]", expand=False))
    CONSOLE.print()

    # Show errors with full context
    if results.errors:
        CONSOLE.print(f"[red]Errors found: {len(results.errors)}[/red]")
        CONSOLE.print()
        for error in results.errors:
            location = (
                f"{display_path(error.file)}:{error.line}"
                if error.line
                else display_path(error.file)
            )
            CONSOLE.print(f"[red]ERROR[/red] {location}: [bold]{error.code}[/bold]")
            _print_error_in_validation(error)
    # Show warnings with full context
    if results.warnings:
        CONSOLE.print(f"[yellow]Warnings found: {len(results.warnings)}[/yellow]")
        CONSOLE.print()
        for warning in results.warnings:
            location = (
                f"{display_path(warning.file)}:{warning.line}"
                if warning.line
                else display_path(warning.file)
            )
            CONSOLE.print(f"[yellow]WARNING[/yellow] {location}")
            _print_error_in_validation(warning)
    # Show metrics
    metrics = results.metrics
    CONSOLE.print("[bold]Metrics:[/bold]")
    CONSOLE.print(f"  Files validated: [cyan]{metrics.files_validated}[/cyan]")
    CONSOLE.print(f"  Imports checked: [cyan]{metrics.imports_checked}[/cyan]")
    CONSOLE.print(f"  Consistency checks: [cyan]{metrics.consistency_checks}[/cyan]")
    CONSOLE.print(f"  Validation time: [cyan]{metrics.validation_time_ms / 1000:.2f}s[/cyan]")
    CONSOLE.print()


def print_output_validation_concise(results: ValidationReport) -> None:
    """Output validation results in concise human-readable format."""
    if results.errors:
        for error in results.errors:
            location = (
                f"{display_path(error.file)}:{error.line}"
                if error.line
                else display_path(error.file)
            )
            CONSOLE.print(f"[red][ERROR][/red] {location}: {error.code} ({error.message})")

    if results.warnings:
        for warning in results.warnings:
            location = (
                f"{display_path(warning.file)}:{warning.line}"
                if warning.line
                else display_path(warning.file)
            )
            CONSOLE.print(f"[yellow][WARNING][/yellow] {location}: {warning.message}")

    # Show summary
    CONSOLE.print()
    CONSOLE.print(f"Files validated: {results.metrics.files_validated}")
    CONSOLE.print(f"Errors: {len(results.errors)}, Warnings: {len(results.warnings)}")


def load_rules(verbose: bool = False) -> RuleEngine:  # noqa: FBT001
    """Load rules from config file, falling back to defaults."""
    rules, _ = load_config_and_rules(verbose=verbose)
    return rules


def collect_py_files(paths: tuple[Path, ...], source: Path | None) -> list[Path]:
    """Collect Python files from given paths or auto-detect source root.

    Args:
        paths: Explicit paths to check. If empty, auto-detect source root.
        source: Optional source root override.

    Returns:
        List of Python file paths to process.
    """
    from exportify.discovery.file_discovery import FileDiscovery

    discovery = FileDiscovery()

    if not paths:
        source_root = source or detect_source_root()
        return discovery.discover_python_files(source_root)

    all_files: list[Path] = []
    for p in paths:
        if not p.exists():
            print_error(f"Path does not exist: {p}")
            raise SystemExit(1)
        if p.is_file():
            all_files.append(p.resolve())
        else:
            all_files.extend(discovery.discover_python_files(p.resolve()))
    return all_files


def path_to_module(path: Path, source_root: Path) -> str:
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


__all__ = (
    "CONSOLE",
    "DEFAULT_CONFIG_PATH",
    "collect_py_files",
    "get_all_source_roots",
    "load_config_and_rules",
    "load_rules",
    "path_to_module",
    "print_error",
    "print_info",
    "print_output_validation_concise",
    "print_output_validation_json",
    "print_output_validation_verbose",
    "print_success",
    "print_validation_results",
    "print_warning",
    "resolve_checks",
)
