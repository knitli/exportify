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

Manage Python package exports: check, fix, and generate `__init__.py` files.

### Table of Contents

- [`check`](#exportify-check)
- [`fix`](#exportify-fix)
- [`generate`](#exportify-generate)
- [`status`](#exportify-status)
- [`doctor`](#exportify-doctor)
- [`init`](#exportify-init)
- [`clear-cache`](#exportify-clear-cache)

**Commands**:

* [`check`](#exportify-check): Check exports and `__all__` declarations for consistency.
* [`clear-cache`](#exportify-clear-cache): Clear the analysis cache.
* [`doctor`](#exportify-doctor): Run health checks and provide actionable advice.
* [`fix`](#exportify-fix): Sync exports and `__all__` declarations to match rules.
* [`generate`](#exportify-generate): Bootstrap new `__init__.py` files for packages that don't have one.
* [`init`](#exportify-init): Initialize exportify with a default configuration file.
* [`status`](#exportify-status): Show current export/import health status.

### exportify check

```console
exportify check [OPTIONS] [ARGS...]
```

Check exports and `__all__` declarations for consistency.

Checks:
- `lateimport()` / `LateImport` calls resolve to real modules (`--lateimports`)
- `_dynamic_imports` entries in `__init__.py` files are consistent (`--dynamic-imports`)
- `__all__` in regular modules matches export rules (`--module-all`)
- `__all__` and exports in `__init__.py` files are consistent (`--package-all`)

If ANY flag is explicitly set to True, only those checks are run.
Use `--no-X` flags to exclude specific checks while running the rest.
If no flags are given, all checks are run.

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

### exportify fix

```console
exportify fix [OPTIONS] [ARGS...]
```

Sync exports and `__all__` declarations to match rules.

Updates:
- `__all__` in regular modules (`--module-all`)
- `_dynamic_imports` and `__all__` in `__init__.py` files (`--dynamic-imports`, `--package-all`)

Does NOT fix `lateimport()` call paths — those require manual correction.

If `--dry-run`: shows what would change without writing any files.

When `__init__.py` is missing entirely, warns and suggests running `generate`.

**Arguments**:

* `PATHS`: Paths to fix (default: whole project)

**Parameters**:

* `--source`: Source root directory
* `--dynamic-imports, --no-dynamic-imports`: Fix `_dynamic_imports` entries in `__init__.py` files
* `--module-all, --no-module-all`: Fix `__all__` in regular modules
* `--package-all, --no-package-all`: Fix `__all__` and exports in `__init__.py` files
* `--dry-run, --no-dry-run`: Show what would change without writing  *[default: False]*
* `--verbose, --no-verbose`: Show detailed output  *[default: False]*

### exportify generate

```console
exportify generate [ARGS]
```

Bootstrap new `__init__.py` files for packages that don't have one.

Analyzes the codebase and creates `__init__.py` files for packages that are
currently missing them, with:
- Proper `__all__` declarations
- `lateimport()` calls for exports (or barrel imports if configured)
- `TYPE_CHECKING` imports where appropriate

Use `fix` to update existing `__init__.py` files.

**Parameters**:

* `MODULE, --module`: Generate for specific module
* `SOURCE, --source`: Source root directory
* `OUTPUT, --output`: Output directory (default: same as source)
* `DRY-RUN, --dry-run, --no-dry-run`: Show changes without writing files  *[default: False]*

### exportify status

```console
exportify status [OPTIONS]
```

Show current export/import health status.

Displays:
- Cache statistics
- Validation status
- Rule configuration status
- Recent activity

**Parameters**:

* `--verbose, --no-verbose`: Show detailed information  *[default: False]*

### exportify doctor

```console
exportify doctor
```

Run health checks and provide actionable advice.

Checks:
- Cache health and validity
- Rule configuration
- Export conflicts
- Performance issues

Provides recommendations for improvements.

### exportify init

```console
exportify init [OPTIONS] [ARGS]
```

Initialize exportify with a default configuration file.

Creates `.exportify/config.yaml` in the current directory with sensible default
rules that work for most Python packages. Edit the file afterwards to
customize which symbols are exported and how they propagate.

**Parameters**:

* `OUTPUT, --output`: Output path for the config YAML  *[default: .exportify/config.yaml]*
* `--dry-run, --no-dry-run`: Show generated config without writing files  *[default: False]*
* `--force, --no-force`: Overwrite existing config file  *[default: False]*
* `--verbose, --no-verbose`: Show full configuration summary  *[default: False]*

### exportify clear-cache

```console
exportify clear-cache
```

Clear the analysis cache.

Removes all cached analysis results. The cache will be rebuilt
on the next validation or generation run.

Use this when:
- Cache is corrupted
- Schema version changed
- Performance issues
