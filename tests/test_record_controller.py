from autotest_ide.core.code_gen import OpMode
from autotest_ide.ui.record_controller import RecordController


def test_initial_state_not_recording():
    rc = RecordController()
    assert not rc.is_recording


def test_start_sets_recording():
    rc = RecordController()
    rc.start([])
    assert rc.is_recording


def test_stop_clears_recording():
    rc = RecordController()
    rc.start([])
    rc.stop()
    assert not rc.is_recording


def test_code_not_generated_when_not_recording():
    rc = RecordController()
    emitted = []
    rc.code_generated.connect(lambda code: emitted.append(code))
    node = {"name": "Play", "type": "Button", "payload": {}, "node_id": "1"}
    rc.on_inspect_result(node, 100, 200, OpMode.CLICK)
    assert len(emitted) == 0


def test_record_click_emits_find_and_tap():
    rc = RecordController()
    emitted = []
    rc.code_generated.connect(lambda code: emitted.append(code))
    rc.start([
        {"name": "root", "type": "", "payload": {}, "node_id": "0", "children": [
            {"name": "Play", "type": "Button", "payload": {}, "node_id": "1", "children": []},
        ]},
    ])
    node = {"name": "Play", "type": "Button", "payload": {}, "node_id": "1"}
    rc.on_inspect_result(node, 100, 200, OpMode.CLICK)
    assert any("auto.find_and_tap('Play')" in code for code in emitted)


def test_record_click_with_assert():
    rc = RecordController()
    emitted = []
    rc.code_generated.connect(lambda code: emitted.append(code))
    rc.start([
        {"name": "root", "type": "", "payload": {}, "node_id": "0", "children": [
            {"name": "Play", "type": "Button", "payload": {}, "node_id": "1", "children": []},
        ]},
    ])
    node = {"name": "Play", "type": "Button", "payload": {}, "node_id": "1"}
    rc.on_inspect_result(node, 100, 200, OpMode.CLICK)
    # Should emit both assert and click
    assert len(emitted) == 2
    assert "assert_exists" in emitted[0]
    assert "auto.find_and_tap" in emitted[1]


def test_record_click_fallback_no_assert():
    rc = RecordController()
    emitted = []
    rc.code_generated.connect(lambda code: emitted.append(code))
    rc.start([])
    rc.on_inspect_failed(300, 400, OpMode.CLICK)
    assert len(emitted) == 1
    assert "auto.click(300, 400)" in emitted[0]
    assert "assert" not in emitted[0]


def test_record_long_press_emits_long_click():
    rc = RecordController()
    emitted = []
    rc.code_generated.connect(lambda code: emitted.append(code))
    rc.start([])
    rc.on_inspect_failed(100, 200, OpMode.LONG_PRESS)
    assert len(emitted) == 1
    assert "auto.long_click(100, 200)" in emitted[0]


def test_record_long_press_with_assert():
    rc = RecordController()
    emitted = []
    rc.code_generated.connect(lambda code: emitted.append(code))
    rc.start([
        {"name": "root", "type": "", "payload": {}, "node_id": "0", "children": [
            {"name": "Hold", "type": "Button", "payload": {}, "node_id": "5", "children": []},
        ]},
    ])
    node = {"name": "Hold", "type": "Button", "payload": {}, "node_id": "5"}
    rc.on_inspect_result(node, 100, 200, OpMode.LONG_PRESS)
    assert len(emitted) == 2
    assert "assert_exists" in emitted[0]
    assert "auto.long_click" in emitted[1]


def test_record_swipe_emits_swipe():
    rc = RecordController()
    emitted = []
    rc.code_generated.connect(lambda code: emitted.append(code))
    rc.start([])
    rc.on_swipe_done(100, 200, 300, 400)
    assert len(emitted) == 1
    assert "auto.swipe(100, 200, 300, 400)" in emitted[0]


def test_record_input_emits_set_text():
    rc = RecordController()
    emitted = []
    rc.code_generated.connect(lambda code: emitted.append(code))
    rc.start([
        {"name": "root", "type": "", "payload": {}, "node_id": "0", "children": [
            {"name": "Field", "type": "InputField", "payload": {}, "node_id": "7", "children": []},
        ]},
    ])
    node = {"name": "Field", "type": "InputField", "payload": {}, "node_id": "7"}
    rc.on_inspect_result(node, 50, 60, OpMode.INPUT, text="hello")
    assert len(emitted) == 2
    assert "assert_exists" in emitted[0]
    assert "auto.set_text('Field', 'hello')" in emitted[1]


def test_record_input_fallback_no_assert():
    rc = RecordController()
    emitted = []
    rc.code_generated.connect(lambda code: emitted.append(code))
    rc.start([])
    rc.on_inspect_failed(50, 60, OpMode.INPUT, text="hello")
    assert len(emitted) == 1
    assert "auto.click(50, 60)" in emitted[0]
