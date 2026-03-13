# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Test TypeVar, TypeVarTuple, and ParamSpec detection in the AST parser."""

from __future__ import annotations

from pathlib import Path

import pytest

from exportify.analysis.ast_parser import ASTParser
from exportify.common.types import MemberType


@pytest.fixture
def parser() -> ASTParser:
    """Create AST parser."""
    return ASTParser()


def create_temp_file(content: str, tmp_path: Path) -> Path:
    """Create a temporary Python file."""
    file_path = tmp_path / "test_module.py"
    file_path.write_text(content)
    return file_path


class TestTypeVarDetection:
    """Test TypeVar detection (pre-3.12 assignment style: T = TypeVar('T'))."""

    def test_simple_typevar_detected(self, parser: ASTParser, tmp_path: Path) -> None:
        """Simple TypeVar assignment should be detected as TYPE_VAR."""
        content = """
from typing import TypeVar

T = TypeVar('T')
"""
        file_path = create_temp_file(content, tmp_path)
        result = parser.parse_file(file_path)

        t_sym = [e for e in result.symbols if e.name == "T"]
        assert len(t_sym) == 1
        assert t_sym[0].member_type == MemberType.TYPE_VAR

    def test_qualified_typevar_detected(self, parser: ASTParser, tmp_path: Path) -> None:
        """typing.TypeVar() should be detected as TYPE_VAR."""
        content = """
import typing

T = typing.TypeVar('T')
"""
        file_path = create_temp_file(content, tmp_path)
        result = parser.parse_file(file_path)

        t_sym = [e for e in result.symbols if e.name == "T"]
        assert len(t_sym) == 1
        assert t_sym[0].member_type == MemberType.TYPE_VAR

    def test_constrained_typevar_detected(self, parser: ASTParser, tmp_path: Path) -> None:
        """TypeVar with type constraints should be detected as TYPE_VAR."""
        content = """
from typing import TypeVar

T = TypeVar('T', int, str)
"""
        file_path = create_temp_file(content, tmp_path)
        result = parser.parse_file(file_path)

        t_sym = [e for e in result.symbols if e.name == "T"]
        assert len(t_sym) == 1
        assert t_sym[0].member_type == MemberType.TYPE_VAR

    def test_bound_typevar_detected(self, parser: ASTParser, tmp_path: Path) -> None:
        """TypeVar with bound should be detected as TYPE_VAR."""
        content = """
from typing import TypeVar

T = TypeVar('T', bound=int)
"""
        file_path = create_temp_file(content, tmp_path)
        result = parser.parse_file(file_path)

        t_sym = [e for e in result.symbols if e.name == "T"]
        assert len(t_sym) == 1
        assert t_sym[0].member_type == MemberType.TYPE_VAR

    def test_covariant_typevar_detected(self, parser: ASTParser, tmp_path: Path) -> None:
        """Covariant TypeVar should be detected as TYPE_VAR."""
        content = """
from typing import TypeVar

T_co = TypeVar('T_co', covariant=True)
"""
        file_path = create_temp_file(content, tmp_path)
        result = parser.parse_file(file_path)

        t_sym = [e for e in result.symbols if e.name == "T_co"]
        assert len(t_sym) == 1
        assert t_sym[0].member_type == MemberType.TYPE_VAR

    def test_contravariant_typevar_detected(self, parser: ASTParser, tmp_path: Path) -> None:
        """Contravariant TypeVar should be detected as TYPE_VAR."""
        content = """
from typing import TypeVar

T_contra = TypeVar('T_contra', contravariant=True)
"""
        file_path = create_temp_file(content, tmp_path)
        result = parser.parse_file(file_path)

        t_sym = [e for e in result.symbols if e.name == "T_contra"]
        assert len(t_sym) == 1
        assert t_sym[0].member_type == MemberType.TYPE_VAR

    def test_private_typevar_is_private(self, parser: ASTParser, tmp_path: Path) -> None:
        """TypeVar with underscore prefix should be marked private."""
        content = """
from typing import TypeVar

_T = TypeVar('_T')
"""
        file_path = create_temp_file(content, tmp_path)
        result = parser.parse_file(file_path)

        t_sym = [e for e in result.symbols if e.name == "_T"]
        assert len(t_sym) == 1
        assert t_sym[0].member_type == MemberType.TYPE_VAR
        assert t_sym[0].is_private is True

    def test_multiple_typevars_detected(self, parser: ASTParser, tmp_path: Path) -> None:
        """Multiple TypeVars should all be detected."""
        content = """
from typing import TypeVar

K = TypeVar('K')
V = TypeVar('V')
T = TypeVar('T')
"""
        file_path = create_temp_file(content, tmp_path)
        result = parser.parse_file(file_path)

        typevars = [e for e in result.symbols if e.member_type == MemberType.TYPE_VAR]
        assert len(typevars) == 3
        assert {tv.name for tv in typevars} == {"K", "V", "T"}


