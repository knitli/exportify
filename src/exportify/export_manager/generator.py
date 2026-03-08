#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Code generator for __init__.py files from export manifests.

This module implements the Code Generator component that takes ExportManifest
objects and generates properly formatted __init__.py files with:
- AST-based preservation of manual code (type aliases, imports, functions, etc.)
- Lazy loading via __getattr__ and _dynamic_imports
- Type checking support
- __all__ list generation
- Atomic writes with backup and rollback
"""

from __future__ import annotations

import ast
import contextlib
import hashlib

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal

import textcase

from exportify.common.config import SpdxConfig
from exportify.common.types import ExportManifest, LazyExport
from exportify.export_manager.file_writer import FileWriter, WriteResult
from exportify.export_manager.section_parser import SectionParser


if TYPE_CHECKING:
    from collections.abc import Sequence


# Sentinel comment for managed section
SENTINEL = "# === MANAGED EXPORTS ==="
MANAGED_COMMENT = """# Exportify manages this section. It contains lazy-loading infrastructure
# for the package: imports and runtime declarations (__all__, __getattr__,
# __dir__). Manual edits will be overwritten by `exportify fix`."""

# Comment markers for preserved sections
PRESERVED_BEGIN = "# --- BEGIN PRESERVED CODE ---"
PRESERVED_END = "# --- END PRESERVED CODE ---"


def _export_sort_key(name: str) -> tuple[Literal[0, 1, 2], str]:
    """Sort key for exports: SCREAMING_SNAKE (0), PascalCase (1), snake_case (2).

    Args:
        name: Export name to classify

    Returns:
        Tuple of (group_number, lowercase_name) for sorting
    """
    if textcase.constant.match(name):
        group = 0  # SCREAMING_SNAKE_CASE
    elif textcase.pascal.match(name):
        group = 1  # PascalCase
    else:
        group = 2  # snake_case
    return (group, name.lower())


@dataclass(frozen=True)
class GeneratedCode:
    """Generated code for a module's __init__.py file."""

    content: str
    manual_section: str
    managed_section: str
    export_count: int
    hash: str

    @classmethod
    def create(
        cls,
        manual: str,
        managed: str,
        export_count: int,
        *,
        spdx_header: str | None = None,
        add_markers: bool = False,
    ) -> GeneratedCode:
        """Create GeneratedCode with computed hash.

        ``from __future__ import annotations`` must be the first non-comment
        statement in every Python file (only a module docstring and comments may
        precede it).  Because the managed section is placed *after* any preserved
        manual code, we can't put it there — it would be too late in the file
        whenever the manual section contains imports.

        Instead, ``create`` extracts any leading module docstring from *manual*,
        then assembles the file in the correct order:

            SPDX comment headers (if spdx_header is provided)
            Module docstring (if found in manual)
            from __future__ import annotations
            Remaining manual body (stripped of any duplicate future import)
            SENTINEL + managed section (which never includes from __future__)

        Args:
            manual: Manual code section to preserve (may include docstring and
                any ``from __future__ import annotations`` lines — both are
                handled safely).
            managed: Generated managed section (must NOT start with
                ``from __future__ import annotations``).
            export_count: Number of exports
            spdx_header: SPDX comment block to prepend (e.g. the output of
                ``SpdxConfig.build_header()``). ``None`` omits all headers.
            add_markers: Whether to add comment markers around preserved code
                (default: False)
        """
        parts = []

        # Add SPDX headers if provided
        if spdx_header:
            parts.append(spdx_header)

        # --- Docstring extraction ---
        # from __future__ import annotations must come *after* the module
        # docstring but *before* any other imports.  We pull the docstring out
        # of the manual section so we can insert it at the right position.
        manual_body = manual.strip() if manual else ""
        docstring_text = ""

        if manual_body:
            with contextlib.suppress(Exception):
                tree = ast.parse(manual_body)
                if (
                    tree.body
                    and isinstance(tree.body[0], ast.Expr)
                    and isinstance(tree.body[0].value, ast.Constant)
                    and isinstance(tree.body[0].value.value, str)
                ):
                    ds_node = tree.body[0]
                    lines = manual_body.splitlines()
                    # Extract only the docstring lines (not preceding comments)
                    docstring_text = "\n".join(lines[ds_node.lineno - 1 : ds_node.end_lineno])
                    # Remove docstring (and any preceding comments) from body
                    manual_body = "\n".join(lines[ds_node.end_lineno :]).strip()

            # Strip any existing from __future__ import annotations — we always
            # re-emit it at the correct position below.
            clean_lines = [
                line
                for line in manual_body.splitlines()
                if line.strip() != "from __future__ import annotations"
            ]
            manual_body = "\n".join(clean_lines).strip()

        if docstring_text:
            parts.append(docstring_text)

        # from __future__ import annotations — always placed here so it is the
        # first executable statement (after comments and the optional docstring).
        parts.append("from __future__ import annotations")

        # Add manual body (without docstring or future import) if non-empty
        if manual_body:
            if add_markers:
                parts.append(f"{PRESERVED_BEGIN}\n{manual_body}\n{PRESERVED_END}")
            else:
                parts.append(manual_body)

        # Add sentinel and managed section
        parts.extend([SENTINEL, MANAGED_COMMENT, managed])

        content = "\n\n".join(parts) + "\n"
        content_hash = hashlib.sha256(content.encode()).hexdigest()

        return cls(
            content=content,
            manual_section=manual,
            managed_section=managed,
            export_count=export_count,
            hash=content_hash,
        )


