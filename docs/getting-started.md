<!--
SPDX-FileCopyrightText: 2026 Knitli Inc.

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Getting Started with Exportify

Exportify manages the public API of your Python packages: it analyzes your source tree, applies a YAML rule set to decide which symbols to export, and writes or updates `__init__.py` files with lazy-loading imports, `__all__` declarations, and `TYPE_CHECKING` blocks — all in a single command.

## Installation

```bash
pip install exportify
```

Python 3.12 or later is required.

## Step 1: Initialize

Run `exportify init` in your project root to create a starter config file:

```bash
exportify init
```

This writes `.exportify/config.yaml` with a set of default rules that work for most packages:

```yaml
schema_version: "1.0"

rules:
  - name: exclude-private-members
    priority: 900
    description: Exclude private members (starting with underscore)
    match:
      name_pattern: ^_.*
    action: exclude

  - name: propagate-exceptions
    priority: 800
    description: Propagate exception classes to root package
    match:
      name_pattern: .*Error$|.*Exception$|.*Warning$
      member_type: class
    action: include
    propagate: root

  - name: include-constants
    priority: 700
    description: Include SCREAMING_SNAKE_CASE constants
    match:
      name_pattern: ^[A-Z][A-Z0-9_]+$
      member_type: constant
    action: include
    propagate: parent

  - name: include-public-functions
    priority: 500
    description: Include public functions
    match:
      member_type: function
    action: include
    propagate: parent

  - name: include-public-classes
    priority: 500
    description: Include public classes
    match:
      member_type: class
    action: include
    propagate: parent
```

To preview what would be generated without writing anything:

```bash
exportify init --dry-run
```

To overwrite an existing config:

```bash
exportify init --force
```

For full documentation on the config format and available rule fields, see the [Rule Engine reference](../src/exportify/rules/README.md).

## Step 2: Check Your Current State

Before making any changes, see what exportify finds:

```bash
exportify check --verbose
```

This runs four checks:

- **lateimports** — verifies that any existing `lateimport()` / `LateImport` calls resolve to real modules
- **dynamic-imports** — verifies `_dynamic_imports` entries in `__init__.py` files are consistent
- **module-all** — checks that `__all__` in regular modules matches your export rules
- **package-all** — checks that `__all__` and exports in `__init__.py` files are consistent

The lateimports check is automatically skipped if `lateimport` is not in your project dependencies.

Example output:

```
Checking src/mypackage...
  [OK] lateimports: 0 issues
  [WARN] module-all: 3 modules missing __all__
  [FAIL] package-all: src/mypackage/core/__init__.py: __all__ contains 'internal_helper' (not in rules)
```

To fail CI on warnings as well as errors, use `--strict`:

```bash
exportify check --strict
```

To get machine-readable output:

```bash
exportify check --json
```

## Step 3: Synchronize Your Project

Align your `__init__.py` files and `__all__` declarations with your rules:

```bash
# Preview what would be changed
exportify sync --dry-run

# Apply the changes (creates and updates files)
exportify sync
```

The `sync` command:
- Creates missing `__init__.py` files in package directories
- Updates `_dynamic_imports` and `__all__` in `__init__.py` files
- Updates `__all__` in regular modules to match export rules
- Preserves manually written code above the managed exports sentinel

Generated files contain:
- `__all__` — the list of exported names, determined by your rules
- `_dynamic_imports` — a mapping used by `lateimport` for lazy loading
- `__getattr__` — the lazy-loading hook
- `TYPE_CHECKING` block — type-only imports for type checker compatibility

To sync a specific module or package only:

```bash
exportify sync src/mypackage/core
```

To sync only `__all__` in regular modules:

```bash
exportify sync --module-all
```

## Step 4: Validate and Monitor

Confirm the current state of your project:

```bash
exportify doctor --short
```

Output:

```
[bold]Exportify Status Snapshot[/bold]

Cache Status:
  Entries: 42/42 valid
  Hit rate: 98.0%

Configuration:
  Rules: ✓ .exportify/config.yaml

System:
  Status: Ready
```

For a deeper health check including cache health, rule configuration, export conflicts, and performance:

```bash
exportify doctor
```

## Understanding the Generated Output

Here is a typical generated `__init__.py` for a package called `mypackage.utils`:

```python
# SPDX-FileCopyrightText: 2026 Acme Corp.
# SPDX-License-Identifier: MIT

"""Utility functions for mypackage."""

from __future__ import annotations

from typing import TYPE_CHECKING

# TYPE_CHECKING block — only imported by type checkers, not at runtime
if TYPE_CHECKING:
    from mypackage.utils.formatting import format_output
    from mypackage.utils.parsing import parse_config

# === MANAGED EXPORTS ===

# This section is automatically managed by exportify.
# Manual edits below this line will be overwritten on the next `sync` run.

from types import MappingProxyType

from lateimport import create_late_getattr

# Maps export name -> (package, module)
_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({
    "format_output": (__spec__.parent, "formatting"),
    "parse_config": (__spec__.parent, "parsing"),
})

# Installs __getattr__ for lazy loading: attributes are only imported when first accessed
__getattr__ = create_late_getattr(_dynamic_imports, globals(), __name__)

# Public API surface
__all__ = (
    "format_output",
    "parse_config",
)
```

Key points:

- Code above `# === MANAGED EXPORTS ===` is yours — it is preserved across re-runs.
- The `_dynamic_imports` dict maps each export name to its source module. Imports happen on first attribute access (lazy loading), so importing the package is fast even with many exports.
- `TYPE_CHECKING` imports make type checkers aware of the exported names without incurring runtime import cost.
- `__all__` is the authoritative public API list; it tells tools like `from mypackage.utils import *` what to expose.

## Code Preservation

The sentinel line `# === MANAGED EXPORTS ===` divides each `__init__.py` into two zones:

**Preserved zone** (above the sentinel) — edited freely, never touched by exportify:

```python
"""My package docstring."""

from __future__ import annotations

__version__ = "1.2.3"

# Custom initialization code here
_registry: dict[str, type] = {}

# === MANAGED EXPORTS ===
```

Managed zone (below the sentinel) — fully controlled by exportify, rewritten on each `sync` run.


If a file has no sentinel, exportify treats the entire file as preserved and will not write to it unless you add the sentinel manually or run `sync` (which creates the sentinel for new or empty files).


## Next Steps

- [CLI Reference](cli-reference.md) — complete command and flag reference
- [Rule Engine](../src/exportify/rules/README.md) — full rule schema, priority bands, match criteria, and examples
- [Caching](caching.md) — how the analysis cache works and when to clear it
- [Init / Configuration](init.md) — details on the `init` command and the Python API for generating configs
