# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Common utilities for lazy import system."""

from __future__ import annotations

from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from exportify.common.snapshot import SnapshotEntry, SnapshotManager, SnapshotManifest

_dynamic_imports: dict[str, tuple[str, str]] = {
    "SnapshotEntry": (".snapshot", "SnapshotEntry"),
    "SnapshotManifest": (".snapshot", "SnapshotManifest"),
    "SnapshotManager": (".snapshot", "SnapshotManager"),
}


def __getattr__(name: str) -> object:
    if name in _dynamic_imports:
        module_path, attr = _dynamic_imports[name]
        import importlib

        module = importlib.import_module(module_path, package=__name__)
        return getattr(module, attr)
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)


__all__ = (
    "SnapshotEntry",
    "SnapshotManager",
    "SnapshotManifest",
)
