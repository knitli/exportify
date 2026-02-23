<!--
SPDX-FileCopyrightText: 2026 Knitli Inc.

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Test Suite

Comprehensive test suite for exportify. Currently 746 tests with 94% coverage.

## Running Tests

```bash
# All tests
uv run pytest tests/

# Single file
uv run pytest tests/test_rules.py

# Single test
uv run pytest tests/test_rules.py::test_priority_ordering

# With coverage
uv run pytest tests/ --cov=exportify --cov-report=term-missing

# By marker
uv run pytest -m integration
uv run pytest -m benchmark
uv run pytest -m "not benchmark"
```

## Test Files

| File | Coverage |
|------|----------|
| `test_ast_parser.py` | AST parsing, symbol extraction, overload grouping |
| `test_benchmarks.py` | Performance benchmarks (marked `benchmark`) |
| `test_cache.py` | `JSONAnalysisCache` — hits, misses, persistence, circuit breaker |
| `test_cli.py` | CLI commands via cyclopts |
| `test_cli_helpers.py` | CLI helper utilities |
| `test_cli_integration.py` | End-to-end CLI invocations |
| `test_cli_simple.py` | Lightweight CLI smoke tests |
| `test_code_preservation.py` | Sentinel-based code preservation across regeneration |
| `test_config.py` | Config file loading and search order |
| `test_discovery.py` | File discovery in source trees |
| `test_file_writer.py` | Atomic file writes, backup handling |
| `test_generator.py` | `__init__.py` code generation |
| `test_graph.py` | Propagation DAG, export propagation, deduplication |
| `test_import_categorization.py` | Import classification (defined/imported/alias) |
| `test_import_vs_definition.py` | Symbol provenance edge cases |
| `test_integration.py` | Full pipeline: discovery → parse → rules → graph → generate |
| `test_migration.py` | `exportify init` config generation |
| `test_overload_handling.py` | `@overload` decorator grouping |
| `test_pipeline.py` | 5-stage pipeline orchestration |
| `test_rules.py` | Rule engine: priority ordering, pattern matching, propagation |
| `test_type_alias_detection.py` | `TypeAlias` / `type` statement detection |
| `test_type_checking_imports.py` | `TYPE_CHECKING` block handling |
| `test_types.py` | Core data types and enums |
| `test_utils.py` | Utility functions |
| `test_validator.py` | `LateImportValidator`, `ImportResolver`, `ConsistencyChecker` |

## Fixtures

`conftest.py` provides shared fixtures. `fixtures/` contains sample Python files used by the AST parser and validator tests.

## Markers

| Marker | Description |
|--------|-------------|
| `integration` | Tests that run the full pipeline or invoke the CLI |
| `benchmark` | Performance tests — slower, skipped in normal runs |

## Coverage Targets

Current overall coverage: **94%**. New code should maintain or improve this. Run:

```bash
uv run pytest tests/ --cov=exportify --cov-report=html
open htmlcov/index.html
```
