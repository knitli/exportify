# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Tests for module_all.py."""

from exportify.export_manager.module_all import _render_all, _export_sort_key


def test_render_all_empty():
    assert _render_all([], "list") == "__all__ = []"
    assert _render_all([], "tuple") == "__all__ = ()"


def test_render_all_single_item():
    assert _render_all(["MyClass"], "list") == '__all__ = ["MyClass"]'
    assert _render_all(["MyClass"], "tuple") == '__all__ = ("MyClass",)'


def test_render_all_multiple_items():
    expected_list = '__all__ = [\n    "A",\n    "B",\n]'
    assert _render_all(["A", "B"], "list") == expected_list

    expected_tuple = '__all__ = (\n    "A",\n    "B",\n)'
    assert _render_all(["A", "B"], "tuple") == expected_tuple


def test_export_sort_key_constant():
    """SCREAMING_SNAKE constants should be grouped as 0."""
    assert _export_sort_key("CONSTANT_VALUE") == (0, "constant_value")
    assert _export_sort_key("SCREAMING_SNAKE") == (0, "screaming_snake")


def test_export_sort_key_grouping_uppercase():
    """Missing edge case: Grouping uppercase names (0).

    A single-word all-caps string should also be treated as a constant (group 0).
    """
    assert _export_sort_key("ABC") == (0, "abc")
    assert _export_sort_key("A") == (0, "a")
    assert _export_sort_key("SINGLEWORDUPPERCASE") == (0, "singleworduppercase")


def test_export_sort_key_pascal():
    """PascalCase classes should be grouped as 1."""
    assert _export_sort_key("PascalCase") == (1, "pascalcase")
    assert _export_sort_key("MyClass") == (1, "myclass")


def test_export_sort_key_snake():
    """snake_case functions should be grouped as 2."""
    assert _export_sort_key("snake_case") == (2, "snake_case")
    assert _export_sort_key("my_function") == (2, "my_function")
    assert _export_sort_key("abc") == (2, "abc")
