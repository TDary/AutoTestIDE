from autotest_ide.core.code_gen import (
    OpMode, gen_click, gen_assert_exists,
    gen_long_click, gen_swipe, gen_input,
    gen_wait_for, gen_wait_for_gone,
)


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


def test_gen_long_click_with_path():
    node = {"name": "Hold", "type": "Button", "payload": {}, "node_id": "5"}
    flat = [
        {"name": "root", "type": "", "payload": {}, "node_id": "0", "children": [
            {"name": "Hold", "type": "Button", "payload": {}, "node_id": "5"},
        ]},
    ]
    assert gen_long_click(node, flat, 100, 200) == "auto.long_click(100, 200, duration=2.0)\n"

def test_gen_long_click_custom_duration():
    node = {"name": "Hold", "type": "Button", "payload": {}, "node_id": "5"}
    flat = []
    assert gen_long_click(node, flat, 100, 200, duration=3.0) == "auto.long_click(100, 200, duration=3.0)\n"

def test_gen_swipe():
    assert gen_swipe(100, 200, 300, 400) == "auto.swipe(100, 200, 300, 400)\n"

def test_gen_swipe_custom_duration():
    assert gen_swipe(100, 200, 300, 400, duration=1.0) == "auto.swipe(100, 200, 300, 400, duration=1.0)\n"

def test_gen_input_with_path():
    node = {"name": "Input", "type": "InputField", "payload": {}, "node_id": "7"}
    flat = [
        {"name": "root", "type": "", "payload": {}, "node_id": "0", "children": [
            {"name": "Input", "type": "InputField", "payload": {}, "node_id": "7"},
        ]},
    ]
    assert gen_input(node, flat, 100, 200, "hello") == "auto.set_text('Input', 'hello')\n"

def test_gen_input_nested_path():
    node = {"name": "Field", "type": "InputField", "payload": {}, "node_id": "7"}
    flat = [
        {"name": "root", "type": "", "payload": {}, "node_id": "0", "children": [
            {"name": "Form", "type": "Panel", "payload": {}, "node_id": "1", "children": [
                {"name": "Field", "type": "InputField", "payload": {}, "node_id": "7"},
            ]},
        ]},
    ]
    assert gen_input(node, flat, 50, 60, "world") == "auto.set_text('Form/Field', 'world')\n"

def test_gen_input_fallback():
    node = {"name": "", "type": "", "payload": {"pos": [50, 60]}, "node_id": "7"}
    assert gen_input(node, [], 50, 60, "text") == "auto.click(50, 60)  # set_text fallback\n"

def test_gen_input_with_jx4_path():
    node = {"name": "Field", "type": "GameObject", "payload": {"path": "Login/Field"}, "node_id": "Login/Field"}
    assert gen_input(node, [], 100, 200, "hello") == "auto.set_text('Login/Field', 'hello')\n"

def test_gen_wait_for():
    assert gen_wait_for("Panel/BtnStart", timeout=10) == "wait_for('Panel/BtnStart', timeout=10)\n"

def test_gen_wait_for_custom_timeout():
    assert gen_wait_for("Btn", timeout=30) == "wait_for('Btn', timeout=30)\n"

def test_gen_wait_for_gone():
    assert gen_wait_for_gone("Panel/Loading", timeout=15) == "wait_for_gone('Panel/Loading', timeout=15)\n"
