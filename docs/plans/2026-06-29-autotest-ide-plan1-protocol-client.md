# Plan 1: Protocol Layer + PocoClient Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the protocol layer (`core/protocol.py`), error hierarchy (`core/errors.py`), the synchronous PocoClient (`core/poco_client.py`), and a fake Poco server test fixture (`tests/fake_poco_server.py`) — all PyQt-free, fully unit-testable.

**Architecture:** TCP socket + JSON-RPC 2.0 over 4-byte-length-prefixed frames. Synchronous request/response (one outstanding request at a time, enforced by a send lock). A background recv thread resolves futures for timeout handling. Binary frames (for screenshot) are distinguished by per-request expectation flags, not by a wire type byte — this preserves the spec's "length prefix + payload" framing while keeping the recv loop unambiguous.

**Tech Stack:** Python 3.8+ stdlib only (socket, struct, json, threading, concurrent.futures). pytest for tests. No PyQt in this plan.

**Spec reference:** `docs/specs/2026-06-29-autotest-ide-clone-design.md` — sections 3 (protocol), 5 (PocoClient), 8 (tests).

**Project root:** `E:/AutoTestIDE/`. All paths below are relative to `E:/AutoTestIDE/`.

**Deviations from spec (noted for transparency):**
1. **No pipelining.** Spec section 5.2 implies async pipelined requests matched by seq. This plan implements synchronous (one-at-a-time) requests. Rationale: Phase 1 operations (UI tree refresh, pick point, heartbeat) don't need concurrency; synchronous design eliminates the binary-frame/seq-matching ambiguity cleanly. Pipelining can be added later without breaking the public API.
2. **Timeout closes the connection.** On timeout, the client closes the socket (connection is in an unknown state). This is heavier than spec section 5.2 implies but is safe and simple. Reconnect is the caller's responsibility (Device layer, Plan 2).
3. **`core/` uses `threading`, not QThread.** Spec section 5.2 mentions QThread for the recv loop, but section 9.1 says `core/` has no PyQt dependency. Resolved: `core/` uses `threading.Thread`; the Qt signal bridge lives in `ui/threads.py` (Plan 3).

---

## File Structure

```
E:/AutoTestIDE/
├── pyproject.toml                    # Task 1: package config (src layout)
├── README.md                         # Task 1: one-line description
├── requirements.txt                   # Task 1: runtime deps (empty for Plan 1)
├── requirements-dev.txt              # Task 1: pytest, ruff
├── src/
│   └── autotest_ide/
│       ├── __init__.py                # Task 1: version
│       └── core/
│           ├── __init__.py           # Task 1: empty
│           ├── errors.py             # Task 2: PocoError hierarchy
│           ├── protocol.py           # Tasks 3-4: frame encode/decode
│           └── poco_client.py         # Tasks 6-15: PocoClient
└── tests/
    ├── __init__.py                   # Task 1: empty
    ├── conftest.py                   # Task 5: shared fixtures
    ├── fake_poco_server.py           # Tasks 5,7,11,13: cumulative fake server
    ├── test_protocol.py              # Tasks 3-4
    ├── test_errors.py                # Task 2
    └── test_poco_client.py           # Tasks 6,8,9,10,12,14,15,16
```

---

## Task 1: Project Scaffolding

**Files:**
- Create: `E:/AutoTestIDE/pyproject.toml`
- Create: `E:/AutoTestIDE/README.md`
- Create: `E:/AutoTestIDE/requirements.txt`
- Create: `E:/AutoTestIDE/requirements-dev.txt`
- Create: `E:/AutoTestIDE/src/autotest_ide/__init__.py`
- Create: `E:/AutoTestIDE/src/autotest_ide/core/__init__.py`
- Create: `E:/AutoTestIDE/tests/__init__.py`

- [ ] **Step 1: Create directory structure**

Run from `E:/AutoTestIDE/`:

```bash
mkdir -p src/autotest_ide/core tests
```

- [ ] **Step 2: Write `pyproject.toml`**

```toml
[build-system]
requires = ["setuptools>=61"]
build-backend = "setuptools.build_meta"

[project]
name = "autotest-ide"
version = "0.1.0"
description = "UI automation IDE for games and apps (Poco protocol, no image recognition)"
requires-python = ">=3.8"
dependencies = []

[project.optional-dependencies]
dev = ["pytest>=7.0", "ruff>=0.1"]

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
```

- [ ] **Step 3: Write `requirements.txt`**

```
# Plan 1: no runtime dependencies (pure stdlib).
# PyQt5, QScintilla, Jinja2, psutil added in later plans.
```

- [ ] **Step 4: Write `requirements-dev.txt`**

```
pytest>=7.0
ruff>=0.1
```

- [ ] **Step 5: Write `src/autotest_ide/__init__.py`**

```python
__version__ = "0.1.0"
```

- [ ] **Step 6: Write `src/autotest_ide/core/__init__.py`**

```python
```

(empty file)

- [ ] **Step 7: Write `tests/__init__.py`**

```python
```

(empty file)

- [ ] **Step 8: Write `README.md`**

```markdown
# autotest-ide

UI automation IDE for games and apps. Uses the Poco UI-tree protocol (no image recognition).

See `docs/specs/2026-06-29-autotest-ide-clone-design.md` for the full design.
```

- [ ] **Step 9: Install package in editable mode**

Run from `E:/AutoTestIDE/`:

```bash
pip install -e .
```

Expected: successful install; `autotest_ide` importable.

- [ ] **Step 10: Verify scaffolding**

Run:

```bash
python -c "import autotest_ide; print(autotest_ide.__version__)"
```

Expected output: `0.1.0`

- [ ] **Step 11: Commit**

```bash
cd E:/AutoTestIDE
git init
git add pyproject.toml README.md requirements.txt requirements-dev.txt src/ tests/
git commit -m "chore: scaffold autotest-ide project (src layout, pytest)"
```

---

## Task 2: Error Hierarchy

**Files:**
- Create: `src/autotest_ide/core/errors.py`
- Test: `tests/test_errors.py`

- [ ] **Step 1: Write the failing test**

`tests/test_errors.py`:

```python
import pytest
from autotest_ide.core.errors import (
    PocoError,
    PocoConnectionError,
    PocoTimeoutError,
    PocoProtocolError,
    PocoRemoteError,
    PocoNodeNotFoundError,
)


def test_all_errors_subclass_poco_error():
    for exc in [
        PocoConnectionError("x"),
        PocoTimeoutError("x"),
        PocoProtocolError("x"),
        PocoRemoteError(1, "x"),
        PocoNodeNotFoundError("x"),
    ]:
        assert isinstance(exc, PocoError)


def test_poco_remote_error_carries_code_message_data():
    err = PocoRemoteError(code=-32601, message="method not found", data={"method": "foo"})
    assert err.code == -32601
    assert err.message == "method not found"
    assert err.data == {"method": "foo"}
    assert "[-32601]" in str(err)
    assert "method not found" in str(err)


def test_poco_remote_error_data_defaults_none():
    err = PocoRemoteError(code=1, message="boom")
    assert err.data is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_errors.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'autotest_ide.core.errors'`

