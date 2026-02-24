<!--
SPDX-FileCopyrightText: 2026 Knitli Inc.

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Suggested Commands

## Development
```bash
uv sync                          # install/sync dependencies
uv run ruff check src/ tests/   # lint (auto-fixes enabled with --fix)
uv run ruff format src/ tests/  # format
uv run ty check                  # type check (NOT mypy)
uv run pytest                    # all tests
uv run pytest tests/test_rules.py  # single file
uv run pytest tests/test_rules.py::test_priority_ordering  # single test
uv run pytest -m integration     # by marker
uv run pytest -m "not benchmark" # exclude benchmark tests
```

## CLI
```bash
uv run exportify --help
uv run exportify validate
uv run exportify generate --dry-run
uv run exportify generate
uv run exportify analyze --module src/mypackage/core
uv run exportify doctor
uv run exportify status
uv run exportify clear-cache
```

## Git & System
```bash
git status / git diff / git log
command cat file  # NOTE: `cat` is aliased to `bat --color=always`; use `command cat` when writing to files
```

## After Task Completion
1. `uv run ruff check src/ tests/` — lint
2. `uv run ruff format src/ tests/` — format
3. `uv run ty check` — type check
4. `uv run pytest` — all tests
