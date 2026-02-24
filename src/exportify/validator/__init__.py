# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Validator module for lazy imports.

Provides validation of lateimport calls, package consistency, and import resolution.
"""

from __future__ import annotations

from exportify.validator.validator import LateImportValidator


ImportValidator = LateImportValidator

# === MANAGED EXPORTS ===

# Exportify manages this section. It contains lazy-loading infrastructure
# for the package: imports and runtime declarations (__all__, __getattr__,
# __dir__). Manual edits will be overwritten by `exportify fix`.

from types import MappingProxyType
from typing import TYPE_CHECKING

from lateimport import create_late_getattr


if TYPE_CHECKING:
    from exportify.validator.consistency import ConsistencyChecker
    from exportify.validator.resolver import ImportResolver
    from exportify.validator.validator import LateImportValidator, ValidationError

_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({
    "ConsistencyChecker": (__spec__.parent, "consistency"),
    "ImportResolver": (__spec__.parent, "resolver"),
    "LateImportValidator": (__spec__.parent, "validator"),
    "ValidationError": (__spec__.parent, "validator"),
})

__getattr__ = create_late_getattr(_dynamic_imports, globals(), __name__)

__all__ = ("ConsistencyChecker", "ImportResolver", "LateImportValidator", "ValidationError")


def __dir__() -> list[str]:
    """List available attributes for the package."""
    return list(__all__)
