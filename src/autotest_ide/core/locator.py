from collections import Counter
from typing import Optional


def generate_locator(node: dict, all_nodes: Optional[list] = None) -> str:
    """Generate a poco(...) locator string for a pick-point hit node.

    Strategy (spec §6.4): name first, fallback to text+type, then type, then node_id.
    """
    name = node.get("name", "")
    ntype = node.get("type", "")
    text = node.get("payload", {}).get("text", "")
    node_id = node.get("node_id", "")

    if name:
        if all_nodes is not None:
            name_counts = Counter(n.get("name", "") for n in all_nodes)
            if name_counts[name] > 1:
                return f"poco(name={name!r}, type={ntype!r})"
        return f"poco({name!r})"

    if text:
        return f"poco(text={text!r}, type={ntype!r})"

    if ntype:
        return f"poco(type={ntype!r})"

    return f"poco(node_id={node_id!r})"


def generate_locator_code(node: dict, all_nodes: Optional[list] = None) -> str:
    """Generate an auto.find_and_tap(...) code line for IDE editor insertion.

    If the node payload already carries a ``path`` (JX4 getNodeByPos),
    use it directly.  Otherwise build an A/B/C path by walking the
    parent chain in all_nodes.  Falls back to auto.click(x, y).
    """
    path = node.get("payload", {}).get("path", "")
    if path:
        return f"auto.find_and_tap('{path}')\n"

    node_id = node.get("node_id", "")
    if not all_nodes or not node_id:
        return _fallback_click(node)

    parent_map = _build_parent_map(all_nodes)
    parts = []
    current_id = node_id
    visited = set()
    while current_id and current_id not in visited:
        visited.add(current_id)
        current_node = parent_map.get(current_id)
        if current_node is None:
            break
        name = current_node.get("name", "")
        if name and name != "root":
            parts.append(name)
        current_id = _find_parent_id(current_id, parent_map)

    parts.reverse()
    if parts:
        path = "/".join(parts)
        return f"auto.find_and_tap('{path}')\n"
    return _fallback_click(node)


def _build_parent_map(nodes: list) -> dict:
    """Map node_id -> node dict, and embed _parent_id for chain walking.

    Accepts either a flat list (from _flatten_tree) or a nested tree root.
    """
    flat = _flatten_nodes(nodes)
    by_id = {}
    for node in flat:
        nid = node.get("node_id", "")
        if nid:
            by_id[nid] = node
    for node in flat:
        for child in node.get("children", []):
            cid = child.get("node_id", "")
            if cid and cid in by_id:
                by_id[cid]["_parent_id"] = node.get("node_id", "")
    return by_id


def _flatten_nodes(nodes: list) -> list:
    """Flatten a list of nodes (possibly nested) into a flat list."""
    result = []
    stack = list(nodes)
    while stack:
        node = stack.pop()
        result.append(node)
        stack.extend(reversed(node.get("children", [])))
    return result


def _find_parent_id(node_id: str, parent_map: dict) -> Optional[str]:
    return parent_map.get(node_id, {}).get("_parent_id")


def _fallback_click(node: dict) -> str:
    bounds = node.get("payload", {}).get("pos", ())
    if isinstance(bounds, (list, tuple)) and len(bounds) >= 2:
        return f"auto.click({int(bounds[0])}, {int(bounds[1])})\n"
    return ""