- [ ] **Step 3: Write minimal implementation**

`src/autotest_ide/core/errors.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_errors.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add src/autotest_ide/core/errors.py tests/test_errors.py
git commit -m "feat(core): add PocoError hierarchy"
```

---

## Task 3: Protocol — Frame Encoding

**Files:**
- Create: `src/autotest_ide/core/protocol.py`
- Test: `tests/test_protocol.py`

- [ ] **Step 1: Write the failing test**

`tests/test_protocol.py`:

```python
import json
import struct

from autotest_ide.core.protocol import encode_json_frame


def test_encode_json_frame_includes_4_byte_length_prefix():
    payload = {"jsonrpc": "2.0", "id": 1, "method": "hello", "params": {}}
    frame = encode_json_frame(payload)
    assert len(frame) > 4
    (length,) = struct.unpack(">I", frame[:4])
    body = frame[4:]
    assert length == len(body)
    assert json.loads(body.decode("utf-8")) == payload


def test_encode_json_frame_uses_big_endian():
    payload = {"method": "ping"}
    frame = encode_json_frame(payload)
    (length,) = struct.unpack(">I", frame[:4])
    assert length == len(frame) - 4


def test_encode_json_frame_utf8_non_ascii():
    payload = {"method": "click", "params": {"name": "开始按钮"}}
    frame = encode_json_frame(payload)
    (length,) = struct.unpack(">I", frame[:4])
    body = frame[4:]
    assert json.loads(body.decode("utf-8"))["params"]["name"] == "开始按钮"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_protocol.py -v`
Expected: FAIL with `ImportError: cannot import name 'encode_json_frame'`

- [ ] **Step 3: Write minimal implementation**

`src/autotest_ide/core/protocol.py`:

```python
import json
import struct
from typing import Any

HEADER_SIZE = 4
MAX_FRAME_SIZE = 64 * 1024 * 1024  # 64 MB safety cap


def encode_json_frame(payload: dict) -> bytes:
    """Encode a dict as a length-prefixed UTF-8 JSON frame."""
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    return struct.pack(">I", len(body)) + body
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_protocol.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add src/autotest_ide/core/protocol.py tests/test_protocol.py
git commit -m "feat(core): add JSON frame encoding (4-byte big-endian length prefix)"
```

---

## Task 4: Protocol — Frame Reading

**Files:**
- Modify: `src/autotest_ide/core/protocol.py`
- Modify: `tests/test_protocol.py`

- [ ] **Step 1: Write the failing tests (append to `tests/test_protocol.py`)**

```python
import io
import socket
import threading

import pytest

from autotest_ide.core.protocol import read_exactly, read_frame, read_json_frame
from autotest_ide.core.errors import PocoProtocolError


def _make_socketpair_with_data(data: bytes):
    """Return a connected socket whose recv yields exactly `data` then EOF."""
    server, client = socket.socketpair()
    server.sendall(data)
    server.close()
    return client


def test_read_exactly_reads_all_bytes():
    sock = _make_socketpair_with_data(b"\x00\x00\x00\x05hello")
    assert read_exactly(sock, 4) == b"\x00\x00\x00\x05"
    assert read_exactly(sock, 5) == b"hello"


def test_read_exactly_returns_empty_on_eof():
    sock = _make_socketpair_with_data(b"")
    assert read_exactly(sock, 4) == b""


def test_read_frame_reads_length_prefixed_body():
    from autotest_ide.core.protocol import encode_json_frame
    frame = encode_json_frame({"method": "ping"})
    sock = _make_socketpair_with_data(frame)
    body = read_frame(sock)
    assert json.loads(body.decode("utf-8")) == {"method": "ping"}


def test_read_frame_empty_on_eof():
    sock = _make_socketpair_with_data(b"")
    assert read_frame(sock) == b""


def test_read_frame_rejects_oversized_frame():
    sock = _make_socketpair_with_data(struct.pack(">I", MAX_FRAME_SIZE + 1))
    with pytest.raises(PocoProtocolError, match="frame too large"):
        read_frame(sock)


def test_read_json_frame_returns_parsed_dict():
    from autotest_ide.core.protocol import encode_json_frame
    sock = _make_socketpair_with_data(encode_json_frame({"id": 1, "result": "ok"}))
    assert read_json_frame(sock) == {"id": 1, "result": "ok"}


def test_read_json_frame_raises_connection_error_on_eof():
    sock = _make_socketpair_with_data(b"")
    with pytest.raises(ConnectionError):
        read_json_frame(sock)


def test_read_json_frame_raises_protocol_error_on_bad_json():
    sock = _make_socketpair_with_data(struct.pack(">I", 3) + b"abc")
    with pytest.raises(PocoProtocolError):
        read_json_frame(sock)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_protocol.py -v`
Expected: FAIL with `ImportError: cannot import name 'read_exactly'`

- [ ] **Step 3: Extend implementation**

Replace `src/autotest_ide/core/protocol.py` with:

```python
import json
import struct
from typing import Any

from autotest_ide.core.errors import PocoProtocolError

HEADER_SIZE = 4
MAX_FRAME_SIZE = 64 * 1024 * 1024  # 64 MB safety cap


def encode_json_frame(payload: dict) -> bytes:
    """Encode a dict as a length-prefixed UTF-8 JSON frame."""
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    return struct.pack(">I", len(body)) + body


def read_exactly(sock, n: int) -> bytes:
    """Read exactly n bytes from sock. Returns b'' if the connection closes early."""
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            return b""
        buf.extend(chunk)
    return bytes(buf)


def read_frame(sock) -> bytes:
    """Read one length-prefixed frame body. Returns b'' on clean EOF."""
    header = read_exactly(sock, HEADER_SIZE)
    if not header:
        return b""
    (length,) = struct.unpack(">I", header)
    if length > MAX_FRAME_SIZE:
        raise PocoProtocolError(f"frame too large: {length}")
    if length == 0:
        return b""
    return read_exactly(sock, length)


def read_json_frame(sock) -> dict:
    """Read one frame and parse as JSON. Raises ConnectionError on EOF, PocoProtocolError on bad JSON."""
    body = read_frame(sock)
    if not body:
        raise ConnectionError("connection closed")
    try:
        return json.loads(body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise PocoProtocolError(f"invalid JSON frame: {e}")


def read_binary_frame(sock) -> bytes:
    """Read one frame as raw bytes. Returns b'' on clean EOF."""
    return read_frame(sock)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_protocol.py -v`
