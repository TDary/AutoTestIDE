from autotest_ide.core.code_gen import OpMode, gen_click, gen_assert_exists


def test_opmode_values():
    assert OpMode.CLICK.value == "click"
    assert OpMode.LONG_PRESS.value == "long_click"
    assert OpMode.SWIPE.value == "swipe"
    assert OpMode.INPUT.value == "set_text"


def test_gen_click_with_path():
    node = {"name": "Play", "type": "Button", "payload": {}, "node_id": "3"}
    flat = [
        {"name": "root", "type": "", "payload": {}, "node_id": "0", "children": [
            {"name": "Play", "type": "Button", "payload": {}, "node_id": "3"},
        ]},
    ]
    assert gen_click(node, flat, 100, 200) == "auto.find_and_tap('Play')\n"


def test_gen_click_with_nested_path():
    node = {"name": "Play", "type": "Button", "payload": {}, "node_id": "3"}
    flat = [
        {"name": "root", "type": "", "payload": {}, "node_id": "0", "children": [
            {"name": "Panel", "type": "Panel", "payload": {}, "node_id": "1", "children": [
                {"name": "Play", "type": "Button", "payload": {}, "node_id": "3"},
            ]},
        ]},
    ]
    assert gen_click(node, flat, 100, 200) == "auto.find_and_tap('Panel/Play')\n"


def test_gen_click_fallback_coordinate():
    node = {"name": "Play", "type": "Button", "payload": {"pos": [100, 200]}, "node_id": "3"}
    assert gen_click(node, [], 100, 200) == "auto.click(100, 200)\n"


def test_gen_click_empty_all_nodes():
    node = {"name": "Play", "type": "Button", "payload": {"pos": [50, 60]}, "node_id": "3"}
    assert gen_click(node, [], 50, 60) == "auto.click(50, 60)\n"


def test_gen_click_no_path_no_pos():
    node = {"name": "", "type": "", "payload": {}, "node_id": "3"}
    assert gen_click(node, [], 0, 0) == ""


def test_gen_click_with_jx4_path():
    node = {"name": "BtnStart", "type": "GameObject", "payload": {"path": "Denglu/BtnStart"}, "node_id": "Denglu/BtnStart"}
    assert gen_click(node, [], 100, 200) == "auto.find_and_tap('Denglu/BtnStart')\n"


def test_gen_assert_exists_with_path():
    node = {"name": "Play", "type": "Button", "payload": {}, "node_id": "3"}
    flat = [
        {"name": "root", "type": "", "payload": {}, "node_id": "0", "children": [
            {"name": "Play", "type": "Button", "payload": {}, "node_id": "3"},
        ]},
    ]
    assert gen_assert_exists(node, flat) == "assert_exists('Play')\n"


def test_gen_assert_exists_nested():
    node = {"name": "Play", "type": "Button", "payload": {}, "node_id": "3"}
    flat = [
        {"name": "root", "type": "", "payload": {}, "node_id": "0", "children": [
            {"name": "Panel", "type": "Panel", "payload": {}, "node_id": "1", "children": [
                {"name": "Play", "type": "Button", "payload": {}, "node_id": "3"},
            ]},
        ]},
    ]
    assert gen_assert_exists(node, flat) == "assert_exists('Panel/Play')\n"


def test_gen_assert_exists_with_jx4_path():
    node = {"name": "BtnStart", "type": "GameObject", "payload": {"path": "Denglu/BtnStart"}, "node_id": "Denglu/BtnStart"}
    assert gen_assert_exists(node, []) == "assert_exists('Denglu/BtnStart')\n"


def test_gen_assert_exists_no_path_returns_empty():
    node = {"name": "", "type": "", "payload": {}, "node_id": "3"}
    assert gen_assert_exists(node, []) == ""
