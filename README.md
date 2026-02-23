<!--
SPDX-FileCopyrightText: 2026 Knitli Inc.

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# exportify

**exportify** is a CLI tool and library for managing Python package exports: generating `__init__.py` files with lazy imports (using [`lateimport`](https://github.com/knitli/lateimport)), managing `__all__` declarations, and validating import consistency.

Exportify was previously developed as an internal dev tool to assist with our [CodeWeaver](https://github.com/knitli/codeweaver) project; it slowly grew in function until it didn't make sense to keep it as part of that project. Here it is for anyone to use.

## What it Does

Exportify **solves the problem of managing consistency and updates in export patterns across a codebase.** It ensures module and package-level `__all__` exports are consistent, accurate, and complete. It can also validate 

Exportify offers a simple rule-based system for enforcing `__all__` and `__init__` patterns across a codebase with optional per-file overrides. Comes with sane defaults.

## Features

- **Lazy `__init__.py` generation** — generates `__init__.py` files using a lazy `__getattr__` pattern powered by [`lateimport`](https://pypi.org/project/lateimport/), keeping package imports fast and circular-import-free
- **YAML-driven rule engine** — declarative rules control which symbols are exported, with priority ordering and pattern matching
- **Export propagation** — symbols exported from submodules automatically propagate up the package hierarchy
- **Code preservation** — manually written code above the `# === MANAGED EXPORTS ===` sentinel is preserved across regeneration
- **Validation** — checks that lazy import calls are well-formed and that `__all__` declarations are consistent
- **Cache** — SHA-256-based analysis cache for fast incremental updates

## Installation

Easiest to install with [`uv`](https://docs.astral.sh/uv/getting-started/installation/):

```bash
uv tool install exportify
```

or `pipx`:

```bash
pipx install exportify
```

Python 3.12+ required.

## Quick Start

```bash
# Create a default config file (.exportify/config.yaml)
exportify init

# Check current state — runs all checks by default
exportify check

# Bootstrap __init__.py files for packages that don't have one
exportify generate

# Preview what fix would change without writing anything
exportify fix --dry-run

# Sync exports and __all__ to match rules
exportify fix

# Show overall export/import health
exportify status
```

## Documentation

### For new users

| Document | Description |
|----------|-------------|
| [Getting Started](docs/getting-started.md) | Step-by-step tutorial for new projects |

### Reference

| Document | Description |
|----------|-------------|
| [CLI Reference](docs/cli-reference.md) | Complete command reference with all flags |
| [Rule Engine](src/exportify/rules/README.md) | Rule syntax, priorities, match criteria, provenance |
| [Configuration](docs/init.md) | Initializing and configuring exportify |

### Guides

| Document | Description |
|----------|-------------|
| [Troubleshooting & FAQ](docs/troubleshooting.md) | Common issues and answers |
| [Contributing](docs/contributing.md) | Development setup and how to contribute |

### Internals (for contributors)

| Document | Description |
|----------|-------------|
| [Caching](docs/caching.md) | Cache implementation and API |
| [Overload Handling](docs/overload-handling.md) | `@overload` decorator support |
| [Provenance Support](docs/provenance.md) | Symbol provenance in rules |
| [Schema Versioning](docs/schema-versioning.md) | Config schema version management |

## Configuration

Rules live in `.exportify/config.yaml` (created by `exportify init` or written manually). Exportify searches for the config file in this order:

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

See the [Rule Engine docs](src/exportify/rules/README.md) for the full rule syntax including logical combinations, match criteria, and advanced propagation options.

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
> To use exportify for lazy `__init__` management, you must add `lateimport` as a runtime dependency.

## Code Preservation

Add a `# === MANAGED EXPORTS ===` sentinel to an existing `__init__.py` to protect manually written code above it:

```python
"""My package."""

from .compat import legacy_function  # kept across regeneration

# === MANAGED EXPORTS ===
# ... generated section below (managed by exportify)
```

Everything above the sentinel is left untouched on every `fix` or `generate` run.

## CLI Reference

| Command | Description |
|---------|-------------|
| `exportify check` | Check exports and `__all__` declarations for consistency |
| `exportify fix` | Sync exports and `__all__` to match rules |
| `exportify generate` | Bootstrap new `__init__.py` files for packages missing one |
| `exportify status` | Show current export/import health status |
| `exportify doctor` | Run health checks and provide actionable advice |
| `exportify init` | Initialize exportify with a default config file |
| `exportify clear-cache` | Clear the analysis cache |

See the [full CLI reference](docs/cli-reference.md) for all flags and options.

## Requirements

- Python 3.12+
- [`lateimport`](https://pypi.org/project/lateimport/) (installed automatically)

## License

Dual-licensed under MIT and Apache 2.0. See [LICENSE-MIT](LICENSE-MIT) and [LICENSE-Apache-2.0](LICENSE-Apache-2.0).