Expected: 11 passed (3 from Task 3 + 8 new)

- [ ] **Step 5: Commit**

```bash
git add src/autotest_ide/core/protocol.py tests/test_protocol.py
git commit -m "feat(core): add frame reading (read_exactly, read_frame, read_json_frame, read_binary_frame)"
```

---

## Task 5: Fake Poco Server v1 (hello + get_screen_size) + conftest

**Files:**
- Create: `tests/fake_poco_server.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Write the fake server**

`tests/fake_poco_server.py`:

```python
import threading
import time

from autotest_ide.core.protocol import encode_json_frame, read_json_frame

FIXED_UI_TREE = {
    "node_id": "root",
    "name": "Canvas",
    "type": "Canvas",
    "payload": {
        "visible": True,
        "visibleBounds": {"x": 0, "y": 0, "width": 1080, "height": 1920},
        "anchor": [0.5, 0.5],
        "text": "",
        "enabled": True,
        "attributes": {},
    },
    "children": [
        {
            "node_id": "btn_play",
            "name": "Button_Play",
            "type": "Button",
            "payload": {
                "visible": True,
                "visibleBounds": {"x": 440, "y": 900, "width": 200, "height": 120},
                "anchor": [0.5, 0.5],
                "text": "Play",
                "enabled": True,
                "attributes": {"unity_path": "/Canvas/Button_Play"},
            },
            "children": [],
        }
    ],
}

# A tiny 1x1 red PNG used for screenshot testing.
TINY_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108020000"
    "00907753de0000000c49444154759c63f8cf0000000200014891bf2b"
    "0000000049454e44ae426082"
)


class FakePocoServer:
    """A minimal Poco protocol server for tests. Listens on an ephemeral port."""

    def __init__(self, host: str = "127.0.0.1", port: int = 0):
        self._host = host
        self._port = port
        self._server_sock = None
        self._thread = None
        self._running = False
        self._client_sock = None
        self.delay = 0.0  # seconds to wait before responding (for timeout tests)
        self.drop_on_next = False  # if True, close the client connection on next request

    def start(self):
        import socket
        self._server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_sock.bind((self._host, self._port))
        self._server_sock.listen(1)
        self._port = self._server_sock.getsockname()[1]
        self._running = True
        self._thread = threading.Thread(target=self._accept_loop, daemon=True)
        self._thread.start()

    @property
    def host(self) -> str:
        return self._host

    @property
    def port(self) -> int:
        return self._port

    def stop(self):
        self._running = False
        if self._client_sock is not None:
            try:
                self._client_sock.close()
            except OSError:
                pass
            self._client_sock = None
        if self._server_sock is not None:
            try:
                self._server_sock.close()
            except OSError:
                pass
            self._server_sock = None

    def _accept_loop(self):
        while self._running:
            try:
                conn, _ = self._server_sock.accept()
            except OSError:
                return
            self._client_sock = conn
            self._serve_client(conn)
            try:
                conn.close()
            except OSError:
                pass
            self._client_sock = None

    def _serve_client(self, conn):
        while self._running:
            try:
                msg = read_json_frame(conn)
            except (ConnectionError, OSError):
                return
            if self.drop_on_next:
                try:
                    conn.close()
                except OSError:
                    pass
                self.drop_on_next = False
                return
            if self.delay > 0:
                time.sleep(self.delay)
            self._handle(conn, msg)

    def _handle(self, conn, msg):
        method = msg.get("method")
        seq = msg.get("id")
        response = self._dispatch(method, msg.get("params", {}), seq, conn)
        if response is None:
            return  # binary frame already sent
        try:
            conn.sendall(encode_json_frame(response))
        except OSError:
            return

    def _dispatch(self, method, params, seq, conn):
        if method == "hello":
            return {"jsonrpc": "2.0", "id": seq, "result": {
                "server_version": "fake-1.0",
                "protocol": "v1",
            }}
        if method == "get_screen_size":
            return {"jsonrpc": "2.0", "id": seq, "result": {"w": 1080, "h": 1920}}
        return {"jsonrpc": "2.0", "id": seq, "error": {
            "code": -32601, "message": f"method not found: {method}"
        }}
```

- [ ] **Step 2: Write conftest with a server fixture**

`tests/conftest.py`:

```python
import pytest

from tests.fake_poco_server import FakePocoServer


@pytest.fixture
def fake_server():
    server = FakePocoServer()
    server.start()
    yield server
    server.stop()
```

- [ ] **Step 3: Verify the fake server starts and accepts a connection**

Run:

```bash
python -c "
from tests.fake_poco_server import FakePocoServer
from autotest_ide.core.protocol import encode_json_frame, read_json_frame
s = FakePocoServer(); s.start()
import socket
sock = socket.create_connection((s.host, s.port), timeout=2)
sock.sendall(encode_json_frame({'jsonrpc':'2.0','id':1,'method':'hello','params':{}}))
print(read_json_frame(sock))
sock.sendall(encode_json_frame({'jsonrpc':'2.0','id':2,'method':'get_screen_size','params':{}}))
print(read_json_frame(sock))
sock.close(); s.stop()
"
```

Expected output:
```
{'jsonrpc': '2.0', 'id': 1, 'result': {'server_version': 'fake-1.0', 'protocol': 'v1'}}
{'jsonrpc': '2.0', 'id': 2, 'result': {'w': 1080, 'h': 1920}}
```

- [ ] **Step 4: Commit**

```bash
git add tests/fake_poco_server.py tests/conftest.py
git commit -m "test: add FakePocoServer fixture (hello + get_screen_size)"
```

---

## Task 6: PocoClient — Connect + Handshake + get_screen_size

**Files:**
- Create: `src/autotest_ide/core/poco_client.py`
- Create: `tests/test_poco_client.py`

- [ ] **Step 1: Write the failing test**

`tests/test_poco_client.py`:

```python
import pytest

from autotest_ide.core.errors import PocoConnectionError, PocoProtocolError
from autotest_ide.core.poco_client import PocoClient


def test_connect_and_handshake(fake_server):
    client = PocoClient(host=fake_server.host, port=fake_server.port)
    client.connect()
    try:
        assert client.server_version == "fake-1.0"
        assert client.protocol_version == "v1"
    finally:
        client.close()


def test_connect_refused_raises_connection_error():
    # port 1 is reserved, should refuse
    client = PocoClient(host="127.0.0.1", port=1)
    with pytest.raises(PocoConnectionError):
        client.connect()