class TestTypeVarVariants:
    """Test ParamSpec and TypeVarTuple detection."""

    def test_paramspec_detected(self, parser: ASTParser, tmp_path: Path) -> None:
        """ParamSpec should be detected as TYPE_VAR."""
        content = """
from typing import ParamSpec

P = ParamSpec('P')
"""
        file_path = create_temp_file(content, tmp_path)
        result = parser.parse_file(file_path)

        p_sym = [e for e in result.symbols if e.name == "P"]
        assert len(p_sym) == 1
        assert p_sym[0].member_type == MemberType.TYPE_VAR

    def test_typevartuple_detected(self, parser: ASTParser, tmp_path: Path) -> None:
        """TypeVarTuple should be detected as TYPE_VAR."""
        content = """
from typing import TypeVarTuple

Ts = TypeVarTuple('Ts')
"""
        file_path = create_temp_file(content, tmp_path)
        result = parser.parse_file(file_path)

        ts_sym = [e for e in result.symbols if e.name == "Ts"]
        assert len(ts_sym) == 1
        assert ts_sym[0].member_type == MemberType.TYPE_VAR

    def test_qualified_paramspec_detected(self, parser: ASTParser, tmp_path: Path) -> None:
        """typing.ParamSpec() should be detected as TYPE_VAR."""
        content = """
import typing

P = typing.ParamSpec('P')
"""
        file_path = create_temp_file(content, tmp_path)
        result = parser.parse_file(file_path)

        p_sym = [e for e in result.symbols if e.name == "P"]
        assert len(p_sym) == 1
        assert p_sym[0].member_type == MemberType.TYPE_VAR

    def test_qualified_typevartuple_detected(self, parser: ASTParser, tmp_path: Path) -> None:
        """typing.TypeVarTuple() should be detected as TYPE_VAR."""
        content = """
import typing

Ts = typing.TypeVarTuple('Ts')
"""
        file_path = create_temp_file(content, tmp_path)
        result = parser.parse_file(file_path)

        ts_sym = [e for e in result.symbols if e.name == "Ts"]
        assert len(ts_sym) == 1
        assert ts_sym[0].member_type == MemberType.TYPE_VAR


class TestTypeVarMetadata:
    """Test metadata stored on detected TypeVar symbols."""

    def test_typevar_metadata_kind(self, parser: ASTParser, tmp_path: Path) -> None:
        """TypeVar should have metadata['kind'] == 'TypeVar'."""
        content = """
from typing import TypeVar

T = TypeVar('T')
"""
        file_path = create_temp_file(content, tmp_path)
        result = parser.parse_file(file_path)

        t_sym = next(e for e in result.symbols if e.name == "T")
        assert t_sym.metadata.get("kind") == "TypeVar"

    def test_paramspec_metadata_kind(self, parser: ASTParser, tmp_path: Path) -> None:
        """ParamSpec should have metadata['kind'] == 'ParamSpec'."""
        content = """
from typing import ParamSpec

P = ParamSpec('P')
"""
        file_path = create_temp_file(content, tmp_path)
        result = parser.parse_file(file_path)

        p_sym = next(e for e in result.symbols if e.name == "P")
        assert p_sym.metadata.get("kind") == "ParamSpec"

    def test_typevartuple_metadata_kind(self, parser: ASTParser, tmp_path: Path) -> None:
        """TypeVarTuple should have metadata['kind'] == 'TypeVarTuple'."""
        content = """
from typing import TypeVarTuple

Ts = TypeVarTuple('Ts')
"""
        file_path = create_temp_file(content, tmp_path)
        result = parser.parse_file(file_path)

        ts_sym = next(e for e in result.symbols if e.name == "Ts")
        assert ts_sym.metadata.get("kind") == "TypeVarTuple"


class TestMixedTypeVarAndAliases:
    """Test TypeVars coexisting with type aliases and other symbols."""

    def test_typevar_with_type_aliases(self, parser: ASTParser, tmp_path: Path) -> None:
        """TypeVars and type aliases should coexist correctly."""
        content = """
from typing import TypeVar, TypeAlias

T = TypeVar('T')

MyAlias: TypeAlias = int | str
type ModernAlias = dict[str, int]
"""
        file_path = create_temp_file(content, tmp_path)
        result = parser.parse_file(file_path)

        types = {e.name: e.member_type for e in result.symbols}
        assert types.get("T") == MemberType.TYPE_VAR
        assert types.get("MyAlias") == MemberType.TYPE_ALIAS
        assert types.get("ModernAlias") == MemberType.TYPE_ALIAS

    def test_typevar_with_all_symbol_types(self, parser: ASTParser, tmp_path: Path) -> None:
        """TypeVar should coexist with classes, functions, constants, and variables."""
        content = """
from typing import TypeVar

T = TypeVar('T')

class Container:
    pass

def process(x: T) -> T:
    return x

MAX_SIZE = 100
config: dict = {}
"""
        file_path = create_temp_file(content, tmp_path)
        result = parser.parse_file(file_path)

        types = {e.name: e.member_type for e in result.symbols}
        assert types.get("T") == MemberType.TYPE_VAR
        assert types.get("Container") == MemberType.CLASS
        assert types.get("process") == MemberType.FUNCTION
        assert types.get("MAX_SIZE") == MemberType.CONSTANT
        assert types.get("config") == MemberType.VARIABLE
