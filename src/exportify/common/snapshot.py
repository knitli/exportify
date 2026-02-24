# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Pre-flight snapshot system for exportify fix runs.

Captures original file contents before the fix command modifies them,
storing snapshots in .exportify/snapshots/last/ so the undo command
can restore them.
"""

from __future__ import annotations

import json
import shutil

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path


@dataclass
class SnapshotEntry:
    """One file in the snapshot."""

    source: str  # relative path from project root
    stored: str  # filename inside files_dir, e.g. "0.py"


@dataclass
class SnapshotManifest:
    """Full manifest for a snapshot."""

    timestamp: str
    entries: list[SnapshotEntry]

    def to_dict(self) -> dict:
        """Serialize this manifest to a plain dict for JSON storage."""
        return {"timestamp": self.timestamp, "entries": [asdict(e) for e in self.entries]}

    @classmethod
    def from_dict(cls, d: dict) -> SnapshotManifest:
        """Deserialize a manifest from a plain dict (as read from JSON)."""
        return cls(
            timestamp=d["timestamp"], entries=[SnapshotEntry(**e) for e in d.get("entries", [])]
        )


class SnapshotManager:
    """Manages pre-flight snapshots for exportify fix runs.

    Snapshots are stored in .exportify/snapshots/last/ relative to the
    project root. Only one snapshot (the most recent) is kept.
    """

    SNAPSHOT_SUBDIR = Path(".exportify") / "snapshots" / "last"

    def __init__(self, project_root: Path | None = None) -> None:
        """Initialize the snapshot manager rooted at ``project_root``.

        Args:
            project_root: Absolute path to the project root directory.
                Defaults to the current working directory.
        """
        self.project_root = (project_root or Path.cwd()).resolve()
        self.snapshot_dir = self.project_root / self.SNAPSHOT_SUBDIR
        self.files_dir = self.snapshot_dir / "files"
        self.manifest_path = self.snapshot_dir / "manifest.json"

    def capture(self, files: list[Path]) -> SnapshotManifest:
        """Capture current content of files before modification.

        Only files that exist are captured. Overwrites any previous snapshot.

        Args:
            files: Absolute paths to files that may be modified.

        Returns:
            The manifest that was written.
        """
        # Wipe and recreate snapshot dirs for clean overwrite
        if self.snapshot_dir.exists():
            shutil.rmtree(self.snapshot_dir)
        self.files_dir.mkdir(parents=True, exist_ok=True)

        entries: list[SnapshotEntry] = []
        for i, file_path in enumerate(files):
            if not file_path.exists():
                continue
            stored_name = f"{i}.py"
            shutil.copy2(file_path, self.files_dir / stored_name)
            resolved = file_path.resolve()
            try:
                rel = str(resolved.relative_to(self.project_root))
            except ValueError:
                rel = str(resolved)
            entries.append(SnapshotEntry(source=rel, stored=stored_name))

        manifest = SnapshotManifest(timestamp=datetime.now(UTC).isoformat(), entries=entries)
        self.manifest_path.write_text(json.dumps(manifest.to_dict(), indent=2), encoding="utf-8")
        return manifest

    def restore(self, paths: list[Path] | None = None) -> list[Path]:
        """Restore files from the last snapshot.

        Idempotent: calling restore multiple times produces the same result.

        Args:
            paths: Optional list of files or directories to filter the restore.
                   A directory path matches all snapshot entries under it.
                   If None, all entries are restored.

        Returns:
            List of file paths that were restored.
        """
        manifest = self.read_manifest()
        if manifest is None:
            return []

        resolved_filters = [p.resolve() for p in paths] if paths else None
        restored: list[Path] = []
        for entry in manifest.entries:
            abs_source = self.project_root / entry.source

            if resolved_filters is not None and not any(
                abs_source == f or abs_source.is_relative_to(f) for f in resolved_filters
            ):
                continue

            stored = self.files_dir / entry.stored
            if not stored.exists():
                continue

            abs_source.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(stored, abs_source)
            restored.append(abs_source)

        return restored

    def has_snapshot(self) -> bool:
        """Return True if a snapshot manifest exists."""
        return self.manifest_path.exists()

    def read_manifest(self) -> SnapshotManifest | None:
        """Read and parse the manifest, returning None if not present."""
        if not self.manifest_path.exists():
            return None
        try:
            data = json.loads(self.manifest_path.read_text(encoding="utf-8"))
            return SnapshotManifest.from_dict(data)
        except (json.JSONDecodeError, KeyError, TypeError):
            return None


__all__ = ("SnapshotEntry", "SnapshotManager", "SnapshotManifest")
