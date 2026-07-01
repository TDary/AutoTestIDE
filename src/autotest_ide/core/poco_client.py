import socket
import threading
from collections import Counter, deque
from concurrent.futures import Future
from typing import Any, Optional

from autotest_ide.core.errors import (
    PocoConnectionError,
    PocoError,
    PocoRemoteError,
    PocoTimeoutError,
)
from autotest_ide.core.log import getLogger
from autotest_ide.core.protocol_base import PocoProtocol
from autotest_ide.core.protocol_poco import PocoTextProtocol

logger = getLogger(__name__)

DEFAULT_TIMEOUT = 10.0


class PocoClient:
    """Synchronous TCP client with pluggable protocol adapters.

    Manages socket lifecycle, threading, and FIFO request/response
    matching.  The protocol adapter (``PocoProtocol``) owns the wire
    format: how requests are encoded, how responses are decoded, and
    how the post-connect handshake works.
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 13000,
        protocol: Optional[PocoProtocol] = None,
    ):
        self._host = host
        self._port = port
        self._protocol = protocol or PocoTextProtocol()
        self._sock: Optional[socket.socket] = None
        self._send_lock = threading.Lock()
        self._pending: deque[tuple[Future, bool]] = deque()
        self._pending_cond = threading.Condition()
        self._recv_thread: Optional[threading.Thread] = None
        self._closed = True
        self.server_version: Optional[str] = None
        self.protocol_version: Optional[str] = None

    @property
    def port(self) -> int:
        return self._port

    @property
    def protocol(self) -> PocoProtocol:
        return self._protocol

    def connect(self):
        try:
            sock, actual_port = self._protocol.create_connection(
                self._host, self._port,
            )
            self._sock = sock
            self._port = actual_port
            # Keep the protocol's timeout (e.g. JX4 sets 60s) active during
            # handshake so a slow server doesn't hang forever. The recv loop
            # below switches to blocking mode after handshake succeeds.
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
        # After handshake, switch to blocking mode for the recv loop.
        # The protocol's read_response() does blocking recv() calls.
        self._sock.settimeout(None)
        logger.info("PocoClient connected %s:%d version=%s",
                     self._host, self._port, self.server_version)

    def _handshake(self):
        self.server_version = self._protocol.handshake(self)
        self.protocol_version = "v1"

    def close(self):
        self._closed = True
        with self._pending_cond:
            self._pending_cond.notify_all()
        if self._sock is not None:
            # Let the protocol send a farewell command (e.g. JX4 CloseConnection)
            # before we close the socket. Best-effort — never block on errors.
            try:
                self._protocol.before_close(self._sock)
            except Exception:
                logger.debug("before_close hook failed", exc_info=True)
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None
        self._drain_pending(PocoConnectionError("client closed"))

    def _drain_pending(self, exc: Exception):
        with self._pending_cond:
            for future, _ in self._pending:
                if not future.done():
                    future.set_exception(exc)
            self._pending.clear()

    def _request_json(self, method: str, *args, **kwargs) -> Any:
        return self._request(method, args, kwargs, expect_binary=False)

    def _request_binary(self, method: str, *args, **kwargs) -> bytes:
        return self._request(method, args, kwargs, expect_binary=True)

    def _request(self, method: str, args: tuple, kwargs: dict,
                 expect_binary: bool, timeout: float = DEFAULT_TIMEOUT):
        if self._closed:
            raise PocoConnectionError("client closed")
        wire_method = self._protocol.resolve_method(method)
        future: Future = Future()
        with self._pending_cond:
            self._pending.append((future, expect_binary))
            self._pending_cond.notify_all()
        with self._send_lock:
            try:
                self._protocol.send_request(self._sock, wire_method, args, kwargs)
            except OSError as e:
                with self._pending_cond:
                    for i, (f, _) in enumerate(self._pending):
                        if f is future:
                            del self._pending[i]
                            break
                logger.warning("PocoClient send failed: %s", e)
                raise PocoConnectionError(f"send failed: {e}")
        try:
            result = future.result(timeout=timeout)
            return self._protocol.transform_result(method, result)
        except TimeoutError:
            with self._pending_cond:
                for i, (f, _) in enumerate(self._pending):
                    if f is future:
                        del self._pending[i]
                        break
            self.close()
            logger.warning("PocoClient %s timed out after %ss", wire_method, timeout)
            raise PocoTimeoutError(f"{wire_method} timed out after {timeout}s")

    def _recv_loop(self):
        while not self._closed:
            with self._pending_cond:
                if not self._pending:
                    self._pending_cond.wait()
                if self._closed:
                    break
                future, expect_binary = self._pending.popleft()
            try:
                result = self._protocol.read_response(self._sock, expect_binary)
                if isinstance(result, dict) and "error" in result:
                    err = result["error"]
                    if isinstance(err, dict):
                        exc = PocoRemoteError(
                            err.get("code", -1),
                            err.get("message", ""),
                            err.get("data"),
                        )
                    else:
                        exc = PocoRemoteError(-1, str(err), None)
                    future.set_exception(exc)
                else:
                    future.set_result(result)
            except (ConnectionError, OSError) as e:
                logger.debug("PocoClient recv connection error: %s", e)
                future.set_exception(PocoConnectionError(str(e)))
                self._drain_pending(PocoConnectionError(str(e)))
                self.close()
                break
            except Exception as e:
                logger.warning("PocoClient recv unexpected error: %s", e, exc_info=True)
                future.set_exception(e)
                self._drain_pending(e)
                self.close()
                break

    # --- public protocol methods ---

    def get_root(self) -> dict:
        return self.dump_hierarchy()

    def dump_hierarchy(self, only_visible: bool = True) -> dict:
        return self._request_json("dump_hierarchy", onlyVisibleNode=only_visible)

    def get_attributes(self, node_id: str, attr: str = "") -> dict:
        if attr:
            return self._request_json("get_attributes", node_id, attr)
        return self._request_json("get_attributes", node_id)

    def inspect_by_point(self, x: int, y: int) -> dict:
        return self._request_json("inspect_by_point", x, y)

    def screenshot(self) -> bytes:
        local = self._protocol.capture_screenshot()
        if local is not None:
            return local
        return self._request_binary("screenshot")

    def heartbeat(self) -> bool:
        if self._closed:
            return False
        with self._pending_cond:
            has_pending = bool(self._pending)
        if has_pending:
            return True
        try:
            self._request_json("getServerVersion", timeout=3.0)
            return True
        except PocoError:
            logger.debug("PocoClient heartbeat failed")
            return False

    def click(self, x: int, y: int) -> dict:
        return self._request_json("click", x, y)

    def set_text(self, node_id: str, text: str) -> dict:
        return self._request_json("set_text", node_id, text)

    def _flatten_tree(self, root: dict) -> list:
        nodes = []
        stack = [root]
        while stack:
            node = stack.pop()
            nodes.append(node)
            stack.extend(reversed(node.get("children", [])))
        return nodes
