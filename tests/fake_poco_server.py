import threading
import time

from autotest_ide.core.protocol import encode_command, encode_json_frame, read_command

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
    """A minimal Poco protocol server for tests.

    Reads text commands (``CommandName arg1 key1=val1 \\n``),
    sends length-prefixed JSON/binary responses.
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 0):
        self._host = host
        self._port = port
        self._server_sock = None
        self._thread = None
        self._running = False
        self._client_sock = None
        self.delay = 0.0
        self.drop_on_next = False
        self.fail_next_request = False

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
                method, args = read_command(conn)
            except (ConnectionError, OSError):
                return
            # Parse keyword arguments from args
            params = {}
            pos_args = []
            for arg in args:
                if "=" in arg:
                    k, v = arg.split("=", 1)
                    params[k] = v
                else:
                    pos_args.append(arg)
            if self.drop_on_next:
                try:
                    conn.close()
                except OSError:
                    pass
                self.drop_on_next = False
                return
            if self.fail_next_request:
                self.fail_next_request = False
                try:
                    conn.sendall(encode_json_frame({
                        "error": {"code": -32603, "message": "internal error (simulated)"}
                    }))
                except OSError:
                    return
                continue
            if self.delay > 0:
                time.sleep(self.delay)
            self._handle(conn, method, pos_args, params)

    def _handle(self, conn, method, pos_args, kwargs):
        if method == "GetScreen":
            self._handle_screen(conn)
            return
        response = self._dispatch(method, pos_args, kwargs)
        if response is None:
            return
        try:
            conn.sendall(encode_json_frame(response))
        except OSError:
            return

    def _dispatch(self, method, pos_args, kwargs):
        if method == "getServerVersion":
            return "fake-1.0"

        if method == "Dump":
            only_visible = kwargs.get("onlyVisibleNode", "True")
            if only_visible == "False":
                return FIXED_UI_TREE
            return FIXED_UI_TREE

        if method == "GetNodeAttr":
            node_id = pos_args[0] if pos_args else ""
            found = self._find_node(FIXED_UI_TREE, node_id)
            if found is None:
                return {"error": {"code": -32000, "message": f"node not found: {node_id}"}}
            return found["payload"]

        if method == "Inspect":
            x = int(pos_args[0]) if len(pos_args) > 0 else 0
            y = int(pos_args[1]) if len(pos_args) > 1 else 0
            btn = FIXED_UI_TREE["children"][0]
            b = btn["payload"]["visibleBounds"]
            if b["x"] <= x <= b["x"] + b["width"] and b["y"] <= y <= b["y"] + b["height"]:
                return {
                    "node_id": btn["node_id"],
                    "path": ["root", btn["node_id"]],
                }
            if x < 0 or y < 0:
                return {"error": {"code": -32001, "message": "no node at point"}}
            return {"node_id": "root", "path": ["root"]}

        if method == "Click":
            return {}

        if method == "SetText":
            return {}

        if method == "GetScreen":
            # This is a binary response — handled specially
            return None  # caller sends binary directly

        return {"error": {"code": -32601, "message": f"method not found: {method}"}}

    def _handle_screen(self, conn):
        import struct
        data = TINY_PNG
        conn.sendall(struct.pack(">I", len(data)) + data)

    @staticmethod
    def _find_node(root, node_id):
        if root["node_id"] == node_id:
            return root
        for child in root.get("children", []):
            found = FakePocoServer._find_node(child, node_id)
            if found is not None:
                return found
        return None
