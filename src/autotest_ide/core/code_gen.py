"""Code generation for AutoTest IDE script editor.

Produces Python script lines (auto.find_and_tap, auto.click, assert_exists, etc.)
from UI node dicts.  Reuses parent-map helpers from locator.py.
"""

from enum import Enum

from autotest_ide.core.locator import _build_parent_map, _flatten_nodes


class OpMode(Enum):
    """Operation modes supported by the code generator."""
    CLICK = "click"
    LONG_PRESS = "long_click"
    SWIPE = "swipe"
    INPUT = "set_text"


def _build_path(node: dict, all_nodes: list) -> str:
    """Walk the parent chain and return a slash-separated path string.

    If *node* already carries ``payload.path`` (JX4 getNodeByPos case),
    return it directly.  Otherwise build A/B/C from the parent map.
    Returns empty string when no path can be constructed.
    """
    # JX4 shortcut: path already embedded in payload
    path = node.get("payload", {}).get("path", "")
    if path:
        return path

    node_id = node.get("node_id", "")
    if not all_nodes or not node_id:
        return ""

    by_id, parent_of = _build_parent_map(all_nodes)
    parts = []
    current_id = node_id
    visited = set()
    while current_id and current_id not in visited:
        visited.add(current_id)
        current_node = by_id.get(current_id)
        if current_node is None:
            break
        name = current_node.get("name", "")
        if name and name != "root":
            parts.append(name)
        current_id = parent_of.get(current_id, "")

    parts.reverse()
    return "/".join(parts) if parts else ""


def _build_all_paths(flat_nodes: list) -> dict[str, str]:
    """Build ``node_id -> path`` for every node in one O(n) pass.

    This replaces the O(n^2) pattern of calling :func:`_build_path` once per
    node, which rebuilt the whole parent map on every call.  Here the parent
    map is built once and paths are resolved with memoization so shared
    ancestors are walked only once — safe even for degenerate (list-like)
    trees and cycle-guarded against malformed input.
    """
    paths: dict[str, str] = {}
    if not flat_nodes:
        return paths

    by_id, parent_of = _build_parent_map(flat_nodes)
    cache: dict[str, str] = {}

    def _resolve(nid: str) -> str:
        if not nid or nid not in by_id:
            return ""
        if nid in cache:
            return cache[nid]

        # Walk up, collecting not-yet-cached ancestors (cycle-safe via `seen`).
        chain: list[str] = []
        seen: set[str] = set()
        cur = nid
        while cur and cur not in cache and cur in by_id and cur not in seen:
            seen.add(cur)
            chain.append(cur)
            cur = parent_of.get(cur, "")

        # `cur` is now "", a cached ancestor, a missing node, or a cycle cut.
        acc = cache[cur] if cur in cache else ""
        for nid2 in reversed(chain):  # root-most first
            node = by_id[nid2]
            embedded = node.get("payload", {}).get("path", "")
            if embedded:
                acc = embedded
            else:
                name = node.get("name", "")
                use_name = name if name and name != "root" else ""
                if use_name:
                    acc = f"{acc}/{use_name}" if acc else use_name
            cache[nid2] = acc
        return cache[nid]

    for nid in by_id:
        paths[nid] = _resolve(nid)
    return paths


def gen_click(node: dict, flat_nodes: list, x: int, y: int) -> str:
    """Generate a click/tap code line.

    Priority:
      1. If a slash-path can be built, emit ``auto.find_and_tap('path')``.
      2. Else if node has ``payload.pos``, emit ``auto.click(x, y)``.
      3. Otherwise return empty string.
    """
    path = _build_path(node, flat_nodes)
    if path:
        return f"auto.find_and_tap({path!r})\n"

    pos = node.get("payload", {}).get("pos", ())
    if isinstance(pos, (list, tuple)) and len(pos) >= 2:
        return f"auto.click({int(pos[0])}, {int(pos[1])})\n"

    return ""


def gen_assert_exists(node: dict, flat_nodes: list) -> str:
    """Generate an assert_exists code line.

    Returns ``assert_exists('path')\\n`` if a path can be built,
    otherwise empty string.
    """
    path = _build_path(node, flat_nodes)
    if path:
        return f"assert_exists({path!r})\n"
    return ""


def gen_long_click(node: dict, flat_nodes: list, x: int, y: int, duration: float = 2.0) -> str:
    """Generate long_click code (always coordinate-based)."""
    return f"auto.long_click({x}, {y}, duration={duration})\n"


def gen_swipe(x1: int, y1: int, x2: int, y2: int, duration: float = 0.5) -> str:
    """Generate swipe code."""
    if duration != 0.5:
        return f"auto.swipe({x1}, {y1}, {x2}, {y2}, duration={duration})\n"
    return f"auto.swipe({x1}, {y1}, {x2}, {y2})\n"


def gen_input(node: dict, flat_nodes: list, x: int, y: int, text: str) -> str:
    """Generate set_text code with path, or coordinate fallback."""
    path = _build_path(node, flat_nodes)
    if path:
        return f"auto.set_text({path!r}, {text!r})\n"
    pos = node.get("payload", {}).get("pos", ())
    if isinstance(pos, (list, tuple)) and len(pos) >= 2:
        return f"auto.click({int(pos[0])}, {int(pos[1])})  # set_text fallback\n"
    return ""


def gen_wait_for(path: str, timeout: int = 10) -> str:
    """Generate wait_for code."""
    return f"wait_for({path!r}, timeout={timeout})\n"


def gen_wait_for_gone(path: str, timeout: int = 10) -> str:
    """Generate wait_for_gone code."""
    return f"wait_for_gone({path!r}, timeout={timeout})\n"