def test_get_screen_size(fake_server):
    client = PocoClient(host=fake_server.host, port=fake_server.port)
    client.connect()
    try:
        assert client.get_screen_size() == {"w": 1080, "h": 1920}
    finally:
        client.close()


def test_handshake_protocol_mismatch_raises(fake_server, monkeypatch):
    # Force the client to advertise an unsupported protocol version
    monkeypatch.setattr("autotest_ide.core.poco_client.PROTOCOL_VERSION", "v99")
    client = PocoClient(host=fake_server.host, port=fake_server.port)
    with pytest.raises(PocoProtocolError, match="protocol mismatch"):
        client.connect()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_poco_client.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'autotest_ide.core.poco_client'`

- [ ] **Step 3: Write minimal implementation**

`src/autotest_ide/core/poco_client.py`:

```python
import socket
import threading
from concurrent.futures import Future
from typing import Optional

from autotest_ide.core.errors import (
    PocoConnectionError,
    PocoProtocolError,
    PocoRemoteError,
    PocoTimeoutError,
)
from autotest_ide.core.protocol import (
    encode_json_frame,
    read_binary_frame,
    read_json_frame,
)

DEFAULT_TIMEOUT = 5.0
CLIENT_VERSION = "1.0"
PROTOCOL_VERSION = "v1"


class PocoClient:
    """Synchronous client for the Poco JSON-RPC protocol over TCP."""

    def __init__(self, host: str = "127.0.0.1", port: int = 5001):
        self._host = host
        self._port = port
        self._sock: Optional[socket.socket] = None
        self._seq = 0
        self._seq_lock = threading.Lock()
        self._send_lock = threading.Lock()
        self._current: Optional[dict] = None  # {"future", "expect_binary"}
        self._request_event = threading.Event()
        self._recv_thread: Optional[threading.Thread] = None
        self._closed = True
        self.server_version: Optional[str] = None
        self.protocol_version: Optional[str] = None

    def connect(self):
        try:
            self._sock = socket.create_connection((self._host, self._port), timeout=5)
            self._sock.settimeout(None)
        except OSError as e:
            raise PocoConnectionError(f"connect failed: {e}")
        self._closed = False
        self._recv_thread = threading.Thread(target=self._recv_loop, daemon=True)
        self._recv_thread.start()
        self._handshake()

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
        self._request_event.set()  # wake the recv loop if it is waiting
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None

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
            self._current = {"future": future, "expect_binary": expect_binary}
            self._request_event.set()
            payload = {"jsonrpc": "2.0", "id": seq, "method": method, "params": params}
            try:
                self._sock.sendall(encode_json_frame(payload))
            except OSError as e:
                self._current = None
                self._request_event.clear()
                raise PocoConnectionError(f"send failed: {e}")
            try:
                return future.result(timeout=timeout)
            except TimeoutError:
                self._current = None
                self._request_event.clear()
                self.close()
                raise PocoTimeoutError(f"{method} timed out after {timeout}s")

    def _recv_loop(self):
        while not self._closed:
            self._request_event.wait()
            if self._closed or self._current is None:
                continue
            expect_binary = self._current["expect_binary"]
            future = self._current["future"]
            try:
                if expect_binary:
                    data = read_binary_frame(self._sock)
                    if not data:
                        future.set_exception(PocoConnectionError("connection closed"))
                    else:
                        future.set_result(data)
                else:
                    msg = read_json_frame(self._sock)
                    if "error" in msg:
                        err = msg["error"]
                        future.set_exception(PocoRemoteError(
                            err.get("code", -1),
                            err.get("message", ""),
                            err.get("data"),
                        ))
                    else:
                        future.set_result(msg.get("result", {}))
            except (ConnectionError, OSError) as e:
                future.set_exception(PocoConnectionError(str(e)))
            except Exception as e:
                future.set_exception(e)
            finally:
                self._current = None
                self._request_event.clear()

    # --- public protocol methods (filled in incrementally) ---

    def get_screen_size(self) -> dict:
        return self._request_json("get_screen_size", {})
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_poco_client.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add src/autotest_ide/core/poco_client.py tests/test_poco_client.py
git commit -m "feat(core): add PocoClient with connect, handshake, get_screen_size"
```

---

## Task 7: Fake Server v2 (get_root, dump_hierarchy, get_attributes)

**Files:**
- Modify: `tests/fake_poco_server.py`

- [ ] **Step 1: Extend the fake server's `_dispatch`**

In `tests/fake_poco_server.py`, replace the `_dispatch` method with:

```python
    def _dispatch(self, method, params, seq, conn):
        if method == "hello":
            return {"jsonrpc": "2.0", "id": seq, "result": {
                "server_version": "fake-1.0",
                "protocol": "v1",
            }}
        if method == "get_screen_size":
            return {"jsonrpc": "2.0", "id": seq, "result": {"w": 1080, "h": 1920}}
        if method == "get_root":
            return {"jsonrpc": "2.0", "id": seq, "result": FIXED_UI_TREE}
        if method == "dump_hierarchy":
            depth = params.get("depth")
            tree = FIXED_UI_TREE
            if depth == 1:
                tree = {**FIXED_UI_TREE, "children": []}
            return {"jsonrpc": "2.0", "id": seq, "result": tree}
        if method == "get_attributes":
            node_id = params.get("node_id")
            found = self._find_node(FIXED_UI_TREE, node_id)
            if found is None:
                return {"jsonrpc": "2.0", "id": seq, "error": {
                    "code": -32000, "message": f"node not found: {node_id}"
                }}
            return {"jsonrpc": "2.0", "id": seq, "result": found["payload"]}
        return {"jsonrpc": "2.0", "id": seq, "error": {
            "code": -32601, "message": f"method not found: {method}"
        }}

    @staticmethod
    def _find_node(root, node_id):
        if root["node_id"] == node_id:
            return root
        for child in root.get("children", []):
            found = FakePocoServer._find_node(child, node_id)
            if found is not None:
                return found
        return None
