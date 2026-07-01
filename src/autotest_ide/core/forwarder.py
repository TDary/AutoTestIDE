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
        return [resolved]
    # Common install locations on Windows
    for candidate in [
        Path("F:/platform-tools/adb.exe"),
        Path("D:/platform-tools/adb.exe"),
        Path("C:/platform-tools/adb.exe"),
        Path("D:/AndroidSDK/platform-tools/adb.exe"),
    ]:
        if candidate.exists():
            return [str(candidate)]
    raise ForwarderError("adb not found on PATH")


def validate_serial(serial: str) -> None:
    if not _SERIAL_RE.match(serial):
        raise ForwarderError(f"invalid device serial: {serial!r}")


class PortForwarder(ABC):
    @property
    @abstractmethod
    def local_port(self) -> int:
        pass

    @abstractmethod
    def start(self) -> None:
        pass

    @abstractmethod
    def stop(self) -> None:
        pass


class LocalForwarder(PortForwarder):
    def __init__(self, local_port: int):
        self._local_port = local_port

    @property
    def local_port(self) -> int:
        return self._local_port

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass


class DirectForwarder(PortForwarder):
    """No-op forwarder for direct IP connections (no adb)."""

    def __init__(self, host: str, port: int):
        self._host = host
        self._local_port = port

    @property
    def host(self) -> str:
        return self._host

    @property
    def local_port(self) -> int:
        return self._local_port

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass


class AdbForwarder(PortForwarder):
    """Android USB forwarder. Uses `adb forward tcp:0` for dynamic local port.

    Supports remote port-scanning: if the agent may listen on any of
    several consecutive ports, pass *remote_ports* as a list.
    """

    def __init__(self, device_serial: str, remote_port: int = 13000,
                 remote_ports: Optional[list[int]] = None,
                 adb_path: Optional[list] = None):
        validate_serial(device_serial)
        self._device_serial = device_serial
        self._remote_port = remote_port
        self._remote_ports = remote_ports or [remote_port]
        self._adb_path = resolve_adb_path(adb_path)
        self._local_port: Optional[int] = None

    @property
    def local_port(self) -> int:
        if self._local_port is None:
            raise ForwarderError("AdbForwarder not started")
        return self._local_port

    @property
    def remote_port(self) -> int:
        return self._remote_port

    def _ensure_adb_server(self) -> None:
        for cmd in [self._adb_path + ["kill-server"],
                     self._adb_path + ["start-server"]]:
            try:
                subprocess.run(cmd, capture_output=True, timeout=5, text=True)
            except (OSError, subprocess.TimeoutExpired):
                logger.debug("adb command %s failed (non-fatal)", cmd)

    def start(self) -> None:
        self._ensure_adb_server()
        last_error = None
        for remote_port in self._remote_ports:
            cmd = self._adb_path + [
                "-s", self._device_serial,
                "forward", "tcp:0", f"tcp:{remote_port}",
            ]
            logger.info("AdbForwarder start: %s", " ".join(cmd))
            try:
                result = subprocess.run(
                    cmd, capture_output=True, timeout=10, text=True,
                )
            except (OSError, subprocess.TimeoutExpired) as e:
                last_error = ForwarderError(f"adb forward failed: {e}")
                logger.debug("adb forward to %d failed: %s", remote_port, e)
                continue
            if result.returncode != 0:
                last_error = ForwarderError(
                    f"adb forward failed: {result.stderr.strip()}"
                )
                logger.debug("adb forward to %d failed: %s", remote_port, result.stderr.strip())
                continue
            stdout = result.stdout.strip()
            if not stdout.isdigit():
                last_error = ForwarderError(
                    f"adb forward returned non-numeric port: {stdout!r}"
                )
                continue
            self._local_port = int(stdout)
            self._remote_port = remote_port
            logger.info("AdbForwarder started: local_port=%d remote_port=%d",
                        self._local_port, self._remote_port)
            return
        raise last_error or ForwarderError("adb forward failed: all remote ports exhausted")

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
