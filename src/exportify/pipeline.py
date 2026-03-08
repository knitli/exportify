#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Pipeline orchestration for lazy import system.

Coordinates the full workflow:
1. File discovery - find Python files
2. AST parsing - extract exports
3. Graph building - propagate exports
4. Manifest generation - create export manifests
5. Code generation - write __init__.py files
"""

from __future__ import annotations

import hashlib
import logging
import time

from dataclasses import dataclass, field
from pathlib import Path

from exportify import ExportManifest
from exportify.analysis.ast_parser import ASTParser
from exportify.common.cache import JSONAnalysisCache
from exportify.common.config import SpdxConfig
from exportify.common.types import (
    ExportGenerationResult,
    GeneratedFile,
    GenerationMetrics,
    SkippedFile,
    UpdatedFile,
)
from exportify.discovery.file_discovery import FileDiscovery
from exportify.export_manager.generator import CodeGenerator
from exportify.export_manager.graph import PropagationGraph
from exportify.export_manager.rules import RuleEngine
from exportify.utils import format_content


logger = logging.getLogger(__name__)


@dataclass
class PipelineStats:
    """Statistics from pipeline execution."""

    files_discovered: int = 0
    files_analyzed: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    exports_extracted: int = 0
    manifests_generated: int = 0
    files_written: int = 0
    errors: list[str] = field(default_factory=list)


class Pipeline:
    """Orchestrate the export generation pipeline."""

    def __init__(
        self,
        rule_engine: RuleEngine,
        cache: JSONAnalysisCache,
        output_dir: Path,
        output_style: str = "lazy",
        spdx_config: SpdxConfig | None = None,
        exclude_paths: list[str] | None = None,
    ):
        """Initialize pipeline with required components.

        Args:
            rule_engine: Rule engine for export decisions
            cache: Analysis cache for performance
            output_dir: Root directory for output
            output_style: Output style — ``"lazy"`` (default) or ``"barrel"``
            spdx_config: Optional SPDX header configuration for generated files.
            exclude_paths: Glob patterns for paths to exclude from discovery
                (relative to each source root).  Supports ``**``.
        """
        self.rule_engine = rule_engine
        self.cache = cache
        self.output_dir = output_dir
        self.output_style = output_style
        self.exclude_paths: list[str] = exclude_paths or []

        # Initialize components
        self.file_discovery = FileDiscovery()
        self.ast_parser = ASTParser()
        self.generator = CodeGenerator(
            output_dir, output_style=output_style, spdx_config=spdx_config
        )
        self.graph = PropagationGraph(rule_engine)

        # Statistics
        self.stats = PipelineStats()

        # Track which module paths are packages (sourced from __init__.py files).
        # Leaf modules (.py files) are added to the graph for export propagation
        # purposes only — they must not get their own __init__.py generated.
        self._package_modules: set[str] = set()

    def _discover_files(self, source_root: Path) -> list[Path]:
        """Discover Python files in the source root.

        Args:
            source_root: Root directory to search
        Returns:
            List of Python file paths
        """
        logger.info("Discovering Python files in %s", source_root)
        python_files = self.file_discovery.discover_python_files(
            source_root, exclude_patterns=self.exclude_paths or None
        )
        self.stats.files_discovered = len(python_files)
        logger.info("Found %d Python files in %s", len(python_files), source_root)
        return python_files

    def _build_manifests(self) -> dict[str, ExportManifest]:
        """Build export manifests from the propagation graph.

        Returns:
            Dictionary mapping module paths to ExportManifests
        """
        logger.info("Building export manifests")
        try:
            manifests = self.graph.build_manifests()
            self.stats.manifests_generated = len(manifests)
        except ValueError as e:
            # Graph building failed (e.g., cycles detected)
            logger.exception("Manifest building failed")
            self.stats.errors.append(str(e))
            manifests = {}
        return manifests

    def _generate_code(
        self, manifests: dict[str, ExportManifest], *, dry_run: bool = False
    ) -> tuple[list[GeneratedFile], list[UpdatedFile], list[SkippedFile]]:
        """Generate code for all manifests."""
        logger.info("Generating code for %d modules", len(manifests))
        generated_files = []
        updated_files = []
        skipped_files = []

        for manifest in manifests.values():
            if not self._should_generate_init(manifest):
                skipped_files.append(
                    SkippedFile(
                        path=Path(manifest.module_path),
                        reason="Not a package or has no exports to generate",
                    )
                )
                continue

            try:
                gen, up, skip = self._process_manifest(manifest, dry_run=dry_run)
                if gen:
                    generated_files.append(gen)
                if up:
                    updated_files.append(up)
                if skip:
                    skipped_files.append(skip)
            except Exception as e:
                logger.exception("Failed to generate %s", manifest.module_path)
                self.stats.errors.append(f"{manifest.module_path}: {e}")

        return generated_files, updated_files, skipped_files

    def _should_generate_init(self, manifest: ExportManifest) -> bool:
        """Determine if this module needs an __init__.py."""
        # It needs one if:
        # 1. It already has one (recorded in self._package_modules)
        # 2. It has exports (own or propagated) AND it has children (it's a directory)
        # 3. It's the root package being processed (optional, but good for consistency)
        is_existing_package = manifest.module_path in self._package_modules
        has_exports = len(manifest.all_exports) > 0

        # Use graph to check if it's a parent of other modules
        node = self.graph.modules.get(manifest.module_path)
        is_parent = bool(node and node.children)

        return is_existing_package or (has_exports and is_parent)

    def _process_manifest(
        self, manifest: ExportManifest, *, dry_run: bool
    ) -> tuple[GeneratedFile | None, UpdatedFile | None, SkippedFile | None]:
        """Generate and potentially write code for a single manifest."""
        code = self.generator.generate(manifest)

        # Determine if file exists and read its content for comparison
        target = self.generator._get_target_path(manifest.module_path)
        file_existed = target.exists()
        existing_content = target.read_text(encoding="utf-8") if file_existed else ""

        # Format content before write so dry-run and written file are identical
        formatted = format_content(code.content, filename=target)

        if not dry_run:
            self._write_manifest_file(manifest, target, formatted)

        # Record generation
        if file_existed:
            # Only record as updated if content actually changed.
            # Normalize line endings for comparison.
            if (
                formatted.replace("\r\n", "\n").strip()
                != existing_content.replace("\r\n", "\n").strip()
            ):
                return (
                    None,
                    UpdatedFile(
                        path=target,
                        old_content=existing_content,
                        new_content=formatted,
                        changes=[f"Updated {len(manifest.all_exports)} exports"],
                    ),
                    None,
                )
            return None, None, SkippedFile(path=target, reason="Already in sync")

        return (
            GeneratedFile(
                path=target,
                content=formatted,
                exports=manifest.export_names,
                source_modules=list({e.target_module for e in manifest.all_exports}),
                timestamp=time.time(),
                hash=code.hash,
            ),
            None,
            None,
        )

    def _write_manifest_file(self, manifest: ExportManifest, target: Path, content: str) -> None:
        """Write generated code to disk."""
        result = self.generator.file_writer.write_file(target, content)
        if not result.success:
            if result.error and "syntax error" in result.error.lower():
                raise SyntaxError(
                    f"Syntax error in generated code for {manifest.module_path}: {result.error}"
                )
            raise OSError(f"Failed to write {target}: {result.error}")
        self.stats.files_written += 1

    def run(
        self, source_root: Path, *, dry_run: bool = False, module: Path | None = None
    ) -> ExportGenerationResult:
        """Execute full pipeline.

        Args:
            source_root: Root directory to process
            dry_run: If True, don't write files
            module: If specified, only process this module

        Returns:
            ExportGenerationResult with complete results
        """
        start_time = time.time()

        # Reset per-run state
        self._package_modules = set()

        # Update generator output directory to match source root
        self.generator.output_dir = source_root

        # Step 1: Discover files
        search_root = module or source_root
        python_files = self._discover_files(search_root)

        # Step 2: Analyze files and build graph
        logger.info("Analyzing files and building propagation graph")
        for file_path in python_files:
            self._process_file(file_path, source_root)

        # Step 3: Build manifests from graph
        manifests = self._build_manifests()

        # Step 4: Generate code
        logger.info("Generating code for %d modules", len(manifests))
        generated_files, updated_files, skipped_files = self._generate_code(
            manifests, dry_run=dry_run
        )

        # Calculate metrics
        processing_time_ms = int((time.time() - start_time) * 1000)
        total_cache_attempts = self.stats.cache_hits + self.stats.cache_misses
        cache_hit_rate = (
            self.stats.cache_hits / total_cache_attempts if total_cache_attempts > 0 else 0.0
        )

        metrics = GenerationMetrics(
            files_analyzed=self.stats.files_analyzed,
            files_generated=len(generated_files),
            files_updated=len(updated_files),
            files_skipped=len(skipped_files),
            exports_created=self.stats.exports_extracted,
            processing_time_ms=processing_time_ms,
            cache_hit_rate=cache_hit_rate,
        )

        return ExportGenerationResult(
            generated_files=generated_files,
            updated_files=updated_files,
            skipped_files=skipped_files,
            metrics=metrics,
            success=len(self.stats.errors) == 0,
            errors=self.stats.errors,
        )

    def _process_file(self, file_path: Path, source_root: Path) -> None:
        """Process a single file (with caching).

        Args:
            file_path: Path to Python file
            source_root: Root directory for module path calculation
        """
        # Calculate module path from file path
        relative = file_path.relative_to(source_root)

        # Remove .py extension and convert to module path
        # e.g., src/codeweaver/core/types.py -> codeweaver.core.types
        parts = list(relative.parts)

        # If filename is __init__.py, use parent directory
        if relative.name == "__init__.py":
            parts = parts[:-1]  # Remove __init__.py
            is_package = True
        else:
            # Remove .py and use as last part
            parts[-1] = relative.stem
            is_package = False

        module_path = ".".join(parts) if parts else "root"

        # Track package modules so the generator only writes __init__.py for them.
        if is_package:
            self._package_modules.add(module_path)

        # Calculate parent module
        parent_module = self._get_parent_module(module_path)

        # Check cache
        content = file_path.read_text()
        file_hash = hashlib.sha256(content.encode()).hexdigest()

        if cached := self.cache.get(file_path, file_hash):
            # Use cached analysis
            self.stats.cache_hits += 1
            analysis = cached
        else:
            # Parse file
            self.stats.cache_misses += 1
            self.stats.files_analyzed += 1

            analysis = self.ast_parser.parse_file(file_path, module_path)

            # Cache result
            self.cache.put(file_path, file_hash, analysis)

        # Add module to graph
        self.graph.add_module(module_path, parent_module)

        # For non-package modules with an explicit __all__, restrict propagation to
        # only the names the module author declared as public.  __init__.py files are
        # excluded from this filter because their __all__ is generated by exportify
        # itself — using it as an input would create a circular dependency.
        symbols_to_process = analysis.symbols
        if not is_package and analysis.declared_all is not None:
            declared_all_set = frozenset(analysis.declared_all)
            symbols_to_process = [s for s in analysis.symbols if s.name in declared_all_set]

        # Add exports to graph
        for symbol in symbols_to_process:
            # Evaluate rules for the symbol
            decision = self.rule_engine.evaluate(symbol, module_path)

            # Add decision to graph
            self.graph.add_export(decision)
            self.stats.exports_extracted += 1

    def _get_parent_module(self, module_path: str) -> str | None:
        """Get parent module path from a module path.

        Args:
            module_path: Full module path (e.g., "codeweaver.core.types")

        Returns:
            Parent module path (e.g., "codeweaver.core") or None if root
        """
        parts = module_path.split(".")
        return None if len(parts) <= 1 else ".".join(parts[:-1])


__all__ = ["Pipeline", "PipelineStats"]
