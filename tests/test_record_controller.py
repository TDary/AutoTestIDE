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


def test_code_generated_on_inspect_result():
    rc = RecordController()
    emitted = []
    rc.code_generated.connect(lambda code: emitted.append(code))
    rc.start([
        {"name": "root", "type": "", "node_id": "0", "children": [
            {"name": "Play", "type": "Button", "node_id": "1", "children": []},
        ]},
    ])
    node = {"name": "Play", "type": "Button", "payload": {}, "node_id": "1"}
    rc.on_inspect_result(node, 100, 200)
    assert len(emitted) == 1
    assert "auto.find_and_tap('Play')" in emitted[0]


def test_code_not_generated_when_not_recording():
    rc = RecordController()
    emitted = []
    rc.code_generated.connect(lambda code: emitted.append(code))
    node = {"name": "Play", "type": "Button", "payload": {}, "node_id": "1"}
    rc.on_inspect_result(node, 100, 200)
    assert len(emitted) == 0


def test_fallback_click_on_inspect_failed():
    rc = RecordController()
    emitted = []
    rc.code_generated.connect(lambda code: emitted.append(code))
    rc.start([])
    rc.on_inspect_failed(300, 400)
    assert len(emitted) == 1
    assert "auto.click(300, 400)" in emitted[0]


def test_no_fallback_when_not_recording():
    rc = RecordController()
    emitted = []
    rc.code_generated.connect(lambda code: emitted.append(code))
    rc.on_inspect_failed(300, 400)
    assert len(emitted) == 0
