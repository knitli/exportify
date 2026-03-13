#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Tests for code generator.

Tests cover:
- Sentinel-based preservation of manual code
- Lazy import generation (_dynamic_imports, __getattr__)
- Type checking support
- __all__ list generation
- Atomic writes with syntax validation
"""

# sourcery skip: require-return-annotation, require-parameter-annotation, no-relative-imports
from __future__ import annotations

import tempfile

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from exportify.common.config import SpdxConfig
from exportify.common.types import ExportManifest, LazyExport
from exportify.export_manager.generator import (
    SENTINEL,
    CodeGenerator,
    GeneratedCode,
    validate_init_file,
)


if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def generator(temp_dir: Path) -> CodeGenerator:
    """Create code generator for tests."""
    return CodeGenerator(temp_dir)


# Test data


def make_lazy_export(
    public_name: str,
    target_module: str,
    target_object: str | None = None,
    *,
    is_type_only: bool = False,
) -> LazyExport:
    """Create test LazyExport."""
    return LazyExport(
        public_name=public_name,
        target_module=target_module,
        target_object=target_object or public_name,
        is_type_only=is_type_only,
    )


def make_manifest(
    module_path: str, own_exports: list[LazyExport], propagated: list[LazyExport] | None = None
) -> ExportManifest:
    """Create test export manifest."""
    propagated = propagated or []
    all_exports = own_exports + propagated

    return ExportManifest(
        module_path=module_path,
        own_exports=own_exports,
        propagated_exports=propagated,
        all_exports=all_exports,
    )


# Basic generation tests


# We need to tell reuse that these are not actual headers, otherwise it'll throw an error.
# REUSE-IgnoreStart
def test_generate_empty_manifest(generator: CodeGenerator):
    """Test generating code from empty manifest."""
    manifest = make_manifest("test.module", own_exports=[])

    code = generator.generate(manifest)

    assert code.export_count == 0
    assert "__all__ = ()" in code.content  # Tuple, not list
    assert SENTINEL in code.content
    assert "from __future__ import annotations" in code.content
    # No lazy-loading infrastructure when there are no exports
    assert "MappingProxyType" not in code.content
    assert "create_late_getattr" not in code.content
    assert "def __dir__()" not in code.content
    assert "if TYPE_CHECKING:" not in code.content


def test_generate_single_export(generator: CodeGenerator):
    """Test generating code with single lazy export."""
    exports = [make_lazy_export("MyClass", "test.module.submodule")]
    manifest = make_manifest("test.module", own_exports=[], propagated=exports)

    code = generator.generate(manifest)

    assert code.export_count == 1
    assert '__all__ = ("MyClass",)' in code.content  # Tuple with trailing comma

    # Check for lazy loading machinery with new format
    assert (
        "_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({"
        in code.content
    )
    assert '"MyClass": (__spec__.parent, "submodule"),' in code.content  # Relative module name
    assert (
        "__getattr__ = create_late_getattr(_dynamic_imports, globals(), __name__)" in code.content
    )
    assert "def __dir__() -> list[str]:" in code.content

    # Should NOT use old-style __getattr__ function
    assert "def __getattr__(name: str):" not in code.content
    assert "import importlib" not in code.content  # No longer needed in generated code


def test_generate_multiple_exports(generator: CodeGenerator):
    """Test generating code with multiple exports."""
    exports = [
        make_lazy_export("ClassA", "test.module.sub1"),
        make_lazy_export("ClassB", "test.module.sub2"),
        make_lazy_export("function_c", "test.module.sub1"),
    ]
    manifest = make_manifest("test.module", own_exports=[], propagated=exports)

    code = generator.generate(manifest)

    assert code.export_count == 3
    # New format with __spec__.parent and relative module names
    assert '"ClassA": (__spec__.parent, "sub1"),' in code.content
    assert '"ClassB": (__spec__.parent, "sub2"),' in code.content
    assert '"function_c": (__spec__.parent, "sub1"),' in code.content

    # Should be sorted in __all__ using custom sort key
    # PascalCase (group 1) comes before snake_case (group 2)
    lines = code.content.split("\n")
    all_section_start = next(i for i, line in enumerate(lines) if line.startswith("__all__ = ("))
    all_lines = lines[all_section_start:]
    all_text = "\n".join(all_lines)

    # ClassA and ClassB (PascalCase) should come before function_c (snake_case)
    assert all_text.index("ClassA") < all_text.index("ClassB")
    assert all_text.index("ClassB") < all_text.index("function_c")


# TYPE_CHECKING tests


def test_type_alias_in_type_checking_block(generator: CodeGenerator):
    """Test type aliases go in TYPE_CHECKING block and ARE in _dynamic_imports."""
    exports = [
        make_lazy_export("MyClass", "test.module.sub"),
        make_lazy_export("MyType", "test.module.sub", is_type_only=True),
    ]
    manifest = make_manifest("test.module", own_exports=[], propagated=exports)

    code = generator.generate(manifest)

    # Should have TYPE_CHECKING import
    assert "from typing import TYPE_CHECKING" in code.content
    assert "if TYPE_CHECKING:" in code.content

    # Both should be in TYPE_CHECKING block with new grouped format
    assert "MyType" in code.content
    assert "MyClass" in code.content
    assert "from test.module.sub import (" in code.content

    # MyType SHOULD be in _dynamic_imports now so it's available at runtime
    assert '"MyType": (__spec__.parent, "sub"),' in code.content

    # MyClass should be in _dynamic_imports with new format
    assert '"MyClass": (__spec__.parent, "sub"),' in code.content


# Sentinel preservation tests


def test_preserve_manual_section(generator: CodeGenerator, temp_dir: Path):
    """Test preserving manual code above sentinel."""
    module_path = "test.module"
    target = temp_dir / "test" / "module" / "__init__.py"
    target.parent.mkdir(parents=True)

    # Write existing file with manual section
    existing_content = """# My custom imports
