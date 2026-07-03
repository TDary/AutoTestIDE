"""页面脚本共享辅助函数 —— 适配 AutoTest IDE 执行环境

所有页面脚本均可 from pages.jx4.helpers import ... 使用。
"""
import time


def object_exists(auto, path: str) -> bool:
    try:
        root = auto.dump_hierarchy()
        flat = _flatten_tree(root)
        return _find_node(flat, path) is not None
    except Exception:
        return False


def safe_find_and_tap(auto, path: str, timeout: float = 0):
    if timeout > 0:
        time.sleep(timeout)
    try:
        auto.find_and_tap(path)
        log(f"点击: {path}")
    except Exception:
        pass


def wait_for(auto, path: str, timeout: float = 30, interval: float = 1) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if object_exists(auto, path):
            return True
        time.sleep(interval)
    return False


def wait_for_gone(auto, path: str, timeout: float = 30, interval: float = 1) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not object_exists(auto, path):
            return True
        time.sleep(interval)
    return False


def find_child_text(auto, parent_path: str) -> str | None:
    try:
        root = auto.dump_hierarchy()
        flat = _flatten_tree(root)
        parent = _find_node(flat, parent_path)
        if parent and parent.get("children"):
            child = parent["children"][0]
            return child.get("payload", {}).get("text", "")
    except Exception:
        pass
    return None


def _get_children_names(auto, parent_path: str) -> list[str]:
    """获取指定路径节点的直接子节点名称列表。"""
    try:
        root = auto.dump_hierarchy()
        flat = _flatten_tree(root)
        parent = _find_node(flat, parent_path)
        if parent and parent.get("children"):
            return [c["name"] for c in parent["children"] if c.get("name")]
    except Exception:
        pass
    return []


def _flatten_tree(root: dict) -> list:
    result = []
    stack = [root]
    while stack:
        node = stack.pop()
        result.append(node)
        stack.extend(reversed(node.get("children", [])))
    return result


def _find_node(nodes: list, path: str) -> dict | None:
    parts = [p for p in path.split("/") if p]
    for node in nodes:
        if node.get("name", "") == parts[-1]:
            return node
    return None
