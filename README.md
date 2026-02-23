<!--
SPDX-FileCopyrightText: 2026 Knitli Inc.

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# exportify

**exportify** is a CLI tool and library for managing Python package exports: generating `__init__.py` files with lazy imports, managing `__all__` declarations, and validating import consistency.

It offers a simple rule-based system for enforcing `__all__` and `__init__` patterns across a codebase with optional per-file overrides. Comes with sane defaults. 

## Features

- **Lazy `__init__.py` generation** — generates `__init__.py` files using a lazy `__getattr__` pattern powered by [`lateimport`](https://pypi.org/project/lateimport/), keeping package imports fast and circular-import-free
- **YAML-driven rule engine** — declarative rules control which symbols are exported, with priority ordering and pattern matching
- **Export propagation** — symbols exported from submodules automatically propagate up the package hierarchy
- **Code preservation** — manually written code above the `# === MANAGED EXPORTS ===` sentinel is preserved across regeneration
- **Validation** — checks that lazy import calls are well-formed and that `__all__` declarations are consistent
- **Analysis** — dry-run mode shows what would be generated without writing files
- **Cache** — SHA-256-based analysis cache for fast incremental updates

## Installation

```bash
pip install exportify
```

## Quick Start

```bash
# Create a default config file (.exportify.yaml)
exportify init

# Analyze what exportify would generate (dry run)
exportify analyze --source src/mypackage

# Generate __init__.py files
exportify generate --source src/mypackage

# Validate existing lazy imports
exportify validate --module src/mypackage/core

# Check overall package status
exportify status
```

## Configuration

Rules live in `.exportify.yaml` (created by `exportify migrate` or written manually). Exportify searches for the config file in this order:

1. `EXPORTIFY_CONFIG` environment variable (any path)
2. `.exportify/config.yaml`
3. `.exportify/config.yml`
4. `.exportify.yaml` in the current working directory
5. `.exportify.yml`
6. `exportify.yaml`
7. `exportify.yml`

```yaml
schema_version: "1.0"

rules:
  - name: "exclude-private"
    priority: 1000
    match:
      name_pattern: "^_"
    action: exclude

  - name: "include-public-classes"
    priority: 700
    match:
      name_pattern: "^[A-Z]"
      member_types: [class]
    action: include
    propagate: root

  - name: "include-public-functions"
    priority: 700
    match:
      name_pattern: "^[a-z]"
      member_types: [function]
    action: include
    propagate: parent
```

### Rule Priority Bands

| Priority | Purpose |
|----------|---------|
| 1000 | Absolute exclusions (private, dunders) |
| 900–800 | Infrastructure/framework exclusions |
| 700 | Primary export rules (classes, functions) |
| 600–500 | Import handling |
| 300–400 | Special cases |
| 0–200 | Defaults/fallbacks |

### Propagation Levels

- `none` — export only in the defining module
- `parent` — export in the defining module and its direct parent
- `root` — export all the way to the package root
- `custom` — specify explicit target module

## Generated Output

Exportify generates `__init__.py` files using the lazy `__getattr__` pattern from `lateimport`:

```python
# SPDX-FileCopyrightText: 2026 Your Name
#
# SPDX-License-Identifier: MIT

# === MANAGED EXPORTS ===
# This section is automatically generated. Manual edits below this line will be overwritten.

from __future__ import annotations

from typing import TYPE_CHECKING
from types import MappingProxyType

from lateimport import create_late_getattr

if TYPE_CHECKING:
    from mypackage.core import MyClass
    from mypackage.utils import helper_function

_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({
    "MyClass": (__spec__.parent, "core"),
    "helper_function": (__spec__.parent, "utils"),
})

__getattr__ = create_late_getattr(_dynamic_imports, globals(), __name__)

__all__ = ("MyClass", "helper_function")

def __dir__() -> list[str]:
    """List available attributes for the package."""
    return list(__all__)
```

> [!IMPORTANT]
> To use exportify for lazy __init__ management, you must add `lateimport` as a runtime dependency.

## Code Preservation

Add a `# === MANAGED EXPORTS ===` sentinel to an existing `__init__.py` to protect manually written code above it:

```python
"""My package."""

from .compat import legacy_function  # kept across regeneration

# === MANAGED EXPORTS ===
# ... generated section below (managed by exportify)
```

## CLI Reference

```
exportify init      Create a default .exportify.yaml config file
exportify analyze   Dry-run analysis showing what would be generated
exportify generate  Generate __init__.py files
exportify validate  Validate existing lazy import calls
exportify status    Show package export status
exportify doctor    Diagnose configuration issues
exportify clear-cache  Clear the analysis cache
```

## Requirements

- Python 3.12+
- [`lateimport`](https://pypi.org/project/lateimport/) (installed automatically)

## License

Dual-licensed under MIT and Apache 2.0. See [LICENSE-MIT](LICENSE-MIT) and [LICENSE-Apache-2.0](LICENSE-Apache-2.0).