from typing import Protocol

# Custom code
CUSTOM_CONSTANT = 42

# === MANAGED EXPORTS ===
# Old managed section (will be replaced)
__all__ = ["OldExport"]
"""
    target.write_text(existing_content)

    # Generate new code
    exports = [make_lazy_export("NewExport", "test.module.sub")]
    manifest = make_manifest(module_path, own_exports=exports)
    code = generator.generate(manifest)

    # Should preserve manual section
    assert "# My custom imports" in code.manual_section
    assert "CUSTOM_CONSTANT = 42" in code.manual_section

    # Should NOT preserve old managed section
    assert "OldExport" not in code.managed_section

    # Should have new managed section
    assert "NewExport" in code.managed_section


def test_sentinel_file_with_manual_all_no_duplicate(generator: CodeGenerator, temp_dir: Path):
    """Regenerating a file whose preserved section has a manual __all__ must not duplicate it."""
    module_path = "test.module"
    target = temp_dir / "test" / "module" / "__init__.py"
    target.parent.mkdir(parents=True)

    # Simulate the export_manager/__init__.py pattern: manual __all__ above the sentinel,
    # generated __all__ below it.
    existing_content = """\
from typing import Protocol

from test.module.sub import OldExport

__all__ = [
    "OldExport",
    "Protocol",
]

# === MANAGED EXPORTS ===

__all__ = ("OldExport",)
"""
    target.write_text(existing_content)

    exports = [make_lazy_export("NewExport", "test.module.sub")]
    manifest = make_manifest(module_path, own_exports=exports)
    code = generator.generate(manifest)

    # The regenerated file must contain exactly one __all__ *assignment*
    all_assignments = [
        line for line in code.content.splitlines() if line.strip().startswith("__all__ =")
    ]
    assert len(all_assignments) == 1, (
        f"Expected 1 __all__ assignment, got {len(all_assignments)}:\n{code.content}"
    )

    # Manual imports are preserved, old __all__ is not
    assert "from test.module.sub import OldExport" in code.content
    assert "OldExport" not in code.managed_section  # replaced by NewExport
    assert "NewExport" in code.managed_section

    # File must be syntactically valid
    import ast as _ast

    _ast.parse(code.content)


def test_no_sentinel_preserves_non_managed_code(generator: CodeGenerator, temp_dir: Path):
    """Test file without sentinel: non-managed user code is preserved, managed imports filtered."""
    module_path = "test.module"
    target = temp_dir / "test" / "module" / "__init__.py"
    target.parent.mkdir(parents=True)

    # Write existing file WITHOUT sentinel that is NOT a lazy-import file
    existing_content = """# Legacy file without sentinel
from typing import Protocol

