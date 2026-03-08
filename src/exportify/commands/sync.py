# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: Apache-2.0 OR MIT

"""Implementation of the ``sync`` command for aligning project code with export rules."""

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
    collect_py_files,
    get_all_source_roots,
    load_config_and_rules,
    path_to_module,
    print_error,
    print_info,
    print_success,
    print_warning,
    resolve_checks,
)
from exportify.common.config import CONFIG_ENV_VAR, SpdxConfig
from exportify.common.snapshot import SnapshotManager
from exportify.export_manager import ModuleAllFixResult, RuleEngine
from exportify.export_manager.module_all import fix_module_all
from exportify.types import ExportGenerationResult
from exportify.utils import detect_source_root, format_file, locate_project_root


SyncCommand = App("sync", help="Synchronize project with export rules", console=CONSOLE)


def _print_sync_results(result: ExportGenerationResult) -> None:
    """Print export synchronization results with colors."""
    CONSOLE.print()
    CONSOLE.print(Panel("[bold]Synchronization Results[/bold]", expand=False))
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
        print_success("Project synchronization completed successfully")
    else:
        print_error("Project synchronization failed")
    CONSOLE.print()


def _report_module_all_dry_run(py_file: Path, result: ModuleAllFixResult) -> None:
    """Print dry-run diff for a single module __all__ fix."""
    print_info(f"Would update {py_file}")
    if result.added:
        CONSOLE.print(f"  [green]+[/green] Add to __all__: {result.added}")
    if result.removed:
        CONSOLE.print(f"  [red]-[/red] Remove from __all__: {result.removed}")
    if result.created:
        CONSOLE.print("  [cyan]new[/cyan] __all__ would be created")


def _report_module_all_applied(py_file: Path, result: ModuleAllFixResult, *, verbose: bool) -> None:
    """Print applied-fix info for a single module __all__ fix."""
    print_success(f"Updated {py_file}")
    if not verbose:
        return
    if result.added:
        CONSOLE.print(f"  [green]+[/green] Added to __all__: {result.added}")
    if result.removed:
        CONSOLE.print(f"  [red]-[/red] Removed from __all__: {result.removed}")
    if result.created:
        CONSOLE.print("  [cyan]new[/cyan] __all__ created")


def _sync_module_all_files(
    py_files: list[Path], source_root: Path, rules: RuleEngine, *, dry_run: bool, verbose: bool
) -> int:
    """Sync __all__ in regular (non-__init__.py) modules. Returns count of changed files."""
    if verbose:
        print_info("Syncing __all__ in regular modules...")
    count = 0
    for py_file in (f for f in py_files if f.name != "__init__.py"):
        module_path = path_to_module(py_file.with_suffix(""), source_root)
        result = fix_module_all(py_file, module_path, rules, dry_run=dry_run)
        if not result.was_modified:
            continue
        count += 1
        if dry_run:
            _report_module_all_dry_run(py_file, result)
        else:
            format_file(py_file, verbose=verbose)
            _report_module_all_applied(py_file, result, verbose=verbose)
    return count


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
) -> int:
    """Run the synchronization pipeline for a single source root. Returns count of changed files."""
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
        _print_sync_results(result)
        if not result.success:
            raise_exit("Synchronization failed - see above for details")
        return result.metrics.files_updated + result.metrics.files_generated
    except SystemExit:
        raise
    except Exception as e:
        print_error(f"Pipeline execution failed: {e}")
        CONSOLE.print()
        import traceback

        CONSOLE.print("[dim]Full traceback:[/dim]")
        CONSOLE.print(traceback.format_exc())
        raise SystemExit(1) from e


