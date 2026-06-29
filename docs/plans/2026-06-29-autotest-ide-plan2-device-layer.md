# Plan 2: Device / Connection Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the device/connection layer (`core/forwarder.py`, `core/device.py`, `core/device_manager.py` + `DeviceError` hierarchy in `core/errors.py`) that wraps Plan 1's `PocoClient` with port forwarding, a connection state machine, heartbeat-based health checks, and device discovery — all PyQt-free and unit-testable with mock adb + the existing fake_poco_server.

**Architecture:** `Device` aggregates a `PortForwarder` (ABC with `AdbForwarder` and `LocalForwarder` implementations) and a `PocoClient`. A background `threading.Thread` polls `PocoClient.heartbeat()` every 5s; 3 consecutive failures flip the device to `offline` (no auto-reconnect — user must call `reconnect()`). `DeviceManager` handles device discovery (`adb devices -l` parsing, local port probing) and owns the single active `Device`, lazily registering an `atexit` shutdown hook on first connect.

**Tech Stack:** Python 3.8+ stdlib (subprocess, socket, threading, atexit, abc, typing). pytest. No PyQt. Reuses Plan 1's `PocoClient` and `fake_poco_server` unchanged.

**Spec reference:** `docs/specs/2026-06-29-autotest-ide-plan2-device-layer-design.md` (the Plan 2 design); parent spec `docs/specs/2026-06-29-autotest-ide-clone-design.md` §4.

**Project root:** `E:/AutoTestIDE/`. All paths relative to it.

