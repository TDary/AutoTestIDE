import pytest

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
