"""Standard Poco text-command protocol adapter.

Request wire format::

    CommandName arg1 arg2 key1=val1 \\n

Response wire format::

    4-byte big-endian length + payload (UTF-8 JSON or raw binary)

This is the default protocol used by most Poco agents (Unity, Cocos, etc.).
"""

from __future__ import annotations

import socket
from typing import Any

from autotest_ide.core.errors import PocoConnectionError, PocoProtocolError
from autotest_ide.core.protocol import (
    encode_command,
    read_binary_frame,
    read_json_frame,
)
from autotest_ide.core.protocol_base import PocoProtocol


class PocoTextProtocol(PocoProtocol):
    """Text-command protocol (the Poco standard)."""

    METHOD_MAP = {
        "dump_hierarchy": "Dump",
        "get_attributes": "GetNodeAttr",
        "inspect_by_point": "Inspect",
        "click": "Click",
        "set_text": "SetText",
        "screenshot": "GetScreen",
    }

    def send_request(
        self,
        sock: socket.socket,
        method: str,
        args: tuple,
        kwargs: dict,
    ) -> None:
        parts = [method]
        parts.extend(str(a) for a in args)
        for k, v in kwargs.items():
            parts.append(f"{k}={v}")
        sock.sendall(encode_command(*parts))

    def read_response(
        self,
        sock: socket.socket,
        expect_binary: bool,
    ) -> Any:
        if expect_binary:
            data = read_binary_frame(sock)
            if not data:
                raise PocoConnectionError("connection closed")
            return data
        return read_json_frame(sock)

    def handshake(self, client: Any) -> str | None:
        from autotest_ide.core.errors import PocoTimeoutError

        try:
            result = client._request_json("getServerVersion")
        except PocoTimeoutError:
            raise PocoConnectionError(
                "handshake failed: Poco service did not respond to getServerVersion"
            )
        if isinstance(result, str):
            return result
        if isinstance(result, dict) and "version" in result:
            return result["version"]
        return str(result) if result else None