```

- [ ] **Step 2: Verify the fake server responds to new methods**

Run:

```bash
python -c "
from tests.fake_poco_server import FakePocoServer
from autotest_ide.core.protocol import encode_json_frame, read_json_frame
import socket
s = FakePocoServer(); s.start()
sock = socket.create_connection((s.host, s.port), timeout=2)
sock.sendall(encode_json_frame({'jsonrpc':'2.0','id':1,'method':'hello','params':{}})); print(read_json_frame(sock)['result']['protocol'])
sock.sendall(encode_json_frame({'jsonrpc':'2.0','id':2,'method':'get_root','params':{}})); print(read_json_frame(sock)['result']['name'])
sock.sendall(encode_json_frame({'jsonrpc':'2.0','id':3,'method':'get_attributes','params':{'node_id':'btn_play'}})); print(read_json_frame(sock)['result']['text'])
sock.close(); s.stop()
"
```

Expected output:
```
v1
Canvas
Play
```

- [ ] **Step 3: Commit**

```bash
git add tests/fake_poco_server.py
git commit -m "test: extend FakePocoServer with get_root, dump_hierarchy, get_attributes"
```

---

## Task 8: PocoClient — get_root, dump_hierarchy, get_attributes

**Files:**
- Modify: `src/autotest_ide/core/poco_client.py`
- Modify: `tests/test_poco_client.py`

- [ ] **Step 1: Write the failing tests (append to `tests/test_poco_client.py`)**

```python
def test_get_root_returns_full_tree(fake_server):
    client = PocoClient(host=fake_server.host, port=fake_server.port)
    client.connect()
    try:
        root = client.get_root()
        assert root["name"] == "Canvas"
        assert root["children"][0]["name"] == "Button_Play"
    finally:
        client.close()


def test_dump_hierarchy_with_depth(fake_server):
    client = PocoClient(host=fake_server.host, port=fake_server.port)
    client.connect()
    try:
        shallow = client.dump_hierarchy(depth=1)
        assert shallow["children"] == []
        full = client.dump_hierarchy()
        assert len(full["children"]) == 1
    finally:
        client.close()


def test_get_attributes(fake_server):
    client = PocoClient(host=fake_server.host, port=fake_server.port)
    client.connect()
    try:
        attrs = client.get_attributes("btn_play")
        assert attrs["text"] == "Play"
        assert attrs["visibleBounds"]["width"] == 200
    finally:
        client.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_poco_client.py -v`
Expected: FAIL with `AttributeError: 'PocoClient' object has no attribute 'get_root'`

- [ ] **Step 3: Add the public methods**

In `src/autotest_ide/core/poco_client.py`, replace the trailing comment block:

```python
    # --- public protocol methods (filled in incrementally) ---

    def get_screen_size(self) -> dict:
        return self._request_json("get_screen_size", {})
```

with:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_poco_client.py -v`
Expected: 7 passed (4 from Task 6 + 3 new)

- [ ] **Step 5: Commit**

```bash
git add src/autotest_ide/core/poco_client.py tests/test_poco_client.py
git commit -m "feat(core): add get_root, dump_hierarchy, get_attributes to PocoClient"
```

---

## Task 9: PocoClient — Timeout Handling

**Files:**
- Modify: `tests/test_poco_client.py`

- [ ] **Step 1: Write the failing test (append to `tests/test_poco_client.py`)**

```python
def test_request_timeout_raises_poco_timeout_error(fake_server):
    fake_server.delay = 2.0  # server responds after 2s
    client = PocoClient(host=fake_server.host, port=fake_server.port)
    client.connect()
    try:
        with pytest.raises(PocoTimeoutError, match="get_screen_size"):
            client.get_screen_size()
    finally:
        client.close()


def test_timeout_closes_connection(fake_server):
    fake_server.delay = 2.0
    client = PocoClient(host=fake_server.host, port=fake_server.port)
    client.connect()
    try:
        with pytest.raises(PocoTimeoutError):
            client.get_screen_size()
    except PocoTimeoutError:
        pass
    # After timeout the client is closed; further calls raise connection error
    with pytest.raises(PocoConnectionError):
        client.get_screen_size()
```

- [ ] **Step 2: Run test to verify it fails (or check behavior)**

Run: `pytest tests/test_poco_client.py::test_request_timeout_raises_poco_timeout_error -v`
Expected: This test should already pass because the implementation in Task 6 closes the connection on timeout and raises `PocoTimeoutError`. If it fails, the implementation has a bug — re-examine `_request`.

If it passes, proceed to Step 3. If it fails, debug the `_request` timeout path in `src/autotest_ide/core/poco_client.py`.

- [ ] **Step 3: Run the full timeout test suite**

Run: `pytest tests/test_poco_client.py -v -k timeout`
Expected: 2 passed

- [ ] **Step 4: Commit**

```bash
git add tests/test_poco_client.py
git commit -m "test(core): cover PocoClient timeout and connection-close-on-timeout"
```

---

## Task 10: PocoClient — Disconnect Detection

**Files:**
- Modify: `tests/test_poco_client.py`

- [ ] **Step 1: Write the failing test (append to `tests/test_poco_client.py`)**

```python
def test_server_drop_mid_request_raises_connection_error(fake_server):
    client = PocoClient(host=fake_server.host, port=fake_server.port)
    client.connect()
    # Tell the server to drop on the next request
    fake_server.drop_on_next = True
    with pytest.raises(PocoConnectionError):
        client.get_root()
    client.close()


def test_server_drop_then_client_closed(fake_server):
    client = PocoClient(host=fake_server.host, port=fake_server.port)
    client.connect()
    fake_server.drop_on_next = True
    with pytest.raises(PocoConnectionError):
        client.get_root()
    # Connection is now dead; subsequent calls fail
    with pytest.raises(PocoConnectionError):
        client.get_root()
```

- [ ] **Step 2: Run test to verify it passes**

Run: `pytest tests/test_poco_client.py -v -k "drop"`
Expected: 2 passed

These should already pass given the `_recv_loop` catches `ConnectionError`/`OSError` and sets a `PocoConnectionError` on the future. If they fail, examine the recv loop's exception handling.

- [ ] **Step 3: Commit**

```bash
git add tests/test_poco_client.py
git commit -m "test(core): cover server-drop disconnect detection"
```

---

## Task 11: Fake Server v3 (inspect_by_point + JSON-RPC error)

**Files:**
- Modify: `tests/fake_poco_server.py`

- [ ] **Step 1: Extend the fake server's `_dispatch`**

In `tests/fake_poco_server.py`, add a branch to `_dispatch` before the final `method not found` return. Insert this block:

```python
        if method == "inspect_by_point":
            x = params.get("x", 0)
            y = params.get("y", 0)
            # Return btn_play if the point falls inside its bounds, else root.
            btn = FIXED_UI_TREE["children"][0]
            b = btn["payload"]["visibleBounds"]
            if b["x"] <= x <= b["x"] + b["width"] and b["y"] <= y <= b["y"] + b["height"]:
                return {"jsonrpc": "2.0", "id": seq, "result": {
                    "node_id": btn["node_id"],
                    "path": ["root", btn["node_id"]],
                }}
            if x < 0 or y < 0:
                return {"jsonrpc": "2.0", "id": seq, "error": {
                    "code": -32001, "message": "no node at point"
                }}
            return {"jsonrpc": "2.0", "id": seq, "result": {
                "node_id": "root",
                "path": ["root"],
            }}
```

