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
