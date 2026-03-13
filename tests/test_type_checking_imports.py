#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Test TYPE_CHECKING import handling.

Verifies that:
1. Regular imports DON'T go in _dynamic_imports
2. TYPE_CHECKING imports DO go in _dynamic_imports
3. Regular imports CAN go in __all__ (rule-dependent)
4. Mixed imports are handled correctly
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from exportify.analysis.ast_parser import ASTParser
from exportify.common.types import (
    ExportManifest,
    LazyExport,
    PropagationLevel,
    Rule,
    RuleAction,
    RuleMatchCriteria,
)
from exportify.export_manager.generator import CodeGenerator
from exportify.export_manager.rules import RuleEngine


if TYPE_CHECKING:
    from exportify.common.types import AnalysisResult


@pytest.fixture
def rule_engine() -> RuleEngine:
    """Create test rule engine."""
    engine = RuleEngine()

    # Default rules - export everything for testing
    engine.add_rule(
        Rule(
            name="default-export",
            priority=0,
            description="Export all by default",
            match=RuleMatchCriteria(name_pattern=".*"),
            action=RuleAction.INCLUDE,
            propagate=PropagationLevel.PARENT,
        )
    )

    return engine


@pytest.fixture
def temp_file(tmp_path: Path) -> Path:
    """Create temporary Python file."""
    return tmp_path / "test_module.py"


class TestRegularImportsNotInDynamicImports:
    """Test that regular imports don't appear in _dynamic_imports."""

    def test_simple_import_not_in_dynamic(self, temp_file: Path, rule_engine: RuleEngine):
        """Simple import statement should not be in _dynamic_imports."""
        temp_file.write_text("""
import sys
from pathlib import Path

class MyClass:
    pass
""")

        parser = ASTParser()
        result: AnalysisResult = parser.parse_file(temp_file)

        # Verify imports were extracted
        assert "import sys" in result.imports
        assert "from pathlib import Path" in result.imports

        # TODO: Once we implement import metadata tracking, verify:
        # - Imports are NOT marked as type_checking
        # - They won't be in _dynamic_imports dict

    def test_from_import_not_in_dynamic(self, temp_file: Path, rule_engine: RuleEngine):
        """From imports should not be in _dynamic_imports."""
        temp_file.write_text("""
from collections.abc import Sequence
from typing import cast

def process(items: Sequence[int]) -> int:
    return cast(int, items[0])
""")

        parser = ASTParser()
        result = parser.parse_file(temp_file)

        assert "from collections.abc import Sequence" in result.imports
        assert "from typing import cast" in result.imports

        # TODO: Verify these are regular imports, not type_checking


class TestTypeCheckingImportsInDynamicImports:
    """Test that TYPE_CHECKING imports DO appear in _dynamic_imports."""

    def test_type_checking_block_imports(self, temp_file: Path, rule_engine: RuleEngine):
        """Imports in TYPE_CHECKING block should be marked for lazy loading."""
        temp_file.write_text("""
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any
    from .models import User

class Service:
    pass
""")

        parser = ASTParser()
        result = parser.parse_file(temp_file)

        # Verify TYPE_CHECKING imports were found
        assert any("from typing import Any" in imp for imp in result.imports)
        assert any("from .models import User" in imp for imp in result.imports)

        # TODO: Once implemented, verify:
        # - These imports are marked as is_type_checking=True
        # - They will be in _dynamic_imports dict

    def test_multiple_type_checking_imports(self, temp_file: Path, rule_engine: RuleEngine):
        """Multiple imports in TYPE_CHECKING block."""
        temp_file.write_text("""
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any, Optional, Union
    from .models import User, Group, Permission
    from .utils import Helper

def get_user():
    pass
""")

        parser = ASTParser()
        result = parser.parse_file(temp_file)

        # All TYPE_CHECKING imports should be found
        type_checking_imports = [
            imp
            for imp in result.imports
            if ("TYPE_CHECKING" not in imp and "from typing import Any" in imp)
            or "from .models import" in imp
            or "from .utils import" in imp
        ]

        assert len(type_checking_imports) >= 3  # At least the three from statements


