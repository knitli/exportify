# sourcery skip: avoid-global-variables
# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""CLI command for running the full export generation pipeline."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, NoReturn


if TYPE_CHECKING:
    from exportify.common.cache import JSONAnalysisCache
    from exportify.common.config import SpdxConfig
    from exportify.export_manager import RuleEngine

from cyclopts import App, Parameter
from rich.panel import Panel

from exportify.commands.utils import (
    CONSOLE,
    find_config_file,
    print_error,
    print_info,
    print_success,
    print_warning,
)
from exportify.common.config import CONFIG_ENV_VAR, SpdxConfig
from exportify.export_manager import RuleEngine
from exportify.types import ExportGenerationResult
from exportify.utils import detect_source_root


GenerateCommand = App(console=CONSOLE)


def _print_generation_results(result: ExportGenerationResult) -> None:
    """Print export generation results with colors."""
    CONSOLE.print()
    CONSOLE.print(Panel("[bold]Export Generation Results[/bold]", expand=False))
    CONSOLE.print()

    # Summary metrics
    metrics = result.metrics
    CONSOLE.print(f"  Files analyzed: [cyan]{metrics.files_analyzed}[/cyan]")
    CONSOLE.print(f"  Files generated: [green]{metrics.files_generated}[/green]")
    CONSOLE.print(f"  Files updated: [yellow]{metrics.files_updated}[/yellow]")
    CONSOLE.print(f"  Files skipped: [dim]{metrics.files_skipped}[/dim]")
    CONSOLE.print(f"  Exports created: [green]{metrics.exports_created}[/green]")
    CONSOLE.print(f"  Processing time: [cyan]{metrics.processing_time_ms / 1000:.2f}s[/cyan]")
    CONSOLE.print(f"  Cache hit rate: [cyan]{metrics.cache_hit_rate * 100:.1f}%[/cyan]")
    CONSOLE.print()

    # Errors if any
    if result.errors:
        CONSOLE.print("[red]Errors encountered:[/red]")
        for error in result.errors:
            CONSOLE.print(f"  [red]•[/red] {error}")
        CONSOLE.print()

    # Status
    if result.success:
        print_success("Export generation completed successfully")
    else:
        print_error("Export generation failed")
    CONSOLE.print()


def _run_pipeline_for_root(
    *,
    root: Path,
    source_root: Path,
    output: Path | None,
    module: Path | None,
    rules: RuleEngine,
    cache: JSONAnalysisCache,
    output_style_value: str,
    spdx_config: SpdxConfig | None,
    exclude_paths: list[str],
    dry_run: bool,
    raise_exit: Callable[[str], NoReturn],
) -> None:
    """Run the generation pipeline for a single source root."""
    from exportify.pipeline import Pipeline

    if root != source_root:
        CONSOLE.print()
        print_info(f"Processing additional source: {root}...")
    else:
        print_info(f"Processing {root}...")
    CONSOLE.print()

    if not root.exists():
        print_error(f"Source directory not found: {root}")
        raise SystemExit(1)

    root_pipeline = Pipeline(
        rule_engine=rules,
        cache=cache,
        output_dir=(output or source_root) if root == source_root else root,
        output_style=output_style_value,
        spdx_config=spdx_config,
        exclude_paths=exclude_paths,
    )

    try:
        result = root_pipeline.run(
            source_root=root, dry_run=dry_run, module=module if root == source_root else None
        )
        _print_generation_results(result)
        if not result.success:
            raise_exit("Export generation failed - see above for details")
    except SystemExit:
        raise
    except Exception as e:
        print_error(f"Pipeline execution failed: {e}")
        CONSOLE.print()
        import traceback

        CONSOLE.print("[dim]Full traceback:[/dim]")
        CONSOLE.print(traceback.format_exc())
        raise SystemExit(1) from e


@GenerateCommand.default
def generate(
    module: Annotated[Path | None, Parameter(help="Limit generation to this path")] = None,
    source: Annotated[Path | None, Parameter(help="Source root directory")] = None,
    output: Annotated[
        Path | None, Parameter(help="Output directory (default: same as source)")
    ] = None,
    dry_run: Annotated[bool, Parameter(help="Show changes without writing files")] = False,
) -> None:
    """Create and update __init__.py files with lazy exports across your package.

    Runs the full export pipeline: discovers Python files, applies export rules,
    then writes or updates every __init__.py in the source tree. New packages get
    fresh files; existing ones are updated in-place, preserving any code above the
    managed-exports sentinel.

    Each generated file includes:
    - A __all__ declaration listing public exports
    - lateimport() calls for lazy loading (or barrel imports if configured)
    - TYPE_CHECKING imports where appropriate

    Use `fix` to make targeted updates — syncing __all__ and _dynamic_imports
    without re-running the full pipeline.

    Examples:
        exportify generate
        exportify generate --dry-run
        exportify generate --module src/mypackage/core
        exportify generate --source src/mypackage --output /tmp/test
    """

    def _raise_system_exit(message: str) -> NoReturn:
        print_error(message)
        raise SystemExit(1)

    from exportify.common.cache import JSONAnalysisCache
    from exportify.common.config import ExportifyConfig, load_config

    source_root = source or detect_source_root()

    print_info("Generating exports...")
    CONSOLE.print()

    # Load rules
    print_info("Loading export rules...")
    rules = RuleEngine()
    rules_path = find_config_file()

    config: ExportifyConfig | None = None
    spdx_config: SpdxConfig | None = None
    if rules_path is None:
        print_warning(f"No config file found (set {CONFIG_ENV_VAR} or create .exportify.yaml)")
        print_info("Using default rules")
        output_style_value = "lazy"
    else:
        rules.load_rules([rules_path])
        print_success(f"Loaded rules from {rules_path}")
        config = load_config(rules_path)
        output_style_value = config.output_style.value
        spdx_config = config.spdx

    CONSOLE.print()

    # Collect all source roots: primary + any additional from config
    additional_source_roots: list[Path] = config.project.additional_source_paths if config else []
    all_source_roots = [source_root, *additional_source_roots]

    # Set up shared cache
    cache = JSONAnalysisCache()

    # Show dry-run status
    if dry_run:
        print_info("Dry run mode - no files will be written")
        CONSOLE.print()

    # Execute pipeline for each source root
    if module:
        print_info(f"Filtering to module: {module}")
        CONSOLE.print()

    exclude_paths: list[str] = config.exclude_paths if config else []

    for root in all_source_roots:
        _run_pipeline_for_root(
            root=root,
            source_root=source_root,
            output=output,
            module=module,
            rules=rules,
            cache=cache,
            output_style_value=output_style_value,
            spdx_config=spdx_config,
            exclude_paths=exclude_paths,
            dry_run=dry_run,
            raise_exit=_raise_system_exit,
        )


if __name__ == "__main__":
    GenerateCommand()

__all__ = ("GenerateCommand",)
