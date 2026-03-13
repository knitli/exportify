from exportify.export_manager.module_all import _render_all

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
