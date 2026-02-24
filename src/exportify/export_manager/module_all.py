# SPDX-FileCopyrightText: 2026 Knitli Inc.
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Check and fix __all__ declarations in regular (non-__init__) Python modules.

This module provides utilities for managing ``__all__`` in ordinary Python source
files (e.g. ``mypackage/core/utils.py``), as opposed to package ``__init__.py``
files, which are handled by the main code-generation pipeline.

The public interface consists of two functions:

- :func:`check_module_all` — report discrepancies between the actual ``__all__``
  and what the configured rules prescribe.
- :func:`fix_module_all` — rewrite ``__all__`` so that it matches the rules,
  either in-place or as a dry-run.
"""

from __future__ import annotations

import ast

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import textcase

from exportify.analysis.ast_parser import ASTParser
from exportify.common.types import RuleAction, SymbolProvenance
from exportify.export_manager.rules import RuleEngine


# ---------------------------------------------------------------------------
# Sort key (mirrors ExportManifest.export_names / generator._export_sort_key)
# ---------------------------------------------------------------------------


def _export_sort_key(name: str) -> tuple[Literal[0, 1, 2], str]:
    """Sort key: SCREAMING_SNAKE (0), PascalCase (1), snake_case (2).

    Args:
        name: Export name to classify.

    Returns:
        Tuple of (group_number, lowercase_name) for stable sorting.
    """
    if textcase.constant.match(name):
        return (0, name.lower())
    return (1, name.lower()) if textcase.pascal.match(name) else (2, name.lower())


# ---------------------------------------------------------------------------
# Public dataclasses
# ---------------------------------------------------------------------------


@dataclass
class ModuleAllIssue:
    """An issue found with ``__all__`` in a regular module.

    Attributes:
        file: Path to the Python source file.
        issue_type: One of ``"missing"``, ``"extra"``, or ``"no_all"``.
        symbol_name: The symbol name involved in the issue.
        message: Human-readable description of the issue.
    """

    file: Path
    issue_type: Literal["missing", "extra", "no_all"]
    symbol_name: str
    message: str


@dataclass
class ModuleAllFixResult:
    """Result of fixing ``__all__`` in a regular module.

    Attributes:
        file: Path to the Python source file.
        was_modified: Whether the file was (or would be) modified.
        dry_run: If ``True`` the file was not written to disk.
        added: Names added (or that would be added) to ``__all__``.
        removed: Names removed (or that would be removed) from ``__all__``.
        created: ``True`` when ``__all__`` was created from scratch because it
            did not exist before.
    """

    file: Path
    was_modified: bool
    dry_run: bool
    added: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    created: bool = False


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _compute_rule_actions(
    file: Path, module_path: str, rules: RuleEngine, tree: ast.Module | None = None
) -> dict[str, RuleAction]:
    """Return a mapping of symbol name to RuleAction for all DEFINED_HERE symbols.

    Only ``DEFINED_HERE`` symbols are considered; imports are intentionally
    excluded.

    Args:
        file: Path to the Python source file.
        module_path: Dotted module path (e.g. ``"mypackage.core.utils"``).
        rules: Configured :class:`~exportify.export_manager.rules.RuleEngine`.
        tree: Optional already-parsed AST module.  Unused by the current
            implementation but accepted so callers can signal intent; the
            ASTParser re-reads the file internally via its own path-based API.

    Returns:
        Mapping of symbol name to its :class:`~exportify.common.types.RuleAction`.
    """
    result = ASTParser().parse_file(file, module_path)
    return {
        symbol.name: rules.evaluate(symbol, module_path).action
        for symbol in result.symbols
        if symbol.provenance is SymbolProvenance.DEFINED_HERE
    }


def _find_all_node(tree: ast.Module) -> ast.Assign | None:
    """Find the module-level ``__all__ = ...`` assignment node, if present.

    Only the *first* top-level assignment whose sole target is ``__all__`` is
    returned.  Augmented assignments (``__all__ += [...]``) are ignored.

    Args:
        tree: Parsed AST of the module.

    Returns:
        The :class:`ast.Assign` node or ``None``.
    """
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if (
            len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id == "__all__"
        ):
            return node
    return None


def _extract_all_names(node: ast.Assign) -> list[str]:
    """Extract the string constants from an ``__all__`` assignment node.

    Supports both list (``[...]``) and tuple (``(...)``) literal values.
    Non-string elements are silently ignored.

    Args:
        node: The ``__all__`` assignment node.

    Returns:
        Ordered list of names in ``__all__``.
    """
    value = node.value
    if not isinstance(value, ast.List | ast.Tuple):
        return []
    return [
        elt.value
        for elt in value.elts
        if isinstance(elt, ast.Constant) and isinstance(elt.value, str)
    ]


def _detect_all_format(node: ast.Assign) -> Literal["list", "tuple"]:
    """Return whether the existing ``__all__`` uses a list or tuple literal.

    Args:
        node: The ``__all__`` assignment node.

    Returns:
        ``"list"`` or ``"tuple"``.
    """
    return "list" if isinstance(node.value, ast.List) else "tuple"


def _render_all(names: list[str], fmt: Literal["list", "tuple"]) -> str:
    """Render an ``__all__`` assignment as source text.

    Args:
        names: Names to include, already in the desired order.
        fmt: Whether to render as a ``list`` or ``tuple``.

    Returns:
        Source text for the complete ``__all__ = ...`` assignment.
    """
    if not names:
        return "__all__ = []" if fmt == "list" else "__all__ = ()"

    open_br = "[" if fmt == "list" else "("
    close_br = "]" if fmt == "list" else ")"

    if len(names) == 1:
        if fmt == "tuple":
            return f'__all__ = ("{names[0]}",)'
        if fmt == "list":
            return f'__all__ = ["{names[0]}"]'

    lines = [f"__all__ = {open_br}"]
    lines.extend(f'    "{name}",' for name in names)
    lines.append(f"{close_br}")
    return "\n".join(lines)


def _merge_names(
    existing: list[str], should_export: set[str], should_exclude: set[str]
) -> tuple[list[str], list[str], list[str]]:
    """Compute the merged ``__all__`` name list together with diff information.

    The merge strategy:
    - Names present in *existing* that are in *should_export* or have
      NO_DECISION (i.e., not in *should_exclude*) are kept in their original
      relative order.
    - New names (``should_export - existing``) are appended in sorted order
      (using :func:`_export_sort_key`).
    - Names in *existing* that are in *should_exclude* are removed.
      Names with NO_DECISION that are already in ``__all__`` are left alone.

    Args:
        existing: Current, ordered list of names in ``__all__``.
        should_export: Set of names with ``INCLUDE`` action from the rule engine.
        should_exclude: Set of names with ``EXCLUDE`` action from the rule engine.

    Returns:
        Three-tuple of ``(merged_names, added_names, removed_names)``.
    """
    existing_names_collection = set(existing)
    added = sorted(should_export - existing_names_collection, key=_export_sort_key)
    # Only remove names that are explicitly EXCLUDED, not NO_DECISION.
    removed = sorted(existing_names_collection & should_exclude)

    # Keep names that are either INCLUDE or NO_DECISION (not in should_exclude).
    # Append newly required INCLUDE names in sorted order.
    merged = [n for n in existing if n not in should_exclude] + added
    return merged, added, removed


# ---------------------------------------------------------------------------
# Node line-range helper
# ---------------------------------------------------------------------------


def _node_line_range(source_lines: list[str], node: ast.Assign) -> tuple[int, int]:
    """Return the inclusive 0-based line range occupied by *node* in the source.

    ``ast.Assign`` gives us ``node.lineno`` (1-based start) but the ``end_lineno``
    attribute (Python 3.8+) is the most reliable way to determine where the
    statement ends.

    Args:
        source_lines: Source split into lines (no newline terminators needed).
        node: The AST assignment node.

    Returns:
        ``(start_idx, end_idx)`` where both are 0-based indices into
        *source_lines*, inclusive.
    """
    start = node.lineno - 1  # Convert 1-based to 0-based
    # end_lineno is available from Python 3.8+; fall back to start if missing.
    end = getattr(node, "end_lineno", node.lineno) - 1
    return start, end


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def check_module_all(file: Path, module_path: str, rules: RuleEngine) -> list[ModuleAllIssue]:
    """Check that ``__all__`` in a regular module matches what the rules prescribe.

    Returns a list of :class:`ModuleAllIssue` objects:

    - ``"missing"`` — a name the rules say should be exported (``INCLUDE``) is
      absent from ``__all__``.
    - ``"extra"`` — a name in ``__all__`` that the rules explicitly say should
      *not* be exported (``EXCLUDE``).  Names with ``NO_DECISION`` that are
      already in ``__all__`` are **not** flagged.
    - ``"no_all"`` — ``__all__`` is absent entirely but the rules prescribe at
      least one export.  A single issue with an empty ``symbol_name`` is returned.

    If neither ``__all__`` is present nor any exports are prescribed, an empty
    list is returned (nothing to do).

    Args:
        file: Path to the Python source file.
        module_path: Dotted module path (e.g. ``"mypackage.core.utils"``).
        rules: Configured :class:`~exportify.export_manager.rules.RuleEngine`.

    Returns:
        Possibly-empty list of :class:`ModuleAllIssue` instances.
    """
    # Parse file once; pass tree to _find_all_node to avoid a second parse.
    source = file.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source, filename=str(file))
    except SyntaxError:
        # Cannot analyze a file with syntax errors; report nothing.
        return []

    # Compute rule actions (ASTParser reads the file again internally, but
    # the AST we hold is used for __all__ location — see Issue 3 rationale
    # in the module docstring).
    rule_actions = _compute_rule_actions(file, module_path, rules, tree)
    should_export: set[str] = {
        name for name, action in rule_actions.items() if action is RuleAction.INCLUDE
    }
    should_exclude: set[str] = {
        name for name, action in rule_actions.items() if action is RuleAction.EXCLUDE
    }

    all_node = _find_all_node(tree)

    if all_node is None:
        if not should_export:
            # Nothing to export and no __all__ — perfectly fine.
            return []
        # __all__ is absent but rules want exports.
        return [
            ModuleAllIssue(
                file=file,
                issue_type="no_all",
                symbol_name="",
                message=(
                    f"{file}: __all__ is absent but {len(should_export)} export(s) "
                    f"are prescribed by rules: {sorted(should_export)}"
                ),
            )
        ]

    actual = set(_extract_all_names(all_node))
    issues: list[ModuleAllIssue] = [
        ModuleAllIssue(
            file=file,
            issue_type="missing",
            symbol_name=name,
            message=(
                f"{file}: '{name}' should be in __all__ (rules prescribe INCLUDE) but is absent"
            ),
        )
        for name in sorted(should_export - actual)
    ]
    # Only flag names that are explicitly EXCLUDED — not NO_DECISION names.
    issues.extend(
        ModuleAllIssue(
            file=file,
            issue_type="extra",
            symbol_name=name,
            message=(f"{file}: '{name}' is in __all__ but rules say EXCLUDE"),
        )
        for name in sorted(actual & should_exclude)
    )

    return issues


def fix_module_all(
    file: Path, module_path: str, rules: RuleEngine, *, dry_run: bool = False
) -> ModuleAllFixResult:
    """Update ``__all__`` in a regular module to match what the rules prescribe.

    Behavior:

    - If ``__all__`` already exists: names with ``EXCLUDE`` action are removed,
      names with ``INCLUDE`` action that are missing are appended (sorted), and
      names with ``NO_DECISION`` that are already present are left untouched.
      The existing ordering of retained names is preserved.
    - If ``__all__`` is absent: it is created at the end of the file (preceded
      by a blank line) as a tuple literal, sorted by :func:`_export_sort_key`.
    - If no exports are prescribed **and** ``__all__`` is absent, the file is
      left unchanged (``was_modified=False``).
    - When *dry_run* is ``True`` the function computes and returns what *would*
      change but does not write to disk.

    Args:
        file: Path to the Python source file.
        module_path: Dotted module path (e.g. ``"mypackage.core.utils"``).
        rules: Configured :class:`~exportify.export_manager.rules.RuleEngine`.
        dry_run: When ``True``, return the result without modifying the file.

    Returns:
        A :class:`ModuleAllFixResult` describing what was (or would be) done.
    """
    # Parse file once; reuse the tree for both __all__ location and rule
    # action computation (avoids a second read+parse of the same file).
    source = file.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source, filename=str(file))
    except SyntaxError:
        # Cannot safely rewrite a file with syntax errors; return a no-op.
        return ModuleAllFixResult(file=file, was_modified=False, dry_run=dry_run)

    rule_actions = _compute_rule_actions(file, module_path, rules, tree)
    should_export: set[str] = {
        name for name, action in rule_actions.items() if action is RuleAction.INCLUDE
    }
    should_exclude: set[str] = {
        name for name, action in rule_actions.items() if action is RuleAction.EXCLUDE
    }

    all_node = _find_all_node(tree)
    source_lines = source.splitlines()

    # ------------------------------------------------------------------
    # Case 1: __all__ does not exist
    # ------------------------------------------------------------------
    if all_node is None:
        return _generate_all_from_exports(should_export, file, dry_run=dry_run, source=source)
    # ------------------------------------------------------------------
    # Case 2: __all__ exists — compute diff and rewrite
    # ------------------------------------------------------------------
    existing_names = _extract_all_names(all_node)
    fmt = _detect_all_format(all_node)
    merged, added, removed = _merge_names(existing_names, should_export, should_exclude)

    if not added and not removed:
        # Already in sync.
        return ModuleAllFixResult(file=file, was_modified=False, dry_run=dry_run)

    new_all_text = _render_all(merged, fmt=fmt)
    start_idx, end_idx = _node_line_range(source_lines, all_node)

    # Replace the lines occupied by the old __all__ assignment with the new
    # rendered text (which may span multiple lines).
    new_lines = source_lines[:start_idx] + new_all_text.splitlines() + source_lines[end_idx + 1 :]
    new_source = "\n".join(new_lines)
    # Preserve a trailing newline if the original had one.
    if source.endswith("\n") and not new_source.endswith("\n"):
        new_source += "\n"

    if not dry_run:
        file.write_text(new_source, encoding="utf-8")

    return ModuleAllFixResult(
        file=file, was_modified=True, dry_run=dry_run, added=added, removed=removed, created=False
    )


def _generate_all_from_exports(
    should_export: set[str], file: Path, *, dry_run: bool, source: str
) -> ModuleAllFixResult:
    """Generate a new __all__ declaration from the prescribed exports when __all__ is absent."""
    if not should_export:
        # Nothing to create.
        return ModuleAllFixResult(file=file, was_modified=False, dry_run=dry_run)

    sorted_names = sorted(should_export, key=_export_sort_key)
    new_all_text = _render_all(sorted_names, fmt="tuple")

    new_source = _append_all(source, new_all_text)

    if not dry_run:
        file.write_text(new_source, encoding="utf-8")

    return ModuleAllFixResult(
        file=file, was_modified=True, dry_run=dry_run, added=sorted_names, removed=[], created=True
    )


# ---------------------------------------------------------------------------
# Internal: append helper
# ---------------------------------------------------------------------------


def _append_all(source: str, new_all_text: str) -> str:
    """Append a new ``__all__`` declaration to the end of *source*.

    A blank separator line is inserted between the existing content and the new
    declaration.  A trailing newline is ensured at the very end.

    Args:
        source: Current file source text.
        new_all_text: The rendered ``__all__ = ...`` source text.

    Returns:
        Updated source text.
    """
    stripped = source.rstrip()
    return f"{stripped}\n\n{new_all_text}\n"


__all__ = ("ModuleAllFixResult", "ModuleAllIssue", "check_module_all", "fix_module_all")
