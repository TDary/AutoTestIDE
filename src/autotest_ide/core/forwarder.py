import re
import shutil
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

import subprocess

from autotest_ide.core.errors import ForwarderError
from autotest_ide.core.log import getLogger

logger = getLogger(__name__)

_SERIAL_RE = re.compile(r"^[a-zA-Z0-9_.:;-]+$")


def resolve_adb_path(adb_path: Optional[list] = None) -> list:
    if adb_path is not None:
        return adb_path
    resolved = shutil.which("adb")
    if resolved:
        logger.info("Resolved adb to: %s", resolved)
        return [str(Path(resolved).resolve())]
    return ["adb"]


def validate_serial(serial: str) -> None:
    if not serial or not _SERIAL_RE.match(serial):
        raise ForwarderError(f"invalid device serial: {serial!r}")


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

    def __init__(self, local_port: int = 13000):
        self._local_port = local_port

    @property
    def local_port(self) -> int:
        return self._local_port

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass


class AdbForwarder(PortForwarder):
    """Android USB forwarder. Uses `adb forward tcp:0` for dynamic local port."""

    def __init__(self, device_serial: str, remote_port: int = 13000,
                 adb_path: Optional[list] = None):
        validate_serial(device_serial)
        self._device_serial = device_serial
        self._remote_port = remote_port
        self._adb_path = resolve_adb_path(adb_path)
        self._local_port: Optional[int] = None

    @property
    def local_port(self) -> int:
        if self._local_port is None:
            raise ForwarderError("forwarder not started")
        return self._local_port

    def _ensure_adb_server(self) -> None:
        """Kill stale ADB daemon and restart it."""
        for cmd in [self._adb_path + ["kill-server"],
                     self._adb_path + ["start-server"]]:
            try:
                subprocess.run(cmd, capture_output=True, timeout=5, text=True)
            except (OSError, subprocess.TimeoutExpired):
                logger.debug("adb command %s failed (non-fatal)", cmd)

    def start(self) -> None:
        self._ensure_adb_server()
        cmd = self._adb_path + [
            "-s", self._device_serial,
            "forward", "tcp:0", f"tcp:{self._remote_port}",
        ]
        logger.info("AdbForwarder start: %s", " ".join(cmd))
        try:
            result = subprocess.run(
                cmd, capture_output=True, timeout=10, text=True,
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
        logger.info("AdbForwarder started: local_port=%d", self._local_port)

    def stop(self) -> None:
        if self._local_port is None:
            return
        cmd = self._adb_path + [
            "-s", self._device_serial,
            "forward", "--remove", f"tcp:{self._local_port}",
        ]
        logger.debug("AdbForwarder stop: %s", " ".join(cmd))
        try:
            subprocess.run(cmd, capture_output=True, timeout=5, text=True)
        except (OSError, subprocess.TimeoutExpired):
            logger.debug("AdbForwarder stop failed", exc_info=True)
        self._local_port = None
