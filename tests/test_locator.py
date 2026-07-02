import pytest

from autotest_ide.core.locator import generate_locator, generate_locator_code


def test_name_unique():
    node = {"name": "Button_Play", "type": "Button", "payload": {"text": ""}}
    assert generate_locator(node, all_nodes=[node]) == "poco('Button_Play')"


def test_name_not_unique_uses_type():
    node = {"name": "Btn", "type": "Button", "payload": {"text": ""}}
    other = {"name": "Btn", "type": "Label", "payload": {"text": ""}}
    assert generate_locator(node, all_nodes=[node, other]) == "poco(name='Btn', type='Button')"


def test_name_empty_uses_text_and_type():
    node = {"name": "", "type": "Button", "payload": {"text": "Play"}}
    assert generate_locator(node) == "poco(text='Play', type='Button')"


def test_name_and_text_empty_uses_type():
    node = {"name": "", "type": "Button", "payload": {"text": ""}}
    assert generate_locator(node) == "poco(type='Button')"


def test_all_empty_uses_node_id():
    node = {"node_id": "btn_play", "name": "", "type": "", "payload": {"text": ""}}
    assert generate_locator(node) == "poco(node_id='btn_play')"


def test_name_unique_without_all_nodes():
    node = {"name": "Button_Play", "type": "Button", "payload": {"text": ""}}
    assert generate_locator(node) == "poco('Button_Play')"


def test_name_with_quotes_escaped():
    node = {"name": 'My "Button"', "type": "Button", "payload": {"text": ""}}
    assert generate_locator(node) == """poco('My "Button"')"""


def test_text_with_quotes_escaped():
    node = {"name": "", "type": "Button", "payload": {"text": "He said 'hi'"}}
    assert generate_locator(node) == """poco(text="He said 'hi'", type='Button')"""


# --- generate_locator_code tests ---


def test_locator_code_with_path():
    node = {"name": "Play", "type": "Button", "payload": {}, "node_id": "3"}
    all_nodes = [
        {"name": "root", "type": "", "payload": {}, "node_id": "0", "children": [
            {"name": "Panel", "type": "Panel", "payload": {}, "node_id": "1", "children": [
                {"name": "Play", "type": "Button", "payload": {}, "node_id": "3"},
            ]},
        ]},
    ]
    assert generate_locator_code(node, all_nodes) == "auto.find_and_tap('Panel/Play')\n"


def test_locator_code_root_named_root():
    node = {"name": "Play", "type": "Button", "payload": {}, "node_id": "3"}
    all_nodes = [
        {"name": "root", "type": "", "payload": {}, "node_id": "0", "children": [
            {"name": "Play", "type": "Button", "payload": {}, "node_id": "3"},
        ]},
    ]
    assert generate_locator_code(node, all_nodes) == "auto.find_and_tap('Play')\n"


def test_locator_code_fallback_click():
    node = {"name": "", "type": "", "payload": {"pos": [100, 200]}, "node_id": "3"}
    assert generate_locator_code(node, []) == "auto.click(100, 200)\n"


def test_locator_code_no_position_no_path():
    node = {"name": "", "type": "", "payload": {}, "node_id": "3"}
    assert generate_locator_code(node, []) == ""


def test_locator_code_empty_all_nodes():
    node = {"name": "Play", "type": "Button", "payload": {"pos": [50, 60]}, "node_id": "3"}
    assert generate_locator_code(node, []) == "auto.click(50, 60)\n"
