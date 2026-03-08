<!--
SPDX-FileCopyrightText: 2026 Knitli Inc.

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# CLI Reference

Complete reference for all exportify commands.

> For a hands-on introduction, see [Getting Started](getting-started.md).

## Commands

```console
exportify COMMAND
```

Manage Python package exports: sync, check, and maintain consistency.

### Table of Contents

- [`init`](#exportify-init)
- [`sync`](#exportify-sync)
- [`check`](#exportify-check)
- [`undo`](#exportify-undo)
- [`doctor`](#exportify-doctor)
- [`cache`](#exportify-cache)

**Commands**:

* [`init`](#exportify-init): Initialize project configuration.
* [`sync`](#exportify-sync): Align project code with export rules.
* [`check`](#exportify-check): Validate exports and `__all__` consistency.
* [`undo`](#exportify-undo): Restore files from the last `sync` run.
* [`doctor`](#exportify-doctor): Run system health checks.
* [`cache`](#exportify-cache): Manage analysis results and cache.

### exportify init

```console
exportify init [OPTIONS] [OUTPUT]
```

Initialize exportify with a default configuration file.

Creates `.exportify/config.yaml` in the current directory with sensible default
rules that work for most Python packages. Edit the file afterwards to
customize which symbols are exported and how they propagate.

**Arguments**:

* `OUTPUT`: Output path for the config YAML  *[default: .exportify/config.yaml]*

**Parameters**:

* `--dry-run, --no-dry-run`: Show generated config without writing files  *[default: False]*
* `--force, --no-force`: Overwrite existing config file  *[default: False]*
* `--verbose, --no-verbose`: Show full configuration summary  *[default: False]*

### exportify sync

```console
exportify sync [OPTIONS] [PATHS...]
```

Align your project's code with your export rules.

The `sync` command ensures that your project's `__init__.py` files and `__all__` declarations exactly match your configured export rules.

Actions:
- Creates missing `__init__.py` files in package directories
- Updates `_dynamic_imports` and `__all__` in `__init__.py` files
- Updates `__all__` in regular modules to match export rules
- Preserves manually written code above the managed exports sentinel

Use `--dry-run` to preview all changes before writing any files.

**Arguments**:

* `PATHS`: Files or directories to limit synchronization to (default: whole project)

**Parameters**:

* `--source`: Source root directory
* `--output`: Output directory (default: same as source)
* `--module-all, --no-module-all`: Only sync `__all__` in regular modules
* `--package-all, --no-package-all`: Only sync `__all__` and exports in `__init__.py` files
* `--dry-run, --no-dry-run`: Show what would change without writing  *[default: False]*
* `--verbose, --no-verbose`: Show detailed output  *[default: False]*

### exportify check

```console
exportify check [OPTIONS] [PATHS...]
```

Validate exports and `__all__` declarations for consistency.

Checks:
- `lateimport()` / `LateImport` calls resolve to real modules (`--lateimports`)
- `_dynamic_imports` entries in `__init__.py` files resolve correctly and match `__all__` (`--dynamic-imports`)
- `__all__` in regular modules matches configured export rules (`--module-all`)
- `__all__` and exports in `__init__.py` files are consistent with each other (`--package-all`)

Pass one or more flags explicitly to run only those checks.
Use `--no-X` flags to skip specific checks while running the rest.
Omit all flags to run every check.

Note: The `lateimports` check is automatically skipped if `lateimport` is not
listed as a project dependency (it's an opt-in library).

**Arguments**:

* `PATHS`: Paths to check (default: whole project)

**Parameters**:

* `--source`: Source root directory
* `--lateimports, --no-lateimports`: Check `lateimport()` / `LateImport` calls
* `--dynamic-imports, --no-dynamic-imports`: Check `_dynamic_imports` entries in `__init__.py` files
* `--module-all, --no-module-all`: Check `__all__` in regular modules
* `--package-all, --no-package-all`: Check `__all__` and exports in `__init__.py` files
* `--strict, --no-strict`: Exit non-zero on warnings  *[default: False]*
* `--json, --no-json`: Output results as JSON  *[default: False]*
* `--verbose, --no-verbose`: Show detailed output  *[default: False]*

### exportify undo

```console
exportify undo [OPTIONS] [PATHS...]
```

Restore files from the last sync run.

Reads the snapshot taken before the most recent `sync` run and restores the original content. Idempotent — safe to run multiple times.

If paths are given, only matching files are restored.

**Arguments**:

* `PATHS`: Files or directories to restore (default: all)

**Parameters**:

* `--verbose, --no-verbose`: Show each restored file  *[default: False]*

### exportify doctor

```console
exportify doctor [OPTIONS]
```

Run system health checks.

Checks:
- Cache health and validity
- Rule configuration
- System readiness

**Parameters**:

* `--short, --no-short`: Show a quick snapshot instead of full health check  *[default: False]*

### exportify cache

Manage analysis results and cache.

#### exportify cache clear

```console
exportify cache clear
```

Delete all cached analysis results.

Removes all cached analysis results. The cache will be rebuilt on the next `check` or `sync` run.

#### exportify cache stats

```console
exportify cache stats
```

Show detailed cache statistics.
