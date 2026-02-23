# sourcery skip: avoid-global-variables
# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Module for the `init` command."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from cyclopts import App, Parameter

from exportify.commands.utils import (
    CONSOLE,
    DEFAULT_CONFIG_PATH,
    print_error,
    print_info,
    print_success,
)


InitCommand = App(console=CONSOLE)


@InitCommand.default
def init(
    output: Annotated[
        Path, Parameter(help="Output path for the config YAML")
    ] = DEFAULT_CONFIG_PATH,
    *,
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
        print_error(f"Config file already exists: {output}")
        print_info("Use --force to overwrite, or --dry-run to preview.")
        CONSOLE.print()
        raise SystemExit(1)

    print_info("Generating default exportify configuration...")
    CONSOLE.print()

    result = migrate_to_yaml(output, dry_run=dry_run)

    if not result.success:
        print_error("Init failed:")
        for error in result.errors:
            CONSOLE.print(f"  [red]•[/red] {error}")
        CONSOLE.print()
        raise SystemExit(1)

    CONSOLE.print()
    print_success("Configuration generated!")
    CONSOLE.print(f"  Rules: [cyan]{len(result.rules_generated)}[/cyan]")
    CONSOLE.print()

    if dry_run:
        print_info("Dry run mode — no files written")
        CONSOLE.print()
        CONSOLE.print("[bold]Generated YAML:[/bold]")
        CONSOLE.print("─" * 80)
        CONSOLE.print(result.yaml_content)
        CONSOLE.print("─" * 80)
    else:
        print_success(f"Config written to: {output}")
        print_info("Edit this file to customise export rules for your project.")

    CONSOLE.print()

    if verbose and result.summary:
        CONSOLE.print("[bold]Configuration Summary:[/bold]")
        CONSOLE.print()
        CONSOLE.print(result.summary)
        CONSOLE.print()


if __name__ == "__main__":
    InitCommand()

__all__ = ("InitCommand",)
