import ast
import contextlib

from pathlib import Path

from exportify.common.types import ExportManifest, LazyExport
from exportify.export_manager.generator import CodeGenerator


def get_preserved_runtime_imports(
    preserved_section: str, package_path: str
) -> set[tuple[str, str]]:
    if not preserved_section:
        return set()
    found: set[tuple[str, str]] = set()
    with contextlib.suppress(SyntaxError, Exception):
        tree = ast.parse(preserved_section)
        for node in tree.body:
            if not isinstance(node, (ast.Import, ast.ImportFrom)):
                continue
            for alias in node.names:
                if isinstance(node, ast.ImportFrom):
                    module = node.module or ""
                    if node.level > 0:
                        parts = package_path.split(".")
                        if node.level == 1:
                            resolved_module = package_path
                        else:
                            base_parts = parts[: -(node.level - 1)]
                            resolved_module = ".".join(base_parts)
                        if module:
                            resolved_module = f"{resolved_module}.{module}"
                    else:
                        resolved_module = module
                    accessible = alias.asname or alias.name
                    found.add((resolved_module, accessible))
                elif isinstance(node, ast.Import):
                    accessible = alias.asname or alias.name
                    found.add((alias.name, accessible))
    return found


def test_userspace_inclusion_in_all() -> None:
    generator = CodeGenerator(output_dir=Path("/tmp"))
    package_path = "mypkg"

    existing_content = """
from types import MappingProxyType
from typing import Annotated

from .my_submodule import MyClass

type MyType = Annotated[MyClass, "This is an annotated type"]
type MyMapping = MappingProxyType[str, int]

# === MANAGED EXPORTS ===
# Managed content
"""
    manual_section = existing_content.split("# === MANAGED EXPORTS ===")[0].strip()
    runtime_imports = get_preserved_runtime_imports(manual_section, package_path)
    print(f"DEBUG: Runtime imports for {package_path}: {runtime_imports}")

    tmp_path = Path("/tmp/mypkg/__init__.py")
    tmp_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path.write_text(existing_content)

    exports = [
        LazyExport(
            public_name="MyClass",
            target_module="mypkg.my_submodule",
            target_object="MyClass",
            is_type_only=False,
        ),
        LazyExport(
            public_name="MyType", target_module="mypkg", target_object="MyType", is_type_only=False
        ),
        LazyExport(
            public_name="MyMapping",
            target_module="mypkg",
            target_object="MyMapping",
            is_type_only=False,
        ),
        LazyExport(
            public_name="OtherPropagated",
            target_module="mypkg.other",
            target_object="OtherPropagated",
            is_type_only=False,
        ),
    ]

    manifest = ExportManifest(
        module_path="mypkg",
        own_exports=[e for e in exports if e.target_module == "mypkg"],
        propagated_exports=[e for e in exports if e.target_module != "mypkg"],
        all_exports=exports,
    )

    code = generator.generate(manifest)
    print("\nGenerated code content:")
    print(code.content)

    assert '"MyClass",' in code.content
    assert '"MyType",' in code.content
    assert '"MyMapping",' in code.content
    assert '"OtherPropagated",' in code.content
    assert '"OtherPropagated":' in code.content
    assert '"MyClass":' not in code.content
    assert '"MyType":' not in code.content
    assert '"MyMapping":' not in code.content

    assert "from types import MappingProxyType" not in code.managed_section

    if tmp_path.exists():
        tmp_path.unlink()


if __name__ == "__main__":
    test_userspace_inclusion_in_all()