**Deviations from spec (noted for transparency):**
1. **AdbForwarder uses `adb forward tcp:0`, no child process held.** Spec §4.3.1 says "PortForwarder manages adb/iproxy subprocess, force-kill on destruct." But `adb forward` is a one-shot command (adb server holds the rule, IDE holds no process). `stop()` calls `adb forward --remove` to clear the server-side rule. The iproxy case (long-running process) is deferred to a later plan.
2. **Device discovery lives in `DeviceManager`, not `Device`** (spec §4.1 Device interface doesn't list discovery). See design §1.4 decision #1.
3. **No auto-reconnect after offline** (spec §4.3.3 only says "3 failures → offline", silent on what follows). See design §1.4 decision #2.
4. **`core/` uses `threading`, not QThread** (inherited from Plan 1 deviation #3). Status change notifications are plain callbacks; the Qt signal bridge is Plan 3.
5. **Heartbeat interval is injectable** (`Device(..., heartbeat_interval=5.0)`) so tests can pass a small value instead of waiting 15s for 3 failures. Default stays 5.0 per spec §4.3.3.

---

## File Structure

```
E:/AutoTestIDE/
├── src/autotest_ide/core/
│   ├── errors.py            # Task 1: extend with DeviceError tree
│   ├── forwarder.py         # Task 2-3: PortForwarder ABC + AdbForwarder + LocalForwarder
│   ├── device.py            # Task 4-6: Device state machine + heartbeat
│   └── device_manager.py    # Task 7-9: DeviceManager (discovery + active + atexit)
└── tests/
    ├── fake_adb.py          # Task 2: fake adb binary (mock subprocess)
    ├── conftest.py          # Task 9: --run-real-device option + real_device marker
    ├── test_forwarder.py    # Task 3
    ├── test_device.py       # Task 4-6
    ├── test_device_manager.py  # Task 7-9
    └── test_real_device.py # Task 10: real-device smoke (skipped by default)
```

---

## Task 1: Extend Error Hierarchy (DeviceError tree)

**Files:**
- Modify: `src/autotest_ide/core/errors.py`
- Test: `tests/test_errors.py`

- [ ] **Step 1: Write the failing test (append to `tests/test_errors.py`)**

```python
from autotest_ide.core.errors import (
    DeviceError,
    ForwarderError,
    DeviceDiscoveryError,
)


def test_device_errors_subclass_device_error():
    for exc in [ForwarderError("x"), DeviceDiscoveryError("x")]:
        assert isinstance(exc, DeviceError)


def test_device_error_is_not_poco_error():
    # Device layer errors must NOT be PocoError (separate trees, per design §3)
    err = ForwarderError("x")
    assert not isinstance(err, PocoError)
    assert not isinstance(PocoConnectionError("x"), DeviceError)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_errors.py -v -k device`
Expected: FAIL with `ImportError: cannot import name 'DeviceError'`

- [ ] **Step 3: Append the DeviceError tree to `src/autotest_ide/core/errors.py`**

Append (after the existing `PocoNodeNotFoundError` class):

```python


class DeviceError(Exception):
    """Base class for all device-layer errors (connection, forwarding, discovery)."""


class ForwarderError(DeviceError):
    """Port forwarding failed (adb error, bad stdout, adb not in PATH)."""


class DeviceDiscoveryError(DeviceError):
    """Device discovery failed (adb devices parse error, port probe error)."""
```

Also add `PocoError` and `PocoConnectionError` to the existing import block at the top of `tests/test_errors.py` if not already imported (they are, per Plan 1 — verify).

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_errors.py -v`
Expected: all pass (Plan 1's tests + 2 new)

- [ ] **Step 5: Commit**

```bash
git add src/autotest_ide/core/errors.py tests/test_errors.py
git commit -m "feat(core): add DeviceError hierarchy (ForwarderError, DeviceDiscoveryError)"
```

---

## Task 2: fake_adb.py + PortForwarder ABC + LocalForwarder

**Files:**
- Create: `tests/fake_adb.py`
- Create: `src/autotest_ide/core/forwarder.py`
- Test: `tests/test_forwarder.py`

- [ ] **Step 1: Write `tests/fake_adb.py`**

A Python script that mimics the adb subset used by `AdbForwarder` and `DeviceManager`. It reads `sys.argv` and behaves like adb for the commands we care about.

```python
"""Fake adb binary for testing AdbForwarder and DeviceManager.

Invoked as: python tests/fake_adb.py [adb args...]
Mimics: adb devices -l, adb -s <serial> forward tcp:0 tcp:<port>, adb -s <serial> forward --remove tcp:<port>
"""
import sys


def main(argv):
    # adb devices -l
    if len(argv) >= 2 and argv[0] == "devices" and argv[1] == "-l":
        sys.stdout.write(
            "List of devices attached\n"
            "emulator-5554   device product:sdk_phone model:Pixel_6 device:emu transport_id:1\n"
            "deadbeef        offline transport_id:2\n"
            "cafebabe        unauthorized transport_id:3\n"
        )
        return 0

    # adb -s <serial> forward tcp:0 tcp:<remote_port>
    if len(argv) >= 3 and argv[0] == "-s" and argv[2] == "forward":
        # argv: [-s, serial, forward, tcp:0, tcp:5001]
        # Emit a fixed allocated local port
        sys.stdout.write("12345\n")
        return 0

    # adb -s <serial> forward --remove tcp:<port>
    if len(argv) >= 4 and argv[0] == "-s" and argv[2] == "forward" and argv[3] == "--remove":
        return 0  # silent success

    # Unknown command
    sys.stderr.write(f"fake_adb: unknown command: {argv}\n")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
```

- [ ] **Step 2: Verify fake_adb.py runs**

Run:
```bash
python tests/fake_adb.py devices -l
python tests/fake_adb.py -s emulator-5554 forward tcp:0 tcp:5001
```

Expected:
```
List of devices attached
emulator-5554   device product:sdk_phone model:Pixel_6 device:emu transport_id:1
...
12345
```

- [ ] **Step 3: Write the failing test for LocalForwarder**

`tests/test_forwarder.py`:

```python
from autotest_ide.core.forwarder import LocalForwarder, PortForwarder


def test_local_forwarder_is_port_forwarder():
    fwd = LocalForwarder(5001)
    assert isinstance(fwd, PortForwarder)


def test_local_forwarder_start_stop_noop():
    fwd = LocalForwarder(5001)
    fwd.start()  # must not raise
    assert fwd.local_port == 5001
    fwd.stop()   # must not raise


def test_local_forwarder_local_port_before_start_returns_value():
    # LocalForwarder has no "not started" state — port is known at construction
    fwd = LocalForwarder(7788)
    assert fwd.local_port == 7788
```

- [ ] **Step 4: Run test to verify it fails**

Run: `pytest tests/test_forwarder.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'autotest_ide.core.forwarder'`

- [ ] **Step 5: Write `src/autotest_ide/core/forwarder.py` (ABC + LocalForwarder only; AdbForwarder in Task 3)**

```python
from abc import ABC, abstractmethod
from typing import Optional


class PortForwarder(ABC):
    """Abstract port forwarder. Implementations: AdbForwarder, LocalForwarder."""

    @property
    @abstractmethod
    def local_port(self) -> int:
        """The local port forwarded to. Raises if not started."""

    @abstractmethod
    def start(self) -> None:
        """Start forwarding. Raises ForwarderError on failure."""

    @abstractmethod
    def stop(self) -> None:
        """Stop forwarding. Best-effort, never raises."""


class LocalForwarder(PortForwarder):
    """No-op forwarder for PC-direct connections (game process on 127.0.0.1)."""

    def __init__(self, local_port: int = 5001):
        self._local_port = local_port

    @property
    def local_port(self) -> int:
        return self._local_port

    def start(self) -> None:
        pass  # no-op

    def stop(self) -> None:
        pass  # no-op
```

- [ ] **Step 6: Run test to verify it passes**

Run: `pytest tests/test_forwarder.py -v`
Expected: 3 passed

- [ ] **Step 7: Commit**

```bash
git add tests/fake_adb.py src/autotest_ide/core/forwarder.py tests/test_forwarder.py
git commit -m "feat(core): add PortForwarder ABC + LocalForwarder + fake_adb test fixture"
```

---

## Task 3: AdbForwarder

**Files:**
- Modify: `src/autotest_ide/core/forwarder.py`
- Modify: `tests/test_forwarder.py`

- [ ] **Step 1: Write the failing tests (append to `tests/test_forwarder.py`)**

```python
import os
import sys

import pytest

from autotest_ide.core.errors import ForwarderError
from autotest_ide.core.forwarder import AdbForwarder

FAKE_ADB = [sys.executable, os.path.join(os.path.dirname(__file__), "fake_adb.py")]


def test_adb_forwarder_start_parses_local_port():
    fwd = AdbForwarder(device_serial="emulator-5554", remote_port=5001,
                       adb_path=FAKE_ADB)
    assert fwd.local_port != fwd.local_port if False else True  # placeholder, see below
    # actually: local_port should raise before start
    with pytest.raises(ForwarderError, match="not started"):
        fwd.local_port
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
    # Use a path that doesn't exist
    fwd = AdbForwarder(device_serial="emulator-5554",
                       adb_path=["./nonexistent-adb-binary"])
    with pytest.raises(ForwarderError):
        fwd.start()


def test_adb_forwarder_start_nonzero_exit_raises():
    # Pass an unknown subcommand to fake_adb — but fake_adb's -s handler
    # accepts any serial, so we instead pass a bogus adb_path that exits nonzero.
    # Use python with a script that exits 1:
    bogus = [sys.executable, "-c", "import sys; sys.exit(1)"]
    fwd = AdbForwarder(device_serial="emulator-5554", adb_path=bogus)
    with pytest.raises(ForwarderError):
        fwd.start()


def test_adb_forwarder_stop_is_idempotent():
    fwd = AdbForwarder(device_serial="emulator-5554", adb_path=FAKE_ADB)
    fwd.start()
    fwd.stop()
    fwd.stop()  # second stop must not raise
```

(Note: the `test_adb_forwarder_start_parses_local_port` test's first assert line is awkward — replace it cleanly. Use the version below for that test.)

Replace the first test with this cleaner version:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_forwarder.py -v -k adb`
Expected: FAIL with `ImportError: cannot import name 'AdbForwarder'`

- [ ] **Step 3: Add AdbForwarder to `src/autotest_ide/core/forwarder.py`**

Append after `LocalForwarder`:

```python
import subprocess

from autotest_ide.core.errors import ForwarderError


class AdbForwarder(PortForwarder):
    """Android USB forwarder. Uses `adb forward tcp:0` for dynamic local port."""

    def __init__(self, device_serial: str, remote_port: int = 5001,
                 adb_path: Optional[list] = None):
        self._device_serial = device_serial
        self._remote_port = remote_port
        self._adb_path = adb_path if adb_path is not None else ["adb"]
        self._local_port: Optional[int] = None

    @property
    def local_port(self) -> int:
        if self._local_port is None:
            raise ForwarderError("forwarder not started")
        return self._local_port

    def start(self) -> None:
        cmd = self._adb_path + [
            "-s", self._device_serial,
            "forward", "tcp:0", f"tcp:{self._remote_port}",
        ]
        try:
            result = subprocess.run(
                cmd, capture_output=True, timeout=5, text=True,
            )
        except (OSError, subprocess.TimeoutExpired) as e:
            raise ForwarderError(f"adb forward failed: {e}") from e
        if result.returncode != 0:
            raise ForwarderError(
                f"adb forward exited {result.returncode}: {result.stderr.strip()}"
            )
        stdout = result.stdout.strip()
        if not stdout.isdigit():
            raise ForwarderError(
                f"adb forward returned non-numeric port: {stdout!r}"
            )
        self._local_port = int(stdout)

    def stop(self) -> None:
        if self._local_port is None:
            return  # already stopped
        cmd = self._adb_path + [
            "-s", self._device_serial,
            "forward", "--remove", f"tcp:{self._local_port}",
        ]
        try:
            subprocess.run(cmd, capture_output=True, timeout=5, text=True)
        except (OSError, subprocess.TimeoutExpired):
            pass  # best-effort, never raise
        self._local_port = None
```

(Move the `import subprocess` and `from autotest_ide.core.errors import ForwarderError` to the top of the file with the other imports — don't leave them mid-file.)

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_forwarder.py -v`
Expected: all pass (3 LocalForwarder + 7 AdbForwarder)

- [ ] **Step 5: Commit**

```bash
git add src/autotest_ide/core/forwarder.py tests/test_forwarder.py
git commit -m "feat(core): add AdbForwarder (adb forward tcp:0, dynamic local port)"
```

---

## Task 4: Device — Constructor + Properties + State Transitions (no heartbeat yet)

**Files:**
- Create: `src/autotest_ide/core/device.py`
- Create: `tests/test_device.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_device.py`:

```python
import pytest

from autotest_ide.core.device import Device
from autotest_ide.core.errors import DeviceError
from autotest_ide.core.forwarder import LocalForwarder


def make_local_device(local_port):
    fwd = LocalForwarder(local_port)
    return Device(name="test", device_type="windows", forwarder=fwd)


def test_device_initial_state_is_disconnected():
    device = make_local_device(5001)
    assert device.status == "disconnected"
    assert device.name == "test"
    assert device.device_type == "windows"


def test_device_poco_raises_when_not_online():
    device = make_local_device(5001)
    with pytest.raises(DeviceError, match="not online"):
        _ = device.poco


def test_device_connect_transitions_to_online(fake_server):
    device = make_local_device(fake_server.port)
    device.connect()
    try:
        assert device.status == "online"
        assert device.poco is not None
    finally:
        device.disconnect()


def test_device_connect_failure_transitions_to_offline():
    # No fake_server running on this port → PocoClient.connect raises PocoConnectionError
    device = make_local_device(1)  # port 1: reserved, will refuse
    device.connect()
    assert device.status == "offline"


def test_device_connect_when_not_disconnected_raises(fake_server):
    device = make_local_device(fake_server.port)
    device.connect()
    try:
        with pytest.raises(DeviceError, match="already"):
            device.connect()
    finally:
        device.disconnect()


def test_device_disconnect_returns_to_disconnected(fake_server):
    device = make_local_device(fake_server.port)
    device.connect()
    assert device.status == "online"
    device.disconnect()
    assert device.status == "disconnected"


def test_device_disconnect_is_idempotent(fake_server):
    device = make_local_device(fake_server.port)
    device.connect()
    device.disconnect()
    device.disconnect()  # must not raise


def test_device_on_status_change_callback_fires(fake_server):
    statuses = []
    device = make_local_device(fake_server.port)
    device.on_status_change(lambda s: statuses.append(s))
    device.connect()
    device.disconnect()
    assert "connecting" in statuses
    assert "online" in statuses
    assert "disconnected" in statuses
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_device.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'autotest_ide.core.device'`

- [ ] **Step 3: Write `src/autotest_ide/core/device.py` (no heartbeat yet — added in Task 5)**

```python
import threading
from typing import Callable, Optional

from autotest_ide.core.errors import DeviceError, ForwarderError
from autotest_ide.core.forwarder import PortForwarder
from autotest_ide.core.poco_client import PocoClient
from autotest_ide.core.errors import PocoConnectionError


class Device:
    """A connectable device wrapping a PortForwarder + PocoClient with a state machine."""

    def __init__(self, name: str, device_type: str, forwarder: PortForwarder,
                 heartbeat_interval: float = 5.0):
        self._name = name
        self._device_type = device_type
        self._forwarder = forwarder
        self._heartbeat_interval = heartbeat_interval
        self._poco: Optional[PocoClient] = None
        self._status = "disconnected"
        self._heartbeat_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._heartbeat_failures = 0
        self._on_status_change: Callable[[str], None] = lambda s: None
        self._lock = threading.Lock()

    @property
    def name(self) -> str:
        return self._name

    @property
    def device_type(self) -> str:
        return self._device_type

    @property
    def status(self) -> str:
        return self._status

    @property
    def poco(self) -> PocoClient:
        if self._status != "online" or self._poco is None:
            raise DeviceError(f"device not online: status={self._status}")
        return self._poco

    def on_status_change(self, callback: Callable[[str], None]) -> None:
        self._on_status_change = callback

    def _set_status(self, status: str) -> None:
        with self._lock:
            self._status = status
        # Call callback outside the lock to avoid deadlock if callback
        # re-enters Device (callers are warned not to, but be safe).
        try:
            self._on_status_change(status)
        except Exception:
            pass  # never let callback errors propagate

    def connect(self) -> None:
        if self._status != "disconnected" and self._status != "offline":
            raise DeviceError(f"already {self._status}")
        self._do_connect()

    def reconnect(self) -> None:
        if self._status != "offline":
            raise DeviceError(f"reconnect only allowed from offline, current={self._status}")
        self._do_connect()

    def _do_connect(self) -> None:
        self._set_status("connecting")
        try:
            self._forwarder.start()
        except ForwarderError:
            self._set_status("offline")
            return
        poco = PocoClient(host="127.0.0.1", port=self._forwarder.local_port)
        try:
            poco.connect()
        except PocoConnectionError:
            try:
                self._forwarder.stop()
            except Exception:
                pass
            self._set_status("offline")
            return
        self._poco = poco
        self._heartbeat_failures = 0
        self._stop_event.clear()
        self._set_status("online")
        self._start_heartbeat()

    def _start_heartbeat(self) -> None:
        # Implemented in Task 5; stubbed here so connect() works.
        pass

    def disconnect(self) -> None:
        self._stop_event.set()
        if self._heartbeat_thread is not None:
            self._heartbeat_thread.join(timeout=2.0)
            self._heartbeat_thread = None
        if self._poco is not None:
            try:
                self._poco.close()
            except Exception:
                pass
            self._poco = None
        try:
            self._forwarder.stop()
        except Exception:
            pass
        self._set_status("disconnected")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_device.py -v`
Expected: 8 passed

- [ ] **Step 5: Commit**

```bash
git add src/autotest_ide/core/device.py tests/test_device.py
git commit -m "feat(core): add Device state machine (disconnected/connecting/online/offline)"
```

---

## Task 5: Device — Heartbeat Thread

**Files:**
- Modify: `src/autotest_ide/core/device.py`
- Modify: `tests/test_device.py`

- [ ] **Step 1: Write the failing tests (append to `tests/test_device.py`)**

```python
def test_heartbeat_keeps_device_online(fake_server):
    device = make_local_device(fake_server.port)
    device._heartbeat_interval = 0.1  # fast for testing
    device.connect()
    try:
        # Wait past one heartbeat cycle
        import time
        time.sleep(0.3)
        assert device.status == "online"
    finally:
        device.disconnect()


def test_heartbeat_3_failures_flip_to_offline(fake_server):
    device = make_local_device(fake_server.port)
    device._heartbeat_interval = 0.1
    device.connect()
    assert device.status == "online"
    # Drop the server-side connection so heartbeat fails
    fake_server.drop_on_next = True
    # Wait for 3 heartbeat failures (3 * 0.1 = 0.3s, give margin)
    import time
    time.sleep(1.0)
    assert device.status == "offline"
    device.disconnect()


def test_heartbeat_resets_failure_count_on_success(fake_server):
    device = make_local_device(fake_server.port)
    device._heartbeat_interval = 0.1
    device.connect()
    # Single drop then recovery: drop_on_next affects one request, then server is healthy
    fake_server.drop_on_next = True
    import time
    time.sleep(0.5)
    # Only 1 failure happened (drop_on_next), device should still be online
    assert device.status == "online"
    device.disconnect()


def test_health_check_returns_true_when_online(fake_server):
    device = make_local_device(fake_server.port)
    device.connect()
    try:
        assert device.health_check() is True
    finally:
        device.disconnect()


def test_health_check_returns_false_and_flips_offline_after_drop(fake_server):
    device = make_local_device(fake_server.port)
    device.connect()
    fake_server.drop_on_next = True
    assert device.health_check() is False
    assert device.status == "offline"
    device.disconnect()


def test_health_check_returns_false_when_disconnected():
    device = make_local_device(5001)
    assert device.health_check() is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_device.py -v -k "heartbeat or health_check"`
Expected: FAIL — heartbeat isn't running (`_start_heartbeat` is a stub), and `health_check` doesn't exist.

- [ ] **Step 3: Implement `_start_heartbeat`, `_heartbeat_loop`, and `health_check` in `src/autotest_ide/core/device.py`**

Replace the `_start_heartbeat` stub method with:

```python
    def _start_heartbeat(self) -> None:
        self._heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop, daemon=True,
        )
        self._heartbeat_thread.start()

    def _heartbeat_loop(self) -> None:
        while not self._stop_event.wait(timeout=self._heartbeat_interval):
            if self._status != "online":
                return
            if self._poco is None:
                return
            try:
                ok = self._poco.heartbeat()
            except Exception:
                ok = False  # defensive: heartbeat shouldn't raise, but guard
            with self._lock:
                if not ok:
                    self._heartbeat_failures += 1
                    if self._heartbeat_failures >= 3:
                        should_flip = True
                    else:
                        should_flip = False
                else:
                    self._heartbeat_failures = 0
                    should_flip = False
            if should_flip:
                self._set_status("offline")
                return  # thread exits, no auto-reconnect (design §1.4 #2)

    def health_check(self) -> bool:
        """Synchronous liveness probe. Flips to offline on failure. Never raises."""
        if self._status != "online" or self._poco is None:
            return False
        try:
            ok = self._poco.heartbeat()
        except Exception:
            ok = False
        if not ok:
            with self._lock:
                self._heartbeat_failures = 3  # force offline
            self._set_status("offline")
        return ok
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_device.py -v`
Expected: all pass (8 from Task 4 + 6 new)

- [ ] **Step 5: Commit**

```bash
git add src/autotest_ide/core/device.py tests/test_device.py
git commit -m "feat(core): add Device heartbeat thread + health_check (3-failure offline)"
```

---

## Task 6: Device — Reconnect from Offline

**Files:**
- Modify: `tests/test_device.py`

- [ ] **Step 1: Write the failing tests (append to `tests/test_device.py`)**

```python
def test_reconnect_from_offline(fake_server):
    device = make_local_device(fake_server.port)
    device._heartbeat_interval = 0.1
    device.connect()
    fake_server.drop_on_next = True
    import time
    time.sleep(1.0)
    assert device.status == "offline"
    # Reconnect: server is healthy again
    device.reconnect()
    assert device.status == "online"
    device.disconnect()


def test_reconnect_from_disconnected_raises(fake_server):
    device = make_local_device(fake_server.port)
    with pytest.raises(DeviceError, match="offline"):
        device.reconnect()


def test_reconnect_from_online_raises(fake_server):
    device = make_local_device(fake_server.port)
    device.connect()
    try:
        with pytest.raises(DeviceError, match="offline"):
            device.reconnect()
    finally:
        device.disconnect()
```

- [ ] **Step 2: Run test to verify it passes**

Run: `pytest tests/test_device.py -v -k reconnect`
Expected: 3 passed

(The `reconnect` method already exists from Task 4 and calls `_do_connect`, which handles `offline → connecting → online`. If it fails, re-examine `_do_connect`'s status guard — `connect()` only allows `disconnected`/`offline`, and `reconnect()` only allows `offline`. Both call `_do_connect`.)

- [ ] **Step 3: Run full device suite**

Run: `pytest tests/test_device.py -v`
Expected: all pass (8 + 6 + 3 = 17)

- [ ] **Step 4: Commit**

```bash
git add tests/test_device.py
git commit -m "test(core): cover Device.reconnect (offline→online, rejects non-offline)"
```

---

## Task 7: DeviceManager — Constructor + adb devices -l Parsing

**Files:**
- Create: `src/autotest_ide/core/device_manager.py`
- Create: `tests/test_device_manager.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_device_manager.py`:

```python
import os
import sys

from autotest_ide.core.device_manager import DeviceManager

FAKE_ADB = [sys.executable, os.path.join(os.path.dirname(__file__), "fake_adb.py")]


def test_list_android_devices_parses_device_rows():
    mgr = DeviceManager(adb_path=FAKE_ADB)
    devices = mgr.list_android_devices()
    # fake_adb emits 3 rows: device, offline, unauthorized — only "device" is returned
    assert len(devices) == 1
    d = devices[0]
    assert d["serial"] == "emulator-5554"
    assert d["state"] == "device"
    assert d["model"] == "Pixel_6"
    assert d["transport_id"] == "1"


def test_list_android_devices_returns_empty_when_no_devices(monkeypatch):
    # Point adb_path at a fake that emits only the header
    import tests.fake_adb as fake_adb_mod
    # Simulate by using a python -c that prints just the header
    empty_adb = [sys.executable, "-c",
                 "print('List of devices attached')"]
    mgr = DeviceManager(adb_path=empty_adb)
    assert mgr.list_android_devices() == []


def test_list_android_devices_adb_failure_raises():
    bogus = [sys.executable, "-c", "import sys; sys.exit(1)"]
    from autotest_ide.core.errors import DeviceDiscoveryError
    mgr = DeviceManager(adb_path=bogus)
    with pytest.raises(DeviceDiscoveryError):
        mgr.list_android_devices()
```

(Add `import pytest` at top of file.)

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_device_manager.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'autotest_ide.core.device_manager'`

- [ ] **Step 3: Write `src/autotest_ide/core/device_manager.py` (constructor + list_android_devices only; list_local_devices in Task 8, connect_* in Task 9)**

```python
import subprocess
from typing import Optional

from autotest_ide.core.errors import DeviceDiscoveryError


class DeviceManager:
    """Manages device discovery and the single active Device."""

    def __init__(self, adb_path: Optional[list] = None):
        self._adb_path = adb_path if adb_path is not None else ["adb"]
        self._devices: list = []
        self._active = None
        self._atexit_registered = False

    # --- discovery (spec §4.2) ---

    def list_android_devices(self) -> list:
        cmd = self._adb_path + ["devices", "-l"]
        try:
            result = subprocess.run(cmd, capture_output=True, timeout=5, text=True)
        except (OSError, subprocess.TimeoutExpired) as e:
            raise DeviceDiscoveryError(f"adb devices failed: {e}") from e
        if result.returncode != 0:
            raise DeviceDiscoveryError(
                f"adb devices exited {result.returncode}: {result.stderr.strip()}"
            )
        return self._parse_devices_output(result.stdout)

    @staticmethod
    def _parse_devices_output(stdout: str) -> list:
        devices = []
        for line in stdout.splitlines():
            line = line.strip()
            if not line or line.startswith("List of devices"):
                continue
            tokens = line.split()
            if len(tokens) < 2:
                continue
            serial = tokens[0]
            state = tokens[1]
            if state != "device":
                continue  # skip offline / unauthorized
            entry = {"serial": serial, "state": state}
            for tok in tokens[2:]:
                if ":" in tok:
                    k, v = tok.split(":", 1)
                    entry[k] = v
            devices.append(entry)
        return devices
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_device_manager.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add src/autotest_ide/core/device_manager.py tests/test_device_manager.py
git commit -m "feat(core): add DeviceManager.list_android_devices (adb devices -l parsing)"
```

---

## Task 8: DeviceManager — list_local_devices (port probing)

**Files:**
- Modify: `src/autotest_ide/core/device_manager.py`
- Modify: `tests/test_device_manager.py`

- [ ] **Step 1: Write the failing tests (append to `tests/test_device_manager.py`)**

```python
def test_list_local_devices_finds_open_port(fake_server):
    mgr = DeviceManager()
    # fake_server is listening on fake_server.port — probe it
    found = mgr.list_local_devices(ports=[fake_server.port])
    assert len(found) == 1
    assert found[0]["host"] == "127.0.0.1"
    assert found[0]["port"] == fake_server.port


def test_list_local_devices_returns_empty_when_nothing_listening():
    mgr = DeviceManager()
    # Port 1 is reserved and nothing listens there
    found = mgr.list_local_devices(ports=[1])
    assert found == []


def test_list_local_devices_default_ports():
    mgr = DeviceManager()
    # Just verify it runs without error with default ports (likely empty)
    found = mgr.list_local_devices()
    assert isinstance(found, list)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_device_manager.py -v -k list_local`
Expected: FAIL with `AttributeError: 'DeviceManager' object has no attribute 'list_local_devices'`

- [ ] **Step 3: Add `list_local_devices` to `src/autotest_ide/core/device_manager.py`**

Append after `list_android_devices` (before `_parse_devices_output` or after it — keep methods grouped):

```python
    def list_local_devices(self, ports: Optional[list] = None) -> list:
        if ports is None:
            ports = [5001, 5002, 5003]
        found = []
        for port in ports:
            try:
                import socket
                s = socket.create_connection(("127.0.0.1", port), timeout=0.5)
                s.close()
                found.append({"host": "127.0.0.1", "port": port})
            except OSError:
                continue  # not listening, skip
        return found
```

(Move `import socket` to the top of the file with the other imports.)

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_device_manager.py -v`
Expected: all pass (3 + 3 = 6)

- [ ] **Step 5: Commit**

```bash
git add src/autotest_ide/core/device_manager.py tests/test_device_manager.py
git commit -m "feat(core): add DeviceManager.list_local_devices (port probing)"
```

---

## Task 9: DeviceManager — connect_android / connect_local / active / shutdown / atexit

**Files:**
- Modify: `src/autotest_ide/core/device_manager.py`
- Modify: `tests/test_device_manager.py`

- [ ] **Step 1: Write the failing tests (append to `tests/test_device_manager.py`)**

```python
def test_connect_local_sets_active_and_returns_device(fake_server):
    mgr = DeviceManager()
    device = mgr.connect_local(port=fake_server.port)
    try:
        assert mgr.active is device
        assert device.status == "online"
        assert device.name == f"localhost:{fake_server.port}"
    finally:
        mgr.disconnect_active()
    assert mgr.active is None


def test_connect_local_default_name():
    mgr = DeviceManager()
    # Use a port nothing listens on → device goes offline, but still created + active
    device = mgr.connect_local(port=1)
    assert device.status == "offline"
    assert mgr.active is device
    mgr.shutdown()


def test_connect_android_uses_fake_adb(fake_server):
    # Connect android: AdbForwarder uses fake_adb (allocates local port 12345).
    # But PocoClient then tries 127.0.0.1:12345 which nothing listens on → offline.
    # To make it online, we'd need a real forward. For unit test, just verify the
    # forwarder was started and device exists.
    mgr = DeviceManager(adb_path=FAKE_ADB)
    device = mgr.connect_android(serial="emulator-5554", remote_port=5001)
    assert device.status == "offline"  # no real poco server at 12345
    assert device.name == "emulator-5554"
    mgr.shutdown()


def test_disconnect_active_clears_active(fake_server):
    mgr = DeviceManager()
    mgr.connect_local(port=fake_server.port)
    assert mgr.active is not None
    mgr.disconnect_active()
    assert mgr.active is None


def test_shutdown_disconnects_all_devices(fake_server):
    mgr = DeviceManager()
    d1 = mgr.connect_local(port=fake_server.port)
    mgr.disconnect_active()
    # shutdown on already-disconnected is a no-op
    mgr.shutdown()
    assert d1.status == "disconnected"


def test_atexit_registered_on_first_connect(fake_server, monkeypatch):
    registered = []
    monkeypatch.setattr("atexit.register", lambda fn: registered.append(fn))
    mgr = DeviceManager()
    assert mgr._atexit_registered is False
    mgr.connect_local(port=fake_server.port)
    assert mgr._atexit_registered is True
    assert len(registered) == 1
    mgr.shutdown()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_device_manager.py -v -k "connect or disconnect or shutdown or atexit"`
Expected: FAIL — `connect_local`, `connect_android`, `active`, `disconnect_active`, `shutdown` don't exist.

- [ ] **Step 3: Add the connect/active/shutdown methods to `src/autotest_ide/core/device_manager.py`**

Append (and add imports at top: `import atexit`, `from autotest_ide.core.device import Device`, `from autotest_ide.core.forwarder import AdbForwarder, LocalForwarder`):

```python
    # --- active device management ---

    def connect_android(self, serial: str, remote_port: int = 5001,
                        name: Optional[str] = None) -> Device:
        fwd = AdbForwarder(device_serial=serial, remote_port=remote_port,
                           adb_path=self._adb_path)
        device = Device(name=name or serial, device_type="android", forwarder=fwd)
        device.connect()
        self._active = device
        self._devices.append(device)
        self._register_atexit()
        return device

    def connect_local(self, port: int, name: Optional[str] = None) -> Device:
        fwd = LocalForwarder(local_port=port)
        device = Device(name=name or f"localhost:{port}", device_type="windows",
                        forwarder=fwd)
        device.connect()
        self._active = device
        self._devices.append(device)
        self._register_atexit()
        return device

    @property
    def active(self):
        return self._active

    def disconnect_active(self) -> None:
        if self._active is not None:
            self._active.disconnect()
            self._active = None

    def shutdown(self) -> None:
        for device in self._devices:
            try:
                device.disconnect()
            except Exception:
                pass  # best-effort
        self._active = None

    def _register_atexit(self) -> None:
        if not self._atexit_registered:
            atexit.register(self.shutdown)
            self._atexit_registered = True
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_device_manager.py -v`
Expected: all pass (6 + 6 = 12)

- [ ] **Step 5: Commit**

```bash
git add src/autotest_ide/core/device_manager.py tests/test_device_manager.py
git commit -m "feat(core): add DeviceManager connect/disconnect/active/shutdown + atexit"
```

---

## Task 10: Real-Device Smoke Test + conftest Marker

**Files:**
- Modify: `tests/conftest.py`
- Create: `tests/test_real_device.py`

- [ ] **Step 1: Extend `tests/conftest.py` with the real_device marker machinery**

Replace the contents of `tests/conftest.py` with:

```python
import os

import pytest

from tests.fake_poco_server import FakePocoServer


@pytest.fixture
def fake_server():
    server = FakePocoServer()
    server.start()
    yield server
    server.stop()


def pytest_addoption(parser):
    parser.addoption(
        "--run-real-device", action="store_true", default=False,
        help="Run real-device smoke tests (requires a connected Android device)",
    )


def pytest_collection_modifyitems(config, items):
    if config.getoption("--run-real-device"):
        return
    skip_real = pytest.mark.skip(reason="need --run-real-device option to run")
    for item in items:
        if "real_device" in item.keywords:
            item.add_marker(skip_real)


@pytest.fixture
def real_android_serial():
    serial = os.environ.get("AUTOTESTIDE_REAL_ANDROID_SERIAL")
    if not serial:
        pytest.skip("AUTOTESTIDE_REAL_ANDROID_SERIAL not set")
    return serial
```

- [ ] **Step 2: Write `tests/test_real_device.py`**

```python
"""Real-device smoke tests. Skipped unless --run-real-device is passed AND
AUTOTESTIDE_REAL_ANDROID_SERIAL env var is set.

Run: pytest tests/test_real_device.py --run-real-device
"""
import pytest

from autotest_ide.core.device_manager import DeviceManager


pytestmark = pytest.mark.real_device


def test_connect_real_android_device(real_android_serial):
    mgr = DeviceManager()
    device = mgr.connect_android(serial=real_android_serial, remote_port=5001)
    try:
        # Wait for the heartbeat to confirm online (give it a moment)
        import time
        for _ in range(20):
            if device.status == "online":
                break
            time.sleep(0.2)
        assert device.status == "online", f"device not online: {device.status}"
        # Smoke: get_screen_size + screenshot
        poco = device.poco
        size = poco.get_screen_size()
        assert "w" in size and "h" in size
        shot = poco.screenshot()
        assert isinstance(shot, bytes)
        assert shot[:8] == b"\x89PNG\r\n\x1a\n"  # PNG header
    finally:
        mgr.shutdown()
```

- [ ] **Step 3: Verify smoke test is skipped by default**

Run: `pytest tests/test_real_device.py -v`
Expected: 1 skipped (reason: "need --run-real-device option to run")

- [ ] **Step 4: Verify --run-real-device without env var also skips**

Run: `pytest tests/test_real_device.py --run-real-device -v`
Expected: 1 skipped (reason: "AUTOTESTIDE_REAL_ANDROID_SERIAL not set")

- [ ] **Step 5: Commit**

```bash
git add tests/conftest.py tests/test_real_device.py
git commit -m "test: add real-device smoke test (skipped by default, --run-real-device)"
```

---

## Task 11: Full Suite Run + Final Verification

**Files:** None (verification only)

- [ ] **Step 1: Run the entire test suite**

Run: `pytest -v`
Expected: all tests pass (Plan 1's ~17 tests + Plan 2's new tests). Real-device test is skipped.

- [ ] **Step 2: Verify core/ has no PyQt dependency**

Run:
```bash
python -c "
import importlib, sys
for mod in ['autotest_ide.core.errors', 'autotest_ide.core.forwarder',
            'autotest_ide.core.device', 'autotest_ide.core.device_manager']:
    m = importlib.import_module(mod)
    assert 'PyQt' not in sys.modules, f'{mod} pulled in PyQt'
    print(f'OK: {mod} (no PyQt)')
"
```

Expected: 4 lines of `OK: ...` (no PyQt pulled in).

- [ ] **Step 3: Verify M3 acceptance criteria**

M3 (spec §10.1): "adb/iproxy subprocess management, state machine tests, real Android device forward + Poco connection."

- adb subprocess management → `test_forwarder.py` AdbForwarder tests ✓
- state machine tests → `test_device.py` 17 tests ✓
- real Android forward + Poco → `test_real_device.py` (skipped by default, runs with `--run-real-device` + env var) ✓

- [ ] **Step 4: Commit (if any cleanup)**

Only if there were changes. Otherwise skip.

---

## Self-Review

### Spec coverage check

| Spec / design section | Task(s) |
|---|---|
| §3 DeviceError / ForwarderError / DeviceDiscoveryError | T1 |
| §4.1 PortForwarder ABC | T2 |
| §4.2 AdbForwarder (`adb forward tcp:0`) | T3 |
| §4.3 LocalForwarder (no-op) | T2 |
| §5.1 Device state machine (disconnected/connecting/online/offline) | T4, T6 |
| §5.2 Device.poco property (raises when not online) | T4 |
| §5.2 Device.connect / disconnect / reconnect / health_check | T4, T5, T6 |
| §5.3 heartbeat thread (5s, 3 failures → offline) | T5 |
| §5.4 on_status_change callback | T4 |
| §6.1 DeviceManager.list_android_devices | T7 |
| §6.1 DeviceManager.list_local_devices | T8 |
| §6.1 DeviceManager.connect_android / connect_local / active / disconnect_active | T9 |
| §6.3 atexit hook (lazy register) | T9 |
| §6.4 adb subprocess call convention (timeout=5, list adb_path) | T3, T7 |
| §7.1 fake_adb.py | T2 |
| §7.2 real-device smoke (skipped by default) | T10 |
| §9 M3 acceptance: state machine tests | T4-T6 |
| §9 M3 acceptance: real Android forward + Poco | T10 |
| Deviation #1 (AdbForwarder no subprocess) | T3 |
| Deviation #4 (core/ no PyQt) | T11 Step 2 |

**Gaps:** None. Every spec/design section in Plan 2's scope has a task.

### Placeholder scan

- No "TBD", "TODO", "implement later" — every code step shows actual code.
- No "add appropriate error handling" — error handling is shown inline.
- No "similar to Task N" — each task is self-contained with full code.
- The awkward first-version of `test_adb_forwarder_start_parses_local_port` in T3 is explicitly called out and replaced with a cleaner version in the same step.

### Type / name consistency

- `PortForwarder.local_port` / `start` / `stop` — defined T2, used T3, T4, T9.
- `AdbForwarder(device_serial, remote_port, adb_path)` — defined T3, used T9 (`connect_android`). `adb_path` is `list`, matches design §4.2.
- `LocalForwarder(local_port)` — defined T2, used T9 (`connect_local`).
- `Device(name, device_type, forwarder, heartbeat_interval=5.0)` — defined T4, used T9. The `heartbeat_interval` param is the injectable addition (deviation #5).
- `DeviceManager(adb_path)` — defined T7, used T9, T10.
- `DeviceManager.list_android_devices` / `list_local_devices` / `connect_android` / `connect_local` / `active` / `disconnect_active` / `shutdown` — names stable T7-T9.
- `ForwarderError` / `DeviceDiscoveryError` / `DeviceError` — defined T1, used T3, T4, T7.
- `fake_server` fixture (from Plan 1 conftest) — reused T4-T9; extended T10 with marker logic.
- `FAKE_ADB = [sys.executable, "tests/fake_adb.py"]` — defined in T3 test, T7 test; identical construction.
- `drop_on_next` (Plan 1 FakePocoServer attribute) — used T5 to force heartbeat failure. Verified exists in Plan 1's `FakePocoServer` (fake_poco_server.py).

**No inconsistencies found.**

---

## Execution Handoff

Plan complete and saved to `docs/plans/2026-06-29-autotest-ide-plan2-device-layer.md`. Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration. Best for an 11-task plan with cumulative edits (device.py is built up across T4-T6, device_manager.py across T7-T9 — review between tasks catches drift early).

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints. Faster turnaround but I hold all the context.

Which approach?
