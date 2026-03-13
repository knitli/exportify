# SPDX-FileCopyrightText: 2026 Knitli Inc.
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Tests for module_all.py."""

from exportify.export_manager.module_all import _export_sort_key


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
