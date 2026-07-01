import ipaddress
import socket
import threading
from collections import Counter
from concurrent.futures import Future
from typing import Optional

from autotest_ide.core.errors import (
    PocoConnectionError,
    PocoError,
    PocoProtocolError,
    PocoRemoteError,
    PocoTimeoutError,
)
from autotest_ide.core.log import getLogger
from autotest_ide.core.protocol import (
    encode_json_frame,
    read_binary_frame,
    read_json_frame,
)

logger = getLogger(__name__)

DEFAULT_TIMEOUT = 5.0
CLIENT_VERSION = "1.0"
PROTOCOL_VERSION = "v1"


def _is_loopback(host: str) -> bool:
    try:
        addr = ipaddress.ip_address(socket.gethostbyname(host))
        return addr.is_loopback
    except (ValueError, socket.gaierror):
        return False


class PocoClient:
    """Synchronous client for the Poco JSON-RPC protocol over TCP.

    Supports multiple in-flight requests: the recv loop dispatches
    responses by their ``id`` field, so heartbeat no longer blocks
    screenshots.
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 13000):
        self._host = host
        self._port = port
        if not _is_loopback(host):
            raise PocoConnectionError(
                f"only loopback addresses are allowed, got {host!r}"
            )
        self._sock: Optional[socket.socket] = None
        self._seq = 0
        self._seq_lock = threading.Lock()
        self._send_lock = threading.Lock()
        self._pending: dict[int, Future] = {}          # seq -> Future (JSON)
        self._pending_binary: dict[int, Future] = {}    # seq -> Future (binary)
        self._pending_cond = threading.Condition()
        self._recv_thread: Optional[threading.Thread] = None
        self._closed = True
        self.server_version: Optional[str] = None
        self.protocol_version: Optional[str] = None

    @property
    def port(self) -> int:
        return self._port

    def connect(self):
        try:
            self._sock = socket.create_connection((self._host, self._port), timeout=5)
            self._sock.settimeout(None)
            self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            if hasattr(socket, "SIO_KEEPALIVE_VALS"):
                self._sock.ioctl(socket.SIO_KEEPALIVE_VALS, (1, 10000, 3000))
        except OSError as e:
            logger.warning("PocoClient connect failed %s:%d: %s", self._host, self._port, e)
            raise PocoConnectionError(f"connect failed: {e}")
        self._closed = False
        self._recv_thread = threading.Thread(target=self._recv_loop, daemon=True)
        self._recv_thread.start()
        self._handshake()
        logger.info("PocoClient connected %s:%d server=%s protocol=%s",
                     self._host, self._port, self.server_version, self.protocol_version)

    def _handshake(self):
        result = self._request_json("hello", {
            "client_version": CLIENT_VERSION,
            "protocols": [PROTOCOL_VERSION],
        })
        if result.get("protocol") != PROTOCOL_VERSION:
            raise PocoProtocolError(
                f"protocol mismatch: server={result.get('protocol')!r}, client={PROTOCOL_VERSION!r}"
            )
        self.server_version = result.get("server_version")
        self.protocol_version = result.get("protocol")

    def close(self):
        self._closed = True
        with self._pending_cond:
            self._pending_cond.notify_all()
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None
        self._drain_pending(PocoConnectionError("client closed"))

    def _drain_pending(self, exc: Exception):
        with self._pending_cond:
            for f in list(self._pending.values()):
                if not f.done():
                    f.set_exception(exc)
            self._pending.clear()
            for f in list(self._pending_binary.values()):
                if not f.done():
                    f.set_exception(exc)
            self._pending_binary.clear()

    def _next_seq(self) -> int:
        with self._seq_lock:
            self._seq += 1
            return self._seq

    def _request_json(self, method: str, params: dict, timeout: float = DEFAULT_TIMEOUT) -> dict:
        return self._request(method, params, timeout, expect_binary=False)

    def _request(self, method: str, params: dict, timeout: float, expect_binary: bool):
        if self._closed:
            raise PocoConnectionError("client closed")
        with self._send_lock:
            seq = self._next_seq()
            future: Future = Future()
            with self._pending_cond:
                if expect_binary:
                    self._pending_binary[seq] = future
                else:
                    self._pending[seq] = future
                self._pending_cond.notify_all()
            payload = {"jsonrpc": "2.0", "id": seq, "method": method, "params": params}
            try:
                self._sock.sendall(encode_json_frame(payload))
            except OSError as e:
                with self._pending_cond:
                    self._pending.pop(seq, None)
                    self._pending_binary.pop(seq, None)
                logger.warning("PocoClient send failed: %s", e)
                raise PocoConnectionError(f"send failed: {e}")
        try:
            return future.result(timeout=timeout)
        except TimeoutError:
            with self._pending_cond:
                self._pending.pop(seq, None)
                self._pending_binary.pop(seq, None)
            self.close()
            logger.warning("PocoClient %s timed out after %ss", method, timeout)
            raise PocoTimeoutError(f"{method} timed out after {timeout}s")

    def _recv_loop(self):
        while not self._closed:
            with self._pending_cond:
                if not self._pending and not self._pending_binary:
                    self._pending_cond.wait()
                if self._closed:
                    break
            try:
                msg = read_json_frame(self._sock)
                seq = msg.get("id")
                if seq is None:
                    continue
                if "error" in msg:
                    err = msg["error"]
                    exc = PocoRemoteError(
                        err.get("code", -1),
                        err.get("message", ""),
                        err.get("data"),
                    )
                else:
                    exc = None
                with self._pending_cond:
                    if seq in self._pending_binary:
                        future = self._pending_binary.pop(seq)
                        if exc:
                            future.set_exception(exc)
                        else:
                            try:
                                data = read_binary_frame(self._sock)
                                if not data:
                                    future.set_exception(PocoConnectionError("connection closed"))
                                else:
                                    future.set_result(data)
                            except Exception as e:
                                future.set_exception(e)
                    elif seq in self._pending:
                        future = self._pending.pop(seq)
                        if exc:
                            future.set_exception(exc)
                        else:
                            future.set_result(msg.get("result", {}))
                    else:
                        logger.debug("Received response for unknown seq %d", seq)
            except (ConnectionError, OSError) as e:
                logger.debug("PocoClient recv connection error: %s", e)
                self._drain_pending(PocoConnectionError(str(e)))
                self.close()
                break
            except Exception as e:
                logger.warning("PocoClient recv unexpected error: %s", e, exc_info=True)
                self._drain_pending(e)
                self.close()
                break

    # --- public protocol methods ---

    def get_screen_size(self) -> dict:
        return self._request_json("get_screen_size", {})

    def get_root(self) -> dict:
        return self._request_json("get_root", {})

    def dump_hierarchy(self, depth: Optional[int] = None) -> dict:
        params = {}
        if depth is not None:
            params["depth"] = depth
        return self._request_json("dump_hierarchy", params)

    def get_attributes(self, node_id: str) -> dict:
        return self._request_json("get_attributes", {"node_id": node_id})

    def inspect_by_point(self, x: int, y: int) -> dict:
        return self._request_json("inspect_by_point", {"x": x, "y": y})

    def _request_binary(self, method: str, params: dict, timeout: float = DEFAULT_TIMEOUT) -> bytes:
        return self._request(method, params, timeout, expect_binary=True)

    def screenshot(self) -> bytes:
        ack = self._request_json("screenshot", {})
        binary_seq = ack["binary_seq"]
        return self._request_binary("binary_read", {"seq": binary_seq})

    def heartbeat(self) -> bool:
        """Cheap liveness probe. Returns True if the connection is alive.

        Uses TCP keepalive and pending-futures check instead of an
        explicit network round-trip. Never blocks other requests.
        """
        if self._closed:
            return False
        with self._pending_cond:
            has_pending = bool(self._pending or self._pending_binary)
        if has_pending:
            return True
        try:
            self._request_json("get_screen_size", {}, timeout=2.0)
            return True
        except PocoError:
            logger.debug("PocoClient heartbeat failed")
            return False

    def click(self, x: int, y: int) -> dict:
        return self._request_json("click", {"x": x, "y": y})

    def set_text(self, node_id: str, text: str) -> dict:
        return self._request_json("set_text", {"node_id": node_id, "text": text})
