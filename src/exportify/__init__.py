# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Lazy import system tools and CLI."""

from __future__ import annotations


def _get_version() -> str:
    """Get the current version of Exportify.

    Because our version is dynamically generated during build/release, we try several methods to get it. If you downloaded Exportify from PyPi, then the first will work, or the second if the file didn't get generated for some reason. If you're running from source, we try to get the version from git tags. If all else fails, we return "0.0.0".
    """
    try:
        from exportify._version import __version__
    except ImportError:
        try:
            import importlib.metadata

            __version__ = importlib.metadata.version("exportify")
        except importlib.metadata.PackageNotFoundError:
            try:
                import shutil
                import subprocess

                # Try to get version from git if available
                # Git commands work from any directory within a repo, so no need to specify cwd
                # The subprocess call is safe because we use the system to find the executable, not user input
                if git := shutil.which("git"):
                    git_describe = subprocess.run(
                        [git, "describe", "--tags", "--always", "--dirty"],
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    if git_describe.returncode == 0:
                        __version__ = git_describe.stdout.strip()
                    else:
                        __version__ = "0.0.0"
                else:
                    __version__ = "0.0.0"
            except Exception:
                __version__ = "0.0.0"
    return __version__


__version__ = _get_version()

# === MANAGED EXPORTS ===

# Exportify manages this section. It contains lazy-loading infrastructure
# for the package: imports and runtime declarations (__all__, __getattr__,
# __dir__). Manual edits will be overwritten by `exportify fix`.

from types import MappingProxyType
from typing import TYPE_CHECKING

from lateimport import create_late_getattr


if TYPE_CHECKING:
    from exportify.analysis.ast_parser import ASTParser
    from exportify.cli import main
    from exportify.common.cache import CircuitBreaker, CircuitState, JSONAnalysisCache
    from exportify.common.config import ExportifyConfig, ProjectConfig, SpdxConfig
    from exportify.common.snapshot import SnapshotEntry, SnapshotManager, SnapshotManifest
    from exportify.common.types import (
        AnalysisResult,
        CacheEntry,
        CacheStatistics,
        CallError,
        ConsistencyIssue,
        CoordinatedResult,
        DetectedSymbol,
        ExportDecision,
        ExportGenerationResult,
        ExportManifest,
        GeneratedFile,
        GenerationMetrics,
        ImportResolution,
        LateImportConfig,
        LazyExport,
        MemberType,
        OutputStyle,
        PropagationLevel,
        Rule,
        RuleAction,
        RuleEvaluationResult,
        RuleMatch,
        RuleMatchCriteria,
        SkippedFile,
        SourceLocation,
        SymbolProvenance,
        UpdatedFile,
        ValidationConfig,
        ValidationError,
        ValidationMetrics,
        ValidationReport,
        ValidationWarning,
    )
    from exportify.discovery.file_discovery import FileDiscovery
    from exportify.export_manager.file_writer import FileWriter, WriteResult
    from exportify.export_manager.generator import CodeGenerator, GeneratedCode
    from exportify.export_manager.graph import (
        CircularDependencyIndicator,
        ExportEntry,
        ModuleNode,
        PropagationGraph,
    )
    from exportify.export_manager.module_all import ModuleAllFixResult, ModuleAllIssue
    from exportify.export_manager.rules import RuleEngine, SchemaVersionError
    from exportify.export_manager.section_parser import ParsedSections, SectionParser
    from exportify.migration import (
        DEFAULT_OUTPUT,
        SCHEMA_VERSION,
        ExtractedRule,
        MigrationResult,
        RuleMigrator,
        cli_init,
        migrate_to_yaml,
        verify_migration,
    )
    from exportify.pipeline import Pipeline, PipelineStats
    from exportify.utils import (
        detect_lateimport_dependency,
        detect_source_root,
        find_project_name,
        format_content,
        format_file,
        formatting_tools_available,
        locate_project_root,
        write_gitignore_patterns,
    )
    from exportify.validator.consistency import ConsistencyChecker
    from exportify.validator.resolver import ImportResolver
    from exportify.validator.validator import LateImportValidator

_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({
    "DEFAULT_OUTPUT": (__spec__.parent, "migration"),
    "SCHEMA_VERSION": (__spec__.parent, "migration"),
    "AnalysisResult": (__spec__.parent, "common.types"),
    "CacheEntry": (__spec__.parent, "common.types"),
    "CacheStatistics": (__spec__.parent, "common.types"),
    "CallError": (__spec__.parent, "common.types"),
    "CircuitBreaker": (__spec__.parent, "common.cache"),
    "CircuitState": (__spec__.parent, "common.cache"),
    "CircularDependencyIndicator": (__spec__.parent, "export_manager.graph"),
    "CodeGenerator": (__spec__.parent, "export_manager.generator"),
    "ConsistencyChecker": (__spec__.parent, "validator.consistency"),
    "ConsistencyIssue": (__spec__.parent, "common.types"),
    "CoordinatedResult": (__spec__.parent, "common.types"),
    "DetectedSymbol": (__spec__.parent, "common.types"),
    "ExportDecision": (__spec__.parent, "common.types"),
    "ExportEntry": (__spec__.parent, "export_manager.graph"),
    "ExportGenerationResult": (__spec__.parent, "common.types"),
    "ExportifyConfig": (__spec__.parent, "common.config"),
    "ExportManifest": (__spec__.parent, "common.types"),
    "ExtractedRule": (__spec__.parent, "migration"),
    "FileDiscovery": (__spec__.parent, "discovery.file_discovery"),
    "FileWriter": (__spec__.parent, "export_manager.file_writer"),
    "GeneratedCode": (__spec__.parent, "export_manager.generator"),
    "GeneratedFile": (__spec__.parent, "common.types"),
    "GenerationMetrics": (__spec__.parent, "common.types"),
    "ImportResolution": (__spec__.parent, "common.types"),
    "ImportResolver": (__spec__.parent, "validator.resolver"),
    "LateImportConfig": (__spec__.parent, "common.types"),
    "LateImportValidator": (__spec__.parent, "validator.validator"),
    "LazyExport": (__spec__.parent, "common.types"),
    "MemberType": (__spec__.parent, "common.types"),
    "MigrationResult": (__spec__.parent, "migration"),
    "ModuleAllFixResult": (__spec__.parent, "export_manager.module_all"),
    "ModuleAllIssue": (__spec__.parent, "export_manager.module_all"),
    "ModuleNode": (__spec__.parent, "export_manager.graph"),
    "OutputStyle": (__spec__.parent, "common.types"),
    "ParsedSections": (__spec__.parent, "export_manager.section_parser"),
    "Pipeline": (__spec__.parent, "pipeline"),
    "PipelineStats": (__spec__.parent, "pipeline"),
    "ProjectConfig": (__spec__.parent, "common.config"),
    "PropagationGraph": (__spec__.parent, "export_manager.graph"),
    "PropagationLevel": (__spec__.parent, "common.types"),
    "Rule": (__spec__.parent, "common.types"),
    "RuleAction": (__spec__.parent, "common.types"),
    "RuleEngine": (__spec__.parent, "export_manager.rules"),
    "RuleEvaluationResult": (__spec__.parent, "common.types"),
    "RuleMatch": (__spec__.parent, "common.types"),
    "RuleMatchCriteria": (__spec__.parent, "common.types"),
    "RuleMigrator": (__spec__.parent, "migration"),
    "SchemaVersionError": (__spec__.parent, "export_manager.rules"),
    "SectionParser": (__spec__.parent, "export_manager.section_parser"),
    "SkippedFile": (__spec__.parent, "common.types"),
    "SnapshotEntry": (__spec__.parent, "common.snapshot"),
    "SnapshotManager": (__spec__.parent, "common.snapshot"),
    "SnapshotManifest": (__spec__.parent, "common.snapshot"),
    "SourceLocation": (__spec__.parent, "common.types"),
    "SpdxConfig": (__spec__.parent, "common.config"),
    "SymbolProvenance": (__spec__.parent, "common.types"),
    "UpdatedFile": (__spec__.parent, "common.types"),
    "ValidationConfig": (__spec__.parent, "common.types"),
    "ValidationError": (__spec__.parent, "common.types"),
    "ValidationMetrics": (__spec__.parent, "common.types"),
    "ValidationReport": (__spec__.parent, "common.types"),
    "ValidationWarning": (__spec__.parent, "common.types"),
    "WriteResult": (__spec__.parent, "export_manager.file_writer"),
    "ASTParser": (__spec__.parent, "analysis.ast_parser"),
    "cli_init": (__spec__.parent, "migration"),
    "detect_lateimport_dependency": (__spec__.parent, "utils"),
    "detect_source_root": (__spec__.parent, "utils"),
    "find_project_name": (__spec__.parent, "utils"),
    "format_content": (__spec__.parent, "utils"),
    "format_file": (__spec__.parent, "utils"),
    "formatting_tools_available": (__spec__.parent, "utils"),
    "JSONAnalysisCache": (__spec__.parent, "common.cache"),
    "locate_project_root": (__spec__.parent, "utils"),
    "main": (__spec__.parent, "cli"),
    "migrate_to_yaml": (__spec__.parent, "migration"),
    "verify_migration": (__spec__.parent, "migration"),
    "write_gitignore_patterns": (__spec__.parent, "utils"),
})

__getattr__ = create_late_getattr(_dynamic_imports, globals(), __name__)

__all__ = (
    "DEFAULT_OUTPUT",
    "SCHEMA_VERSION",
    "ASTParser",
    "AnalysisResult",
    "CacheEntry",
    "CacheStatistics",
    "CallError",
    "CircuitBreaker",
    "CircuitState",
    "CircularDependencyIndicator",
    "CodeGenerator",
    "ConsistencyChecker",
    "ConsistencyIssue",
    "CoordinatedResult",
    "DetectedSymbol",
    "ExportDecision",
    "ExportEntry",
    "ExportGenerationResult",
    "ExportManifest",
    "ExportifyConfig",
    "ExtractedRule",
    "FileDiscovery",
    "FileWriter",
    "GeneratedCode",
    "GeneratedFile",
    "GenerationMetrics",
    "ImportResolution",
    "ImportResolver",
    "JSONAnalysisCache",
    "LateImportConfig",
    "LateImportValidator",
    "LazyExport",
    "MemberType",
    "MigrationResult",
    "ModuleAllFixResult",
    "ModuleAllIssue",
    "ModuleNode",
    "OutputStyle",
    "ParsedSections",
    "Pipeline",
    "PipelineStats",
    "ProjectConfig",
    "PropagationGraph",
    "PropagationLevel",
    "Rule",
    "RuleAction",
    "RuleEngine",
    "RuleEvaluationResult",
    "RuleMatch",
    "RuleMatchCriteria",
    "RuleMigrator",
    "SchemaVersionError",
    "SectionParser",
    "SkippedFile",
    "SnapshotEntry",
    "SnapshotManager",
    "SnapshotManifest",
    "SourceLocation",
    "SpdxConfig",
    "SymbolProvenance",
    "UpdatedFile",
    "ValidationConfig",
    "ValidationError",
    "ValidationMetrics",
    "ValidationReport",
    "ValidationWarning",
    "WriteResult",
    "cli_init",
    "detect_lateimport_dependency",
    "detect_source_root",
    "find_project_name",
    "format_content",
    "format_file",
    "formatting_tools_available",
    "locate_project_root",
    "main",
    "migrate_to_yaml",
    "verify_migration",
    "write_gitignore_patterns",
)


def __dir__() -> list[str]:
    """List available attributes for the package."""
    return list(__all__)
