import time
import ast
import tempfile
from pathlib import Path
from exportify.validator.validator import LateImportValidator

sample_content = """
from typing import TYPE_CHECKING
import os
import sys

if TYPE_CHECKING:
    from typing import Any, Callable

def sample_function(x: int) -> int:
    return x * 2

class SampleClass:
    def __init__(self, value: int):
        self.value = value

    def do_something(self) -> None:
        pass

__all__ = ["sample_function", "SampleClass"]

""" * 1000

with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
    f.write(sample_content)
    file_path = Path(f.name)

try:
    validator = LateImportValidator()

    # Original
    start_time = time.time()
    for _ in range(5):
        validator.validate_file(file_path)
    duration_orig = time.time() - start_time

    # Let's monkey patch it for the optimized version
    original_validate_all_declaration = LateImportValidator._validate_all_declaration

    def optimized_validate_all_declaration(self, file_path, node, tree):
        from exportify.common.types import ValidationError, ValidationWarning
        import contextlib
        issues = []

        if not isinstance(node.value, ast.List):
            return issues

        # Get all names in __all__
        all_names = []
        all_names.extend(
            elt.value
            for elt in node.value.elts
            if isinstance(elt, ast.Constant) and isinstance(elt.value, str)
        )
        # Use provided tree to find defined names
        with contextlib.suppress(Exception):
            # Collect defined names
            defined_names = set()
            for node_item in ast.walk(tree):
                if isinstance(node_item, (ast.FunctionDef, ast.ClassDef)):
                    defined_names.add(node_item.name)
                elif isinstance(node_item, ast.Assign):
                    for target in node_item.targets:
                        if isinstance(target, ast.Name):
                            defined_names.add(target.id)

            # Check for undefined names in __all__
            issues.extend(
                ValidationError(
                    file=file_path,
                    line=node.lineno,
                    message=f"Name '{name}' in __all__ is not defined in module",
                    suggestion=f"Define '{name}' or remove from __all__",
                    code="UNDEFINED_IN_ALL",
                )
                for name in all_names
                if name not in defined_names and name != "__all__"
            )
        return issues

    LateImportValidator._validate_all_declaration = optimized_validate_all_declaration

    start_time = time.time()
    for _ in range(5):
        validator.validate_file(file_path)
    duration_opt = time.time() - start_time

    print(f"Original: {duration_orig:.4f}s")
    print(f"Optimized: {duration_opt:.4f}s")
    print(f"Speedup: {duration_orig/duration_opt:.2f}x")

finally:
    file_path.unlink()
