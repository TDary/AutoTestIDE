import threading
from typing import Callable, Optional

from autotest_ide.core.errors import DeviceError, ForwarderError, PocoConnectionError, PocoError
from autotest_ide.core.forwarder import PortForwarder
from autotest_ide.core.log import getLogger
from autotest_ide.core.poco_client import PocoClient

logger = getLogger(__name__)


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
            old = self._status
            self._status = status
        logger.info("Device %s: %s -> %s", self._name, old, status)
        try:
            self._on_status_change(status)
        except Exception:
            logger.debug("status change callback failed", exc_info=True)

    def connect(self) -> None:
        if self._status not in ("disconnected", "offline"):
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
            logger.warning("Device %s: forwarder start failed", self._name, exc_info=True)
            self._set_status("offline")
            return
        poco = PocoClient(host="127.0.0.1", port=self._forwarder.local_port)
        try:
            poco.connect()
        except PocoConnectionError:
            logger.warning("Device %s: poco connect failed on port %d", self._name, self._forwarder.local_port, exc_info=True)
            try:
                self._forwarder.stop()
            except Exception:
                logger.debug("Device %s: forwarder stop after connect failure", self._name, exc_info=True)
            self._set_status("offline")
            return
        self._poco = poco
        self._heartbeat_failures = 0
        self._stop_event.clear()
        self._set_status("online")
        self._start_heartbeat()

    def _start_heartbeat(self) -> None:
        self._heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop, daemon=True,
        )
        self._heartbeat_thread.start()

    def _heartbeat_loop(self) -> None:
        while not self._stop_event.wait(timeout=self._heartbeat_interval):
            with self._lock:
                status = self._status
                poco = self._poco
            if status != "online":
                return
            if poco is None:
                return
            try:
                ok = poco.heartbeat()
            except PocoError:
                ok = False
            except Exception:
                logger.warning("Device %s: unexpected heartbeat error", self._name, exc_info=True)
                ok = False
            with self._lock:
                if not ok:
                    self._heartbeat_failures += 1
                    should_flip = self._heartbeat_failures >= 3
                    if self._heartbeat_failures < 3:
                        logger.debug("Device %s: heartbeat fail (%d/3)", self._name, self._heartbeat_failures)
                else:
                    self._heartbeat_failures = 0
                    should_flip = False
            if should_flip:
                logger.warning("Device %s: %d consecutive heartbeat failures, going offline", self._name, self._heartbeat_failures)
                self._set_status("offline")
                return

    def health_check(self) -> bool:
        if self._status != "online" or self._poco is None:
            return False
        try:
            ok = self._poco.heartbeat()
        except Exception:
            ok = False
        if not ok:
            logger.warning("Device %s: health check failed, going offline", self._name)
            with self._lock:
                self._heartbeat_failures = 3
            self._set_status("offline")
        return ok

    def disconnect(self) -> None:
        self._stop_event.set()
        if self._heartbeat_thread is not None:
            self._heartbeat_thread.join(timeout=2.0)
            self._heartbeat_thread = None
        if self._poco is not None:
            try:
                self._poco.close()
            except Exception:
                logger.debug("Device %s: poco close failed during disconnect", self._name, exc_info=True)
            self._poco = None
        try:
            self._forwarder.stop()
        except Exception:
            logger.debug("Device %s: forwarder stop failed during disconnect", self._name, exc_info=True)
        self._set_status("disconnected")
