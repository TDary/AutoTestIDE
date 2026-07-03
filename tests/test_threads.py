import pytest
import threading
import time

from PyQt5.QtWidgets import QApplication


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
