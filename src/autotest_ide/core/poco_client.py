import socket
import struct
import threading
import time
from collections import deque
from concurrent.futures import Future
from typing import Any, Optional

from autotest_ide.core.errors import (
    PocoConnectionError,
    PocoError,
    PocoRemoteError,
    PocoTimeoutError,
)
from autotest_ide.core.locator import _flatten_nodes
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
        cache_ttl: float = 1.0,
    ):
        self._host = host
        self._port = port
        self._protocol = protocol or PocoTextProtocol()
        self._sock: Optional[socket.socket] = None
        self._send_lock = threading.Lock()
        self._close_lock = threading.Lock()
        self._pending: deque[tuple[Future, bool]] = deque()
        self._pending_cond = threading.Condition()
        self._recv_thread: Optional[threading.Thread] = None
        self._closed = True
        self.server_version: Optional[str] = None
        self.protocol_version: Optional[str] = None
        self._hier_cache: Optional[dict] = None
        self._hier_cache_ts: float = 0.0
        self._hier_cache_ttl: float = cache_ttl
        self._cache_lock = threading.Lock()

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
        """Close the TCP connection and stop the recv loop."""
        # Merge both _close_lock acquisitions into one so that _closed=True
        # and _sock=None happen atomically — no gap where another thread
        # sees _closed=True but _sock is still not None.
        with self._close_lock:
            if self._closed:
                return
            self._closed = True
            sock = self._sock
            self._sock = None
        # Wake recv loop so it can check _closed and exit.
        with self._pending_cond:
            self._pending_cond.notify_all()
        if sock is not None:
            # Send farewell command so the server can clean up (JX4: CloseConnection).
            # Best-effort — never block on errors.
            try:
                self._protocol.before_close(sock)
                # Half-close: tell server we're done writing.  This lets the
                # server read the farewell and close its side, avoiding CLOSE_WAIT.
                sock.shutdown(socket.SHUT_WR)
                # Drain any remaining data from the server briefly.
                sock.settimeout(1.0)
                try:
                    while sock.recv(4096):
                        pass
                except (socket.timeout, OSError):
                    pass
            except Exception:
                logger.debug("close/shutdown failed", exc_info=True)
            try:
                sock.close()
            except OSError:
                pass
        self._drain_pending(PocoConnectionError("client closed"))
        with self._cache_lock:
            self._hier_cache = None
            self._hier_cache_ts = 0.0
        if self._recv_thread is not None:
            if threading.current_thread() is not self._recv_thread:
                self._recv_thread.join(timeout=2.0)
            self._recv_thread = None

    # Backwards-compatible alias used by Device.disconnect()
    disconnect = close

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
        # Hold _send_lock while both appending to _pending and sending so
        # the FIFO order of futures matches the wire order of requests.
        # Without this, two threads can interleave append+send, causing
        # the recv loop to match a response to the wrong future.
        with self._send_lock:
            with self._pending_cond:
                self._pending.append((future, expect_binary))
                self._pending_cond.notify_all()
            try:
                self._protocol.send_request(self._sock, wire_method, args, kwargs)
            except OSError as e:
                # Mark the future as failed so the recv loop can skip it
                # when popped.  Do NOT try to delete from _pending by index —
                # the recv loop may have already popped earlier entries,
                # making indices stale and causing wrong-entry deletion.
                future.set_exception(PocoConnectionError(f"send failed: {e}"))
                logger.warning("PocoClient send failed: %s", e)
                raise PocoConnectionError(f"send failed: {e}")
        try:
            result = future.result(timeout=timeout)
            return self._protocol.transform_result(method, result)
        except TimeoutError:
            # Mark future as timed-out before close() so recv loop skips it.
            # close() will drain remaining pending futures; the timed-out
            # future is already done, so drain skips it — the caller gets
            # PocoTimeoutError from the raise below, not PocoConnectionError.
            future.set_exception(
                PocoTimeoutError(f"{wire_method} timed out after {timeout}s")
            )
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
            # Skip futures already resolved (timed out or send-failed).
            # The request was either never sent on the wire (send failure)
            # or the client is about to be closed (timeout), so there is
            # no response to consume from the socket — skipping keeps the
            # FIFO stream aligned for the next pending future.
            if future.done():
                continue
            # Snapshot socket under _close_lock to avoid crash if close()
            # nulls _sock between popleft and read_response.  Also re-check
            # _closed here — a concurrent close() may have set _closed=True
            # after the loop-top check but before this point.
            with self._close_lock:
                if self._closed or self._sock is None:
                    if not future.done():
                        future.set_exception(PocoConnectionError("client closed"))
                    break
                sock = self._sock
            try:
                result = self._protocol.read_response(sock, expect_binary)
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
                if not future.done():
                    future.set_exception(PocoConnectionError(str(e)))
                self._drain_pending(PocoConnectionError(str(e)))
                self.close()
                break
            except Exception as e:
                logger.warning("PocoClient recv unexpected error: %s", e, exc_info=True)
                if not future.done():
                    future.set_exception(e)
                self._drain_pending(e)
                self.close()
                break

    # --- public protocol methods ---

    def get_root(self) -> dict:
        return self.dump_hierarchy()

    def dump_hierarchy(self, only_visible: bool = True) -> dict:
        if only_visible and self._hier_cache_ttl > 0:
            with self._cache_lock:
                if self._hier_cache is not None:
                    if time.monotonic() - self._hier_cache_ts < self._hier_cache_ttl:
                        return self._hier_cache
        result = self._request_json("dump_hierarchy", onlyVisibleNode=only_visible)
        if only_visible:
            with self._cache_lock:
                self._hier_cache = result
                self._hier_cache_ts = time.monotonic()
        return result

    def get_attributes(self, node_id: str, attr: str = "") -> dict:
        if attr:
            return self._request_json("get_attributes", node_id, attr)
        return self._request_json("get_attributes", node_id)

    def inspect_by_point(self, x: int, y: int) -> dict:
        return self._request_json("inspect_by_point", x, y)

    def screenshot(self) -> bytes:
        result = self._protocol.capture_screenshot()
        if result is not None:
            return result
        # PocoTextProtocol etc. return None → fall back to TCP binary cmd
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

    def find_and_tap(
        self,
        path: str,
        camera: str = "",
        rml: int = -1,
        by: str = "path",
    ) -> dict:
        """Find a UI node and tap it (server-side find+tap).

        *path* is the lookup value. *by* selects the search strategy:

        - ``"path"`` (default) — hierarchy path like ``A/B/C``
        - ``"name"`` — By.NAME: ``A/B/C`` (same as path for JX4)
        - ``"tag"`` — By.TAG: ``//*[@tag=value]``
        - ``"layer"`` — By.LAYER: ``//*[@layer=value]``
        - ``"component"`` — By.COMPONENT: ``//*[@component=value]``
        - ``"id"`` — By.ID: *path* is passed as-is
        """
        if by == "tag":
            wire_path = f"//*[@tag={path}]"
        elif by == "layer":
            wire_path = f"//*[@layer={path}]"
        elif by == "component":
            wire_path = f"//*[@component={path}]"
        elif by == "id":
            wire_path = path
        else:
            wire_path = path
        enabled = "true"
        return self._request_json("find_and_tap", wire_path, camera, enabled, rml)

    def set_text(self, node_id: str, text: str) -> dict:
        return self._request_json("set_text", node_id, text)

    def long_click(self, x: int, y: int, duration: float = 2.0) -> dict:
        return self._request_json("long_click", x, y, duration)

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration: float = 0.5) -> dict:
        return self._request_json("swipe", x1, y1, x2, y2, duration)

    def drag(self, node_id: str, x2: int, y2: int) -> dict:
        return self._request_json("drag", node_id, x2, y2)

    def wait_for_node(self, path: str, timeout: float = 10.0) -> dict:
        return self._request_json("wait_for_node", path, timeout)

    def wait_for_gone(self, path: str, timeout: float = 10.0) -> dict:
        return self._request_json("wait_for_gone", path, timeout)

    def get_node_by_path(self, path: str) -> dict:
        return self._request_json("get_node_by_path", path)

    def _flatten_tree(self, root: dict) -> list:
        return _flatten_nodes([root])
