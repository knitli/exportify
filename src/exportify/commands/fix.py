# sourcery skip: avoid-global-variables
# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Implementation of the ``fix`` command for syncing exports and ``__all__`` declarations to configured rules."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from cyclopts import App, Parameter

from exportify.commands.utils import (
    CONSOLE,
    collect_py_files,
    get_all_source_roots,
    load_config_and_rules,
    load_rules,
    path_to_module,
    print_error,
    print_info,
    print_success,
    print_warning,
    resolve_checks,
)
from exportify.common.cache import JSONAnalysisCache
from exportify.common.config import SpdxConfig
from exportify.common.snapshot import SnapshotManager
from exportify.export_manager import ModuleAllFixResult, RuleEngine
from exportify.export_manager.module_all import fix_module_all
from exportify.pipeline import Pipeline
from exportify.utils import detect_source_root, format_file, locate_project_root


FixCommand = App(console=CONSOLE)


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


def _fix_module_all_files(
    py_files: list[Path], source_root: Path, rules: RuleEngine, *, dry_run: bool, verbose: bool
) -> int:
    """Fix __all__ in regular (non-__init__.py) modules. Returns count of changed files."""
    if verbose:
        print_info("Fixing __all__ in regular modules...")
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


def _warn_missing_inits(py_files: list[Path], source_root: Path) -> None:
    """Warn about package directories that are missing __init__.py."""
    package_dirs: set[Path] = {f.parent for f in py_files if f.parent != source_root}
    for pkg_dir in sorted(package_dirs):
        if not (pkg_dir / "__init__.py").exists():
            print_warning(f"{pkg_dir} has no __init__.py")
            CONSOLE.print("  Run `exportify generate` to bootstrap it first")


def _fix_init_files(
    py_files: list[Path],
    source_root: Path,
    rules: RuleEngine,
    *,
    dry_run: bool,
    verbose: bool,
    spdx_config: SpdxConfig | None = None,
) -> int:
    """Fix __init__.py files via the Pipeline. Returns count of changed files."""
    if verbose:
        print_info("Fixing __init__.py exports...")

    _warn_missing_inits(py_files, source_root)

    cache = JSONAnalysisCache()
    pipeline = Pipeline(
        rule_engine=rules, cache=cache, output_dir=source_root, spdx_config=spdx_config
    )

    try:
        result = pipeline.run(source_root=source_root, dry_run=dry_run)
    except Exception as e:
        print_error(f"Pipeline execution failed: {e}")
        if verbose:
            import traceback

            CONSOLE.print("[dim]Full traceback:[/dim]")
            CONSOLE.print(traceback.format_exc())
        raise SystemExit(1) from e

    count = result.metrics.files_updated + result.metrics.files_generated
    if dry_run and verbose:
        print_info(f"Would update {result.metrics.files_updated} __init__.py file(s)")
        print_info(f"Would generate {result.metrics.files_generated} new __init__.py file(s)")
    elif not dry_run and verbose:
        print_info(f"Updated {result.metrics.files_updated} __init__.py file(s)")
    return count


def _print_summary(count: int, *, dry_run: bool) -> None:
    """Print the final summary line."""
    CONSOLE.print()
    if count == 0:
        print_success("Everything is already in sync — no changes needed")
    elif dry_run:
        print_info(f"Dry run: {count} file(s) would be modified")
    else:
        print_success(f"Fixed {count} file(s)")
    CONSOLE.print()


@FixCommand.default
def fix(
    *paths: Annotated[Path, Parameter(help="Files or directories to fix")],
    source: Annotated[Path | None, Parameter(help="Source root directory")] = None,
    dynamic_imports: Annotated[
        bool | None,
        Parameter(
            name="dynamic-imports", help="Rewrite _dynamic_imports in __init__.py to match rules"
        ),
    ] = None,
    module_all: Annotated[
        bool | None,
        Parameter(name="module-all", help="Update __all__ in modules to match export rules"),
    ] = None,
    package_all: Annotated[
        bool | None,
        Parameter(name="package-all", help="Update __all__ and exports in __init__.py files"),
    ] = None,
    dry_run: Annotated[
        bool, Parameter(name="dry-run", help="Show what would change without writing")
    ] = False,
    verbose: Annotated[bool, Parameter(help="Show detailed output")] = False,
) -> None:
    """Sync exports and __all__ declarations to match configured rules.

    Updates:
    - __all__ in regular modules to match export rules (--module-all)
    - _dynamic_imports and __all__ in __init__.py files (--dynamic-imports, --package-all)

    Skips lateimport() call paths — those import targets require manual correction.

    Use --dry-run to preview all changes before writing any files.

    Warns when a package directory has no __init__.py and suggests running `generate` first.

    Examples:
        exportify fix
        exportify fix --dry-run
        exportify fix --module-all
        exportify fix src/mypackage/core
    """
    fixes_to_run = resolve_checks(
        {"dynamic_imports", "module_all", "package_all"},
        dynamic_imports=dynamic_imports,
        module_all=module_all,
        package_all=package_all,
    )

    print_info("Dry run mode — no files will be written") if dry_run else print_info(
        "Fixing exports and __all__ declarations..."
    )
    CONSOLE.print()

    source_root = source or detect_source_root()
    rules, config = load_config_and_rules(verbose=verbose)

    # Load config for spdx and additional source roots
    spdx_config: SpdxConfig | None = config.spdx if config else None
    all_source_roots = get_all_source_roots(source)

    # Collect all files upfront (for snapshot and per-root routing)
    if paths:
        all_py_files = collect_py_files(paths, source)
    else:
        all_py_files = [f for root in all_source_roots for f in root.rglob("*.py")]

    if not dry_run:
        SnapshotManager(locate_project_root()).capture(all_py_files)
        if verbose:
            print_info(f"Snapshot captured ({len(all_py_files)} file(s))")

    total = 0

    for root in all_source_roots:
        if root != source_root and verbose:
            CONSOLE.print()
            print_info(f"Processing additional source: {root}...")

        root_py_files = [f for f in all_py_files if f.is_relative_to(root)]

        if "module_all" in fixes_to_run:
            total += _fix_module_all_files(
                root_py_files, root, rules, dry_run=dry_run, verbose=verbose
            )

        if "dynamic_imports" in fixes_to_run or "package_all" in fixes_to_run:
            total += _fix_init_files(
                root_py_files,
                root,
                rules,
                dry_run=dry_run,
                verbose=verbose,
                spdx_config=spdx_config,
            )

    _print_summary(total, dry_run=dry_run)


if __name__ == "__main__":
    FixCommand()

__all__ = ("FixCommand",)
