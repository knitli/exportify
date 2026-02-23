# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Validator module for lazy imports.

Provides validation of lateimport calls, package consistency, and import resolution.
"""

from __future__ import annotations

from exportify.validator.consistency import ConsistencyChecker
from exportify.validator.resolver import ImportResolver
from exportify.validator.validator import LateImportValidator


# Alias for backward compatibility with tests
ImportValidator = LateImportValidator

__all__ = ["ConsistencyChecker", "ImportResolver", "ImportValidator", "LateImportValidator"]
