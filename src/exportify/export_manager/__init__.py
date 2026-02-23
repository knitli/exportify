# SPDX-FileCopyrightText: 2026 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Export management components.

This package contains the core export management system responsible for
determining which exports should be included in __init__.py files and how
they should propagate through the package hierarchy.

Components:
- RuleEngine: Priority-based rule evaluation
- PropagationGraph: Bottom-up export propagation
- CodeGenerator: __init__.py file generation
"""

from __future__ import annotations

from exportify.export_manager.generator import (
    CodeGenerator,
    GeneratedCode,
    validate_init_file,
)
from exportify.export_manager.graph import PropagationGraph
from exportify.export_manager.rules import RuleEngine


__all__ = ["CodeGenerator", "GeneratedCode", "PropagationGraph", "RuleEngine", "validate_init_file"]