@SyncCommand.default
def sync(
    *paths: Annotated[Path, Parameter(help="Files or directories to limit synchronization to")],
    source: Annotated[Path | None, Parameter(help="Source root directory")] = None,
    output: Annotated[
        Path | None, Parameter(help="Output directory (default: same as source)")
    ] = None,
    module_all: Annotated[
        bool | None,
        Parameter(name="module-all", help="Only sync \\_\\_all\\_\\_ in regular modules"),
    ] = None,
    package_all: Annotated[
        bool | None,
        Parameter(name="package-all", help="Only sync \\_\\_all\\_\\_ and exports in \\_\\_init\\_\\_.py files"),
    ] = None,
    dry_run: Annotated[bool, Parameter(help="Show changes without writing files")] = False,
    verbose: Annotated[bool, Parameter(help="Show detailed output")] = False,
) -> None:
    """Align your project's code with your export rules.

    The `sync` command ensures that your project's `__init__.py` files and
    `__all__` declarations exactly match your configured export rules.

    Actions:
    - Creates missing `__init__.py` files in package directories
    - Updates `_dynamic_imports` and `__all__` in `__init__.py` files
    - Updates `__all__` in regular modules to match export rules
    - Preserves manually written code above the managed exports sentinel

    Pass one or more paths to limit synchronization to specific modules or packages.
    Omit paths to process the entire project.

    Use `--dry-run` to preview all changes before writing any files.

    Examples:
        exportify sync
        exportify sync --dry-run
        exportify sync src/mypackage/core
        exportify sync --no-module-all
    """

    def _raise_system_exit(message: str) -> NoReturn:
        print_error(message)
        raise SystemExit(1)

    from exportify.common.cache import JSONAnalysisCache

    checks_to_run = resolve_checks(
        {"module_all", "package_all"},
        module_all=module_all,
        package_all=package_all,
    )

    print_info("Dry run mode — no files will be written") if dry_run else print_info(
        "Synchronizing project with export rules..."
    )
    CONSOLE.print()

    source_root = source or detect_source_root()
    rules, config = load_config_and_rules(verbose=verbose)

    spdx_config: SpdxConfig | None = None
    output_style_value = "lazy"
    exclude_paths: list[str] = []

    if config:
        spdx_config = config.spdx
        output_style_value = config.output_style.value
        exclude_paths = config.exclude_paths
    else:
        print_warning(f"No config file found (set {CONFIG_ENV_VAR} or create .exportify.yaml)")
        print_info("Using default rules and lazy output style")

    CONSOLE.print()

    # Collect all source roots: primary + any additional from config
    all_source_roots = get_all_source_roots(source)

    # Set up shared cache
    cache = JSONAnalysisCache()

    # Snapshot for undo
    if not dry_run:
        all_py_files = (
            collect_py_files(paths, source)
            if paths
            else [f for root in all_source_roots for f in root.rglob("*.py")]
        )
        SnapshotManager(locate_project_root()).capture(all_py_files)
        if verbose:
            print_info(f"Snapshot captured ({len(all_py_files)} file(s))")

    total_changed = 0

    for root in all_source_roots:
        root_paths = [
            p
            for p in paths
            if p.is_relative_to(root) or p.resolve().is_relative_to(root.resolve())
        ]

        if paths and not root_paths:
            continue

        # Collect files for this root for module_all sync
        if "module_all" in checks_to_run:
            root_py_files = (
                [f for f in collect_py_files(paths, source) if f.is_relative_to(root)]
                if paths
                else list(root.rglob("*.py"))
            )
            total_changed += _sync_module_all_files(
                root_py_files, root, rules, dry_run=dry_run, verbose=verbose
            )

        # Run pipeline for package_all sync
        if "package_all" in checks_to_run:
            if not root_paths and not paths:
                total_changed += _run_pipeline_for_root(
                    root=root,
                    source_root=source_root,
                    output=output,
                    module=None,
                    rules=rules,
                    cache=cache,
                    output_style_value=output_style_value,
                    spdx_config=spdx_config,
                    exclude_paths=exclude_paths,
                    dry_run=dry_run,
                    raise_exit=_raise_system_exit,
                )
            else:
                for mod_path in root_paths:
                    total_changed += _run_pipeline_for_root(
                        root=root,
                        source_root=source_root,
                        output=output,
                        module=mod_path,
                        rules=rules,
                        cache=cache,
                        output_style_value=output_style_value,
                        spdx_config=spdx_config,
                        exclude_paths=exclude_paths,
                        dry_run=dry_run,
                        raise_exit=_raise_system_exit,
                    )

    CONSOLE.print()
    if total_changed == 0:
        print_success("Everything is already in sync — no changes needed")
    elif dry_run:
        print_info(f"Dry run: {total_changed} file(s) would be modified")
    else:
        print_success(f"Synchronized {total_changed} file(s)")
    CONSOLE.print()


if __name__ == "__main__":
    SyncCommand()

__all__ = ("SyncCommand",)
