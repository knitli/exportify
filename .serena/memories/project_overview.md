# Exportify Project Overview

## Purpose
CLI tool + library for managing Python package exports: generating `__init__.py` files with lazy imports, managing `__all__` declarations, and validating import consistency. Standalone package extracted from CodeWeaver monorepo.

## Tech Stack
- Python 3.12+
- uv (package manager / venv)
- ruff (linter/formatter, line length 100)
- ty (Astral type checker, NOT mypy)
- pytest (test framework)
- Cyclopts (CLI framework)
- PyYAML (config loading)
- lateimport (lazy import runtime)
- Hatchling + uv-dynamic-versioning (build)

## Key Commands
- `uv sync` — install deps
- `uv run ruff check src/ tests/` — lint
- `uv run ruff format src/ tests/` — format
- `uv run ty check` — type check
- `uv run pytest` — all tests
- `uv run exportify --help` — CLI

## Architecture: 5-Stage Pipeline
1. File Discovery (`discovery/file_discovery.py`)
2. AST Parsing (`analysis/ast_parser.py`) → DetectedSymbol
3. Rule Engine (`export_manager/rules.py`) → ExportDecision
4. Propagation Graph (`export_manager/graph.py`) → ExportManifest
5. Code Generation (`export_manager/generator.py`) → __init__.py files

## Source Layout
- `src/exportify/` — main package
  - `cli.py` — Cyclopts CLI entry point
  - `pipeline.py` — orchestrates the 5-stage pipeline
  - `common/` — shared types, config, cache
  - `export_manager/` — rules, graph, generator, section_parser
  - `analysis/` — AST parsing
  - `discovery/` — file discovery
  - `validator/` — import validation
  - `rules/` — default_rules.yaml
  - `commands/` — CLI command implementations
- `.exportify/config.yaml` — project config for exportify itself
- `tests/` — test suite

## Code Style
- `from __future__ import annotations` in every module
- TYPE_CHECKING blocks for type-only imports
- SPDX headers required: `SPDX-FileCopyrightText: 2026 Knitli Inc.` + `SPDX-License-Identifier: MIT OR Apache-2.0`
- Google-style docstrings
- snake_case (Python), no mixed conventions
