"""Unit tests for pages.jx4.helpers — path index, object_exists, find_child_text."""

from unittest.mock import MagicMock

from pages.jx4.helpers import (
    _build_path_index,
    object_exists,
    find_child_text,
    _get_children_names,
)

# ── Sample hierarchy trees ────────────────────────────────────────────

SIMPLE_TREE = {
    "name": "Canvas",
    "payload": {"text": ""},
    "children": [
        {
            "name": "Button_Play",
            "payload": {"text": "Play"},
            "children": [],
        },
        {
            "name": "Button_Quit",
            "payload": {"text": "Quit"},
            "children": [],
        },
    ],
}

DUPLICATE_LEAF_TREE = {
    "name": "Main",
    "payload": {"text": ""},
    "children": [
        {
            "name": "UIRoot",
            "payload": {"text": ""},
            "children": [
                {
                    "name": "RootCanvas",
                    "payload": {"text": ""},
                    "children": [
                        {
                            "name": "Secondary",
                            "payload": {"text": ""},
                            "children": [
                                {
                                    "name": "UILogin",
                                    "payload": {"text": ""},
                                    "children": [
                                        {
                                            "name": "Anniu",
                                            "payload": {"text": "Login"},
                                            "children": [],
                                        },
                                    ],
                                },
                                {
                                    "name": "UICreate",
                                    "payload": {"text": ""},
                                    "children": [
                                        {
                                            "name": "Anniu",
                                            "payload": {"text": "Create"},
                                            "children": [],
                                        },
                                    ],
                                },
                            ],
                        },
                    ],
                },
            ],
        },
    ],
}

TREE_WITH_CHILDREN = {
    "name": "Root",
    "payload": {"text": ""},
    "children": [
        {
            "name": "Parent",
            "payload": {"text": ""},
            "children": [
                {
                    "name": "Child1",
                    "payload": {"text": "Hello"},
                    "children": [],
                },
                {
                    "name": "Child2",
                    "payload": {"text": "World"},
                    "children": [],
                },
            ],
        },
    ],
}


# ── _build_path_index ─────────────────────────────────────────────────


def test_build_path_index_simple():
    index = _build_path_index(SIMPLE_TREE)
    assert "Canvas" in index
    assert "Canvas/Button_Play" in index
    assert "Canvas/Button_Quit" in index
    assert index["Canvas/Button_Play"]["payload"]["text"] == "Play"


def test_build_path_index_duplicate_leaf_names():
    index = _build_path_index(DUPLICATE_LEAF_TREE)
    # Two nodes named "Anniu" at different paths — both must appear
    path_login = "Main/UIRoot/RootCanvas/Secondary/UILogin/Anniu"
    path_create = "Main/UIRoot/RootCanvas/Secondary/UICreate/Anniu"
    assert path_login in index
    assert path_create in index
    assert index[path_login]["payload"]["text"] == "Login"
    assert index[path_create]["payload"]["text"] == "Create"


def test_build_path_index_counts_all_nodes():
    index = _build_path_index(DUPLICATE_LEAF_TREE)
    assert len(index) == 8  # Main, UIRoot, RootCanvas, Secondary, UILogin, UICreate, 2x Anniu


# ── object_exists ─────────────────────────────────────────────────────


def test_object_exists_true():
    auto = MagicMock()
    auto.dump_hierarchy.return_value = SIMPLE_TREE
    assert object_exists(auto, "Canvas/Button_Play") is True


def test_object_exists_with_leading_slash():
    auto = MagicMock()
    auto.dump_hierarchy.return_value = SIMPLE_TREE
    assert object_exists(auto, "/Canvas/Button_Play") is True


def test_object_exists_false():
    auto = MagicMock()
    auto.dump_hierarchy.return_value = SIMPLE_TREE
    assert object_exists(auto, "Canvas/NoSuchButton") is False


def test_object_exists_duplicate_leaf_picks_right_one():
    auto = MagicMock()
    auto.dump_hierarchy.return_value = DUPLICATE_LEAF_TREE
    assert object_exists(auto, "Main/UIRoot/RootCanvas/Secondary/UILogin/Anniu") is True
    assert object_exists(auto, "Main/UIRoot/RootCanvas/Secondary/UICreate/Anniu") is True
    assert object_exists(auto, "Anniu") is False  # leaf-only match no longer works


def test_object_exists_on_exception():
    auto = MagicMock()
    auto.dump_hierarchy.side_effect = RuntimeError("boom")
    assert object_exists(auto, "any/path") is False


# ── find_child_text ───────────────────────────────────────────────────


def test_find_child_text():
    auto = MagicMock()
    auto.dump_hierarchy.return_value = TREE_WITH_CHILDREN
    assert find_child_text(auto, "Root/Parent") == "Hello"


def test_find_child_text_with_leading_slash():
    auto = MagicMock()
    auto.dump_hierarchy.return_value = TREE_WITH_CHILDREN
    assert find_child_text(auto, "/Root/Parent") == "Hello"


def test_find_child_text_no_children():
    auto = MagicMock()
    auto.dump_hierarchy.return_value = SIMPLE_TREE
    assert find_child_text(auto, "Canvas/Button_Play") is None


def test_find_child_text_duplicate_parent():
    auto = MagicMock()
    auto.dump_hierarchy.return_value = DUPLICATE_LEAF_TREE
    text = find_child_text(auto, "Main/UIRoot/RootCanvas/Secondary/UILogin/Anniu")
    assert text is None  # leaf node has no children


# ── _get_children_names ───────────────────────────────────────────────


def test_get_children_names():
    auto = MagicMock()
    auto.dump_hierarchy.return_value = TREE_WITH_CHILDREN
    names = _get_children_names(auto, "Root/Parent")
    assert names == ["Child1", "Child2"]


def test_get_children_names_no_children():
    auto = MagicMock()
    auto.dump_hierarchy.return_value = SIMPLE_TREE
    names = _get_children_names(auto, "Canvas/Button_Play")
    assert names == []


def test_get_children_names_not_found():
    auto = MagicMock()
    auto.dump_hierarchy.return_value = SIMPLE_TREE
    names = _get_children_names(auto, "NoSuch/Path")
    assert names == []


# ── ClickablePanel name-keyword pre-filter ──────────────────────────


def test_clickable_name_keywords():
    from autotest_ide.ui.clickable_panel import _CLICKABLE_NAME_KEYWORDS
    for kw in ("Btn", "Anniu", "Button", "Toggle", "btn"):
        assert any(kw in name for name in (
            f"{kw}_Close", f"Login{kw}", f"{kw}01", f"Anniu_Fanhui"
        ))


def test_attrs_has_button():
    from autotest_ide.ui.clickable_panel import _attrs_has_button
    attrs = {"components": [{"type": "UnityEngine.UI.Button"}]}
    assert _attrs_has_button(attrs) is True
    attrs_empty = {"components": []}
    assert _attrs_has_button(attrs_empty) is False
    attrs_none = {}
    assert _attrs_has_button(attrs_none) is False
