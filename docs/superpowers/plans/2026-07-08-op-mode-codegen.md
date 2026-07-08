# 操作模式切换 + 代码生成 + 录制断言 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现点击截图生成多类型 UI 交互用例代码，包括操作模式切换 UI、协议映射扩充、代码生成模块化、录制断言自动插入。

**Architecture:** 底层先扩协议映射和 PocoClient 方法，中间层建 code_gen 模块替代散落的代码拼接逻辑，上层改造 DevicePanel 交互 + PocoWorker 操作 + RecordController 代码生成，MainWindow 做信号编排。

**Tech Stack:** Python 3.10+, PyQt5, pytest

---

## File Structure

| File | Responsibility | Change |
|------|---------------|--------|
| `src/autotest_ide/core/code_gen.py` | OpMode 枚举 + 所有 gen_* 函数 | **新增** |
| `src/autotest_ide/core/locator.py` | generate_locator (poco(...)定位字符串) | 修改：移除 generate_locator_code |
| `src/autotest_ide/core/poco_client.py` | TCP 客户端 | 修改：新增 6 方法 |
| `src/autotest_ide/sdks/jx4/protocol.py` | JX4 协议适配 | 修改：METHOD_MAP 扩充 |
| `src/autotest_ide/runner/recorder.py` | 录制包装 | 修改：新增 5 操作录制 |
| `src/autotest_ide/runner/runtime.py` | auto 命名空间 | 修改：新增 wait_for/wait_for_gone |
| `src/autotest_ide/ui/device_panel.py` | 截图面板 | 修改：工具栏 + op_mode + 新信号 + 滑动交互 |
| `src/autotest_ide/ui/threads.py` | PocoWorker | 修改：新增 long_press/swipe/input_text + swipe_done 信号 |
| `src/autotest_ide/ui/record_controller.py` | 录制状态机 | 修改：op_mode 参数 + 调用 code_gen |
| `src/autotest_ide/ui/main_window.py` | 主窗口 | 修改：新信号连接 + 槽函数 + op_mode 传递 |
| `tests/test_code_gen.py` | code_gen 单元测试 | **新增** |
| `tests/test_locator.py` | locator 测试 | 修改：移除 generate_locator_code 测试 |
| `tests/test_poco_client.py` | PocoClient 测试 | 修改：新增新方法测试 |
| `tests/test_jx4_protocol.py` | JX4 协议测试 | 修改：新增映射测试 |
| `tests/test_recorder.py` | 录制器测试 | 修改：新增操作录制测试 |
| `tests/test_runtime.py` | runtime 测试 | 修改：新增辅助函数测试 |
| `tests/test_record_controller.py` | RecordController 测试 | 修改：新增 op_mode + 断言测试 |
| `tests/test_threads.py` | PocoWorker 测试 | 修改：新增操作信号测试 |

---

### Task 1: 新增 core/code_gen.py — OpMode 枚举 + gen_click + gen_assert_exists

**Files:**
- Create: `src/autotest_ide/core/code_gen.py`
- Test: `tests/test_code_gen.py`

- [ ] **Step 1: Write the failing test for OpMode and gen_click**

```python
# tests/test_code_gen.py
from autotest_ide.core.code_gen import OpMode, gen_click, gen_assert_exists


def test_opmode_values():
    assert OpMode.CLICK.value == "click"
    assert OpMode.LONG_PRESS.value == "long_click"
    assert OpMode.SWIPE.value == "swipe"
    assert OpMode.INPUT.value == "set_text"


def test_gen_click_with_path():
    node = {"name": "Play", "type": "Button", "payload": {}, "node_id": "3"}
    flat = [
        {"name": "root", "type": "", "payload": {}, "node_id": "0", "children": [
            {"name": "Play", "type": "Button", "payload": {}, "node_id": "3"},
        ]},
    ]
    assert gen_click(node, flat, 100, 200) == "auto.find_and_tap('Play')\n"


def test_gen_click_with_nested_path():
    node = {"name": "Play", "type": "Button", "payload": {}, "node_id": "3"}
    flat = [
        {"name": "root", "type": "", "payload": {}, "node_id": "0", "children": [
            {"name": "Panel", "type": "Panel", "payload": {}, "node_id": "1", "children": [
                {"name": "Play", "type": "Button", "payload": {}, "node_id": "3"},
            ]},
        ]},
    ]
    assert gen_click(node, flat, 100, 200) == "auto.find_and_tap('Panel/Play')\n"


def test_gen_click_fallback_coordinate():
    node = {"name": "Play", "type": "Button", "payload": {"pos": [100, 200]}, "node_id": "3"}
    assert gen_click(node, [], 100, 200) == "auto.click(100, 200)\n"


def test_gen_click_empty_all_nodes():
    node = {"name": "Play", "type": "Button", "payload": {"pos": [50, 60]}, "node_id": "3"}
    assert gen_click(node, [], 50, 60) == "auto.click(50, 60)\n"


def test_gen_click_no_path_no_pos():
    node = {"name": "", "type": "", "payload": {}, "node_id": "3"}
    assert gen_click(node, [], 0, 0) == ""


def test_gen_click_with_jx4_path():
    """When node payload already has a path (from JX4 getNodeByPos), use it directly."""
    node = {"name": "BtnStart", "type": "GameObject", "payload": {"path": "Denglu/BtnStart"}, "node_id": "Denglu/BtnStart"}
    assert gen_click(node, [], 100, 200) == "auto.find_and_tap('Denglu/BtnStart')\n"


def test_gen_assert_exists_with_path():
    node = {"name": "Play", "type": "Button", "payload": {}, "node_id": "3"}
    flat = [
        {"name": "root", "type": "", "payload": {}, "node_id": "0", "children": [
            {"name": "Play", "type": "Button", "payload": {}, "node_id": "3"},
        ]},
    ]
    assert gen_assert_exists(node, flat) == "assert_exists('Play')\n"


def test_gen_assert_exists_nested():
    node = {"name": "Play", "type": "Button", "payload": {}, "node_id": "3"}
    flat = [
        {"name": "root", "type": "", "payload": {}, "node_id": "0", "children": [
            {"name": "Panel", "type": "Panel", "payload": {}, "node_id": "1", "children": [
                {"name": "Play", "type": "Button", "payload": {}, "node_id": "3"},
            ]},
        ]},
    ]
    assert gen_assert_exists(node, flat) == "assert_exists('Panel/Play')\n"


def test_gen_assert_exists_with_jx4_path():
    node = {"name": "BtnStart", "type": "GameObject", "payload": {"path": "Denglu/BtnStart"}, "node_id": "Denglu/BtnStart"}
    assert gen_assert_exists(node, []) == "assert_exists('Denglu/BtnStart')\n"


def test_gen_assert_exists_no_path_returns_empty():
    node = {"name": "", "type": "", "payload": {}, "node_id": "3"}
    assert gen_assert_exists(node, []) == ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd E:/AutoTestIDE && python -m pytest tests/test_code_gen.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'autotest_ide.core.code_gen'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/autotest_ide/core/code_gen.py
"""Modular code generation for UI operation scripts.

Each gen_* function produces a single code line (trailing newline included)
suitable for editor insertion.  Path generation reuses the parent-chain
walker from locator.py.
"""
from enum import Enum
from typing import Optional

from autotest_ide.core.locator import _build_parent_map, _flatten_nodes


class OpMode(Enum):
    """Operation mode for the device screenshot panel."""
    CLICK = "click"
    LONG_PRESS = "long_click"
    SWIPE = "swipe"
    INPUT = "set_text"


def _build_path(node: dict, all_nodes: list) -> str:
    """Walk the parent chain and return a slash-separated path string.

    Returns empty string if no meaningful path can be built.
    """
    path_in_payload = node.get("payload", {}).get("path", "")
    if path_in_payload:
        return path_in_payload

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


def gen_click(node: dict, flat_nodes: list, x: int, y: int) -> str:
    """Generate click code: auto.find_and_tap('path') or auto.click(x, y)."""
    path = _build_path(node, flat_nodes)
    if path:
        return f"auto.find_and_tap('{path}')\n"

    pos = node.get("payload", {}).get("pos", ())
    if isinstance(pos, (list, tuple)) and len(pos) >= 2:
        return f"auto.click({int(pos[0])}, {int(pos[1])})\n"

    return ""


def gen_assert_exists(node: dict, flat_nodes: list) -> str:
    """Generate assert_exists('path') or empty string if no path."""
    path = _build_path(node, flat_nodes)
    if path:
        return f"assert_exists('{path}')\n"
    return ""
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd E:/AutoTestIDE && python -m pytest tests/test_code_gen.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
cd E:/AutoTestIDE && git add src/autotest_ide/core/code_gen.py tests/test_code_gen.py && git commit -m "feat: add code_gen module with OpMode, gen_click, gen_assert_exists"
```