class CodeGenerator:
    """Generates __init__.py files from export manifests."""

    def __init__(
        self, output_dir: Path, output_style: str = "lazy", spdx_config: SpdxConfig | None = None
    ) -> None:
        """Initialize code generator.

        Args:
            output_dir: Directory to write generated files to
            output_style: Output style — ``"lazy"`` (default) uses lateimport lazy
                loading via ``__getattr__``; ``"barrel"`` generates direct ``from .mod
                import Name`` style imports.
            spdx_config: Optional SPDX header configuration. When provided and
                enabled, each generated file will include SPDX comment headers.
        """
        self.output_dir = output_dir
        self._output_style = output_style
        self._spdx_config = spdx_config
        self.file_writer = FileWriter(validator=self._create_validator())
        self.section_parser = SectionParser()

    def generate(self, manifest: ExportManifest) -> GeneratedCode:
        """Generate code for a single module."""
        # Get target file path
        target = self._get_target_path(manifest.module_path)

        # Preserve manual section if file exists
        manual_section = ""
        if target.exists():
            manual_section = self._preserve_manual_section(target.read_text())

        # Generate managed section (pass preserved section so we can skip
        # infrastructure imports that already exist there)
        managed_section = self._generate_managed_section(manifest, manual_section)

        spdx_header = self._spdx_config.build_header() if self._spdx_config else None
        return GeneratedCode.create(
            manual=manual_section,
            managed=managed_section,
            export_count=len(manifest.all_exports),
            spdx_header=spdx_header,
        )

    def write_file(self, module_path: str, code: GeneratedCode) -> WriteResult:
        """Write generated code to disk (atomic with backup).

        Args:
            module_path: Module path (e.g., 'codeweaver.core.types')
            code: Generated code to write

        Returns:
            WriteResult with success status and paths

        Raises:
            SyntaxError: If generated code has syntax errors
            IOError: If file write fails for other reasons
        """
        target = self._get_target_path(module_path)
        result = self.file_writer.write_file(target, code.content)

        if not result.success:
            # Re-raise syntax errors to match original behavior
            if result.error and "syntax error" in result.error.lower():
                raise SyntaxError(
                    f"❌ Error: Generated code has syntax errors\n\n{result.error}\n\n"
                    "This is a bug in the code generator."
                )
            raise OSError(f"Failed to write {target}: {result.error}")

        return result

    def validate_generated(self, code: GeneratedCode) -> list[str]:
        """Validate generated code (syntax, imports, etc.)."""
        return self._create_validator()(code.content)

    def _create_validator(self):
        """Create validation function for generated code."""

        def validator(content: str) -> list[str]:
            errors = []
            try:
                tree = ast.parse(content)
            except SyntaxError as e:
                errors.append(f"Syntax error at line {e.lineno}: {e.msg}")
                return errors

            has_all = any(
                isinstance(target, ast.Name) and target.id == "__all__"
                for node in ast.walk(tree)
                if isinstance(node, ast.Assign)
                for target in node.targets
            )

            if not has_all:
                errors.append("Missing __all__ declaration")

            return errors

        return validator

    def _preserve_manual_section(self, existing: str) -> str:
        """Extract manual code using AST-based parsing.

        Uses SectionParser to identify and preserve user-defined code sections:
        - Non-TYPE_CHECKING imports
        - Class definitions
        - Function definitions (except __dir__)
        - Variable assignments (except managed ones)
        - Type aliases
        - Constants
        - Comments outside managed sections

        Args:
            existing: Content of existing __init__.py file

        Returns:
            Preserved code section (empty string if nothing to preserve)
        """
        if SENTINEL not in existing:
            # Detect whether this sentinel-less file already contains lazy-import
            # infrastructure written by a previous run (before sentinels were
            # added) or by hand.  If so, use the AST-based section parser to
            # filter out the managed nodes — otherwise they would end up in the
            # preserved section and get duplicated in the new managed section.
            _dynamic_import_identifiers = (
                "_dynamic_imports",
                "from lateimport import create_late_getattr",
            )
            is_lazy_managed = any(marker in existing for marker in _dynamic_import_identifiers)

            if is_lazy_managed:
                with contextlib.suppress(Exception):
                    parsed = self.section_parser.parse_content(existing)
                    return parsed.preserved_code
            # Non-managed file: preserve all content (including standalone
            # comments that AST parsing would drop).  from __future__ import
            # annotations is stripped here because GeneratedCode.create()
            # always re-emits it at the correct position.
            lines = [
                line
                for line in existing.splitlines()
                if line.strip() != "from __future__ import annotations"
            ]
            return "\n".join(lines).rstrip()

        try:
            # Use AST-based parsing to extract preserved sections above the sentinel
            parsed = self.section_parser.parse_content(existing)
        except Exception:
            # Fallback: split on sentinel directly
            return existing.split(SENTINEL)[0].rstrip()
        else:
            return parsed.preserved_code

    def _generate_managed_section(
        self, manifest: ExportManifest, preserved_section: str = ""
    ) -> str:
        """Generate the managed section below sentinel, dispatching on output style."""
        if self._output_style == "barrel":
            return self._generate_barrel_managed_section(manifest, preserved_section)
        return self._generate_lazy_managed_section(manifest, preserved_section)

    def _has_preserved_definition(self, preserved_section: str, name: str) -> bool:
        """Return True if the preserved section defines *name* at the top level.

        Checks for:
        - Function definitions: ``def name(...)``
        - Assignments: ``name = ...`` or ``name: type = ...``

        Used to avoid emitting duplicate ``__dir__`` or ``__getattr__`` when the
        user has written their own implementation in the preserved (non-managed)
        block.

        Args:
            preserved_section: The preserved code above the sentinel.
            name: Identifier to look for (e.g. ``"__dir__"``, ``"__getattr__"``).

        Returns:
            ``True`` if *name* is defined at module scope in the preserved section.
        """
        if not preserved_section:
            return False
        with contextlib.suppress(SyntaxError, Exception):
            tree = ast.parse(preserved_section)
            for node in tree.body:
                if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name == name:
                    return True
                if isinstance(node, ast.Assign) and any(
                    isinstance(t, ast.Name) and t.id == name for t in node.targets
                ):
                    return True
                if (
                    isinstance(node, ast.AnnAssign)
                    and isinstance(node.target, ast.Name)
                    and node.target.id == name
                ):
                    return True
        return False

    def _get_preserved_runtime_imports(
        self, preserved_section: str, package_path: str
    ) -> set[tuple[str, str]]:
        """Return (module, accessible_name) pairs for top-level imports in preserved_section.

        Only top-level (non-conditional) imports are considered — these are the names
        available in the module's runtime namespace.  Imports inside ``if TYPE_CHECKING:``
        or other conditional blocks are not included.

        Used to avoid emitting duplicate infrastructure imports when the user's preserved
        code already imports the same name (e.g., ``from types import MappingProxyType``).
        """
        if not preserved_section:
            return set()
        found: set[tuple[str, str]] = set()
        with contextlib.suppress(SyntaxError, Exception):
            tree = ast.parse(preserved_section)
            for node in tree.body:
                if not isinstance(node, (ast.Import, ast.ImportFrom)):
                    continue
                for alias in node.names:
                    if isinstance(node, ast.ImportFrom):
                        # Resolve relative module
                        module = node.module or ""
                        if node.level > 0:
                            parts = package_path.split(".")
                            # For __init__.py, level 1 is the package itself.
                            # level 2 is the parent package, etc.
                            if node.level == 1:
                                resolved_module = package_path
                            else:
                                base_parts = parts[: -(node.level - 1)]
                                resolved_module = ".".join(base_parts)

                            if module:
                                resolved_module = f"{resolved_module}.{module}"
                        else:
                            resolved_module = module

                        accessible = alias.asname or alias.name
                        found.add((resolved_module, accessible))
                    elif isinstance(node, ast.Import):
                        accessible = alias.asname or alias.name
                        found.add((alias.name, accessible))
        return found

    def _get_preserved_names(self, preserved_section: str) -> set[str]:
        """Return all names defined or imported at module scope in preserved_section.

        Includes names from:
        - Imports: ``import X``, ``from X import Y``
        - Functions: ``def X(...)``
        - Assignments: ``X = ...``, ``X: type = ...``
        """
        if not preserved_section:
            return set()
        names: set[str] = set()
        with contextlib.suppress(SyntaxError, Exception):
            tree = ast.parse(preserved_section)
            for node in tree.body:
                # Imports
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    for alias in node.names:
                        names.add(alias.asname or alias.name)
                # Functions
                elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    names.add(node.name)
                # Assignments
                elif isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            names.add(target.id)
                elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                    names.add(node.target.id)
        return names

    def _generate_lazy_managed_section(
        self, manifest: ExportManifest, preserved_section: str = ""
    ) -> str:
        """Generate the managed section using lazy lateimport pattern."""
        preserved_names = self._get_preserved_names(preserved_section)

        # all_exports: everything that should be in __all__.
        all_exports = sorted(manifest.all_exports, key=lambda x: _export_sort_key(x.public_name))

        if not all_exports:
            return "__all__ = ()"

        # prop_exports: things that need lazy-loading infrastructure.
        # We ONLY include propagated things that are NOT already in the preserved section.
        prop_exports = [
            e for e in manifest.propagated_exports if e.public_name not in preserved_names
        ]
        prop_exports = sorted(prop_exports, key=lambda x: _export_sort_key(x.public_name))

        if not prop_exports:
            return self._generate_all_only_section(all_exports, preserved_section)

        parts: list[str] = []

        # 1. Infrastructure imports
        infra_imports = self._generate_infra_imports(
            prop_exports, preserved_section, manifest.module_path
        )
        if infra_imports:
            parts.extend((infra_imports, ""))

        # 2. TYPE_CHECKING block
        type_lines = self._generate_type_checking_imports(prop_exports)
        if type_lines:
            parts.extend(["if TYPE_CHECKING:", *[f"    {line}" for line in type_lines], ""])

        # 3. _dynamic_imports
        parts.extend([self._generate_dynamic_imports_dict(prop_exports, manifest.module_path)])

        # 4. __getattr__
        if not self._has_preserved_definition(preserved_section, "__getattr__"):
            parts.extend([
                "",
                "__getattr__ = create_late_getattr(_dynamic_imports, globals(), __name__)",
            ])

        # 5. __all__ and __dir__
        parts.extend(["", self._generate_all_tuple(all_exports)])

        if not self._has_preserved_definition(preserved_section, "__dir__"):
            parts.extend([
                "",
                "def __dir__() -> list[str]:",
                '    """List available attributes for the package."""',
                "    return list(__all__)",
            ])

        return "\n".join(parts)

    def _generate_all_only_section(
        self, all_exports: Sequence[LazyExport], preserved_section: str
    ) -> str:
        """Generate a section containing only __all__ and __dir__."""
        parts = [self._generate_all_tuple(all_exports)]
        if not self._has_preserved_definition(preserved_section, "__dir__"):
            parts.extend([
                "",
                "def __dir__() -> list[str]:",
                '    """List available attributes for the package."""',
                "    return list(__all__)",
            ])
        return "\n".join(parts)

    def _generate_infra_imports(
        self, prop_exports: Sequence[LazyExport], preserved_section: str, package_path: str
    ) -> str:
        """Generate infrastructure imports (typing, types, lateimport)."""
        preserved_runtime = self._get_preserved_runtime_imports(preserved_section, package_path)
        has_preserved_getattr = self._has_preserved_definition(preserved_section, "__getattr__")

        needs_type_checking = ("typing", "TYPE_CHECKING") not in preserved_runtime
        needs_mapping_proxy = ("types", "MappingProxyType") not in preserved_runtime
        needs_create_late_getattr = (
            not has_preserved_getattr
            and ("lateimport", "create_late_getattr") not in preserved_runtime
        )

        infra_group1 = []
        if needs_type_checking:
            infra_group1.append("from typing import TYPE_CHECKING")
        if needs_mapping_proxy:
            infra_group1.append("from types import MappingProxyType")

        infra_group2 = []
        if needs_create_late_getattr:
            infra_group2.append("from lateimport import create_late_getattr")

        lines = []
        if infra_group1:
            lines.extend(infra_group1)
        if infra_group2:
            if lines:
                lines.append("")
            lines.extend(infra_group2)

        return "\n".join(lines)

    def _generate_dynamic_imports_dict(
        self, prop_exports: Sequence[LazyExport], package_path: str
    ) -> str:
        """Generate the _dynamic_imports dictionary string."""
        # Include all propagated exports in _dynamic_imports so they are available at runtime.
        # Previously we filtered by is_type_only, but if a symbol is in __all__, it MUST
        # be available at runtime via __getattr__ to avoid AttributeError.

        lines = ["_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({"]

        for export in prop_exports:
            relative_module = self._extract_relative_module(export.target_module, package_path)
            lines.append(f'    "{export.public_name}": (__spec__.parent, "{relative_module}"),')

        lines.append("})")
        return "\n".join(lines)

    def _generate_barrel_managed_section(
        self, manifest: ExportManifest, preserved_section: str = ""
    ) -> str:
        """Generate the managed section using barrel (direct import) pattern.

        Produces ``from .<module> import Name`` style imports instead of lazy
        loading.  Previously, type-only exports were wrapped in an
        ``if TYPE_CHECKING:`` block, but if a symbol is in ``__all__``,
        it must be available at runtime.

        Args:
            manifest: Export manifest describing what to expose.
            preserved_section: Code in the preserved (non-managed) section.
                Used to avoid emitting duplicate ``__dir__`` definitions.

        Returns:
            Formatted string for the managed section (without the sentinel
            header, which is added by :meth:`GeneratedCode.create`).
        """
        preserved_names = self._get_preserved_names(preserved_section)

        # all_exports should include everything
        all_exports = sorted(manifest.all_exports, key=lambda x: _export_sort_key(x.public_name))

        if not all_exports:
            return "__all__ = ()"

        # Only import things that aren't already in userspace
        import_exports = [e for e in manifest.all_exports if e.public_name not in preserved_names]
        import_exports = sorted(import_exports, key=lambda x: _export_sort_key(x.public_name))

        parts: list[str] = []

        # Emit direct runtime imports for things not in userspace
        if import_exports:
            parts.append("")
            parts.extend(self._barrel_import_lines(import_exports, manifest.module_path, indent=""))

        parts.extend(["", self._generate_all_tuple(all_exports)])

        if not self._has_preserved_definition(preserved_section, "__dir__"):
            parts.extend([
                "",
                "def __dir__() -> list[str]:",
                '    """List available attributes for the package."""',
                "    return list(__all__)",
            ])
        return "\n".join(parts)

    def _barrel_import_lines(
        self, exports: list[LazyExport], package_path: str, *, indent: str
    ) -> list[str]:
        """Build ``from .<module> import ...`` lines for a group of exports.

        Args:
            exports: Exports to emit (all should share the same is_type_only value).
            package_path: Package module path used to compute relative names.
            indent: Leading whitespace for each generated line (``""`` for
                top-level, ``"    "`` inside a ``TYPE_CHECKING`` block).

        Returns:
            List of import statement strings.
        """
        by_module: dict[str, list[LazyExport]] = {}
        for export in exports:
            by_module.setdefault(export.target_module, []).append(export)

        lines: list[str] = []
        for module in sorted(by_module):
            relative = self._extract_relative_module(module, package_path)
            names = sorted(by_module[module], key=lambda e: _export_sort_key(e.public_name))
            name_tokens: list[str] = []
            for e in names:
                if e.public_name != e.target_object:
                    name_tokens.append(f"{e.target_object} as {e.public_name}")
                else:
                    name_tokens.append(e.public_name)
            # If _extract_relative_module returned the module unchanged, it is outside
            # this package — emit an absolute import instead of a broken relative one.
            if relative == module:
                import_stmt = f"{indent}from {module} import {', '.join(name_tokens)}"
            else:
                import_stmt = f"{indent}from .{relative} import {', '.join(name_tokens)}"
            lines.append(import_stmt)
        return lines

    def _generate_type_checking_imports(self, exports: Sequence[LazyExport]) -> list[str]:
        """Generate import lines for TYPE_CHECKING block, grouped by source module."""
        # Group exports by source module
        by_module: dict[str, list[str]] = {}
        for export in exports:
            if export.target_module not in by_module:
                by_module[export.target_module] = []
            if export.public_name != export.target_object:
                # Aliased import: from mod import obj as alias
                by_module[export.target_module].append(
                    f"{export.target_object} as {export.public_name}"
                )
            else:
                by_module[export.target_module].append(export.public_name)

        # Generate import statements grouped by module
        lines = []
        for module in sorted(by_module.keys()):
            names = sorted(by_module[module], key=_export_sort_key)

            # Multi-line format with trailing comma on last item
            lines.append(f"from {module} import (")
            lines.extend(f"    {name}," for name in names)
            lines.append(")")

        return lines

    def _generate_all_tuple(self, exports: Sequence[LazyExport]) -> str:
        """Generate __all__ tuple (not list)."""
        if not exports:
            return "__all__ = ()"

        names = sorted({e.public_name for e in exports}, key=_export_sort_key)

        if len(names) == 1:
            return f'__all__ = ("{names[0]}",)'

        lines = ["__all__ = ("]
        lines.extend(f'    "{name}",' for name in names)
        lines.append(")")
        return "\n".join(lines)

    def _extract_relative_module(self, target_module: str, package_path: str) -> str:
        """Extract relative module name from full module path.

        Args:
            target_module: Full module path (e.g., 'codeweaver.core.types.models')
            package_path: Package path (e.g., 'codeweaver.core.types')

        Returns:
            Relative module name (e.g., 'models')
        """
        # Remove package prefix to get relative name
        if target_module.startswith(f"{package_path}."):
            return target_module[len(package_path) + 1 :]
        return target_module

    def _get_target_path(self, module_path: str) -> Path:
        """Get target file path for a module."""
        parts = module_path.split(".")
        return self.output_dir / Path(*parts) / "__init__.py"


