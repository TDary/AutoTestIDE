import atexit
import socket
import subprocess
from typing import Optional

from autotest_ide.core.device import Device
from autotest_ide.core.errors import DeviceDiscoveryError
from autotest_ide.core.forwarder import AdbForwarder, DirectForwarder, LocalForwarder, resolve_adb_path
from autotest_ide.core.log import getLogger
from autotest_ide.core.protocol_base import PocoProtocol

logger = getLogger(__name__)


class DeviceManager:
    """Manages device discovery and the single active Device."""

    def __init__(self, adb_path: Optional[list] = None):
        self._adb_path = resolve_adb_path(adb_path)
        self._devices: list = []
        self._active = None
        self._atexit_registered = False

    # --- discovery (spec §4.2) ---

    def _ensure_adb_server(self) -> None:
        """Kill any stale ADB daemon, then start a fresh one."""
        for cmd in [self._adb_path + ["kill-server"],
                     self._adb_path + ["start-server"]]:
            try:
                subprocess.run(cmd, capture_output=True, timeout=5, text=True)
            except (OSError, subprocess.TimeoutExpired):
                logger.debug("adb command %s failed (non-fatal)", cmd)

    def list_android_devices(self) -> list:
        self._ensure_adb_server()
        cmd = self._adb_path + ["devices", "-l"]
        try:
            result = subprocess.run(cmd, capture_output=True, timeout=10, text=True)
        except (OSError, subprocess.TimeoutExpired) as e:
            raise DeviceDiscoveryError(f"adb devices failed: {e}") from e
        if result.returncode != 0:
            raise DeviceDiscoveryError(
                f"adb devices exited {result.returncode}: {result.stderr.strip()}"
            )
        devices = self._parse_devices_output(result.stdout)
        logger.info("ADB discovery found %d device(s)", len(devices))
        return devices

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
            if state == "device":
                entry = {"serial": serial, "state": state}
                for tok in tokens[2:]:
                    if ":" in tok:
                        k, v = tok.split(":", 1)
                        entry[k] = v
                devices.append(entry)
            elif state in ("unauthorized", "offline"):
                devices.append({"serial": serial, "state": state, "model": f"({state})"})
        return devices

    def list_local_devices(self, ports: Optional[list] = None) -> list:
        if ports is None:
            ports = [13000, 13001, 13002]
        found = []
        for port in ports:
            try:
                s = socket.create_connection(("127.0.0.1", port), timeout=0.5)
                s.close()
                found.append({"host": "127.0.0.1", "port": port})
            except OSError:
                logger.debug("Local port %d not listening", port)
                continue
        logger.info("Local discovery found %d device(s)", len(found))
        return found

    # --- active device management ---

    def connect_android(self, serial: str, remote_port: int = 13000,
                        name: Optional[str] = None,
                        protocol: Optional[PocoProtocol] = None) -> Device:
        logger.info("Connecting android device serial=%s remote_port=%d", serial, remote_port)
        # Use protocol's declared remote ports (e.g. JX4 scans 13000-13004)
        remote_ports = None
        if protocol is not None:
            remote_ports = protocol.get_default_remote_ports()
        fwd = AdbForwarder(device_serial=serial, remote_port=remote_port,
                           remote_ports=remote_ports,
                           adb_path=self._adb_path)
        device = Device(name=name or serial, device_type="android", forwarder=fwd,
                        protocol=protocol)
        device.connect()
        self._active = device
        self._devices.append(device)
        self._register_atexit()
        return device

    def connect_local(self, port: int, name: Optional[str] = None,
                      protocol: Optional[PocoProtocol] = None) -> Device:
        logger.info("Connecting local device port=%d", port)
        fwd = LocalForwarder(local_port=port)
        device = Device(name=name or f"localhost:{port}", device_type="windows",
                        forwarder=fwd, protocol=protocol)
        device.connect()
        self._active = device
        self._devices.append(device)
        self._register_atexit()
        return device

    def connect_ip(self, host: str, port: int = 13000,
                   name: Optional[str] = None,
                   protocol: Optional[PocoProtocol] = None) -> Device:
        logger.info("Connecting IP device host=%s port=%d", host, port)
        fwd = DirectForwarder(host=host, port=port)
        device = Device(name=name or f"{host}:{port}", device_type="remote",
                        forwarder=fwd, protocol=protocol)
        device.connect()
        self._active = device
        self._devices.append(device)
        self._register_atexit()
        return device

    @property
    def active(self) -> Optional[Device]:
        return self._active

    def disconnect_active(self) -> None:
        logger.info("Disconnecting active device")
        if self._active is not None:
            self._active.disconnect()
            self._devices = [d for d in self._devices if d is not self._active]
            self._active = None

    def shutdown(self) -> None:
        logger.info("DeviceManager shutdown")
        for device in self._devices:
            try:
                device.disconnect()
            except Exception:
                logger.warning("Failed to disconnect device %s during shutdown", device.name, exc_info=True)
        self._active = None

    def _register_atexit(self) -> None:
        if not self._atexit_registered:
            atexit.register(self.shutdown)
            self._atexit_registered = True
