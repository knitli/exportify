# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""This module provides the main command classes for the Exportify CLI."""

from __future__ import annotations

from types import MappingProxyType

# === MANAGED EXPORTS ===
# Exportify manages this section. It contains lazy-loading infrastructure
# for the package: imports and runtime declarations (__all__, __getattr__,
# __dir__). Manual edits will be overwritten by `exportify fix`.
from typing import TYPE_CHECKING

from lateimport import create_late_getattr


if TYPE_CHECKING:
    from exportify.commands.cache import CacheCommand
    from exportify.commands.check import CheckCommand
    from exportify.commands.doctor import DoctorCommand
    from exportify.commands.init import InitCommand
    from exportify.commands.sync import SyncCommand
    from exportify.commands.undo import UndoCommand
    from exportify.commands.utils import (
        CONSOLE,
        DEFAULT_CONFIG_PATH,
        collect_py_files,
        get_all_source_roots,
        load_config_and_rules,
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
        resolve_checks,
    )

_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({
    "CONSOLE": (__spec__.parent, "utils"),
    "DEFAULT_CONFIG_PATH": (__spec__.parent, "utils"),
    "CacheCommand": (__spec__.parent, "cache"),
    "CheckCommand": (__spec__.parent, "check"),
    "DoctorCommand": (__spec__.parent, "doctor"),
    "InitCommand": (__spec__.parent, "init"),
    "SyncCommand": (__spec__.parent, "sync"),
    "UndoCommand": (__spec__.parent, "undo"),
    "collect_py_files": (__spec__.parent, "utils"),
    "get_all_source_roots": (__spec__.parent, "utils"),
    "load_config_and_rules": (__spec__.parent, "utils"),
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
    "resolve_checks": (__spec__.parent, "utils"),
})

__getattr__ = create_late_getattr(_dynamic_imports, globals(), __name__)

__all__ = (
    "CONSOLE",
    "DEFAULT_CONFIG_PATH",
    "CacheCommand",
    "CheckCommand",
    "DoctorCommand",
    "InitCommand",
    "SyncCommand",
    "UndoCommand",
    "collect_py_files",
    "get_all_source_roots",
    "load_config_and_rules",
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
    "resolve_checks",
)


def __dir__() -> list[str]:
    """List available attributes for the package."""
    return list(__all__)
