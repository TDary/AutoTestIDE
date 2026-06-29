import os
import sys

import pytest

from autotest_ide.core.errors import ForwarderError
from autotest_ide.core.forwarder import AdbForwarder, LocalForwarder, PortForwarder

FAKE_ADB = [sys.executable, os.path.join(os.path.dirname(__file__), "fake_adb.py")]


# --- LocalForwarder ---


def test_local_forwarder_is_port_forwarder():
    fwd = LocalForwarder(5001)
    assert isinstance(fwd, PortForwarder)


def test_local_forwarder_start_stop_noop():
    fwd = LocalForwarder(5001)
    fwd.start()
    assert fwd.local_port == 5001
    fwd.stop()


def test_local_forwarder_local_port_before_start_returns_value():
    fwd = LocalForwarder(7788)
    assert fwd.local_port == 7788


# --- AdbForwarder ---


def test_adb_forwarder_local_port_raises_before_start():
    fwd = AdbForwarder(device_serial="emulator-5554", remote_port=5001,
                       adb_path=FAKE_ADB)
    with pytest.raises(ForwarderError, match="not started"):
        fwd.local_port


def test_adb_forwarder_start_parses_local_port():
    fwd = AdbForwarder(device_serial="emulator-5554", remote_port=5001,
                       adb_path=FAKE_ADB)
    fwd.start()
    assert fwd.local_port == 12345


def test_adb_forwarder_start_with_default_remote_port():
    fwd = AdbForwarder(device_serial="emulator-5554", adb_path=FAKE_ADB)
    fwd.start()
    assert fwd.local_port == 12345


def test_adb_forwarder_stop_clears_local_port():
    fwd = AdbForwarder(device_serial="emulator-5554", adb_path=FAKE_ADB)
    fwd.start()
    assert fwd.local_port == 12345
    fwd.stop()
    with pytest.raises(ForwarderError, match="not started"):
        fwd.local_port


def test_adb_forwarder_start_adb_not_in_path_raises():
    fwd = AdbForwarder(device_serial="emulator-5554",
                       adb_path=["./nonexistent-adb-binary"])
    with pytest.raises(ForwarderError):
        fwd.start()


def test_adb_forwarder_start_nonzero_exit_raises():
    bogus = [sys.executable, "-c", "import sys; sys.exit(1)"]
    fwd = AdbForwarder(device_serial="emulator-5554", adb_path=bogus)
    with pytest.raises(ForwarderError):
        fwd.start()


def test_adb_forwarder_stop_is_idempotent():
    fwd = AdbForwarder(device_serial="emulator-5554", adb_path=FAKE_ADB)
    fwd.start()
    fwd.stop()
    fwd.stop()
