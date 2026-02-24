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
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    pass

# Pre-3.12 style type aliases (X: TypeAlias = Y)
type FilePath = str | Path
type ModuleName = str
type RulePattern = str
type ExportName = str
type ErrorMessage = str
type ConfigDict = dict[str, str | int | bool | list[str]]
type NamePair = tuple[str, str]

# Python 3.12+ style type aliases (type X = Y)
type FileContent = str
type LineNumber = int
type ColumnNumber = int
type SymbolName = str
type ModulePath = str
