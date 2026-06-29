from typing import Any, Optional


class PocoError(Exception):
    """Base class for all Poco-related errors."""


class PocoConnectionError(PocoError):
    """TCP connection failed or was dropped."""


class PocoTimeoutError(PocoError):
    """A request did not complete within the timeout."""


class PocoProtocolError(PocoError):
    """Wire protocol violation (bad JSON, version mismatch, frame too large)."""


class PocoRemoteError(PocoError):
    """The server returned a JSON-RPC error response."""

    def __init__(self, code: int, message: str, data: Optional[Any] = None):
        super().__init__(f"[{code}] {message}")
        self.code = code
        self.message = message
        self.data = data


class PocoNodeNotFoundError(PocoError):
    """A referenced node id no longer exists on the server."""


class DeviceError(Exception):
    """Base class for all device-layer errors (connection, forwarding, discovery)."""


class ForwarderError(DeviceError):
    """Port forwarding failed (adb error, bad stdout, adb not in PATH)."""


class DeviceDiscoveryError(DeviceError):
    """Device discovery failed (adb devices parse error, port probe error)."""