__all__ = ["LegacyExport"]
"""
    target.write_text(existing_content)

    # Generate new code
    exports = [make_lazy_export("NewExport", "test.module.sub")]
    manifest = make_manifest(module_path, own_exports=exports)
    code = generator.generate(manifest)

    # The manual section stores the original preserved text (non-lazy file: all except from __future__)
    assert "# Legacy file without sentinel" in code.manual_section
    assert "LegacyExport" in code.manual_section


def test_no_sentinel_lazy_file_filters_managed_imports(generator: CodeGenerator, temp_dir: Path):
    """Test that a sentinel-less file with lazy imports has them filtered, not duplicated."""
    module_path = "test.module"
    target = temp_dir / "test" / "module" / "__init__.py"
    target.parent.mkdir(parents=True)

    # Simulate a file generated before sentinels were added (lazy import pattern, no sentinel)
    existing_content = '''"""Package docstring."""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from lateimport import create_late_getattr

if TYPE_CHECKING:
    from test.module.sub import OldExport

_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({
    "OldExport": (__spec__.parent, "sub"),
})

__getattr__ = create_late_getattr(_dynamic_imports, globals(), __name__)

__all__ = ("OldExport",)


def __dir__() -> list[str]:
    """List available attributes for the package."""
    return list(__all__)
'''
    target.write_text(existing_content)

    exports = [make_lazy_export("NewExport", "test.module.sub")]
    manifest = make_manifest(module_path, own_exports=exports)
    code = generator.generate(manifest)

    # Managed infrastructure must NOT appear in the preserved manual section
    assert "_dynamic_imports" not in code.manual_section
    assert "create_late_getattr" not in code.manual_section
    assert "OldExport" not in code.manual_section

    # New export should be in the managed section
    assert "NewExport" in code.managed_section

    # The generated file must be syntactically valid
    import ast as _ast

    _ast.parse(code.content)

    # from __future__ import annotations must be the first executable statement
    lines = [
        line
        for line in code.content.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    assert lines[0] in ('"""Package docstring."""', "from __future__ import annotations"), (
        f"Unexpected first executable line: {lines[0]!r}"
    )


# Atomic write tests


def test_write_file_creates_directories(generator: CodeGenerator, temp_dir: Path):
    """Test write_file creates parent directories."""
    module_path = "test.deeply.nested.module"
    exports = [make_lazy_export("MyClass", module_path)]
    manifest = make_manifest(module_path, own_exports=exports)
    code = generator.generate(manifest)

    generator.write_file(module_path, code)

    # Should create directory structure
    target = temp_dir / "test" / "deeply" / "nested" / "module" / "__init__.py"
    assert target.exists()
    assert target.is_file()


def test_write_file_overwrites_existing(generator: CodeGenerator, temp_dir: Path):
    """Test write_file overwrites an existing file with new content."""
    module_path = "test.module"
    target = temp_dir / "test" / "module" / "__init__.py"
    target.parent.mkdir(parents=True)

    # Write initial file
    initial_content = "# Initial content\n__all__ = []"
    target.write_text(initial_content)

    # Write new file
    exports = [make_lazy_export("NewClass", module_path)]
    manifest = make_manifest(module_path, own_exports=exports)
    code = generator.generate(manifest)
    generator.write_file(module_path, code)

    # File should have new content
    new_content = target.read_text()
    assert "NewClass" in new_content
    assert initial_content != new_content


def test_write_file_atomic_on_syntax_error(generator: CodeGenerator, temp_dir: Path):
    """Test write_file rolls back on syntax errors (should not happen)."""
    module_path = "test.module"
    target = temp_dir / "test" / "module" / "__init__.py"
    target.parent.mkdir(parents=True)

    # Write initial file
    initial_content = "# Initial content\n__all__ = []"
    target.write_text(initial_content)

    # Create invalid code (force syntax error)
    exports = [make_lazy_export("MyClass", module_path)]
    manifest = make_manifest(module_path, own_exports=exports)
    generator.generate(manifest)

    # Corrupt the code to force syntax error
    corrupted = GeneratedCode(
        content="def broken(\n",  # Missing closing paren
        manual_section="",
        managed_section="def broken(\n",
        export_count=1,
        hash="fake",
    )

    # Should raise SyntaxError
    with pytest.raises(SyntaxError) as exc:
        generator.write_file(module_path, corrupted)

    assert "Generated code has syntax errors" in str(exc.value)

    # Original file should be preserved
    assert target.read_text() == initial_content


# Validation tests


def test_validate_generated_valid_code(generator: CodeGenerator):
    """Test validation passes for valid code."""
    exports = [make_lazy_export("MyClass", "test.module")]
    manifest = make_manifest("test.module", own_exports=exports)
    code = generator.generate(manifest)

    errors = generator.validate_generated(code)
    assert errors == []


def test_validate_generated_syntax_error(generator: CodeGenerator):
    """Test validation catches syntax errors."""
    code = GeneratedCode(
        content="def broken(\n",
        manual_section="",
        managed_section="def broken(\n",
        export_count=0,
        hash="fake",
    )

    errors = generator.validate_generated(code)
    assert len(errors) > 0
    assert "Syntax error" in errors[0]


def test_validate_generated_missing_all(generator: CodeGenerator):
    """Test validation catches missing __all__."""
    code = GeneratedCode(
        content="# Valid Python but no __all__\npass\n",
        manual_section="",
        managed_section="pass\n",
        export_count=0,
        hash="fake",
    )

    errors = generator.validate_generated(code)
    assert any("__all__" in err for err in errors)


# validate_init_file tests


def test_validate_init_file_valid(temp_dir: Path):
    """Test validating a valid __init__.py file."""
    init_file = temp_dir / "test" / "__init__.py"
    init_file.parent.mkdir(parents=True)

    content = f"""from __future__ import annotations