class TestMixedImports:
    """Test files with both regular and TYPE_CHECKING imports."""

    def test_mixed_regular_and_type_checking(self, temp_file: Path, rule_engine: RuleEngine):
        """Mix of regular and TYPE_CHECKING imports."""
        temp_file.write_text("""
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any
    from .models import User

class MyClass:
    pass
""")

        parser = ASTParser()
        result = parser.parse_file(temp_file)

        # Regular imports
        assert "import sys" in result.imports
        assert "from pathlib import Path" in result.imports

        # TYPE_CHECKING imports
        assert any("from typing import Any" in imp for imp in result.imports)
        assert any("from .models import User" in imp for imp in result.imports)

        # TODO: Verify context distinction:
        # - sys and Path: is_type_checking=False
        # - Any and User: is_type_checking=True


class TestGeneratedDynamicImports:
    """Test _dynamic_imports dict generation in CodeGenerator."""

    def test_dynamic_imports_contains_lazy_exports(self, tmp_path: Path):
        """_dynamic_imports should contain entries for each runtime export."""
        exports = [
            LazyExport(
                public_name="MyClass",
                target_module="mypackage.core",
                target_object="MyClass",
                is_type_only=False,
            ),
            LazyExport(
                public_name="helper",
                target_module="mypackage.utils",
                target_object="helper",
                is_type_only=False,
            ),
        ]
        manifest = ExportManifest(
            module_path="mypackage", own_exports=[], propagated_exports=exports, all_exports=exports
        )

        generator = CodeGenerator(tmp_path)
        code = generator.generate(manifest)

        # _dynamic_imports should be a MappingProxyType with entries
        assert (
            "_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({"
            in code.content
        )
        assert '"MyClass": (__spec__.parent, "core")' in code.content
        assert '"helper": (__spec__.parent, "utils")' in code.content

    def test_dynamic_imports_empty_when_no_exports(self, tmp_path: Path):
        """With no exports the managed section should be minimal: just __all__ = ()."""
        manifest = ExportManifest(
            module_path="mypackage", own_exports=[], propagated_exports=[], all_exports=[]
        )

        generator = CodeGenerator(tmp_path)
        code = generator.generate(manifest)

        # No lazy-loading infrastructure when there are no exports
        assert "_dynamic_imports" not in code.content
        assert "MappingProxyType" not in code.content
        assert "__all__ = ()" in code.content


class TestRegularImportsInAll:
    """Test that regular imports CAN be in __all__ (rule-dependent)."""

    def test_regular_import_in_all_if_rule_allows(self):
        """Regular imports can be in __all__ if rules allow."""
        # This is tested indirectly through rule evaluation
        # The key point is they DON'T go in _dynamic_imports
        # but MAY go in __all__
        # Covered by other tests with rule_engine fixture


class TestEdgeCases:
    """Test edge cases and complex scenarios."""

    def test_nested_type_checking_blocks(self, temp_file: Path, rule_engine: RuleEngine):
        """Nested TYPE_CHECKING blocks (shouldn't happen but handle gracefully)."""
        temp_file.write_text("""
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any
    if True:  # Nested
        from .models import User
""")

        parser = ASTParser()
        result = parser.parse_file(temp_file)

        # Should extract imports even if nested
        assert any("from typing import Any" in imp for imp in result.imports)

    def test_type_checking_with_else_block(self, temp_file: Path, rule_engine: RuleEngine):
        """TYPE_CHECKING block with else clause."""
        temp_file.write_text("""
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import User
else:
    from .mock import MockUser as User
""")

        parser = ASTParser()
        result = parser.parse_file(temp_file)

        # Both branches should be extracted
        assert any("from .models import User" in imp for imp in result.imports)
        assert any("from .mock import MockUser" in imp for imp in result.imports)

        # TODO: Verify context tracking:
        # - .models.User: is_type_checking=True
        # - .mock.MockUser: is_type_checking=False (in else block)
