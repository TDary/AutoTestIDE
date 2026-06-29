"""Real-device smoke tests. Skipped unless --run-real-device is passed AND
AUTOTESTIDE_REAL_ANDROID_SERIAL env var is set.

Run: pytest tests/test_real_device.py --run-real-device
"""
import time

import pytest

from autotest_ide.core.device_manager import DeviceManager

pytestmark = pytest.mark.real_device


def test_connect_real_android_device(real_android_serial):
    mgr = DeviceManager()
    device = mgr.connect_android(serial=real_android_serial, remote_port=5001)
    try:
        for _ in range(20):
            if device.status == "online":
                break
            time.sleep(0.2)
        assert device.status == "online", f"device not online: {device.status}"
        poco = device.poco
        size = poco.get_screen_size()
        assert "w" in size and "h" in size
        shot = poco.screenshot()
        assert isinstance(shot, bytes)
        assert shot[:8] == b"\x89PNG\r\n\x1a\n"
    finally:
        mgr.shutdown()