{SENTINEL}
# Managed section

__all__ = ("MyClass",)

def __dir__() -> list[str]:
    \"\"\"List available attributes for the package.\"\"\"
    return list(__all__)
"""
    init_file.write_text(content)

    errors = validate_init_file(init_file)
    assert errors == []


def test_validate_init_file_missing(temp_dir: Path):
    """Test validating non-existent file."""
    init_file = temp_dir / "nonexistent" / "__init__.py"

    errors = validate_init_file(init_file)
    assert len(errors) > 0
    assert "does not exist" in errors[0]


def test_validate_init_file_syntax_error(temp_dir: Path):
    """Test validating file with syntax error."""
    init_file = temp_dir / "test" / "__init__.py"
    init_file.parent.mkdir(parents=True)

    init_file.write_text("def broken(\n")

    errors = validate_init_file(init_file)
    assert len(errors) > 0
    assert "Syntax error" in errors[0]


def test_validate_init_file_missing_all(temp_dir: Path):
    """Test validating file without __all__."""
    init_file = temp_dir / "test" / "__init__.py"
    init_file.parent.mkdir(parents=True)

    init_file.write_text("# Valid Python but no __all__\n")

    errors = validate_init_file(init_file)
    assert any("__all__" in err for err in errors)


# Sorting tests


def test_export_sorting_screaming_snake_pascal_snake(generator: CodeGenerator):
    """Test exports are sorted by custom key: SCREAMING_SNAKE, PascalCase, snake_case."""
    exports = [
        make_lazy_export("function_c", "test.module.sub"),
        make_lazy_export("ClassB", "test.module.sub"),
        make_lazy_export("CONSTANT_A", "test.module.sub"),
        make_lazy_export("another_function", "test.module.sub"),
        make_lazy_export("AnotherClass", "test.module.sub"),
        make_lazy_export("ANOTHER_CONST", "test.module.sub"),
    ]
    manifest = make_manifest("test.module", own_exports=exports)
    code = generator.generate(manifest)

    # Extract __all__ section
    lines = code.content.split("\n")
    all_start = next(i for i, line in enumerate(lines) if line.startswith("__all__ = ("))
    all_end = next(i for i in range(all_start, len(lines)) if lines[i] == ")")
    all_items = [
        line.strip().strip('",')
        for line in lines[all_start + 1 : all_end]
        if line.strip() and line.strip() != ","
    ]

    # Expected order: CONSTANTS first (group 0), then Classes (group 1), then functions (group 2)
    expected_order = [
        "ANOTHER_CONST",  # SCREAMING_SNAKE (sorted alphabetically within group)
        "CONSTANT_A",
        "AnotherClass",  # PascalCase
        "ClassB",
        "another_function",  # snake_case
        "function_c",
    ]

    assert all_items == expected_order


def test_type_checking_imports_grouped_by_module(generator: CodeGenerator):
    """Test TYPE_CHECKING imports are grouped by source module."""
    exports = [
        make_lazy_export("ClassA", "test.module.sub1"),
        make_lazy_export("ClassB", "test.module.sub2"),
        make_lazy_export("ClassC", "test.module.sub1"),  # Same module as ClassA
        make_lazy_export("function_d", "test.module.sub2"),  # Same module as ClassB
    ]
    manifest = make_manifest("test.module", own_exports=[], propagated=exports)
    code = generator.generate(manifest)

    # Should group imports by module with multi-line format
    assert "from test.module.sub1 import (" in code.content
    assert "from test.module.sub2 import (" in code.content

    # Check proper formatting with trailing commas
    lines = code.content.split("\n")

    # Find sub1 import section
    sub1_start = next(i for i, line in enumerate(lines) if "from test.module.sub1 import (" in line)
    sub1_section = []
    for i in range(sub1_start + 1, len(lines)):
        if lines[i].strip() == ")":
            break
        sub1_section.append(lines[i].strip())

    # Both ClassA and ClassC should be in sub1 group
    assert "ClassA," in sub1_section
    assert "ClassC," in sub1_section


def test_spdx_headers_present(temp_dir: Path):
    """Test SPDX headers are included when SpdxConfig is enabled."""
    spdx = SpdxConfig(enabled=True, copyright="2026 Test Corp.", license="MIT OR Apache-2.0")
    gen = CodeGenerator(temp_dir, spdx_config=spdx)
    exports = [make_lazy_export("MyClass", "test.module.sub")]
    manifest = make_manifest("test.module", own_exports=exports)
    code = gen.generate(manifest)

    # Check SPDX header lines
    assert "# SPDX-FileCopyrightText: 2026 Test Corp." in code.content
    assert "# SPDX-License-Identifier: MIT OR Apache-2.0" in code.content

    # Headers should be at the very beginning
    lines = code.content.split("\n")
    assert lines[0].startswith("# SPDX-FileCopyrightText:")


def test_spdx_headers_absent_by_default(generator: CodeGenerator):
    """Test no SPDX headers when SpdxConfig is not configured."""
    exports = [make_lazy_export("MyClass", "test.module.sub")]
    manifest = make_manifest("test.module", own_exports=exports)
    code = generator.generate(manifest)

    assert "SPDX-FileCopyrightText" not in code.content
    assert "SPDX-License-Identifier" not in code.content


# REUSE-IgnoreEnd


def test_mapping_proxy_type_annotation(generator: CodeGenerator):
    """Test _dynamic_imports has correct MappingProxyType annotation."""
    exports = [make_lazy_export("MyClass", "test.module.sub")]
    manifest = make_manifest("test.module", own_exports=[], propagated=exports)
    code = generator.generate(manifest)

    assert (
        "_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({"
        in code.content
    )


def test_spec_parent_usage(generator: CodeGenerator):
    """Test __spec__.parent is used instead of hardcoded package name."""
    exports = [make_lazy_export("MyClass", "test.module.submodule")]
    manifest = make_manifest("test.module", own_exports=[], propagated=exports)
    code = generator.generate(manifest)

    # Should use __spec__.parent, not hardcoded "test.module"
    assert "(__spec__.parent," in code.content
    assert '"test.module"' not in code.content.split("_dynamic_imports")[1].split("}")[0]


# Integration tests


def test_full_generation_workflow(generator: CodeGenerator, temp_dir: Path):
    """Test complete generation workflow."""
    module_path = "codeweaver.core.types"

    # Create manifest with mixed exports
    exports = [
        make_lazy_export("MyClass", "codeweaver.core.types.models"),
        make_lazy_export("MyEnum", "codeweaver.core.types.enums"),
        make_lazy_export("MyType", "codeweaver.core.types.aliases", is_type_only=True),
        make_lazy_export("CONSTANT", "codeweaver.core.types.constants"),
    ]
    manifest = make_manifest(module_path, own_exports=[], propagated=exports)

    # Generate code
    code = generator.generate(manifest)

    # Validate
    errors = generator.validate_generated(code)
    assert errors == []

    # Write
    generator.write_file(module_path, code)

    # Verify file exists and is valid
    target = temp_dir / "codeweaver" / "core" / "types" / "__init__.py"
    assert target.exists()

    # Validate written file
    errors = validate_init_file(target)
    assert errors == []

    # Check content
    content = target.read_text()
    assert "MyClass" in content
    assert "MyEnum" in content
    assert "MyType" in content
    assert "CONSTANT" in content
    assert "TYPE_CHECKING" in content  # For MyType
    assert "_dynamic_imports" in content
    assert "__getattr__" in content
    assert "__all__" in content


def test_regeneration_preserves_manual(generator: CodeGenerator, temp_dir: Path):
    """Test regenerating file preserves manual section."""
    module_path = "test.module"
    target = temp_dir / "test" / "module" / "__init__.py"
    target.parent.mkdir(parents=True)

    # First generation
    manual_code = """# User's custom imports