---

### Task 2: 补全 code_gen.py — gen_long_click, gen_swipe, gen_input, gen_wait_for, gen_wait_for_gone

**Files:**
- Modify: `src/autotest_ide/core/code_gen.py`
- Test: `tests/test_code_gen.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_code_gen.py`:

```python
def test_gen_long_click_with_path():
    node = {"name": "Hold", "type": "Button", "payload": {}, "node_id": "5"}
    flat = [
        {"name": "root", "type": "", "payload": {}, "node_id": "0", "children": [
            {"name": "Hold", "type": "Button", "payload": {}, "node_id": "5"},
        ]},
    ]
    assert gen_long_click(node, flat, 100, 200) == "auto.long_click(100, 200, duration=2.0)\n"


def test_gen_long_click_custom_duration():
    node = {"name": "Hold", "type": "Button", "payload": {}, "node_id": "5"}
    flat = []
    assert gen_long_click(node, flat, 100, 200, duration=3.0) == "auto.long_click(100, 200, duration=3.0)\n"


def test_gen_swipe():
    assert gen_swipe(100, 200, 300, 400) == "auto.swipe(100, 200, 300, 400)\n"


def test_gen_swipe_custom_duration():
    assert gen_swipe(100, 200, 300, 400, duration=1.0) == "auto.swipe(100, 200, 300, 400, duration=1.0)\n"


def test_gen_input_with_path():
    node = {"name": "Input", "type": "InputField", "payload": {}, "node_id": "7"}
    flat = [
        {"name": "root", "type": "", "payload": {}, "node_id": "0", "children": [
            {"name": "Input", "type": "InputField", "payload": {}, "node_id": "7"},
        ]},
    ]
    assert gen_input(node, flat, 100, 200, "hello") == "auto.set_text('Input', 'hello')\n"


def test_gen_input_nested_path():
    node = {"name": "Field", "type": "InputField", "payload": {}, "node_id": "7"}
    flat = [
        {"name": "root", "type": "", "payload": {}, "node_id": "0", "children": [
            {"name": "Form", "type": "Panel", "payload": {}, "node_id": "1", "children": [
                {"name": "Field", "type": "InputField", "payload": {}, "node_id": "7"},
            ]},
        ]},
    ]
    assert gen_input(node, flat, 50, 60, "world") == "auto.set_text('Form/Field', 'world')\n"


def test_gen_input_fallback():
    node = {"name": "", "type": "", "payload": {"pos": [50, 60]}, "node_id": "7"}
    assert gen_input(node, [], 50, 60, "text") == "auto.click(50, 60)  # set_text fallback\n"


def test_gen_input_with_jx4_path():
    node = {"name": "Field", "type": "GameObject", "payload": {"path": "Login/Field"}, "node_id": "Login/Field"}
    assert gen_input(node, [], 100, 200, "hello") == "auto.set_text('Login/Field', 'hello')\n"


def test_gen_wait_for():
    assert gen_wait_for("Panel/BtnStart", timeout=10) == "wait_for('Panel/BtnStart', timeout=10)\n"


def test_gen_wait_for_custom_timeout():
    assert gen_wait_for("Btn", timeout=30) == "wait_for('Btn', timeout=30)\n"


def test_gen_wait_for_gone():
    assert gen_wait_for_gone("Panel/Loading", timeout=15) == "wait_for_gone('Panel/Loading', timeout=15)\n"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd E:/AutoTestIDE && python -m pytest tests/test_code_gen.py -v -k "long_click or swipe or input or wait_for"`
Expected: FAIL — `ImportError: cannot import name 'gen_long_click'`

- [ ] **Step 3: Add the implementations**

Append to `src/autotest_ide/core/code_gen.py` (after existing functions):

```python
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
        return f"auto.set_text('{path}', '{text}')\n"
    pos = node.get("payload", {}).get("pos", ())
    if isinstance(pos, (list, tuple)) and len(pos) >= 2:
        return f"auto.click({int(pos[0])}, {int(pos[1])})  # set_text fallback\n"
    return ""


def gen_wait_for(path: str, timeout: int = 10) -> str:
    """Generate wait_for code."""
    return f"wait_for('{path}', timeout={timeout})\n"


def gen_wait_for_gone(path: str, timeout: int = 10) -> str:
    """Generate wait_for_gone code."""
    return f"wait_for_gone('{path}', timeout={timeout})\n"
```

Update the imports at the top of `tests/test_code_gen.py`:

```python
from autotest_ide.core.code_gen import (
    OpMode, gen_click, gen_assert_exists,
    gen_long_click, gen_swipe, gen_input,
    gen_wait_for, gen_wait_for_gone,
)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd E:/AutoTestIDE && python -m pytest tests/test_code_gen.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
cd E:/AutoTestIDE && git add src/autotest_ide/core/code_gen.py tests/test_code_gen.py && git commit -m "feat: add gen_long_click, gen_swipe, gen_input, gen_wait_for, gen_wait_for_gone"
```

---

### Task 3: 重构 locator.py — 移除 generate_locator_code，迁移到 code_gen

**Files:**
- Modify: `src/autotest_ide/core/locator.py`
- Modify: `tests/test_locator.py`

- [ ] **Step 1: Update test_locator.py — 移除 generate_locator_code 测试**

Remove all `test_locator_code_*` tests from `tests/test_locator.py`. Update import to only `generate_locator`:

```python
# tests/test_locator.py
import pytest

from autotest_ide.core.locator import generate_locator


def test_name_unique():
    node = {"name": "Button_Play", "type": "Button", "payload": {"text": ""}}
    assert generate_locator(node, all_nodes=[node]) == "poco('Button_Play')"


def test_name_not_unique_uses_type():
    node = {"name": "Btn", "type": "Button", "payload": {"text": ""}}
    other = {"name": "Btn", "type": "Label", "payload": {"text": ""}}
    assert generate_locator(node, all_nodes=[node, other]) == "poco(name='Btn', type='Button')"


def test_name_empty_uses_text_and_type():
    node = {"name": "", "type": "Button", "payload": {"text": "Play"}}
    assert generate_locator(node) == "poco(text='Play', type='Button')"


def test_name_and_text_empty_uses_type():
    node = {"name": "", "type": "Button", "payload": {"text": ""}}
    assert generate_locator(node) == "poco(type='Button')"


def test_all_empty_uses_node_id():
    node = {"node_id": "btn_play", "name": "", "type": "", "payload": {"text": ""}}
    assert generate_locator(node) == "poco(node_id='btn_play')"


def test_name_unique_without_all_nodes():
    node = {"name": "Button_Play", "type": "Button", "payload": {"text": ""}}
    assert generate_locator(node) == "poco('Button_Play')"


def test_name_with_quotes_escaped():
    node = {"name": 'My "Button"', "type": "Button", "payload": {"text": ""}}
    assert generate_locator(node) == """poco('My "Button"')"""


def test_text_with_quotes_escaped():
    node = {"name": "", "type": "Button", "payload": {"text": "He said 'hi'"}}
    assert generate_locator(node) == """poco(text="He said 'hi'", type='Button')"""
```

- [ ] **Step 2: Remove generate_locator_code from locator.py**

Edit `src/autotest_ide/core/locator.py` — remove `generate_locator_code`, `_build_parent_map`, `_flatten_nodes`, `_fallback_click`. The final file should only contain `generate_locator`:

```python
# src/autotest_ide/core/locator.py
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
```

