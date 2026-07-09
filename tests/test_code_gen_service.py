from autotest_ide.core.code_gen import OpMode
from autotest_ide.ui.code_gen_service import CodeGenService


def _make_tree(node_name="Play", node_id="1"):
    """Build a minimal tree with one child under root."""
    return [
        {"name": "root", "type": "", "payload": {}, "node_id": "0", "children": [
            {"name": node_name, "type": "Button", "payload": {}, "node_id": node_id, "children": []},
        ]},
    ]


def test_default_not_recording():
    svc = CodeGenService()
    assert not svc.is_recording


def test_start_recording():
    svc = CodeGenService()
    svc.start_recording()
    assert svc.is_recording


def test_stop_recording():
    svc = CodeGenService()
    svc.start_recording()
    svc.stop_recording()
    assert not svc.is_recording


def test_inspect_result_click_non_recording():
    """Non-recording mode: only the operation code is emitted, no assert."""
    svc = CodeGenService()
    emitted = []
    svc.code_insert_requested.connect(lambda code: emitted.append(code))

    flat = _make_tree()
    node = {"name": "Play", "type": "Button", "payload": {}, "node_id": "1"}
    svc.on_inspect_result(node, flat, 100, 200, OpMode.CLICK)

    assert len(emitted) == 1
    assert "auto.find_and_tap('Play')" in emitted[0]


def test_inspect_result_click_recording():
    """Recording mode: assert_exists emitted before the click."""
    svc = CodeGenService()
    emitted = []
    svc.code_insert_requested.connect(lambda code: emitted.append(code))

    flat = _make_tree()
    node = {"name": "Play", "type": "Button", "payload": {}, "node_id": "1"}
    svc.start_recording()
    svc.on_inspect_result(node, flat, 100, 200, OpMode.CLICK)

    assert len(emitted) == 2
    assert "assert_exists" in emitted[0]
    assert "auto.find_and_tap" in emitted[1]


def test_inspect_result_long_press_recording():
    svc = CodeGenService()
    emitted = []
    svc.code_insert_requested.connect(lambda code: emitted.append(code))

    flat = _make_tree("Hold", "5")
    node = {"name": "Hold", "type": "Button", "payload": {}, "node_id": "5"}
    svc.start_recording()
    svc.on_inspect_result(node, flat, 100, 200, OpMode.LONG_PRESS)

    assert len(emitted) == 2
    assert "assert_exists" in emitted[0]
    assert "auto.long_click" in emitted[1]


def test_inspect_result_long_press_non_recording():
    svc = CodeGenService()
    emitted = []
    svc.code_insert_requested.connect(lambda code: emitted.append(code))

    flat = _make_tree("Hold", "5")
    node = {"name": "Hold", "type": "Button", "payload": {}, "node_id": "5"}
    svc.on_inspect_result(node, flat, 100, 200, OpMode.LONG_PRESS)

    assert len(emitted) == 1
    assert "auto.long_click" in emitted[0]


def test_inspect_result_input_recording():
    svc = CodeGenService()
    emitted = []
    svc.code_insert_requested.connect(lambda code: emitted.append(code))

    flat = _make_tree("Field", "7")
    node = {"name": "Field", "type": "InputField", "payload": {}, "node_id": "7"}
    svc.start_recording()
    svc.on_inspect_result(node, flat, 50, 60, OpMode.INPUT, text="hello")

    assert len(emitted) == 2
    assert "assert_exists" in emitted[0]
    assert "auto.set_text('Field', 'hello')" in emitted[1]


def test_inspect_result_input_non_recording():
    svc = CodeGenService()
    emitted = []
    svc.code_insert_requested.connect(lambda code: emitted.append(code))

    flat = _make_tree("Field", "7")
    node = {"name": "Field", "type": "InputField", "payload": {}, "node_id": "7"}
    svc.on_inspect_result(node, flat, 50, 60, OpMode.INPUT, text="hello")

    assert len(emitted) == 1
    assert "auto.set_text('Field', 'hello')" in emitted[0]


def test_inspect_failed_click():
    svc = CodeGenService()
    emitted = []
    svc.code_insert_requested.connect(lambda code: emitted.append(code))
    svc.on_inspect_failed(300, 400, OpMode.CLICK)

    assert len(emitted) == 1
    assert "auto.click(300, 400)" in emitted[0]


def test_inspect_failed_long_press():
    svc = CodeGenService()
    emitted = []
    svc.code_insert_requested.connect(lambda code: emitted.append(code))
    svc.on_inspect_failed(100, 200, OpMode.LONG_PRESS)

    assert len(emitted) == 1
    assert "auto.long_click(100, 200)" in emitted[0]


def test_inspect_failed_input():
    svc = CodeGenService()
    emitted = []
    svc.code_insert_requested.connect(lambda code: emitted.append(code))
    svc.on_inspect_failed(50, 60, OpMode.INPUT, text="hello")

    assert len(emitted) == 1
    assert "auto.click(50, 60)" in emitted[0]
    assert "fallback" in emitted[0]


def test_inspect_failed_always_emits_even_non_recording():
    """on_inspect_failed emits regardless of recording state."""
    svc = CodeGenService()
    emitted = []
    svc.code_insert_requested.connect(lambda code: emitted.append(code))
    # Not recording
    assert not svc.is_recording
    svc.on_inspect_failed(10, 20, OpMode.CLICK)
    assert len(emitted) == 1


def test_swipe_done():
    svc = CodeGenService()
    emitted = []
    svc.code_insert_requested.connect(lambda code: emitted.append(code))
    svc.on_swipe_done(100, 200, 300, 400)

    assert len(emitted) == 1
    assert "auto.swipe(100, 200, 300, 400)" in emitted[0]


def test_swipe_done_always_emits_even_non_recording():
    svc = CodeGenService()
    emitted = []
    svc.code_insert_requested.connect(lambda code: emitted.append(code))
    assert not svc.is_recording
    svc.on_swipe_done(100, 200, 300, 400)
    assert len(emitted) == 1


def test_inspect_result_no_code_no_emit():
    """If gen_* returns empty string, nothing is emitted."""
    svc = CodeGenService()
    emitted = []
    svc.code_insert_requested.connect(lambda code: emitted.append(code))
    # Node with no path and no pos => gen_click returns ""
    node = {"name": "", "type": "", "payload": {}, "node_id": ""}
    svc.on_inspect_result(node, [], 0, 0, OpMode.CLICK)
    assert len(emitted) == 0
