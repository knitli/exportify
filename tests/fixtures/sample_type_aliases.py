# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Sample module with type aliases for testing the AST parser.

This file serves as a real-world fixture for testing type alias detection.
It contains both Python 3.12+ and pre-3.12 style type aliases, mimicking
realistic usage patterns from a package like exportify itself.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, TypeAlias

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

# Pre-3.12 style type aliases (X: TypeAlias = Y)
FilePath: TypeAlias = str | Path
ModuleName: TypeAlias = str
RulePattern: TypeAlias = str
ExportName: TypeAlias = str
ErrorMessage: TypeAlias = str
ConfigDict: TypeAlias = dict[str, str | int | bool | list[str]]
NamePair: TypeAlias = tuple[str, str]

# Python 3.12+ style type aliases (type X = Y)
type FileContent = str
type LineNumber = int
type ColumnNumber = int
type SymbolName = str
type ModulePath = str
