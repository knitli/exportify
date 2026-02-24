# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""This module provides the main command classes for the Exportify CLI."""

from __future__ import annotations

# === MANAGED EXPORTS ===

# Exportify manages this section. It contains lazy-loading infrastructure
# for the package: imports and runtime declarations (__all__, __getattr__,
# __dir__). Manual edits will be overwritten by `exportify fix`.

from typing import TYPE_CHECKING
from types import MappingProxyType

from lateimport import create_late_getattr

if TYPE_CHECKING:
    from exportify.commands.check import CheckCommand
    from exportify.commands.clear_cache import ClearCacheCommand
    from exportify.commands.doctor import DoctorCommand
    from exportify.commands.fix import FixCommand
    from exportify.commands.generate import GenerateCommand
    from exportify.commands.init import InitCommand
    from exportify.commands.status import StatusCommand
    from exportify.commands.undo import UndoCommand
    from exportify.commands.utils import (
        CONSOLE,
        DEFAULT_CONFIG_PATH,
        collect_py_files,
        load_rules,
        path_to_module,
        print_error,
        print_info,
        print_output_validation_concise,
        print_output_validation_json,
        print_output_validation_verbose,
        print_success,
        print_validation_results,
        print_warning,
    )

_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({
    "CONSOLE": (__spec__.parent, "utils"),
    "DEFAULT_CONFIG_PATH": (__spec__.parent, "utils"),
    "CheckCommand": (__spec__.parent, "check"),
    "ClearCacheCommand": (__spec__.parent, "clear_cache"),
    "DoctorCommand": (__spec__.parent, "doctor"),
    "FixCommand": (__spec__.parent, "fix"),
    "GenerateCommand": (__spec__.parent, "generate"),
    "InitCommand": (__spec__.parent, "init"),
    "StatusCommand": (__spec__.parent, "status"),
    "UndoCommand": (__spec__.parent, "undo"),
    "collect_py_files": (__spec__.parent, "utils"),
    "load_rules": (__spec__.parent, "utils"),
    "path_to_module": (__spec__.parent, "utils"),
    "print_error": (__spec__.parent, "utils"),
    "print_info": (__spec__.parent, "utils"),
    "print_output_validation_concise": (__spec__.parent, "utils"),
    "print_output_validation_json": (__spec__.parent, "utils"),
    "print_output_validation_verbose": (__spec__.parent, "utils"),
    "print_success": (__spec__.parent, "utils"),
    "print_validation_results": (__spec__.parent, "utils"),
    "print_warning": (__spec__.parent, "utils"),
})

__getattr__ = create_late_getattr(_dynamic_imports, globals(), __name__)

__all__ = (
    "CONSOLE",
    "DEFAULT_CONFIG_PATH",
    "CheckCommand",
    "ClearCacheCommand",
    "DoctorCommand",
    "FixCommand",
    "GenerateCommand",
    "InitCommand",
    "StatusCommand",
    "UndoCommand",
    "collect_py_files",
    "load_rules",
    "path_to_module",
    "print_error",
    "print_info",
    "print_output_validation_concise",
    "print_output_validation_json",
    "print_output_validation_verbose",
    "print_success",
    "print_validation_results",
    "print_warning",
)


def __dir__() -> list[str]:
    """List available attributes for the package."""
    return list(__all__)
