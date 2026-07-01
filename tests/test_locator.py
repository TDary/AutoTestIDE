import pytest

from autotest_ide.core.locator import generate_locator


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
