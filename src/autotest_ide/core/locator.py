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
        if all_nodes is None or sum(1 for n in all_nodes if n.get("name") == name) <= 1:
            return f'poco("{name}")'
        return f'poco(name="{name}", type="{ntype}")'

    if text:
        return f'poco(text="{text}", type="{ntype}")'

    if ntype:
        return f'poco(type="{ntype}")'

    return f'poco(node_id="{node_id}")'