from typing import Protocol

# Custom constant
CUSTOM = 42
"""
    target.write_text(f"{manual_code}\n{SENTINEL}\n__all__ = []")

    _create_file("ClassV1", module_path, generator)
    _create_file("ClassV2", module_path, generator)
    # Manual section should be preserved across both regenerations
    final_content = target.read_text()
    assert "CUSTOM = 42" in final_content
    assert "ClassV2" in final_content
    assert "ClassV1" not in final_content  # Old export replaced


def _create_file(arg0, module_path, generator):
    # First regeneration
    exports_v1 = [make_lazy_export(arg0, module_path + ".sub")]
    manifest_v1 = make_manifest(module_path, own_exports=exports_v1)
    code_v1 = generator.generate(manifest_v1)
    generator.write_file(module_path, code_v1)


# --- Additional tests for uncovered lines ---


# GeneratedCode.create() with add_markers=True (lines 112, 115)


def test_generated_code_create_with_markers():
    """Test GeneratedCode.create with add_markers=True adds preserved code markers."""
    from exportify.export_manager.generator import PRESERVED_BEGIN, PRESERVED_END

    manual = "# some custom code\nMY_VAR = 1"
    managed = "__all__ = ()\ndef __dir__(): return []"

    code = GeneratedCode.create(manual=manual, managed=managed, export_count=1, add_markers=True)

    assert PRESERVED_BEGIN in code.content
    assert PRESERVED_END in code.content
    assert manual in code.content


def test_generated_code_create_without_markers():
    """Test GeneratedCode.create without add_markers does not add markers."""
    from exportify.export_manager.generator import PRESERVED_BEGIN, PRESERVED_END

    manual = "# custom\nX = 1"
    managed = "__all__ = ()\ndef __dir__(): return []"

    code = GeneratedCode.create(manual=manual, managed=managed, export_count=1, add_markers=False)

    assert PRESERVED_BEGIN not in code.content
    assert PRESERVED_END not in code.content


def test_generated_code_create_no_spdx_header():
    """Test GeneratedCode.create with spdx_header=None omits SPDX headers."""

    managed = "__all__ = ()\ndef __dir__(): return []"
    code = GeneratedCode.create(manual="", managed=managed, export_count=0, spdx_header=None)

    assert "SPDX-FileCopyrightText" not in code.content


# write_file raises OSError for non-syntax write failures (line 191)


def test_write_file_raises_oserror_on_non_syntax_failure(generator, temp_dir, monkeypatch):
    """Test write_file raises OSError when file writing fails for non-syntax reasons."""
    from exportify.export_manager.file_writer import WriteResult

    # Create a FileWriter that returns a non-syntax error
    def failing_writer(target, content):
        return WriteResult.failure_result(target, "disk full or something")

    # Monkeypatch the file_writer's write_file to simulate a non-syntax failure
    original_write = generator.file_writer.write_file
    generator.file_writer.write_file = failing_writer

    try:
        module_path = "test.module"
        exports = [make_lazy_export("MyClass", module_path + ".sub")]
        manifest = make_manifest(module_path, own_exports=exports)
        code = generator.generate(manifest)

        with pytest.raises(OSError):
            generator.write_file(module_path, code)
    finally:
        generator.file_writer.write_file = original_write


# _preserve_manual_section exception fallback (lines 264-266)


def test_preserve_manual_section_section_parser_exception(generator, temp_dir, monkeypatch):
    """Test _preserve_manual_section falls back to split on sentinel if SectionParser raises."""
    module_path = "test.fallback"
    target = temp_dir / "test" / "fallback" / "__init__.py"
    target.parent.mkdir(parents=True)

    existing = f"# Manual code above\nMY_VAR = 99\n\n{SENTINEL}\n__all__ = []\n"
    target.write_text(existing)

    # Make section_parser.parse_content raise an exception to trigger the fallback path
    def broken_parse(content):
        raise RuntimeError("simulated parser failure")

    monkeypatch.setattr(generator.section_parser, "parse_content", broken_parse)

    exports = [make_lazy_export("MyClass", module_path + ".sub")]
    manifest = make_manifest(module_path, own_exports=exports)
    code = generator.generate(manifest)

    # Fallback: everything before the sentinel is preserved
    assert "MY_VAR = 99" in code.manual_section


# _generate_managed_section barrel dispatch (line 273)


def test_generate_barrel_style(temp_dir):
    """Test CodeGenerator with barrel output_style generates barrel imports."""
    generator_barrel = CodeGenerator(temp_dir, output_style="barrel")
    exports = [
        make_lazy_export("MyClass", "test.module.sub"),
        make_lazy_export("MyFunc", "test.module.sub2"),
    ]
    manifest = make_manifest("test.module", own_exports=exports)
    code = generator_barrel.generate(manifest)

    # Barrel style: from .sub import MyClass
    assert "from .sub import" in code.content
    assert "from .sub2 import" in code.content
    # No lateimport machinery
    assert "create_late_getattr" not in code.content
    assert "_dynamic_imports" not in code.content


# _generate_barrel_managed_section (lines 341-366)


def test_barrel_managed_section_with_type_only(temp_dir):
    """Test barrel output emits all exports as direct imports."""
    generator_barrel = CodeGenerator(temp_dir, output_style="barrel")
    exports = [
        make_lazy_export("RuntimeClass", "test.module.runtime"),
        make_lazy_export("TypeAlias", "test.module.types", is_type_only=True),
    ]
    manifest = make_manifest("test.module", own_exports=exports)
    code = generator_barrel.generate(manifest)

    # Both should be direct imports now
    assert "from .runtime import RuntimeClass" in code.content
    assert "from .types import TypeAlias" in code.content
    assert "if TYPE_CHECKING:" not in code.content


def test_barrel_managed_section_no_type_only(temp_dir):
    """Test barrel output without type-only exports has no TYPE_CHECKING block."""
    generator_barrel = CodeGenerator(temp_dir, output_style="barrel")
    exports = [make_lazy_export("MyClass", "test.module.sub")]
    manifest = make_manifest("test.module", own_exports=exports)
    code = generator_barrel.generate(manifest)

    assert "TYPE_CHECKING" not in code.content
    assert "from .sub import MyClass" in code.content


def test_barrel_managed_section_empty(temp_dir):
    """Test barrel output with no exports generates minimal valid code."""
    generator_barrel = CodeGenerator(temp_dir, output_style="barrel")
    manifest = make_manifest("test.module", own_exports=[])
    code = generator_barrel.generate(manifest)

    assert "__all__ = ()" in code.content
    assert "def __dir__" not in code.content  # No __dir__ when there are no exports


# _barrel_import_lines (lines 382-403)


def test_barrel_import_lines_aliased(temp_dir):
    """Test barrel imports with aliased exports (target_object != public_name)."""
    generator_barrel = CodeGenerator(temp_dir, output_style="barrel")
    exports = [
        # aliased: from .sub import _OriginalClass as PublicClass
        make_lazy_export("PublicClass", "test.module.sub", target_object="_OriginalClass")
    ]
    manifest = make_manifest("test.module", own_exports=exports)
    code = generator_barrel.generate(manifest)

    assert "_OriginalClass as PublicClass" in code.content


def test_barrel_import_lines_external_module(temp_dir):
    """Test barrel import from module outside the package uses absolute import."""
    generator_barrel = CodeGenerator(temp_dir, output_style="barrel")
    # target_module does NOT start with 'test.module.' so relative can't be computed
    exports = [make_lazy_export("ExternalClass", "other.package.module")]
    manifest = make_manifest("test.module", own_exports=exports)
    code = generator_barrel.generate(manifest)

    # Should use absolute import since it's outside the package
    assert "from other.package.module import ExternalClass" in code.content


def test_barrel_import_lines_multiple_from_same_module(temp_dir):
    """Test barrel imports from same module are grouped together."""
    generator_barrel = CodeGenerator(temp_dir, output_style="barrel")
    exports = [
        make_lazy_export("ClassA", "test.module.sub"),
        make_lazy_export("ClassB", "test.module.sub"),
    ]
    manifest = make_manifest("test.module", own_exports=exports)
    code = generator_barrel.generate(manifest)

    # Should have one import line with both names
    assert "from .sub import ClassA, ClassB" in code.content


# _generate_type_checking_imports with aliased import (line 414)


def test_type_checking_import_aliased(generator):
    """Test TYPE_CHECKING block includes 'obj as alias' when names differ."""
    exports = [make_lazy_export("PublicAlias", "test.module.sub", target_object="InternalClass")]
    manifest = make_manifest("test.module", own_exports=[], propagated=exports)
    code = generator.generate(manifest)

    # The TYPE_CHECKING block should contain 'InternalClass as PublicAlias'
    assert "InternalClass as PublicAlias" in code.content


# _validate_sentinel_section with multiple sentinels (lines 492, 494)


def test_validate_sentinel_section_multiple_sentinels(temp_dir):
    """Test validate_init_file catches multiple SENTINEL occurrences."""
    init_file = temp_dir / "double_sentinel" / "__init__.py"
    init_file.parent.mkdir(parents=True)

    # Two sentinels — invalid
    content = f"""from __future__ import annotations