def _check_ast_declarations(tree: ast.AST) -> bool:
    """Check for __all__ in AST."""
    return any(
        isinstance(target, ast.Name) and target.id == "__all__"
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        for target in node.targets
    )


def _validate_sentinel_section(content: str) -> list[str]:
    """Validate sentinel and managed section."""
    errors = []
    if SENTINEL not in content:
        return errors

    parts = content.split(SENTINEL)
    if len(parts) != 2:
        errors.append("Multiple sentinels")
    elif "__all__" not in parts[1]:
        errors.append("__all__ not in managed section")

    return errors


def validate_init_file(file_path: Path) -> list[str]:
    """Validate an existing __init__.py file."""
    if not file_path.exists():
        return [f"File does not exist: {file_path}"]
    try:
        content = file_path.read_text()
        tree = ast.parse(content)
    except SyntaxError as e:
        return [f"Syntax error at line {e.lineno}: {e.msg}"]
    except OSError as e:
        return [str(e)]

    errors = []
    has_all = _check_ast_declarations(tree)

    if not has_all:
        errors.append("Missing __all__ declaration")

    errors.extend(_validate_sentinel_section(content))
    return errors


__all__ = [
    "MANAGED_COMMENT",
    "PRESERVED_BEGIN",
    "PRESERVED_END",
    "SENTINEL",
    "CodeGenerator",
    "GeneratedCode",
    "WriteResult",
    "validate_init_file",
]
