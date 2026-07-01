"""Abstract base class for Poco protocol adapters.

Different game SDKs speak different wire protocols over the same TCP
socket.  A ``PocoProtocol`` adapter encapsulates:

* How to **encode** a request (text command, JSON-RPC, custom binary …)
* How to **decode** a response (length-prefixed JSON, raw binary, …)
* How to **handshake** after TCP connect (getServerVersion, Dump, …)
* How to **map** public method names to the wire-format method names
"""

from __future__ import annotations

from abc import ABC, abstractmethod
import socket
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from autotest_ide.core.poco_client import PocoClient


class PocoProtocol(ABC):
    """Interface that every protocol adapter must implement."""

    # Subclasses override this to map Python API names → wire method names.
    # Keys are the public PocoClient method names (snake_case).
    # Values are what the agent on the other side of the socket expects.
    METHOD_MAP: dict[str, str] = {}

    def resolve_method(self, name: str) -> str:
        """Translate a public API name to the wire method name.

        Falls back to returning *name* unchanged when no mapping exists.
        """
        return self.METHOD_MAP.get(name, name)

    @abstractmethod
    def send_request(
        self,
        sock: socket.socket,
        method: str,
        args: tuple,
        kwargs: dict,
    ) -> None:
        """Encode and send one request on *sock*.

        *method* has already been resolved via ``resolve_method``.
        """

    @abstractmethod
    def read_response(
        self,
        sock: socket.socket,
        expect_binary: bool,
    ) -> Any:
        """Read one response from *sock*.

        Returns the decoded payload.  For binary responses this is ``bytes``;
        for JSON responses it is the parsed Python object (dict/list/str/…).
        Must raise ``PocoConnectionError`` on clean EOF and
        ``PocoProtocolError`` on malformed data.
        """

    @abstractmethod
    def handshake(self, client: PocoClient) -> str | None:
        """Perform the post-connect handshake.

        *client* is the owning ``PocoClient``; use ``client._request_json``
        (or the lower-level ``_request``) to send/receive on the socket.

        Returns the server version string, or ``None`` if unavailable.
        """

    def create_connection(
        self,
        host: str,
        port: int,
        timeout: float = 5.0,
    ) -> tuple[socket.socket, int]:
        """Create a TCP connection to the agent.

        Default: single port, ``socket.create_connection``.
        Protocols that need port-scanning (e.g. JX4) override this.

        Returns ``(connected_socket, actual_port)``.
        """
        sock = socket.create_connection((host, port), timeout=timeout)
        return sock, port

    def before_close(self, sock: socket.socket) -> None:
        """Hook called before the socket is closed.

        Default: no-op. Protocols that need to send a farewell command
        (e.g. JX4's ``CloseConnection``) override this.
        """
        return None

    def transform_result(self, method: str, result: Any) -> Any:
        """Post-process a decoded response before returning it to the caller.

        *method* is the public API name (e.g. ``"dump_hierarchy"``).
        Default: identity.  Protocols whose wire format differs from the
        expected internal structure override this (e.g. JX4 hierarchy
        conversion).
        """
        return result