The full `_dispatch` now reads (for verification):

```python
    def _dispatch(self, method, params, seq, conn):
        if method == "hello":
            return {"jsonrpc": "2.0", "id": seq, "result": {
                "server_version": "fake-1.0",
                "protocol": "v1",
            }}
        if method == "get_screen_size":
            return {"jsonrpc": "2.0", "id": seq, "result": {"w": 1080, "h": 1920}}
        if method == "get_root":
            return {"jsonrpc": "2.0", "id": seq, "result": FIXED_UI_TREE}
        if method == "dump_hierarchy":
            depth = params.get("depth")
            tree = FIXED_UI_TREE
            if depth == 1:
                tree = {**FIXED_UI_TREE, "children": []}
            return {"jsonrpc": "2.0", "id": seq, "result": tree}
        if method == "get_attributes":
            node_id = params.get("node_id")
            found = self._find_node(FIXED_UI_TREE, node_id)
            if found is None:
                return {"jsonrpc": "2.0", "id": seq, "error": {
                    "code": -32000, "message": f"node not found: {node_id}"
                }}
            return {"jsonrpc": "2.0", "id": seq, "result": found["payload"]}
        if method == "inspect_by_point":
            x = params.get("x", 0)
            y = params.get("y", 0)
            btn = FIXED_UI_TREE["children"][0]
            b = btn["payload"]["visibleBounds"]
            if b["x"] <= x <= b["x"] + b["width"] and b["y"] <= y <= b["y"] + b["height"]:
                return {"jsonrpc": "2.0", "id": seq, "result": {
                    "node_id": btn["node_id"],
                    "path": ["root", btn["node_id"]],
                }}
            if x < 0 or y < 0:
                return {"jsonrpc": "2.0", "id": seq, "error": {
                    "code": -32001, "message": "no node at point"
                }}
            return {"jsonrpc": "2.0", "id": seq, "result": {
                "node_id": "root",
                "path": ["root"],
            }}
        return {"jsonrpc": "2.0", "id": seq, "error": {
            "code": -32601, "message": f"method not found: {method}"
        }}
```

- [ ] **Step 2: Verify inspect_by_point works**

Run:

```bash
python -c "
from tests.fake_poco_server import FakePocoServer
from autotest_ide.core.protocol import encode_json_frame, read_json_frame
import socket
s = FakePocoServer(); s.start()
sock = socket.create_connection((s.host, s.port), timeout=2)
sock.sendall(encode_json_frame({'jsonrpc':'2.0','id':1,'method':'hello','params':{}})); read_json_frame(sock)
sock.sendall(encode_json_frame({'jsonrpc':'2.0','id':2,'method':'inspect_by_point','params':{'x':540,'y':960}})); print(read_json_frame(sock))
sock.close(); s.stop()
"
```

Expected output contains `'node_id': 'btn_play'`.

- [ ] **Step 3: Commit**

```bash
git add tests/fake_poco_server.py
git commit -m "test: extend FakePocoServer with inspect_by_point (hit/miss/error)"
```

---

## Task 12: PocoClient — inspect_by_point + Remote/Node-Not-Found Errors

**Files:**
- Modify: `src/autotest_ide/core/poco_client.py`
- Modify: `tests/test_poco_client.py`

- [ ] **Step 1: Write the failing tests (append to `tests/test_poco_client.py`)**

```python
def test_inspect_by_point_hits_button(fake_server):
    client = PocoClient(host=fake_server.host, port=fake_server.port)
    client.connect()
    try:
        result = client.inspect_by_point(540, 960)  # center of btn_play
        assert result["node_id"] == "btn_play"
        assert result["path"] == ["root", "btn_play"]
    finally:
        client.close()


def test_inspect_by_point_misses_returns_root(fake_server):
    client = PocoClient(host=fake_server.host, port=fake_server.port)
    client.connect()
    try:
        result = client.inspect_by_point(10, 10)  # top-left corner
        assert result["node_id"] == "root"
    finally:
        client.close()


def test_inspect_by_point_remote_error_raises_poco_remote_error(fake_server):
    client = PocoClient(host=fake_server.host, port=fake_server.port)
    client.connect()
    try:
        with pytest.raises(PocoRemoteError) as exc_info:
            client.inspect_by_point(-1, -1)
        assert exc_info.value.code == -32001
        assert "no node at point" in exc_info.value.message
    finally:
        client.close()


def test_get_attributes_node_not_found_raises_remote_error(fake_server):
    client = PocoClient(host=fake_server.host, port=fake_server.port)
    client.connect()
    try:
        with pytest.raises(PocoRemoteError) as exc_info:
            client.get_attributes("does_not_exist")
        assert exc_info.value.code == -32000
    finally:
        client.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_poco_client.py -v -k inspect`
Expected: FAIL with `AttributeError: 'PocoClient' object has no attribute 'inspect_by_point'`

- [ ] **Step 3: Add the inspect_by_point method**

In `src/autotest_ide/core/poco_client.py`, append to the public methods section (after `get_attributes`):

```python
    def inspect_by_point(self, x: int, y: int) -> dict:
        return self._request_json("inspect_by_point", {"x": x, "y": y})
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_poco_client.py -v`
Expected: 15 passed (7 + 2 + 2 + 4 new)

- [ ] **Step 5: Commit**

```bash
git add src/autotest_ide/core/poco_client.py tests/test_poco_client.py
git commit -m "feat(core): add inspect_by_point; cover PocoRemoteError mapping"
```

---

## Task 13: Fake Server v4 (screenshot + binary_read)

**Files:**
- Modify: `tests/fake_poco_server.py`

- [ ] **Step 1: Extend the fake server to handle screenshot and binary_read**

In `tests/fake_poco_server.py`, modify `_handle` and add a `_screenshot_seqs` counter. Replace the `_handle` method with:

```python
    def _handle(self, conn, msg):
        method = msg.get("method")
        seq = msg.get("id")
        params = msg.get("params", {})

        if method == "screenshot":
            # Respond with a JSON ack carrying a binary_seq, then the caller
            # will issue binary_read to fetch the bytes.
            binary_seq = self._next_binary_seq()
            self._pending_screenshots[binary_seq] = TINY_PNG
            conn.sendall(encode_json_frame({
                "jsonrpc": "2.0", "id": seq, "result": {"binary_seq": binary_seq}
            }))
            return

        if method == "binary_read":
            binary_seq = params.get("seq")
            data = self._pending_screenshots.pop(binary_seq, None)
            if data is None:
                conn.sendall(encode_json_frame({
                    "jsonrpc": "2.0", "id": seq, "error": {
                        "code": -32002, "message": f"unknown binary seq: {binary_seq}"
                    }
                }))
                return
            # Send a raw binary frame: 4-byte length + bytes (NOT JSON).
            import struct
            conn.sendall(struct.pack(">I", len(data)) + data)
            return

        # All other methods go through _dispatch (JSON response).
        response = self._dispatch(method, params, seq, conn)
        if response is None:
            return
        try:
            conn.sendall(encode_json_frame(response))
        except OSError:
            return
```

