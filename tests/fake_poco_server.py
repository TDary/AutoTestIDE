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
        self.fail_next_request = False  # if True, return a JSON-RPC error on next request (keeps connection open)
        self._binary_seq_counter = 0
        self._binary_seq_lock = threading.Lock()
        self._pending_screenshots: dict = {}

    def _next_binary_seq(self) -> int:
        with self._binary_seq_lock:
            self._binary_seq_counter += 1
            return self._binary_seq_counter

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
            if self.fail_next_request:
                self.fail_next_request = False
                seq = msg.get("id")
                try:
                    conn.sendall(encode_json_frame({
                        "jsonrpc": "2.0", "id": seq, "error": {
                            "code": -32603, "message": "internal error (simulated)"
                        }
                    }))
                except OSError:
                    return
                continue
            if self.delay > 0:
                time.sleep(self.delay)
            self._handle(conn, msg)

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
        if method == "click":
            return {"jsonrpc": "2.0", "id": seq, "result": {}}
        if method == "set_text":
            return {"jsonrpc": "2.0", "id": seq, "result": {}}
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

    @staticmethod
    def _find_node(root, node_id):
        if root["node_id"] == node_id:
            return root
        for child in root.get("children", []):
            found = FakePocoServer._find_node(child, node_id)
            if found is not None:
                return found
        return None