Note: `_build_parent_map` and `_flatten_nodes` are also used by `code_gen.py`. We need to **keep** them in `locator.py` as internal helpers (or move them). Since `code_gen.py` already imports them, let's keep them in `locator.py` but not as public API — they stay as module-level functions:

Add back to `locator.py` (below `generate_locator`):

```python
def _build_parent_map(nodes: list) -> dict:
    """Map node_id -> (node dict, parent_id) without mutating input nodes."""
    flat = _flatten_nodes(nodes)
    by_id = {}
    parent_of = {}
    for node in flat:
        nid = node.get("node_id", "")
        if nid:
            by_id[nid] = node
    for node in flat:
        for child in node.get("children", []):
            cid = child.get("node_id", "")
            if cid and cid in by_id:
                parent_of[cid] = node.get("node_id", "")
    return by_id, parent_of


def _flatten_nodes(nodes: list) -> list:
    """Flatten a list of nodes (possibly nested) into a flat list."""
    result = []
    stack = list(nodes)
    while stack:
        node = stack.pop()
        result.append(node)
        stack.extend(reversed(node.get("children", [])))
    return result
```

- [ ] **Step 3: Run all tests to verify nothing is broken**

Run: `cd E:/AutoTestIDE && python -m pytest tests/test_locator.py tests/test_code_gen.py -v`
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
cd E:/AutoTestIDE && git add src/autotest_ide/core/locator.py tests/test_locator.py && git commit -m "refactor: remove generate_locator_code from locator.py, keep _build_parent_map and _flatten_nodes as internal helpers"
```

---

### Task 4: JX4 协议映射扩充

**Files:**
- Modify: `src/autotest_ide/sdks/jx4/protocol.py`
- Test: `tests/test_jx4_protocol.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_jx4_protocol.py`:

```python
def test_method_map_long_click():
    p = JX4Protocol()
    assert p.resolve_method("long_click") == "LongClick"


def test_method_map_swipe():
    p = JX4Protocol()
    assert p.resolve_method("swipe") == "Swipe"


def test_method_map_wait_for_node():
    p = JX4Protocol()
    assert p.resolve_method("wait_for_node") == "WaitForNode"


def test_method_map_wait_for_gone():
    p = JX4Protocol()
    assert p.resolve_method("wait_for_gone") == "WaitForNodeDisappear"


def test_method_map_drag():
    p = JX4Protocol()
    assert p.resolve_method("drag") == "dragObject"


def test_method_map_get_node_by_path():
    p = JX4Protocol()
    assert p.resolve_method("get_node_by_path") == "findObject"


def test_encode_long_click():
    data = _encode_request("LongClick", (540, 960, 2.0), {})
    assert data == b"LongClick;540;960;2.0;&"


def test_encode_swipe():
    data = _encode_request("Swipe", (100, 200, 300, 400, 0.5), {})
    assert data == b"Swipe;100;200;300;400;0.5;&"


def test_encode_wait_for_node():
    data = _encode_request("WaitForNode", ("Panel/Btn", 10.0), {})
    assert data == b"WaitForNode;Panel/Btn;10.0;&"