- [ ] **Step 2: Add the binary-seq counter and pending-screenshots dict to `__init__`**

In `tests/fake_poco_server.py`, inside `FakePocoServer.__init__`, after `self.drop_on_next = False`, add:

```python
        self._binary_seq_counter = 0
        self._binary_seq_lock = threading.Lock()
        self._pending_screenshots: dict = {}

    def _next_binary_seq(self) -> int:
        with self._binary_seq_lock:
            self._binary_seq_counter += 1
            return self._binary_seq_counter
```

(Remove the original `self.drop_on_next = False` line's trailing newline issue — the two new lines go right after it, and the `_next_binary_seq` method becomes a class method. Make sure indentation is correct: the three new instance attributes are inside `__init__`, and `_next_binary_seq` is a method at class level.)

- [ ] **Step 3: Verify screenshot two-step works at the socket level**

Run:

```bash
python -c "
import struct, socket
from tests.fake_poco_server import FakePocoServer, TINY_PNG
from autotest_ide.core.protocol import encode_json_frame, read_json_frame, read_binary_frame
s = FakePocoServer(); s.start()
sock = socket.create_connection((s.host, s.port), timeout=2)
sock.sendall(encode_json_frame({'jsonrpc':'2.0','id':1,'method':'hello','params':{}})); read_json_frame(sock)
sock.sendall(encode_json_frame({'jsonrpc':'2.0','id':2,'method':'screenshot','params':{}}))
resp = read_json_frame(sock); print('binary_seq =', resp['result']['binary_seq'])
sock.sendall(encode_json_frame({'jsonrpc':'2.0','id':3,'method':'binary_read','params':{'seq':resp['result']['binary_seq']}}))
data = read_binary_frame(sock); print('bytes =', len(data), 'match =', data == TINY_PNG)
sock.close(); s.stop()
"
```

Expected output:
```
binary_seq = 1
bytes = 70 match = True
```

- [ ] **Step 4: Commit**

```bash
git add tests/fake_poco_server.py
git commit -m "test: extend FakePocoServer with screenshot + binary_read (two-step binary)"
```

---

## Task 14: PocoClient — screenshot (two-step binary)

**Files:**
- Modify: `src/autotest_ide/core/poco_client.py`
- Modify: `tests/test_poco_client.py`

- [ ] **Step 1: Write the failing tests (append to `tests/test_poco_client.py`)**

```python
from tests.fake_poco_server import TINY_PNG


def test_screenshot_returns_png_bytes(fake_server):
    client = PocoClient(host=fake_server.host, port=fake_server.port)
    client.connect()
    try:
        data = client.screenshot()
        assert isinstance(data, bytes)
        assert data == TINY_PNG
    finally:
        client.close()


def test_screenshot_two_round_trips(fake_server):
    client = PocoClient(host=fake_server.host, port=fake_server.port)
    client.connect()
    try:
        first = client.screenshot()
        second = client.screenshot()
        assert first == second == TINY_PNG
    finally:
        client.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_poco_client.py -v -k screenshot`
Expected: FAIL with `AttributeError: 'PocoClient' object has no attribute 'screenshot'`

- [ ] **Step 3: Add the screenshot method**

In `src/autotest_ide/core/poco_client.py`, add a `_request_binary` helper and the `screenshot` public method. Append to the public methods section:

```python
    def _request_binary(self, method: str, params: dict, timeout: float = DEFAULT_TIMEOUT) -> bytes:
        result = self._request(method, params, timeout, expect_binary=True)
        return result

    def screenshot(self) -> bytes:
        ack = self._request_json("screenshot", {})
        binary_seq = ack["binary_seq"]
        return self._request_binary("binary_read", {"seq": binary_seq})
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_poco_client.py -v -k screenshot`
Expected: 2 passed

- [ ] **Step 5: Run the full suite**

Run: `pytest tests/test_poco_client.py -v`
Expected: 17 passed

- [ ] **Step 6: Commit**

```bash
git add src/autotest_ide/core/poco_client.py tests/test_poco_client.py
git commit -m "feat(core): add screenshot (two-step binary frame) to PocoClient"
```

---

## Task 15: PocoClient — Heartbeat

**Files:**
- Modify: `src/autotest_ide/core/poco_client.py`
- Modify: `tests/test_poco_client.py`

- [ ] **Step 1: Write the failing tests (append to `tests/test_poco_client.py`)**

```python
def test_heartbeat_returns_true_when_healthy(fake_server):
    client = PocoClient(host=fake_server.host, port=fake_server.port)
    client.connect()
    try:
        assert client.heartbeat() is True
    finally:
        client.close()


def test_heartbeat_returns_false_after_server_drop(fake_server):
    client = PocoClient(host=fake_server.host, port=fake_server.port)
    client.connect()
    assert client.heartbeat() is True
    fake_server.drop_on_next = True
    # The next request will fail; heartbeat should return False, not raise.
    assert client.heartbeat() is False
    client.close()


def test_heartbeat_returns_false_on_closed_client(fake_server):
    client = PocoClient(host=fake_server.host, port=fake_server.port)
    client.connect()
    client.close()
    assert client.heartbeat() is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_poco_client.py -v -k heartbeat`
Expected: FAIL with `AttributeError: 'PocoClient' object has no attribute 'heartbeat'`

- [ ] **Step 3: Add the heartbeat method**

In `src/autotest_ide/core/poco_client.py`, append to the public methods section:

```python
    def heartbeat(self) -> bool:
        """Cheap liveness probe. Returns True if the server responded.

        Never raises: callers use this for periodic health checks and
        should not have to wrap it in try/except.
        """
        if self._closed:
            return False
        try:
            self._request_json("get_screen_size", {}, timeout=2.0)
            return True
        except PocoError:
            return False
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_poco_client.py -v -k heartbeat`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add src/autotest_ide/core/poco_client.py tests/test_poco_client.py
git commit -m "feat(core): add heartbeat (non-raising liveness probe via get_screen_size)"
```

---

## Task 16: End-to-End Integration Test (Pick-Point Flow)

**Files:**
- Create: `tests/test_integration_pick_point.py`

- [ ] **Step 1: Write the integration test**

`tests/test_integration_pick_point.py`:

```python
"""End-to-end test of the pick-point flow against the fake server.

This mirrors what the IDE will do when the user clicks the device screen:
  1. Connect and handshake.
  2. Take a screenshot (for the device panel display).
  3. Inspect a point to find the UI node under the cursor.
  4. Fetch that node's attributes (for the property panel).
  5. Heartbeat confirms the connection is still alive.
"""

from tests.fake_poco_server import FIXED_UI_TREE, TINY_PNG
from autotest_ide.core.poco_client import PocoClient


def test_full_pick_point_flow(fake_server):
    client = PocoClient(host=fake_server.host, port=fake_server.port)
    client.connect()
    try:
        # 1. handshake already done in connect()
        assert client.protocol_version == "v1"

        # 2. screenshot for the device panel
        shot = client.screenshot()
        assert shot == TINY_PNG

        # 3. inspect the center of the Play button (540, 960)
        hit = client.inspect_by_point(540, 960)
        assert hit["node_id"] == "btn_play"

        # 4. fetch attributes for the hit node
        attrs = client.get_attributes(hit["node_id"])
        assert attrs["text"] == "Play"
        assert attrs["visibleBounds"] == {"x": 440, "y": 900, "width": 200, "height": 120}

        # 5. heartbeat still healthy after the flow
        assert client.heartbeat() is True
    finally:
        client.close()


def test_pick_point_then_dump_hierarchy(fake_server):
    """UI tree panel uses dump_hierarchy; verify it works after a pick."""
    client = PocoClient(host=fake_server.host, port=fake_server.port)
    client.connect()
    try:
        client.inspect_by_point(540, 960)
        tree = client.dump_hierarchy()
        # The hit node should be findable in the dumped tree
        assert tree["children"][0]["node_id"] == "btn_play"
        assert tree["children"][0] == FIXED_UI_TREE["children"][0]
    finally:
        client.close()
```

- [ ] **Step 2: Run the integration test**

Run: `pytest tests/test_integration_pick_point.py -v`
Expected: 2 passed

- [ ] **Step 3: Run the entire test suite**

Run: `pytest -v`
Expected: all tests pass (errors + protocol + poco_client + integration). Count should be around 30+ tests.

- [ ] **Step 4: Commit**

```bash
git add tests/test_integration_pick_point.py
git commit -m "test: add end-to-end pick-point integration test against fake server"
```

---

## Self-Review

### Spec coverage check

| Spec section / requirement | Task(s) covering it |
|---|---|
| §3.1 TCP socket + 4-byte big-endian length prefix | T3, T4 |
| §3.2 `hello` handshake | T6 |
| §3.2 `get_root` | T7, T8 |
| §3.2 `dump_hierarchy` (with depth) | T7, T8 |
| §3.2 `get_screen_size` | T5, T6 |
| §3.2 `get_attributes` | T7, T8 |
| §3.2 `inspect_by_point` | T11, T12 |
| §3.2 `screenshot` (binary) | T13, T14 |
| §3.2 `binary_read` | T13, T14 |
| §3.3 binary frames avoid base64 | T13, T14 |
| §3.5 version negotiation (mismatch rejects) | T6 (`test_handshake_protocol_mismatch_raises`) |
| §3.6 errors: connection drop, timeout, JSON-RPC error | T9, T10, T12 |
| §5.1 PocoClient public methods | T6, T8, T12, T14, T15 |
| §5.2 5-second default timeout | T6 (`DEFAULT_TIMEOUT = 5.0`) |
| §5.2 timeout does not raise for heartbeat | T15 |
| §5.3 PocoError hierarchy (all 5 classes) | T2 |
| §5.3 PocoRemoteError carries code/message/data | T2, T12 |
| §5.3 PocoNodeNotFoundError | T2 (defined; the fake server uses generic -32000 for "node not found" which maps to PocoRemoteError — this is acceptable for Phase 1 since the spec lets the SDK decide error codes; the IDE-side PocoNodeNotFoundError is reserved for client-side node-validity checks that arrive later in Plan 3) |
| §8 fake_poco_server.py | T5, T7, T11, T13 |
| §8 mock socket tests | T3, T4 (socketpair) |
| §8 PocoClient mock tests (timeout, disconnect) | T9, T10 |
| §9.1 core/ has no PyQt dependency | All tasks (verified: no PyQt imports anywhere in `src/autotest_ide/core/`) |
| §9.1 runner/ is independent | Not in this plan (Plan 4) — correct, Plan 1 is core only |
| §10 M1: fake server + protocol, get_root works | T1-T8 |
| §10 M2: PocoClient + unit tests covering timeout/disconnect/node-not-found | T6-T15 |

**Gaps found:** None. Every spec section §3, §5, §8 that falls within Plan 1's scope (M1+M2) has at least one task.

### Placeholder scan

- No "TBD", "TODO", "implement later", "fill in details" found.
- Every code step shows actual code, not "add appropriate error handling".
- Every test step shows actual test code.
- No "similar to Task N" references — each task is self-contained.

### Type / name consistency check

- `encode_json_frame` — used consistently in T3, T4, T5, T13.
- `read_exactly`, `read_frame`, `read_json_frame`, `read_binary_frame` — defined in T4, used in T5, T13, T14.
- `PocoClient.connect` / `close` / `_request_json` / `_request_binary` / `_request` / `_recv_loop` / `_handshake` / `_next_seq` — names stable across T6–T15.
- `DEFAULT_TIMEOUT`, `CLIENT_VERSION`, `PROTOCOL_VERSION` — module-level constants in `poco_client.py`, referenced consistently.
- `FakePocoServer.start` / `stop` / `host` / `port` / `delay` / `drop_on_next` — consistent across T5, T9, T10.
- `_dispatch` vs `_handle` split in `FakePocoServer`: `_handle` routes binary methods (screenshot/binary_read), `_dispatch` handles JSON-RPC methods. This split is introduced in T5 (`_handle` + `_dispatch`) and extended in T13 (`_handle` gains binary branches). Consistent.
- `TINY_PNG`, `FIXED_UI_TREE` — module-level constants in `fake_poco_server.py`, imported in T14, T16. Consistent.
- `heartbeat()` returns `bool`, never raises — stated in T15, relied on by T15 tests. Consistent.

**No inconsistencies found.**

---

## Execution Handoff

Plan complete and saved to `E:/AutoTestIDE/docs/plans/2026-06-29-autotest-ide-plan1-protocol-client.md`. Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration. Best for a 16-task plan with cumulative file edits (the fake server is built up across 4 tasks, so review between tasks catches drift early).

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints. Faster turnaround but I hold all the context.

Which approach?
