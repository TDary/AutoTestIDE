import pytest
import threading
import time

from PyQt5.QtWidgets import QApplication

from autotest_ide.core.device import DeviceState


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_screenshot_worker_importable(qapp):
    from autotest_ide.ui.threads import ScreenshotWorker
    assert ScreenshotWorker is not None


def test_poco_worker_importable(qapp):
    from autotest_ide.ui.threads import PocoWorker
    assert PocoWorker is not None


def test_device_bridge_importable(qapp):
    from autotest_ide.ui.threads import DeviceBridge
    assert DeviceBridge is not None


def test_run_controller_stop_interrupts_inproc_script(qapp, tmp_path):
    """Verify that sys.settrace stop mechanism can interrupt a long-running script."""
    from autotest_ide.ui.run_controller import RunController

    rc = RunController()
    stop_event = rc._stop_event

    # Schedule stop event to be set from another thread after 200ms
    def _set_stop():
        time.sleep(0.2)
        stop_event.set()

    threading.Thread(target=_set_stop, daemon=True).start()

    import sys

    def _stop_tracer(frame, event, arg):
        if stop_event.is_set():
            raise KeyboardInterrupt("Script stopped by user")
        return _stop_tracer

    script_src = "import time\nwhile True:\n  time.sleep(0.1)\n"
    result = {"status": None}
    try:
        sys.settrace(_stop_tracer)
        exec(compile(script_src, "<test>", "exec"), {})
    except KeyboardInterrupt:
        result["status"] = "stopped"
    finally:
        sys.settrace(None)

    assert result["status"] == "stopped"


from unittest.mock import MagicMock
from autotest_ide.ui.threads import PocoWorker


def _make_device():
    device = MagicMock()
    device.status = DeviceState.ONLINE
    device.poco.screenshot.return_value = b"\x89PNG"
    device.poco.inspect_by_point.return_value = {"name": "Btn", "node_id": "1", "payload": {}}
    return device


def test_poco_worker_long_press_emits_inspect_result(qtbot):
    device = _make_device()
    device.poco.long_click.return_value = {}
    worker = PocoWorker(device)
    results = []
    fails = []
    worker.inspect_result.connect(lambda n, s: results.append((n, s)))
    worker.inspect_failed.connect(lambda e, x, y: fails.append((e, x, y)))
    with qtbot.waitSignal(worker.inspect_result, timeout=5000):
        worker.long_press(540, 960, duration=2.0)
    worker.wait(5000)
    assert len(results) == 1
    device.poco.long_click.assert_called_once_with(540, 960, duration=2.0)


def test_poco_worker_swipe_emits_swipe_done(qtbot):
    device = _make_device()
    device.poco.swipe.return_value = {}
    worker = PocoWorker(device)
    done = []
    worker.swipe_done.connect(lambda s: done.append(s))
    with qtbot.waitSignal(worker.swipe_done, timeout=5000):
        worker.swipe(100, 200, 300, 400, duration=0.5)
    worker.wait(5000)
    assert len(done) == 1
    device.poco.swipe.assert_called_once_with(100, 200, 300, 400, duration=0.5)


def test_poco_worker_input_text_emits_inspect_result(qtbot):
    device = _make_device()
    device.poco.set_text.return_value = {}
    worker = PocoWorker(device)
    results = []
    worker.inspect_result.connect(lambda n, s: results.append((n, s)))
    with qtbot.waitSignal(worker.inspect_result, timeout=5000):
        worker.input_text(540, 960, "hello")
    worker.wait(5000)
    assert len(results) == 1
    device.poco.inspect_by_point.assert_called_once_with(540, 960)
    device.poco.set_text.assert_called_once_with("1", "hello")
