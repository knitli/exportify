<!--
SPDX-FileCopyrightText: 2026 Knitli Inc.

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Contributing to exportify

Thank you for your interest in contributing. This guide covers development setup, code standards, project layout, and the process for submitting changes.

## Development Setup

### Prerequisites

- Python 3.12+
- [`uv`](https://github.com/astral-sh/uv) (package and environment manager)

### Clone and install

```bash
git clone https://github.com/knitli/exportify
cd exportify

# Install all dependencies (including dev extras)
uv sync
```

### Running tests

```bash
# Run the full test suite
uv run pytest

# Run with coverage report
uv run pytest tests/ --cov=exportify --cov-report=term-missing

# Run a single test file
uv run pytest tests/test_rules.py

# Run a specific test
uv run pytest tests/test_rules.py::test_priority_ordering

# Run only integration tests
uv run pytest -m integration

# Skip benchmarks
uv run pytest -m "not benchmark"
```

### Linting and formatting

```bash
# Check and auto-fix lint issues
uv run ruff check src/ tests/

# Format code
uv run ruff format src/ tests/
```

### Type checking

```bash
uv run ty check
```

> [!NOTE]
> This project uses `ty` (from Astral, the makers of `ruff`), not `mypy`. Make sure you are running `ty` and not `mypy` when type-checking.

### Running the CLI locally

```bash
uv run exportify --help
uv run exportify check
uv run exportify sync --dry-run
```

## Code Style

- **Formatter/linter**: `ruff` with line length 100, Google-style docstrings, Python 3.12+ target
- **Type checker**: `ty` (Astral) — not mypy
- **Imports**: All modules start with `from __future__ import annotations`; type-only imports go in `TYPE_CHECKING` blocks
- **License headers**: Every source file requires an SPDX header:

```python
# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0
```

Markdown and YAML files use the HTML comment form:

```html
<!--
SPDX-FileCopyrightText: 2026 Knitli Inc.

SPDX-License-Identifier: MIT OR Apache-2.0
-->
```

Test files have relaxed lint rules (see `ruff.toml` `[lint.per-file-ignores]`).

## Project Structure

```
src/exportify/
  cli.py                     # CLI entry point (cyclopts App, registers all commands)
  commands/                  # CLI command implementations
    init.py                  # exportify init
    sync.py                  # exportify sync
    check.py                 # exportify check
    undo.py                  # exportify undo
    doctor.py                # exportify doctor
    cache.py                 # exportify cache
    utils.py                 # Shared CLI helpers (output, config loading, file collection)
  export_manager/            # Core pipeline components
    rules.py                 # Rule engine — evaluates YAML rules against symbols
    graph.py                 # Propagation DAG — propagates exports up module hierarchy
    generator.py             # Code generation — converts manifests to __init__.py files
    section_parser.py        # Section parsing — preserves code above the managed sentinel
    module_all.py            # __all__ checking and fixing for regular modules
  analysis/                  # AST parsing and symbol extraction
    ast_parser.py            # Extracts DetectedSymbol instances from source files
    ast_parser_overload.py   # @overload grouping logic
  discovery/                 # File discovery
    file_discovery.py        # Finds Python files in a source tree
  validator/                 # Import validation
    validator.py             # LateImportValidator — validates lazy import calls
    resolver.py              # ImportResolver — resolves module paths
    consistency.py           # ConsistencyChecker — validates __all__ consistency
  common/                    # Shared types, cache, utilities
    types.py                 # Core data types (DetectedSymbol, ExportDecision, etc.)
    cache.py                 # JSONAnalysisCache — SHA-256-keyed file analysis cache
    config.py                # Config file loading and search
  rules/                     # Default YAML rule files
    default_rules.yaml       # Built-in rule set (reference and template)
    README.md                # Rule engine documentation
  pipeline.py                # 5-stage pipeline orchestrator
  migration.py               # Config generation (used by exportify init)
  utils.py                   # Utility functions (source root detection, etc.)
tests/
  fixtures/                  # Test fixture files (sample Python modules)
  test_pipeline.py           # Pipeline integration tests
  test_rules.py              # Rule engine unit tests
  test_validator.py          # Validator unit tests
  ...                        # Additional per-module test files
```

## Pipeline Overview

The core workflow is a five-stage pipeline (`pipeline.py`):

1. **File Discovery** (`discovery/file_discovery.py`) — finds Python files in a source tree
2. **AST Parsing** (`analysis/ast_parser.py`) — extracts `DetectedSymbol` instances from each file, handling `@overload` grouping
3. **Rule Engine** (`export_manager/rules.py`) — evaluates YAML-configured rules against each symbol, producing `ExportDecision` objects
4. **Propagation Graph** (`export_manager/graph.py`) — builds the module hierarchy as a DAG and propagates export decisions upward, generating `ExportManifest` objects per module
5. **Code Generation** (`export_manager/generator.py`) — converts manifests to `__init__.py` files using the lazy `__getattr__` pattern; preserves manually written code above the `# === MANAGED EXPORTS ===` sentinel

## Adding Rules

Built-in rules live in `src/exportify/rules/default_rules.yaml`. See the [Rule Engine documentation](../src/exportify/rules/README.md) for the full YAML syntax.

When adding a new built-in rule:

1. Understand the existing priority bands before choosing a priority
2. Write clear `name` and `description` fields
3. Use specific `match` criteria — prefer narrow patterns over broad catches
4. Test the rule against real source files before committing
5. Update `src/exportify/rules/README.md` if the rule introduces a new pattern

User-defined rules go in the project config file (`.exportify/config.yaml`), not in `default_rules.yaml`.

## Adding Tests

- Test files live in `tests/`, named `test_*.py`
- Aim for 100% coverage on new code (the project currently sits at ~94% overall)
- Use `pytest` fixtures; see existing tests for patterns
- Mark integration tests with `@pytest.mark.integration`
- Mark benchmarks with `@pytest.mark.benchmark`
- Fixture files (sample Python modules used in tests) go in `tests/fixtures/`

## Submitting Changes

1. Fork the repository and create a feature branch from `main`
2. Write tests for your changes
3. Run `uv run ruff check src/ tests/` and `uv run ty check` — fix any issues before opening a PR
4. Run `uv run pytest` — all tests must pass
5. Open a pull request with a clear description of what changed and why

Commit messages should follow the conventional commits format where practical (e.g., `feat:`, `fix:`, `refactor:`, `test:`, `docs:`).

## Reporting Issues

Open an issue at <https://github.com/knitli/exportify/issues> and include:

- What you expected to happen
- What actually happened (error message, unexpected output, etc.)
- A minimal reproducible example if possible
- Your Python version and exportify version (`exportify --version` or `pip show exportify`)
