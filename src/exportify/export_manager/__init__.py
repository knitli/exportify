# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Export management components.

This package contains the core export management system responsible for
determining which exports should be included in __init__.py files and how
they should propagate through the package hierarchy.

Components:
- RuleEngine: Priority-based rule evaluation
- PropagationGraph: Bottom-up export propagation
- CodeGenerator: __init__.py file generation
"""

from __future__ import annotations

from exportify.export_manager.generator import CodeGenerator, GeneratedCode, validate_init_file
from exportify.export_manager.graph import PropagationGraph
from exportify.export_manager.module_all import (
    ModuleAllFixResult,
    ModuleAllIssue,
    check_module_all,
    fix_module_all,
)
from exportify.export_manager.rules import RuleEngine

# === MANAGED EXPORTS ===

# Exportify manages this section. It contains lazy-loading infrastructure
# for the package: imports and runtime declarations (__all__, __getattr__,
# __dir__). Manual edits will be overwritten by `exportify fix`.

from typing import TYPE_CHECKING
from types import MappingProxyType

from lateimport import create_late_getattr

if TYPE_CHECKING:
    from exportify.export_manager.file_writer import FileWriter, WriteResult
    from exportify.export_manager.generator import (
        MANAGED_COMMENT,
        PRESERVED_BEGIN,
        PRESERVED_END,
        SENTINEL,
        SPDX_HEADERS,
        CodeGenerator,
        GeneratedCode,
        validate_init_file,
    )
    from exportify.export_manager.graph import (
        CircularDependencyIndicator,
        ExportEntry,
        ModuleNode,
        PropagationGraph,
        export_sort_key,
    )
    from exportify.export_manager.module_all import (
        ModuleAllFixResult,
        ModuleAllIssue,
        check_module_all,
        fix_module_all,
    )
    from exportify.export_manager.rules import (
        CURRENT_SCHEMA_VERSION,
        SUPPORTED_VERSIONS,
        RuleEngine,
        SchemaVersionError,
    )
    from exportify.export_manager.section_parser import (
        ParsedSections,
        SectionParser,
        parse_init_file,
    )

_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({
    "CURRENT_SCHEMA_VERSION": (__spec__.parent, "rules"),
    "MANAGED_COMMENT": (__spec__.parent, "generator"),
    "PRESERVED_BEGIN": (__spec__.parent, "generator"),
    "PRESERVED_END": (__spec__.parent, "generator"),
    "SENTINEL": (__spec__.parent, "generator"),
    "SPDX_HEADERS": (__spec__.parent, "generator"),
    "SUPPORTED_VERSIONS": (__spec__.parent, "rules"),
    "CircularDependencyIndicator": (__spec__.parent, "graph"),
    "CodeGenerator": (__spec__.parent, "generator"),
    "ExportEntry": (__spec__.parent, "graph"),
    "FileWriter": (__spec__.parent, "file_writer"),
    "GeneratedCode": (__spec__.parent, "generator"),
    "ModuleAllFixResult": (__spec__.parent, "module_all"),
    "ModuleAllIssue": (__spec__.parent, "module_all"),
    "ModuleNode": (__spec__.parent, "graph"),
    "ParsedSections": (__spec__.parent, "section_parser"),
    "PropagationGraph": (__spec__.parent, "graph"),
    "RuleEngine": (__spec__.parent, "rules"),
    "SchemaVersionError": (__spec__.parent, "rules"),
    "SectionParser": (__spec__.parent, "section_parser"),
    "WriteResult": (__spec__.parent, "file_writer"),
    "check_module_all": (__spec__.parent, "module_all"),
    "export_sort_key": (__spec__.parent, "graph"),
    "fix_module_all": (__spec__.parent, "module_all"),
    "parse_init_file": (__spec__.parent, "section_parser"),
    "validate_init_file": (__spec__.parent, "generator"),
})

__getattr__ = create_late_getattr(_dynamic_imports, globals(), __name__)

__all__ = (
    "CURRENT_SCHEMA_VERSION",
    "MANAGED_COMMENT",
    "PRESERVED_BEGIN",
    "PRESERVED_END",
    "SENTINEL",
    "SPDX_HEADERS",
    "SUPPORTED_VERSIONS",
    "CircularDependencyIndicator",
    "CodeGenerator",
    "ExportEntry",
    "FileWriter",
    "GeneratedCode",
    "ModuleAllFixResult",
    "ModuleAllIssue",
    "ModuleNode",
    "ParsedSections",
    "PropagationGraph",
    "RuleEngine",
    "SchemaVersionError",
    "SectionParser",
    "WriteResult",
    "check_module_all",
    "export_sort_key",
    "fix_module_all",
    "parse_init_file",
    "validate_init_file",
)


def __dir__() -> list[str]:
    """List available attributes for the package."""
    return list(__all__)
