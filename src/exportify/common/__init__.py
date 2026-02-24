# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Common utilities for lazy import system."""

from __future__ import annotations

from types import MappingProxyType

# === MANAGED EXPORTS ===
# Exportify manages this section. It contains lazy-loading infrastructure
# for the package: imports and runtime declarations (__all__, __getattr__,
# __dir__). Manual edits will be overwritten by `exportify fix`.
from typing import TYPE_CHECKING

from lateimport import create_late_getattr


if TYPE_CHECKING:
    from exportify.common.cache import CircuitBreaker, CircuitState, JSONAnalysisCache, T
    from exportify.common.config import (
        CONFIG_ENV_VAR,
        DEFAULT_CACHE_SUBDIR,
        DEFAULT_CONFIG_NAMES,
        DEFAULT_SNAPSHOT_DIR,
        ExportifyConfig,
        detect_lateimport_dependency,
        find_config_file,
        load_config,
    )
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

_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({
    "CONFIG_ENV_VAR": (__spec__.parent, "config"),
    "DEFAULT_CACHE_SUBDIR": (__spec__.parent, "config"),
    "DEFAULT_CONFIG_NAMES": (__spec__.parent, "config"),
    "DEFAULT_SNAPSHOT_DIR": (__spec__.parent, "config"),
    "T": (__spec__.parent, "cache"),
    "AnalysisResult": (__spec__.parent, "types"),
    "CacheEntry": (__spec__.parent, "types"),
    "CacheStatistics": (__spec__.parent, "types"),
    "CallError": (__spec__.parent, "types"),
    "CircuitBreaker": (__spec__.parent, "cache"),
    "CircuitState": (__spec__.parent, "cache"),
    "ConsistencyIssue": (__spec__.parent, "types"),
    "CoordinatedResult": (__spec__.parent, "types"),
    "DetectedSymbol": (__spec__.parent, "types"),
    "ExportDecision": (__spec__.parent, "types"),
    "ExportGenerationResult": (__spec__.parent, "types"),
    "ExportifyConfig": (__spec__.parent, "config"),
    "ExportManifest": (__spec__.parent, "types"),
    "GeneratedFile": (__spec__.parent, "types"),
    "GenerationMetrics": (__spec__.parent, "types"),
    "ImportResolution": (__spec__.parent, "types"),
    "LateImportConfig": (__spec__.parent, "types"),
    "LazyExport": (__spec__.parent, "types"),
    "MemberType": (__spec__.parent, "types"),
    "OutputStyle": (__spec__.parent, "types"),
    "PropagationLevel": (__spec__.parent, "types"),
    "Rule": (__spec__.parent, "types"),
    "RuleAction": (__spec__.parent, "types"),
    "RuleEvaluationResult": (__spec__.parent, "types"),
    "RuleMatch": (__spec__.parent, "types"),
    "RuleMatchCriteria": (__spec__.parent, "types"),
    "SkippedFile": (__spec__.parent, "types"),
    "SnapshotEntry": (__spec__.parent, "snapshot"),
    "SnapshotManager": (__spec__.parent, "snapshot"),
    "SnapshotManifest": (__spec__.parent, "snapshot"),
    "SourceLocation": (__spec__.parent, "types"),
    "SymbolProvenance": (__spec__.parent, "types"),
    "UpdatedFile": (__spec__.parent, "types"),
    "ValidationConfig": (__spec__.parent, "types"),
    "ValidationError": (__spec__.parent, "types"),
    "ValidationMetrics": (__spec__.parent, "types"),
    "ValidationReport": (__spec__.parent, "types"),
    "ValidationWarning": (__spec__.parent, "types"),
    "detect_lateimport_dependency": (__spec__.parent, "config"),
    "find_config_file": (__spec__.parent, "config"),
    "JSONAnalysisCache": (__spec__.parent, "cache"),
    "load_config": (__spec__.parent, "config"),
})

__getattr__ = create_late_getattr(_dynamic_imports, globals(), __name__)

__all__ = (
    "CONFIG_ENV_VAR",
    "DEFAULT_CACHE_SUBDIR",
    "DEFAULT_CONFIG_NAMES",
    "DEFAULT_SNAPSHOT_DIR",
    "AnalysisResult",
    "CacheEntry",
    "CacheStatistics",
    "CallError",
    "CircuitBreaker",
    "CircuitState",
    "ConsistencyIssue",
    "CoordinatedResult",
    "DetectedSymbol",
    "ExportDecision",
    "ExportGenerationResult",
    "ExportManifest",
    "ExportifyConfig",
    "GeneratedFile",
    "GenerationMetrics",
    "ImportResolution",
    "JSONAnalysisCache",
    "LateImportConfig",
    "LazyExport",
    "MemberType",
    "OutputStyle",
    "PropagationLevel",
    "Rule",
    "RuleAction",
    "RuleEvaluationResult",
    "RuleMatch",
    "RuleMatchCriteria",
    "SkippedFile",
    "SnapshotEntry",
    "SnapshotManager",
    "SnapshotManifest",
    "SourceLocation",
    "SymbolProvenance",
    "T",
    "UpdatedFile",
    "ValidationConfig",
    "ValidationError",
    "ValidationMetrics",
    "ValidationReport",
    "ValidationWarning",
    "detect_lateimport_dependency",
    "find_config_file",
    "load_config",
)


def __dir__() -> list[str]:
    """List available attributes for the package."""
    return list(__all__)
