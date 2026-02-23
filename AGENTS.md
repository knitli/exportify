# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Exportify** is a CLI tool and library for managing Python package exports: generating `__init__.py` files with lazy imports, managing `__all__` declarations, and validating import consistency. It was extracted from the CodeWeaver monorepo and is being established as a standalone package.

## Commands

```bash
# Install dependencies
uv sync

# Run linter (auto-fixes enabled)
uv run ruff check src/ tests/
uv run ruff format src/ tests/

# Type checking (ty, not mypy)
uv run ty check

# Run all tests
uv run pytest

# Run a single test file
uv run pytest tests/test_rules.py

# Run a specific test
uv run pytest tests/test_rules.py::test_priority_ordering

# Run with markers
uv run pytest -m integration
uv run pytest -m "not benchmark"

# Run the CLI
uv run exportify --help
uv run exportify validate
uv run exportify generate --dry-run
uv run exportify analyze --module src/mypackage/core
```

## Architecture

The core workflow is a **5-stage pipeline** (`pipeline.py`):

1. **File Discovery** (`discovery/file_discovery.py`) — Finds Python files in a source tree
2. **AST Parsing** (`analysis/ast_parser.py`) — Extracts `DetectedSymbol` instances from each file, handling `@overload` grouping via `ast_parser_overload.py`
3. **Rule Engine** (`export_manager/rules.py`) — Evaluates YAML-configured rules against each symbol, producing `ExportDecision` objects with `RuleAction` (include/exclude/no_decision) and `PropagationLevel` (none/parent/root)
4. **Propagation Graph** (`export_manager/graph.py`) — Builds the module hierarchy as a DAG and propagates export decisions upward, generating `ExportManifest` objects per module
5. **Code Generation** (`export_manager/generator.py`) — Converts manifests to `__init__.py` files using lazy `__getattr__` pattern; preserves manually written code above the `# === MANAGED EXPORTS ===` sentinel

**Validation** (`validator/`) runs independently: `LazyImportValidator` uses `ImportResolver` and `ConsistencyChecker` to verify that existing lazy import calls resolve correctly and that `__all__` declarations match `_dynamic_imports`.

**Cache** (`common/cache.py`) — `JSONAnalysisCache` stores `AnalysisResult` objects keyed by file path + SHA-256 hash, stored at `.codeweaver/cache/analysis_cache.json`.

## Key Data Types (`common/types.py`)

The type system follows the pipeline phases:
- `DetectedSymbol` — raw AST-extracted symbol with `MemberType` and `SymbolProvenance`
- `ExportDecision` — rule evaluation result for one symbol
- `ExportManifest` — all exports for a single module after propagation
- `LazyExport` — a single entry in a generated `__init__.py`

Enums: `MemberType` (class/function/constant/variable/type_alias/imported), `SymbolProvenance` (defined_here/imported/alias_imported), `RuleAction` (include/exclude/no_decision), `PropagationLevel` (none/parent/root/custom).

## Rule System (`src/exportify/rules/`)

Rules live in YAML files with `schema_version: "1.0"`. The rule engine evaluates rules in **priority order (0–1000, highest first)**; ties break alphabetically by rule name. First matching rule wins.

Rule priority bands:
- **1000**: Absolute exclusions (private, dunders)
- **900–800**: Infrastructure/framework exclusions
- **700**: Primary export rules (defined classes, functions, constants)
- **600–500**: Import handling
- **300–400**: Special cases
- **0–200**: Defaults/fallbacks

Override files (`overrides/*.yaml`) bypass all rules — use sparingly.

## Code Preservation in Generated Files

The generator uses a **sentinel-based section system**: code above `# === MANAGED EXPORTS ===` is "preserved" and kept on regeneration. Code below is fully managed. `SectionParser` (`export_manager/section_parser.py`) uses AST analysis to identify managed vs. preserved sections in existing files.

## CLI (`cli.py`)

Built with [Cyclopts](https://github.com/BrianPugh/cyclopts). Commands: `validate`, `generate`, `analyze`, `doctor`, `migrate`, `status`, `clear-cache`. The `generate` command loads rules from `.codeweaver/lazy_import_rules.yaml` by default (falling back to built-in defaults if absent).

## Code Style

- **Formatter/linter**: ruff (line length 100, Google-style docstrings, Python 3.12+ target)
- **Type checker**: `ty` (Astral) — configured in `pyproject.toml` under `[tool.ty]`
- **Imports**: `from __future__ import annotations` at top of all modules; `TYPE_CHECKING` blocks for type-only imports
- **License headers**: SPDX headers required on all source files (`MIT OR Apache-2.0`)
- Test files have relaxed ruff rules (see `ruff.toml` `[lint.per-file-ignores]`)