{SENTINEL}
__all__ = ("A",)
def __dir__(): return list(__all__)

{SENTINEL}
__all__ = ("B",)
def __dir__(): return list(__all__)
"""
    init_file.write_text(content)
    errors = validate_init_file(init_file)
    assert any("Multiple sentinels" in e for e in errors)


def test_validate_sentinel_section_missing_all_in_managed(temp_dir):
    """Test _validate_sentinel_section catches missing __all__ after sentinel."""
    from exportify.export_manager.generator import _validate_sentinel_section

    # sentinel present but nothing that looks like __all__ appears after it
    content = f"# preamble\n\n{SENTINEL}\n# no declaration here\ndef __dir__(): return []\n"
    errors = _validate_sentinel_section(content)
    assert any("__all__ not in managed section" in e for e in errors)


# validate_init_file OSError branch (lines 508-509)


def test_validate_init_file_oserror(temp_dir, monkeypatch):
    """Test validate_init_file returns an error string when read raises OSError."""
    init_file = temp_dir / "unreadable" / "__init__.py"
    init_file.parent.mkdir(parents=True)
    init_file.write_text("__all__ = ()\ndef __dir__(): return []")

    # Monkeypatch Path.read_text to raise OSError
    original_read_text = Path.read_text

    def patched_read_text(self, *args, **kwargs):
        if self == init_file:
            raise OSError("Permission denied")
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", patched_read_text)

    errors = validate_init_file(init_file)
    assert len(errors) > 0
    assert "Permission denied" in errors[0]


def test_has_preserved_definition_function(generator: CodeGenerator):
    """Test _has_preserved_definition detects a function."""
    assert generator._has_preserved_definition("def my_func(): pass", "my_func")
    assert not generator._has_preserved_definition("def my_func(): pass", "other_func")

def test_has_preserved_definition_async_function(generator: CodeGenerator):
    """Test _has_preserved_definition detects an async function."""
    assert generator._has_preserved_definition("async def my_async_func(): pass", "my_async_func")

def test_has_preserved_definition_assign(generator: CodeGenerator):
    """Test _has_preserved_definition detects a variable assignment."""
    assert generator._has_preserved_definition("my_var = 1", "my_var")
    assert generator._has_preserved_definition("my_var = my_other_var = 1", "my_var")
    assert generator._has_preserved_definition("my_var = my_other_var = 1", "my_other_var")

def test_has_preserved_definition_ann_assign(generator: CodeGenerator):
    """Test _has_preserved_definition detects an annotated assignment."""
    assert generator._has_preserved_definition("my_var: int = 1", "my_var")
    assert not generator._has_preserved_definition("my_var: int = 1", "other_var")

def test_has_preserved_definition_syntax_error(generator: CodeGenerator):
    """Test _has_preserved_definition handles syntax errors gracefully."""
    # Invalid syntax will be suppressed, resulting in False
    assert not generator._has_preserved_definition("def my_func(:: pass", "my_func")

def test_has_preserved_definition_empty(generator: CodeGenerator):
    """Test _has_preserved_definition handles empty preserved sections."""
    assert not generator._has_preserved_definition("", "my_func")
