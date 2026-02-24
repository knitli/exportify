# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""AST analysis package for lazy import system."""

from __future__ import annotations

from types import MappingProxyType

# === MANAGED EXPORTS ===
# Exportify manages this section. It contains lazy-loading infrastructure
# for the package: imports and runtime declarations (__all__, __getattr__,
# __dir__). Manual edits will be overwritten by `exportify fix`.
from typing import TYPE_CHECKING

from lateimport import create_late_getattr

from exportify.analysis.ast_parser import ASTParser


if TYPE_CHECKING:
    from exportify.analysis.ast_parser import ASTParser
    from exportify.analysis.ast_parser_overload import (
        group_functions_by_name,
        is_overloaded_function,
    )

_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({
    "ASTParser": (__spec__.parent, "ast_parser"),
    "group_functions_by_name": (__spec__.parent, "ast_parser_overload"),
    "is_overloaded_function": (__spec__.parent, "ast_parser_overload"),
})

__getattr__ = create_late_getattr(_dynamic_imports, globals(), __name__)

__all__ = ("ASTParser", "group_functions_by_name", "is_overloaded_function")


def __dir__() -> list[str]:
    """List available attributes for the package."""
    return list(__all__)
