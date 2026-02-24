# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""File discovery package for lazy import system."""

from __future__ import annotations

from types import MappingProxyType

# === MANAGED EXPORTS ===
# Exportify manages this section. It contains lazy-loading infrastructure
# for the package: imports and runtime declarations (__all__, __getattr__,
# __dir__). Manual edits will be overwritten by `exportify fix`.
from typing import TYPE_CHECKING

from lateimport import create_late_getattr


if TYPE_CHECKING:
    from exportify.discovery.file_discovery import FileDiscovery

_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({
    "FileDiscovery": (__spec__.parent, "file_discovery")
})

__getattr__ = create_late_getattr(_dynamic_imports, globals(), __name__)

__all__ = ("FileDiscovery",)


def __dir__() -> list[str]:
    """List available attributes for the package."""
    return list(__all__)
