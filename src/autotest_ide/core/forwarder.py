from abc import ABC, abstractmethod
from typing import Optional

import subprocess

from autotest_ide.core.errors import ForwarderError


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
        pass

    def stop(self) -> None:
        pass


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
            return
        cmd = self._adb_path + [
            "-s", self._device_serial,
            "forward", "--remove", f"tcp:{self._local_port}",
        ]
        try:
            subprocess.run(cmd, capture_output=True, timeout=5, text=True)
        except (OSError, subprocess.TimeoutExpired):
            pass  # best-effort, never raise
        self._local_port = None