def test_encode_find_object():
    data = _encode_request("findObject", ("path", "Panel/Btn"), {})
    assert data == b"findObject;path;Panel/Btn;&"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd E:/AutoTestIDE && python -m pytest tests/test_jx4_protocol.py -v -k "long_click or swipe or wait_for or drag or get_node"`
Expected: FAIL — `assert 'long_click' == 'LongClick'`

- [ ] **Step 3: Update METHOD_MAP**

Edit `src/autotest_ide/sdks/jx4/protocol.py` — add new entries to `METHOD_MAP`:

```python
    METHOD_MAP = {
        "dump_hierarchy": "getHierarchy",
        "get_attributes": "getInspector",
        "inspect_by_point": "getNodeByPos",
        "click": "tap",
        "find_and_tap": "findObjectAndTap",
        "set_text": "setText",
        "get_server_version": "getServerVersion",
        "get_screen_size": "getScreen",
        # --- new mappings ---
        "long_click":        "LongClick",
        "swipe":             "Swipe",
        "wait_for_node":     "WaitForNode",
        "wait_for_gone":     "WaitForNodeDisappear",
        "drag":              "dragObject",
        "get_node_by_path":  "findObject",
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd E:/AutoTestIDE && python -m pytest tests/test_jx4_protocol.py -v -k "long_click or swipe or wait_for or drag or get_node"`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
cd E:/AutoTestIDE && git add src/autotest_ide/sdks/jx4/protocol.py tests/test_jx4_protocol.py && git commit -m "feat: add JX4 METHOD_MAP entries for LongClick, Swipe, WaitFor, drag, findObject"
```

---

### Task 5: PocoClient 新增 6 个方法

**Files:**
- Modify: `src/autotest_ide/core/poco_client.py`
- Test: `tests/test_poco_client.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_poco_client.py`:

```python
def test_long_click_sends_correct_request(fake_server):
    client = PocoClient(host=fake_server.host, port=fake_server.port)
    client.connect()
    try:
        result = client.long_click(540, 960, duration=2.0)
        assert result == {}  # FakePocoServer returns {} for Click
    finally:
        client.close()


def test_swipe_sends_correct_request(fake_server):
    client = PocoClient(host=fake_server.host, port=fake_server.port)
    client.connect()
    try:
        result = client.swipe(100, 200, 300, 400, duration=0.5)
        assert result == {}
    finally:
        client.close()


def test_drag_sends_correct_request(fake_server):
    client = PocoClient(host=fake_server.host, port=fake_server.port)
    client.connect()
    try:
        result = client.drag("node_1", 500, 600)
        assert result == {}
    finally:
        client.close()


def test_wait_for_node_sends_correct_request(fake_server):
    client = PocoClient(host=fake_server.host, port=fake_server.port)
    client.connect()
    try:
        result = client.wait_for_node("Panel/Btn", timeout=10.0)
        assert result == {}
    finally:
        client.close()


def test_wait_for_gone_sends_correct_request(fake_server):
    client = PocoClient(host=fake_server.host, port=fake_server.port)
    client.connect()
    try:
        result = client.wait_for_gone("Panel/Loading", timeout=10.0)
        assert result == {}
    finally:
        client.close()


def test_get_node_by_path_sends_correct_request(fake_server):
    client = PocoClient(host=fake_server.host, port=fake_server.port)
    client.connect()
    try:
        result = client.get_node_by_path("Panel/Btn")
        assert result == {}
    finally:
        client.close()
```

Note: `FakePocoServer._dispatch` currently returns `{"error": ...}` for unknown methods. We need to add a catch-all that returns `{}` for the new operations. Edit `tests/fake_poco_server.py`:

```python
    def _dispatch(self, method, pos_args, kwargs):
        self.request_count += 1
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

        # --- Accept all new operation methods with empty success ---
        if method in ("Click", "SetText", "LongClick", "Swipe",
                      "WaitForNode", "WaitForNodeDisappear",
                      "dragObject", "findObject", "tap",
                      "findObjectAndTap", "getHierarchy"):
            return {}

        if method == "GetScreen":
            return None

        return {"error": {"code": -32601, "message": f"method not found: {method}"}}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd E:/AutoTestIDE && python -m pytest tests/test_poco_client.py -v -k "long_click or swipe or drag or wait_for or get_node"`
Expected: FAIL — `AttributeError: 'PocoClient' object has no attribute 'long_click'`

- [ ] **Step 3: Add the 6 methods to PocoClient**

Append to `src/autotest_ide/core/poco_client.py` (after `set_text` method, before `_flatten_tree`):

```python
    def long_click(self, x: int, y: int, duration: float = 2.0) -> dict:
        return self._request_json("long_click", x, y, duration)

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration: float = 0.5) -> dict:
        return self._request_json("swipe", x1, y1, x2, y2, duration)

    def drag(self, node_id: str, x2: int, y2: int) -> dict:
        return self._request_json("drag", node_id, x2, y2)

    def wait_for_node(self, path: str, timeout: float = 10.0) -> dict:
        return self._request_json("wait_for_node", path, timeout)

    def wait_for_gone(self, path: str, timeout: float = 10.0) -> dict:
        return self._request_json("wait_for_gone", path, timeout)

    def get_node_by_path(self, path: str) -> dict:
        return self._request_json("get_node_by_path", path)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd E:/AutoTestIDE && python -m pytest tests/test_poco_client.py -v -k "long_click or swipe or drag or wait_for or get_node"`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
cd E:/AutoTestIDE && git add src/autotest_ide/core/poco_client.py tests/test_poco_client.py tests/fake_poco_server.py && git commit -m "feat: add long_click, swipe, drag, wait_for_node, wait_for_gone, get_node_by_path to PocoClient"
```

---

### Task 6: RecordingPocoClient 扩充 5 个操作录制

**Files:**
- Modify: `src/autotest_ide/runner/recorder.py`
- Test: `tests/test_recorder.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_recorder.py`:

```python
def test_long_click_records_step():
    inner = MagicMock()
    inner.screenshot.return_value = b"\x89PNG"
    reporter = MagicMock()
    rec = RecordingPocoClient(inner, reporter)

    rec.long_click(540, 960, duration=2.0)
    reporter.step_start.assert_called_once_with("long_click(540, 960, duration=2.0)")
    reporter.step_pass.assert_called_once()
    inner.long_click.assert_called_once_with(540, 960, duration=2.0)


def test_long_click_failure_records_fail():
    inner = MagicMock()
    inner.long_click.side_effect = Exception("timeout")
    inner.screenshot.return_value = b"\x89PNG"
    reporter = MagicMock()
    rec = RecordingPocoClient(inner, reporter)

    with pytest.raises(Exception, match="timeout"):
        rec.long_click(540, 960)
    reporter.step_start.assert_called_once()
    reporter.step_fail.assert_called_once()


def test_swipe_records_step():
    inner = MagicMock()
    inner.screenshot.return_value = b"\x89PNG"
    reporter = MagicMock()
    rec = RecordingPocoClient(inner, reporter)

    rec.swipe(100, 200, 300, 400, duration=0.5)
    reporter.step_start.assert_called_once_with("swipe(100, 200, 300, 400, duration=0.5)")
    reporter.step_pass.assert_called_once()
    inner.swipe.assert_called_once_with(100, 200, 300, 400, duration=0.5)


def test_drag_records_step():
    inner = MagicMock()
    inner.screenshot.return_value = b"\x89PNG"
    reporter = MagicMock()
    rec = RecordingPocoClient(inner, reporter)

    rec.drag("node_1", 500, 600)
    reporter.step_start.assert_called_once_with("drag('node_1', 500, 600)")
    reporter.step_pass.assert_called_once()
    inner.drag.assert_called_once_with("node_1", 500, 600)


def test_wait_for_node_records_step():
    inner = MagicMock()
    inner.screenshot.return_value = b"\x89PNG"
    reporter = MagicMock()
    rec = RecordingPocoClient(inner, reporter)

    rec.wait_for_node("Panel/Btn", timeout=10.0)
    reporter.step_start.assert_called_once_with("wait_for_node('Panel/Btn', timeout=10.0)")
    reporter.step_pass.assert_called_once()
    inner.wait_for_node.assert_called_once_with("Panel/Btn", timeout=10.0)


def test_wait_for_gone_records_step():
    inner = MagicMock()
    inner.screenshot.return_value = b"\x89PNG"
    reporter = MagicMock()
    rec = RecordingPocoClient(inner, reporter)

    rec.wait_for_gone("Panel/Loading", timeout=15.0)
    reporter.step_start.assert_called_once_with("wait_for_gone('Panel/Loading', timeout=15.0)")
    reporter.step_pass.assert_called_once()
    inner.wait_for_gone.assert_called_once_with("Panel/Loading", timeout=15.0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd E:/AutoTestIDE && python -m pytest tests/test_recorder.py -v -k "long_click or swipe or drag or wait_for"`
Expected: FAIL — `AttributeError: 'RecordingPocoClient' object has no attribute 'long_click'`

- [ ] **Step 3: Add the 5 recording methods**

Append to `src/autotest_ide/runner/recorder.py` (before `__getattr__`):

```python
    def long_click(self, x: int, y: int, duration: float = 2.0):
        self._reporter.step_start(f"long_click({x}, {y}, duration={duration})")
        try:
            self._inner.long_click(x, y, duration=duration)
            self._reporter.step_pass(screenshot=self._inner.screenshot())
        except Exception as e:
            try:
                shot = self._inner.screenshot()
            except Exception:
                logger.warning("Screenshot fallback failed after long_click error", exc_info=True)
                shot = b""
            self._reporter.step_fail(error=str(e), screenshot=shot)
            raise

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration: float = 0.5):
        self._reporter.step_start(f"swipe({x1}, {y1}, {x2}, {y2}, duration={duration})")
        try:
            self._inner.swipe(x1, y1, x2, y2, duration=duration)
            self._reporter.step_pass(screenshot=self._inner.screenshot())
        except Exception as e:
            try:
                shot = self._inner.screenshot()
            except Exception:
                logger.warning("Screenshot fallback failed after swipe error", exc_info=True)
                shot = b""
            self._reporter.step_fail(error=str(e), screenshot=shot)
            raise

    def drag(self, node_id: str, x2: int, y2: int):
        self._reporter.step_start(f"drag({node_id!r}, {x2}, {y2})")
        try:
            self._inner.drag(node_id, x2, y2)
            self._reporter.step_pass(screenshot=self._inner.screenshot())
        except Exception as e:
            try:
                shot = self._inner.screenshot()
            except Exception:
                logger.warning("Screenshot fallback failed after drag error", exc_info=True)
                shot = b""
            self._reporter.step_fail(error=str(e), screenshot=shot)
            raise

    def wait_for_node(self, path: str, timeout: float = 10.0):
        self._reporter.step_start(f"wait_for_node({path!r}, timeout={timeout})")
        try:
            self._inner.wait_for_node(path, timeout=timeout)
            self._reporter.step_pass(screenshot=self._inner.screenshot())
        except Exception as e:
            try:
                shot = self._inner.screenshot()
            except Exception:
                logger.warning("Screenshot fallback failed after wait_for_node error", exc_info=True)
                shot = b""
            self._reporter.step_fail(error=str(e), screenshot=shot)
            raise

    def wait_for_gone(self, path: str, timeout: float = 10.0):
        self._reporter.step_start(f"wait_for_gone({path!r}, timeout={timeout})")
        try:
            self._inner.wait_for_gone(path, timeout=timeout)
            self._reporter.step_pass(screenshot=self._inner.screenshot())
        except Exception as e:
            try:
                shot = self._inner.screenshot()
            except Exception:
                logger.warning("Screenshot fallback failed after wait_for_gone error", exc_info=True)
                shot = b""
            self._reporter.step_fail(error=str(e), screenshot=shot)
            raise
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd E:/AutoTestIDE && python -m pytest tests/test_recorder.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
cd E:/AutoTestIDE && git add src/autotest_ide/runner/recorder.py tests/test_recorder.py && git commit -m "feat: add recording for long_click, swipe, drag, wait_for_node, wait_for_gone"
```

---

### Task 7: runtime.py 扩充 wait_for / wait_for_gone

**Files:**
- Modify: `src/autotest_ide/runner/runtime.py`
- Test: `tests/test_runtime.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_runtime.py`:

```python
def test_namespace_has_wait_for():
    recorder = MagicMock()
    reporter = MagicMock()
    ns = build_namespace(recorder, reporter)
    assert callable(ns["wait_for"])


def test_namespace_has_wait_for_gone():
    recorder = MagicMock()
    reporter = MagicMock()
    ns = build_namespace(recorder, reporter)
    assert callable(ns["wait_for_gone"])


def test_wait_for_delegates_to_poco():
    recorder = MagicMock()
    reporter = MagicMock()
    ns = build_namespace(recorder, reporter)
    ns["wait_for"]("Panel/Btn", timeout=10)
    recorder.wait_for_node.assert_called_once_with("Panel/Btn", 10)


def test_wait_for_gone_delegates_to_poco():
    recorder = MagicMock()
    reporter = MagicMock()
    ns = build_namespace(recorder, reporter)
    ns["wait_for_gone"]("Panel/Loading", timeout=15)
    recorder.wait_for_gone.assert_called_once_with("Panel/Loading", 15)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd E:/AutoTestIDE && python -m pytest tests/test_runtime.py -v -k "wait_for"`
Expected: FAIL — `KeyError: 'wait_for'`

- [ ] **Step 3: Add the helper functions**

Edit `src/autotest_ide/runner/runtime.py`:

```python
from autotest_ide.core.errors import PocoConnectionError
from autotest_ide.core.log import getLogger
from autotest_ide.runner.recorder import RecordingPocoClient
from autotest_ide.runner.reporter import Reporter

logger = getLogger(__name__)


class By:
    """Lookup strategies for ``poco.find_and_tap(by=...)``."""
    PATH = "path"
    NAME = "path"       # same as PATH for JX4
    TAG = "tag"
    LAYER = "layer"
    COMPONENT = "component"
    ID = "id"


def build_namespace(poco: RecordingPocoClient, reporter: Reporter) -> dict:
    def snapshot() -> None:
        shot = poco.screenshot()
        reporter.step_start("snapshot()")
        reporter.step_pass(screenshot=shot)

    def assert_exists(locator: str, msg: str = "") -> None:
        reporter.step_start(f"assert_exists({locator!r})")
        try:
            if not poco.heartbeat():
                raise PocoConnectionError("heartbeat failed")
            reporter.step_pass(screenshot=poco.screenshot())
        except Exception as e:
            reporter.step_fail(error=str(e), screenshot=poco.screenshot())
            logger.warning("assert_exists failed: %s", e)
            raise AssertionError(msg or str(e))

    def log(msg: str) -> None:
        reporter.step_start(f"log: {msg}")
        reporter.step_pass()
        print(msg)

    def wait_for(locator: str, timeout: int = 10) -> None:
        poco.wait_for_node(locator, timeout)

    def wait_for_gone(locator: str, timeout: int = 10) -> None:
        poco.wait_for_gone(locator, timeout)

    return {
        "auto": poco,
        "By": By,
        "snapshot": snapshot,
        "assert_exists": assert_exists,
        "log": log,
        "wait_for": wait_for,
        "wait_for_gone": wait_for_gone,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd E:/AutoTestIDE && python -m pytest tests/test_runtime.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
cd E:/AutoTestIDE && git add src/autotest_ide/runner/runtime.py tests/test_runtime.py && git commit -m "feat: add wait_for/wait_for_gone helpers to runtime namespace"
```

---

### Task 8: DevicePanel 改造 — 工具栏 + OpMode + 新信号 + 滑动交互

**Files:**
- Modify: `src/autotest_ide/ui/device_panel.py`
- Test: `tests/test_device_panel.py` (新增)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_device_panel.py
from PyQt5.QtCore import QPoint
from autotest_ide.core.code_gen import OpMode
from autotest_ide.ui.device_panel import DevicePanel, OverlayWidget


def test_default_opmode_is_click(qtbot):
    panel = DevicePanel()
    assert panel.op_mode == OpMode.CLICK


def test_opmode_switch_emits_correct_signal(qtbot):
    panel = DevicePanel()
    panel.resize(400, 600)
    clicks = []
    longs = []
    swipes = []
    inputs = []
    panel.inspect_requested.connect(lambda x, y: clicks.append((x, y)))
    panel.long_press_requested.connect(lambda x, y: longs.append((x, y)))
    panel.swipe_requested.connect(lambda x1, y1, x2, y2: swipes.append((x1, y1, x2, y2)))
    panel.input_text_requested.connect(lambda x, y: inputs.append((x, y)))
    # Simulate clicking each toolbar button
    panel._btn_long_press.click()
    assert panel.op_mode == OpMode.LONG_PRESS
    panel._btn_swipe.click()
    assert panel.op_mode == OpMode.SWIPE
    panel._btn_input.click()
    assert panel.op_mode == OpMode.INPUT
    panel._btn_click.click()
    assert panel.op_mode == OpMode.CLICK
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd E:/AutoTestIDE && python -m pytest tests/test_device_panel.py -v`
Expected: FAIL — `ImportError` or `AttributeError` for `op_mode`, `_btn_long_press`, etc.

- [ ] **Step 3: Implement DevicePanel with toolbar and new signals**

Replace entire `src/autotest_ide/ui/device_panel.py`:

```python
from PyQt5.QtCore import Qt, pyqtSignal, QRect, QPoint
from PyQt5.QtGui import QPixmap, QPainter, QPen, QColor
from PyQt5.QtWidgets import QLabel, QWidget, QVBoxLayout, QHBoxLayout, QToolButton

from autotest_ide.core.code_gen import OpMode


class OverlayWidget(QWidget):
    """Semi-transparent overlay for drawing highlight rectangles and swipe lines."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rects: list = []
        self._swipe_start: QPoint = QPoint()
        self._swipe_end: QPoint = QPoint()
        self._show_swipe: bool = False

    def set_rects(self, rects: list):
        self._rects = rects
        self.update()

    def set_swipe_line(self, start: QPoint, end: QPoint):
        self._swipe_start = start
        self._swipe_end = end
        self._show_swipe = True
        self.update()

    def clear_swipe_line(self):
        self._show_swipe = False
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        # Highlight rectangles
        pen = QPen(QColor("#f38ba8"), 2, Qt.DashLine)
        painter.setPen(pen)
        for r in self._rects:
            painter.drawRect(r)
        # Swipe trajectory line
        if self._show_swipe and not self._swipe_start.isNull() and not self._swipe_end.isNull():
            line_pen = QPen(QColor("#f38ba8"), 3, Qt.SolidLine)
            painter.setPen(line_pen)
            painter.drawLine(self._swipe_start, self._swipe_end)
            # Draw circles at start and end
            painter.setBrush(QColor("#f38ba8"))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(self._swipe_start, 5, 5)
            painter.drawEllipse(self._swipe_end, 5, 5)
        painter.end()


class DevicePanel(QWidget):
    """Device screenshot panel with operation mode toolbar."""

    inspect_requested = pyqtSignal(int, int)
    long_press_requested = pyqtSignal(int, int)
    swipe_requested = pyqtSignal(int, int, int, int)
    input_text_requested = pyqtSignal(int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(240)

        self._op_mode: OpMode = OpMode.CLICK

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # --- Operation mode toolbar ---
        toolbar = QWidget()
        toolbar.setObjectName("op_mode_bar")
        toolbar.setFixedHeight(32)
        tb_layout = QHBoxLayout(toolbar)
        tb_layout.setContentsMargins(4, 2, 4, 2)
        tb_layout.setSpacing(2)

        self._btn_click = self._make_mode_btn("🖱️ 点击", OpMode.CLICK, True)
        self._btn_long_press = self._make_mode_btn("✋ 长按", OpMode.LONG_PRESS)
        self._btn_swipe = self._make_mode_btn("↔️ 滑动", OpMode.SWIPE)
        self._btn_input = self._make_mode_btn("⌨️ 输入", OpMode.INPUT)

        tb_layout.addWidget(self._btn_click)
        tb_layout.addWidget(self._btn_long_press)
        tb_layout.addWidget(self._btn_swipe)
        tb_layout.addWidget(self._btn_input)
        tb_layout.addStretch()
        layout.addWidget(toolbar)

        # --- Screenshot label ---
        self._screenshot_label = QLabel()
        self._screenshot_label.setAlignment(Qt.AlignCenter)
        self._screenshot_label.setStyleSheet("background-color: #11111b;")
        layout.addWidget(self._screenshot_label)

        # --- Overlay ---
        self._overlay = OverlayWidget(self._screenshot_label)
        self._overlay.setGeometry(self._screenshot_label.geometry())

        # Screenshot geometry
        self._current_pixmap: QPixmap = QPixmap()
        self._scale_ratio: float = 1.0
        self._scaled_w: int = 0
        self._scaled_h: int = 0
        self._offset_x: float = 0.0
        self._offset_y: float = 0.0

        # Swipe state
        self._swipe_start_dev: tuple = (0, 0)  # device coordinates
        self._swiping: bool = False

    @property
    def op_mode(self) -> OpMode:
        return self._op_mode

    def _make_mode_btn(self, text: str, mode: OpMode, selected: bool = False) -> QToolButton:
        btn = QToolButton()
        btn.setText(text)
        btn.setToolButtonStyle(Qt.ToolButtonTextOnly)
        btn.setFixedHeight(26)
        btn.clicked.connect(lambda: self._set_op_mode(mode))
        self._update_btn_style(btn, mode == self._op_mode)
        return btn

    def _set_op_mode(self, mode: OpMode):
        self._op_mode = mode
        for btn, m in [
            (self._btn_click, OpMode.CLICK),
            (self._btn_long_press, OpMode.LONG_PRESS),
            (self._btn_swipe, OpMode.SWIPE),
            (self._btn_input, OpMode.INPUT),
        ]:
            self._update_btn_style(btn, m == mode)

    def _update_btn_style(self, btn: QToolButton, selected: bool):
        if selected:
            btn.setStyleSheet(
                "QToolButton { background: #f38ba8; color: #1e1e2e; "
                "border: none; border-radius: 4px; padding: 2px 8px; font-size: 12px; font-weight: bold; }"
            )
        else:
            btn.setStyleSheet(
                "QToolButton { background: #313244; color: #cdd6f4; "
                "border: none; border-radius: 4px; padding: 2px 8px; font-size: 12px; }"
            )

    def update_screenshot(self, data):
        if isinstance(data, bytes):
            pm = QPixmap()
            pm.loadFromData(data)
            if pm.isNull():
                return
            self._current_pixmap = pm
        else:
            self._current_pixmap = data
        label_size = self._screenshot_label.size()
        scaled = self._current_pixmap.scaled(label_size, Qt.KeepAspectRatio, Qt.FastTransformation)
        self._screenshot_label.setPixmap(scaled)
        if not self._current_pixmap.isNull() and label_size.width() > 0:
            self._scale_ratio = scaled.width() / self._current_pixmap.width()
            self._scaled_w = scaled.width()
            self._scaled_h = scaled.height()
            self._offset_x = (label_size.width() - scaled.width()) / 2
            self._offset_y = (label_size.height() - scaled.height()) / 2
        else:
            self._scale_ratio = 1.0

    def highlight_region(self, bounds: dict):
        if self._current_pixmap.isNull() or not bounds:
            self._overlay.set_rects([])
            return
        r = self._scale_ratio
        x = int(bounds.get("x", 0) * r)
        y = int(bounds.get("y", 0) * r)
        w = int(bounds.get("width", 0) * r)
        h = int(bounds.get("height", 0) * r)
        self._overlay.set_rects([QRect(x, y, w, h)])
        self._overlay.raise_()

    def clear_highlight(self):
        self._overlay.set_rects([])

    def _widget_to_device(self, pos) -> tuple:
        """Convert widget position to device pixel coordinates."""
        lx = pos.x() - self._screenshot_label.pos().x() - self._offset_x
        ly = pos.y() - self._screenshot_label.pos().y() - self._offset_y
        if lx < 0 or ly < 0 or lx >= self._scaled_w or ly >= self._scaled_h:
            return None, None
        x = int(lx / self._scale_ratio)
        y = int(ly / self._scale_ratio)
        return x, y

    def _widget_to_overlay(self, pos) -> QPoint:
        """Convert widget position to overlay-local coordinates."""
        return QPoint(
            int(pos.x() - self._screenshot_label.pos().x() - self._offset_x),
            int(pos.y() - self._screenshot_label.pos().y() - self._offset_y),
        )

    def mousePressEvent(self, event):
        if self._current_pixmap.isNull() or self._scale_ratio == 0:
            return
        if event.button() != Qt.LeftButton:
            return
        x, y = self._widget_to_device(event.pos())
        if x is None:
            return

        if self._op_mode == OpMode.CLICK:
            self.inspect_requested.emit(x, y)
        elif self._op_mode == OpMode.LONG_PRESS:
            self.long_press_requested.emit(x, y)
        elif self._op_mode == OpMode.SWIPE:
            self._swipe_start_dev = (x, y)
            self._swiping = True
        elif self._op_mode == OpMode.INPUT:
            self.input_text_requested.emit(x, y)

    def mouseMoveEvent(self, event):
        if not self._swiping:
            return
        start_overlay = self._widget_to_overlay(
            self._screenshot_label.mapFromParent(
                QPoint(
                    int(self._swipe_start_dev[0] * self._scale_ratio + self._offset_x + self._screenshot_label.pos().x()),
                    int(self._swipe_start_dev[1] * self._scale_ratio + self._offset_y + self._screenshot_label.pos().y()),
                )
            )
        )
        end_overlay = self._widget_to_overlay(event.pos())
        self._overlay.set_swipe_line(start_overlay, end_overlay)

    def mouseReleaseEvent(self, event):
        if not self._swiping:
            return
        self._swiping = False
        self._overlay.clear_swipe_line()

        x2, y2 = self._widget_to_device(event.pos())
        if x2 is None:
            return
        x1, y1 = self._swipe_start_dev
        dx = abs(x2 - x1)
        dy = abs(y2 - y1)
        if dx < 10 and dy < 10:
            return  # Too short, ignore
        self.swipe_requested.emit(x1, y1, x2, y2)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._overlay.setGeometry(self._screenshot_label.geometry())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd E:/AutoTestIDE && python -m pytest tests/test_device_panel.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
cd E:/AutoTestIDE && git add src/autotest_ide/ui/device_panel.py tests/test_device_panel.py && git commit -m "feat: add op mode toolbar, new signals, and swipe interaction to DevicePanel"
```

---

### Task 9: PocoWorker 扩展 — 新增 long_press / swipe / input_text

**Files:**
- Modify: `src/autotest_ide/ui/threads.py`
- Test: `tests/test_threads.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_threads.py`:

```python
from unittest.mock import MagicMock, PropertyMock
from autotest_ide.ui.threads import PocoWorker


def _make_device():
    device = MagicMock()
    device.status = "online"
    device.poco.screenshot.return_value = b"\x89PNG"
    device.poco.inspect_by_point.return_value = {"name": "Btn", "node_id": "1", "payload": {}}
    return device


def test_poco_worker_long_press_emits_inspect_result(qtbot):
    device = _make_device()
    device.poco.long_click.return_value = {}
    worker = PocoWorker(device)
    results = []
    fails = []
    worker.inspect_result.connect(lambda n, s: results.append((n, s)))
    worker.inspect_failed.connect(lambda e, x, y: fails.append((e, x, y)))
    worker.long_press(540, 960, duration=2.0)
    with qtbot.waitSignal(worker.inspect_result, timeout=5000):
        worker.start()
        worker.wait(5000)
    assert len(results) == 1
    device.poco.long_click.assert_called_once_with(540, 960, duration=2.0)


def test_poco_worker_swipe_emits_swipe_done(qtbot):
    device = _make_device()
    device.poco.swipe.return_value = {}
    worker = PocoWorker(device)
    done = []
    worker.swipe_done.connect(lambda s: done.append(s))
    worker.swipe(100, 200, 300, 400, duration=0.5)
    with qtbot.waitSignal(worker.swipe_done, timeout=5000):
        worker.start()
        worker.wait(5000)
    assert len(done) == 1
    device.poco.swipe.assert_called_once_with(100, 200, 300, 400, duration=0.5)


def test_poco_worker_input_text_emits_inspect_result(qtbot):
    device = _make_device()
    device.poco.set_text.return_value = {}
    worker = PocoWorker(device)
    results = []
    worker.inspect_result.connect(lambda n, s: results.append((n, s)))
    worker.input_text(540, 960, "hello")
    with qtbot.waitSignal(worker.inspect_result, timeout=5000):
        worker.start()
        worker.wait(5000)
    assert len(results) == 1
    device.poco.inspect_by_point.assert_called_once_with(540, 960)
    device.poco.set_text.assert_called_once_with("1", "hello")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd E:/AutoTestIDE && python -m pytest tests/test_threads.py -v -k "long_press or swipe or input_text"`
Expected: FAIL — `AttributeError: 'PocoWorker' object has no attribute 'long_press'`

- [ ] **Step 3: Implement PocoWorker new methods**

Edit `src/autotest_ide/ui/threads.py` — replace the `PocoWorker` class:

```python
class PocoWorker(QThread):
    inspect_result = pyqtSignal(dict, bytes)
    inspect_failed = pyqtSignal(str, int, int)
    swipe_done = pyqtSignal(bytes)

    def __init__(self, device: Device, parent=None):
        super().__init__(parent)
        self._device = device
        self._task = None

    def inspect(self, x: int, y: int):
        if self.isRunning():
            return
        self._task = ("inspect", x, y)
        self.start()

    def long_press(self, x: int, y: int, duration: float = 2.0):
        if self.isRunning():
            return
        self._task = ("long_press", x, y, duration)
        self.start()

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration: float = 0.5):
        if self.isRunning():
            return
        self._task = ("swipe", x1, y1, x2, y2, duration)
        self.start()

    def input_text(self, x: int, y: int, text: str):
        if self.isRunning():
            return
        self._task = ("input_text", x, y, text)
        self.start()

    def run(self):
        if not self._task:
            return
        kind = self._task[0]
        try:
            if kind == "inspect":
                x, y = self._task[1], self._task[2]
                result = self._device.poco.inspect_by_point(x, y)
                shot = self._device.poco.screenshot()
                self.inspect_result.emit(result, shot)
            elif kind == "long_press":
                x, y, duration = self._task[1], self._task[2], self._task[3]
                self._device.poco.long_click(x, y, duration=duration)
                result = self._device.poco.inspect_by_point(x, y)
                shot = self._device.poco.screenshot()
                self.inspect_result.emit(result, shot)
            elif kind == "swipe":
                x1, y1, x2, y2, duration = (
                    self._task[1], self._task[2],
                    self._task[3], self._task[4], self._task[5],
                )
                self._device.poco.swipe(x1, y1, x2, y2, duration=duration)
                shot = self._device.poco.screenshot()
                self.swipe_done.emit(shot)
            elif kind == "input_text":
                x, y, text = self._task[1], self._task[2], self._task[3]
                result = self._device.poco.inspect_by_point(x, y)
                node_id = result.get("node_id", "")
                if node_id:
                    self._device.poco.set_text(node_id, text)
                shot = self._device.poco.screenshot()
                self.inspect_result.emit(result, shot)
        except Exception as e:
            if kind in ("inspect", "long_press", "input_text"):
                x = self._task[1]
                y = self._task[2]
                logger.warning("PocoWorker %s failed at (%d, %d): %s", kind, x, y, e)
                self.inspect_failed.emit(str(e), x, y)
            elif kind == "swipe":
                logger.warning("PocoWorker swipe failed: %s", e)
                self.inspect_failed.emit(str(e), 0, 0)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd E:/AutoTestIDE && python -m pytest tests/test_threads.py -v -k "long_press or swipe or input_text"`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
cd E:/AutoTestIDE && git add src/autotest_ide/ui/threads.py tests/test_threads.py && git commit -m "feat: add long_press, swipe, input_text to PocoWorker with swipe_done signal"
```

---

### Task 10: RecordController 改造 — op_mode 参数 + 断言插入

**Files:**
- Modify: `src/autotest_ide/ui/record_controller.py`
- Test: `tests/test_record_controller.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_record_controller.py`:

```python
from autotest_ide.core.code_gen import OpMode


def test_record_click_emits_find_and_tap():
    rc = RecordController()
    emitted = []
    rc.code_generated.connect(lambda code: emitted.append(code))
    rc.start([
        {"name": "root", "type": "", "node_id": "0", "children": [
            {"name": "Play", "type": "Button", "node_id": "1", "children": []},
        ]},
    ])
    node = {"name": "Play", "type": "Button", "payload": {}, "node_id": "1"}
    rc.on_inspect_result(node, 100, 200, OpMode.CLICK)
    assert len(emitted) == 1
    assert "auto.find_and_tap('Play')" in emitted[0]


def test_record_click_with_assert():
    rc = RecordController()
    emitted = []
    rc.code_generated.connect(lambda code: emitted.append(code))
    rc.start([
        {"name": "root", "type": "", "node_id": "0", "children": [
            {"name": "Play", "type": "Button", "node_id": "1", "children": []},
        ]},
    ])
    node = {"name": "Play", "type": "Button", "payload": {}, "node_id": "1"}
    rc.on_inspect_result(node, 100, 200, OpMode.CLICK)
    # Should emit both assert and click
    assert len(emitted) == 2
    assert "assert_exists" in emitted[0]
    assert "auto.find_and_tap" in emitted[1]


def test_record_click_fallback_no_assert():
    rc = RecordController()
    emitted = []
    rc.code_generated.connect(lambda code: emitted.append(code))
    rc.start([])
    rc.on_inspect_failed(300, 400, OpMode.CLICK)
    assert len(emitted) == 1
    assert "auto.click(300, 400)" in emitted[0]
    assert "assert" not in emitted[0]


def test_record_long_press_emits_long_click():
    rc = RecordController()
    emitted = []
    rc.code_generated.connect(lambda code: emitted.append(code))
    rc.start([])
    rc.on_inspect_failed(100, 200, OpMode.LONG_PRESS)
    assert len(emitted) == 1
    assert "auto.long_click(100, 200)" in emitted[0]


def test_record_swipe_emits_swipe():
    rc = RecordController()
    emitted = []
    rc.code_generated.connect(lambda code: emitted.append(code))
    rc.start([])
    rc.on_swipe_done(100, 200, 300, 400)
    assert len(emitted) == 1
    assert "auto.swipe(100, 200, 300, 400)" in emitted[0]


def test_record_input_emits_set_text():
    rc = RecordController()
    emitted = []
    rc.code_generated.connect(lambda code: emitted.append(code))
    rc.start([
        {"name": "root", "type": "", "node_id": "0", "children": [
            {"name": "Field", "type": "InputField", "node_id": "7", "children": []},
        ]},
    ])
    node = {"name": "Field", "type": "InputField", "payload": {}, "node_id": "7"}
    rc.on_inspect_result(node, 50, 60, OpMode.INPUT, text="hello")
    assert len(emitted) == 2
    assert "assert_exists" in emitted[0]
    assert "auto.set_text('Field', 'hello')" in emitted[1]


def test_record_input_fallback_no_assert():
    rc = RecordController()
    emitted = []
    rc.code_generated.connect(lambda code: emitted.append(code))
    rc.start([])
    rc.on_inspect_failed(50, 60, OpMode.INPUT, text="hello")
    assert len(emitted) == 1
    assert "auto.click(50, 60)" in emitted[0]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd E:/AutoTestIDE && python -m pytest tests/test_record_controller.py -v`
Expected: FAIL — `TypeError: on_inspect_result() takes 4 positional arguments but 5 were given`

- [ ] **Step 3: Implement the new RecordController**

Replace `src/autotest_ide/ui/record_controller.py`:

```python
from PyQt5.QtCore import QObject, pyqtSignal

from autotest_ide.core.code_gen import OpMode, gen_click, gen_assert_exists, gen_long_click, gen_swipe, gen_input
from autotest_ide.core.log import getLogger

logger = getLogger(__name__)


class RecordController(QObject):
    code_generated = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._recording = False
        self._cached_flat: list = []

    @property
    def is_recording(self) -> bool:
        return self._recording

    def start(self, cached_flat: list):
        self._recording = True
        self._cached_flat = cached_flat
        logger.info("Recording started")

    def stop(self):
        self._recording = False
        self._cached_flat = []
        logger.info("Recording stopped")

    def on_inspect_result(self, node: dict, x: int, y: int, op_mode: OpMode = OpMode.CLICK, text: str = ""):
        if not self._recording:
            return

        if op_mode == OpMode.CLICK:
            code = gen_click(node, self._cached_flat, x, y)
            if code:
                assertion = gen_assert_exists(node, self._cached_flat)
                if assertion:
                    self.code_generated.emit(assertion)
                self.code_generated.emit(code)
            return

        if op_mode == OpMode.LONG_PRESS:
            code = gen_long_click(node, self._cached_flat, x, y)
            if code:
                assertion = gen_assert_exists(node, self._cached_flat)
                if assertion:
                    self.code_generated.emit(assertion)
                self.code_generated.emit(code)
            return

        if op_mode == OpMode.INPUT:
            code = gen_input(node, self._cached_flat, x, y, text)
            if code:
                assertion = gen_assert_exists(node, self._cached_flat)
                if assertion:
                    self.code_generated.emit(assertion)
                self.code_generated.emit(code)
            return

    def on_inspect_failed(self, x: int, y: int, op_mode: OpMode = OpMode.CLICK, text: str = ""):
        if not self._recording:
            return

        if op_mode == OpMode.CLICK:
            self.code_generated.emit(f"auto.click({x}, {y})\n")
        elif op_mode == OpMode.LONG_PRESS:
            self.code_generated.emit(f"auto.long_click({x}, {y})\n")
        elif op_mode == OpMode.INPUT:
            self.code_generated.emit(f"auto.click({x}, {y})  # set_text fallback\n")
        else:
            self.code_generated.emit(f"auto.click({x}, {y})\n")

    def on_swipe_done(self, x1: int, y1: int, x2: int, y2: int):
        if not self._recording:
            return
        self.code_generated.emit(gen_swipe(x1, y1, x2, y2))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd E:/AutoTestIDE && python -m pytest tests/test_record_controller.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
cd E:/AutoTestIDE && git add src/autotest_ide/ui/record_controller.py tests/test_record_controller.py && git commit -m "feat: rewrite RecordController with op_mode support and assert insertion"
```

---

### Task 11: MainWindow 编排 — 新信号连接 + 槽函数 + op_mode 传递

**Files:**
- Modify: `src/autotest_ide/ui/main_window.py`

- [ ] **Step 1: Update imports**

Change the import of `generate_locator_code` to use `code_gen`:

```python
# Replace:
from autotest_ide.core.locator import generate_locator_code

# With:
from autotest_ide.core.code_gen import OpMode, gen_click, gen_assert_exists, gen_long_click, gen_input, gen_swipe
```

- [ ] **Step 2: Add new signal connections in `_init_connections`**

After the existing `inspect_requested` connection, add:

```python
        self.device_panel.long_press_requested.connect(self._on_long_press_requested)
        self.device_panel.swipe_requested.connect(self._on_swipe_requested)
        self.device_panel.input_text_requested.connect(self._on_input_text_requested)
```

- [ ] **Step 3: Add new slot methods**

After `_on_inspect_failed`, add:

```python
    def _on_long_press_requested(self, x: int, y: int):
        device = self._device_mgr.active
        if not device or device.status != "online":
            return
        self.status_coords.setText(f"  坐标: ({x}, {y})  ")
        self._last_inspect_xy = (x, y)
        if self._poco_worker and not self._poco_worker.isRunning():
            self._poco_worker.long_press(x, y, duration=2.0)
        else:
            self._on_inspect_failed("inspect worker busy or unavailable", x, y)

    def _on_swipe_requested(self, x1: int, y1: int, x2: int, y2: int):
        device = self._device_mgr.active
        if not device or device.status != "online":
            return
        self.status_coords.setText(f"  坐标: ({x1},{y1})→({x2},{y2})  ")
        self._last_swipe_xy = (x1, y1, x2, y2)
        if self._poco_worker and not self._poco_worker.isRunning():
            self._poco_worker.swipe(x1, y1, x2, y2, duration=0.5)
        else:
            self.console.append_warn("滑动操作失败: worker 忙碌")

    def _on_input_text_requested(self, x: int, y: int):
        device = self._device_mgr.active
        if not device or device.status != "online":
            return
        text, ok = QInputDialog.getText(self, "输入文本", "请输入要设置的文本:")
        if not ok or not text:
            return
        self.status_coords.setText(f"  坐标: ({x}, {y})  ")
        self._last_inspect_xy = (x, y)
        if self._poco_worker and not self._poco_worker.isRunning():
            self._poco_worker.input_text(x, y, text)
        else:
            self._on_inspect_failed("inspect worker busy or unavailable", x, y)
```

- [ ] **Step 4: Connect swipe_done in both connect methods**

In `_connect_selected_device` and `_connect_ip_device`, after connecting `inspect_failed`, add:

```python
        self._poco_worker.swipe_done.connect(self._on_swipe_done)
```

- [ ] **Step 5: Add _on_swipe_done slot**

```python
    def _on_swipe_done(self, screenshot: bytes):
        self.device_panel.update_screenshot(screenshot)
        x1, y1, x2, y2 = getattr(self, "_last_swipe_xy", (0, 0, 0, 0))
        code = gen_swipe(x1, y1, x2, y2)
        if self._record_controller.is_recording:
            self._record_controller.on_swipe_done(x1, y1, x2, y2)
        else:
            if code:
                self.editor.insert_locator_code(code)
```

- [ ] **Step 6: Update _on_inspect_result to use code_gen + op_mode**

```python
    def _on_inspect_result(self, node: dict, screenshot: bytes):
        self.device_panel.update_screenshot(screenshot)
        bounds = node.get("payload", {}).get("pos", {})
        if bounds:
            self.device_panel.highlight_region(bounds)
        node_id = node.get("node_id", "")
        if node_id:
            self.tree_panel.highlight_node(node_id)
        self.property_panel.show_properties(node.get("payload", {}))
        x, y = getattr(self, "_last_inspect_xy", (0, 0))
        op_mode = self.device_panel.op_mode
        text = getattr(self, "_last_input_text", "")
        if self._record_controller.is_recording:
            self._record_controller.on_inspect_result(node, x, y, op_mode, text=text)
        else:
            if op_mode == OpMode.CLICK:
                code = gen_click(node, self._cached_flat, x, y)
            elif op_mode == OpMode.LONG_PRESS:
                code = gen_long_click(node, self._cached_flat, x, y)
            elif op_mode == OpMode.INPUT:
                code = gen_input(node, self._cached_flat, x, y, text)
            else:
                code = gen_click(node, self._cached_flat, x, y)
            if code:
                self.editor.insert_locator_code(code)
```

- [ ] **Step 7: Update _on_inspect_failed to use op_mode**

```python
    def _on_inspect_failed(self, error: str, x: int, y: int):
        self.console.append_warn(f"检查节点失败: {error}")
        op_mode = self.device_panel.op_mode
        text = getattr(self, "_last_input_text", "")
        if self._record_controller.is_recording:
            self._record_controller.on_inspect_failed(x, y, op_mode, text=text)
        else:
            if op_mode == OpMode.LONG_PRESS:
                self.editor.insert_locator_code(f"auto.long_click({x}, {y})\n")
            elif op_mode == OpMode.INPUT:
                self.editor.insert_locator_code(f"auto.click({x}, {y})  # set_text fallback\n")
            else:
                self.editor.insert_locator_code(f"auto.click({x}, {y})\n")
```

- [ ] **Step 8: Add _last_swipe_xy and _last_input_text to __init__**

In `__init__`, after `self._last_inspect_xy = (0, 0)`, add:

```python
        self._last_swipe_xy = (0, 0, 0, 0)
        self._last_input_text = ""
```

- [ ] **Step 9: Store input text in _on_input_text_requested**

In `_on_input_text_requested`, after getting text from QInputDialog, add:

```python
        self._last_input_text = text
```

- [ ] **Step 10: Run full test suite**

Run: `cd E:/AutoTestIDE && python -m pytest tests/ -v --ignore=tests/test_real_device.py`
Expected: All PASS

- [ ] **Step 11: Commit**

```bash
cd E:/AutoTestIDE && git add src/autotest_ide/ui/main_window.py && git commit -m "feat: wire new device panel signals to MainWindow, use code_gen for code insertion"
```

---

### Task 12: 全量回归测试 + 清理

**Files:**
- All modified files

- [ ] **Step 1: Run the full test suite**

Run: `cd E:/AutoTestIDE && python -m pytest tests/ -v --ignore=tests/test_real_device.py`
Expected: All PASS

- [ ] **Step 2: Check for any remaining imports of generate_locator_code**

Run: `cd E:/AutoTestIDE && grep -r "generate_locator_code" src/ tests/`
Expected: No results (or only in comments)

- [ ] **Step 3: Commit any cleanup**

```bash
cd E:/AutoTestIDE && git add -A && git commit -m "chore: final cleanup after op-mode and code-gen refactor"
```
