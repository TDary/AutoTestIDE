# 操作模式切换 + 代码生成模块化 + 录制断言 设计文档

> 日期: 2026-07-08

## 1. 目标

实现点击截图后能生成多类型 UI 交互用例代码，包括：

- 操作模式切换 UI（单击/长按/滑动/输入）
- JX4 协议映射 LongClick/Swipe/WaitFor 等 + PocoClient 对应方法
- 代码生成模板模块化（`core/code_gen.py`）
- 录制模式下自动插入断言（assert_exists）
- Runner 层 RecordingPocoClient + runtime 扩充

**不包含**：P0 JX4 `getNodeByPos` 实现（等 Unity SDK 侧修复）。

---

## 2. 操作模式切换 UI

### 2.1 DevicePanel 改造

**文件**: `ui/device_panel.py`

在 `DevicePanel` 顶部增加 `QHBoxLayout` 工具栏，4 个 `QToolButton`：

| 按钮 | op_mode | 默认选中 |
|------|---------|---------|
| 🖱️ 点击 | `CLICK` | ✅ |
| ✋ 长按 | `LONG_PRESS` | |
| ↔️ 滑动 | `SWIPE` | |
| ⌨️ 输入 | `INPUT` | |

选中态：`#f38ba8` 粉色背景 + `#1e1e2e` 深色文字（与 Overlay 高亮色一致）。
未选中态：`#313244` 背景 + `#cdd6f4` 文字。

新增 `OpMode` 枚举（定义在 `core/code_gen.py`，UI 层 import）：

```python
class OpMode(Enum):
    CLICK = "click"
    LONG_PRESS = "long_click"
    SWIPE = "swipe"
    INPUT = "set_text"
```

`DevicePanel` 新增属性 `op_mode`，按钮切换时更新。

### 2.2 鼠标交互改造

| op_mode | mousePressEvent | mouseMoveEvent | mouseReleaseEvent |
|---------|----------------|-----------------|-------------------|
| CLICK | 记录坐标，发射 `inspect_requested(x, y)` | 无 | 无 |
| LONG_PRESS | 记录坐标，发射 `long_press_requested(x, y)` | 无 | 无 |
| SWIPE | 记录起点 `(x1, y1)` | 在 Overlay 上画轨迹线 | 记录终点 `(x2, y2)`，发射 `swipe_requested(x1,y1,x2,y2)` |
| INPUT | 记录坐标，发射 `input_text_requested(x, y)` | 无 | 无 |

### 2.3 新信号

```python
class DevicePanel(QWidget):
    inspect_requested = pyqtSignal(int, int)          # 已有
    long_press_requested = pyqtSignal(int, int)        # 新增
    swipe_requested = pyqtSignal(int, int, int, int)    # 新增 (x1,y1,x2,y2)
    input_text_requested = pyqtSignal(int, int)        # 新增
```

### 2.4 OverlayWidget 扩展

新增轨迹线绘制能力：

```python
class OverlayWidget(QWidget):
    def set_swipe_line(self, start: QPoint, end: QPoint):
        """设置滑动轨迹线（设备坐标空间，经 scale_ratio 缩放后绘制）"""
    def clear_swipe_line(self):
        """清除轨迹线"""
```

`paintEvent` 中额外绘制：粉色实线 + 起终点圆点（`#f38ba8`）。

滑动模式下 `mouseMoveEvent` 实时调用 `set_swipe_line` 刷新轨迹，`mouseReleaseEvent` 后调用 `clear_swipe_line`。

---

## 3. 协议映射 + PocoClient 新方法

### 3.1 JX4Protocol.METHOD_MAP 扩充

**文件**: `sdks/jx4/protocol.py`

```python
METHOD_MAP = {
    # 已有...
    "long_click":        "LongClick",
    "swipe":             "Swipe",
    "wait_for_node":     "WaitForNode",
    "wait_for_gone":     "WaitForNodeDisappear",
    "drag":              "dragObject",
    "get_node_by_path":  "findObject",
}
```

参数格式（对齐 AltrunUnityDriver 协议文档）：

- `LongClick;x;y;duration;&`
- `Swipe;x1;y1;x2;y2;duration;&`
- `WaitForNode;path;timeout;&`
- `WaitForNodeDisappear;path;timeout;&`
- `dragObject;alt_object_json;&`
- `findObject;by;value;&`

### 3.2 PocoClient 新增方法

**文件**: `core/poco_client.py`

| 方法 | 签名 | 请求格式 |
|------|------|----------|
| `long_click` | `(x: int, y: int, duration: float = 2.0)` | `_request_json("long_click", x, y, duration)` |
| `swipe` | `(x1: int, y1: int, x2: int, y2: int, duration: float = 0.5)` | `_request_json("swipe", x1, y1, x2, y2, duration)` |
| `drag` | `(node_id: str, x2: int, y2: int)` | `_request_json("drag", node_id, x2, y2)` |
| `wait_for_node` | `(path: str, timeout: float = 10.0)` | `_request_json("wait_for_node", path, timeout)` |
| `wait_for_gone` | `(path: str, timeout: float = 10.0)` | `_request_json("wait_for_gone", path, timeout)` |
| `get_node_by_path` | `(path: str)` | `_request_json("get_node_by_path", path)` |

### 3.3 RecordingPocoClient 扩充

**文件**: `runner/recorder.py`

为 `long_click`、`swipe`、`drag`、`wait_for_node`、`wait_for_gone` 添加录制步骤，与现有 `click`/`set_text`/`find_and_tap` 模式一致：`step_start` → try/`step_pass`/`step_fail`。

### 3.4 runtime.py 扩充

**文件**: `runner/runtime.py`

`build_namespace` 中增加辅助函数：

```python
def wait_for(locator: str, timeout: int = 10):
    poco.wait_for_node(locator, timeout)

def wait_for_gone(locator: str, timeout: int = 10):
    poco.wait_for_gone(locator, timeout)
```

`auto` 对象上的新方法通过 `RecordingPocoClient.__getattr__` 代理自动可用，无需额外处理。

---

## 4. 代码生成模板模块化

### 4.1 新模块 core/code_gen.py

**文件**: 新增 `core/code_gen.py`

`OpMode` 枚举定义于此（UI 和 RecordController 共享）。

生成函数签名：

```python
def gen_click(node: dict, flat_nodes: list, x: int, y: int) -> str
def gen_long_click(node: dict, flat_nodes: list, x: int, y: int, duration: float = 2.0) -> str
def gen_swipe(x1: int, y1: int, x2: int, y2: int, duration: float = 0.5) -> str
def gen_input(node: dict, flat_nodes: list, x: int, y: int, text: str) -> str
def gen_assert_exists(node: dict, flat_nodes: list) -> str
def gen_wait_for(path: str, timeout: int = 10) -> str
def gen_wait_for_gone(path: str, timeout: int = 10) -> str
```

每条生成规则：

| 操作 | 优先级 | 生成的代码 |
|------|--------|-----------|
| click | 1 | `auto.find_and_tap('A/B/C')\n` |
| click | 2 (fallback) | `auto.click(x, y)\n` |
| long_click | 1 | `auto.long_click(x, y, duration=2.0)\n` |
| swipe | - | `auto.swipe(x1, y1, x2, y2)\n` |
| input | 1 | `auto.set_text('A/B/C', 'text')\n` |
| input | 2 (fallback) | `auto.click(x, y)  # set_text fallback\n` |
| assert_exists | 1 | `assert_exists('A/B/C')\n` |
| assert_exists | - (无节点时) | 不生成 |
| wait_for | - | `wait_for('A/B/C', timeout=10)\n` |
| wait_for_gone | - | `wait_for_gone('A/B/C', timeout=10)\n` |

路径生成复用 `locator.py` 中 `_build_parent_map` 逻辑。`locator.py` 只保留 `generate_locator`（poco(...) 定位字符串），`generate_locator_code` 迁移到 `code_gen.py`。

### 4.2 断言插入策略

**仅在录制模式下**生效：

- `gen_click` / `gen_long_click` / `gen_input` 成功生成路径代码时，**先插入 `gen_assert_exists`，再插入操作代码**
- 如果 inspect 失败（无节点信息），跳过断言，只生成坐标操作
- 非录制模式下不插入断言

示例输出（录制模式，inspect 成功）：

```python
assert_exists('Denglu/BtnStart')
auto.find_and_tap('Denglu/BtnStart')
```

示例输出（录制模式，inspect 失败）：

```python
auto.click(100, 200)
```

### 4.3 调用方改造

**文件**: `ui/record_controller.py`

`on_inspect_result` 和 `on_inspect_failed` 新增 `op_mode` 参数，根据模式调用对应 `code_gen.gen_X` 函数。

**文件**: `ui/main_window.py`

- 非录制模式下的代码插入改用 `code_gen.gen_X`
- 新增 `_on_long_press_requested`、`_on_swipe_requested`、`_on_input_text_requested` 槽函数
- `_on_input_text_requested` 中弹出 `QInputDialog` 获取文本
- 从 `self.device_panel.op_mode` 读取当前模式传给 RecordController

---

## 5. 信号链路 + MainWindow 编排

### 5.1 PocoWorker 扩展

**文件**: `ui/threads.py`

| Worker 方法 | PocoClient 调用 | 发射信号 |
|-------------|----------------|---------|
| `inspect(x, y)` | `poco.inspect_by_point()` + `poco.screenshot()` | `inspect_result(node, bytes)` / `inspect_failed(str, x, y)` |
| `long_press(x, y, duration)` | `poco.long_click(x, y, duration)` + `poco.screenshot()` | `inspect_result(node, bytes)` / `inspect_failed(str, x, y)` |
| `swipe(x1, y1, x2, y2, duration)` | `poco.swipe(...)` + `poco.screenshot()` | `swipe_done(bytes)` |
| `input_text(x, y, text)` | `poco.inspect_by_point()` → 拿节点 → `poco.set_text(node_id, text)` + `poco.screenshot()` | `inspect_result(node, bytes)` / `inspect_failed(str, x, y)` |

新增信号：`swipe_done = pyqtSignal(bytes)`

### 5.2 MainWindow 槽函数

```python
def _on_long_press_requested(self, x, y):
    if not device online: return
    self.poco_worker.long_press(x, y, duration=2.0)

def _on_swipe_requested(self, x1, y1, x2, y2):
    if not device online: return
    self.poco_worker.swipe(x1, y1, x2, y2, duration=0.5)

def _on_input_text_requested(self, x, y):
    text, ok = QInputDialog.getText(self, "输入文本", "请输入要设置的文本:")
    if not ok or not text: return
    self.poco_worker.input_text(x, y, text)

def _on_swipe_done(self, screenshot_bytes):
    self.device_panel.update_screenshot(screenshot_bytes)
    code = code_gen.gen_swipe(x1, y1, x2, y2)  # 坐标从 poco_worker 取回
    if self.record_controller.is_recording:
        self.record_controller.code_generated.emit(code)
    else:
        self.editor.insert_locator_code(code)
```

### 5.3 op_mode 传递

`MainWindow` 从 `self.device_panel.op_mode` 读取当前模式，传给 `RecordController`，避免修改已有信号签名。

### 5.4 滑动防抖

滑动距离 < 10px（设备坐标空间）时忽略，不执行操作、不生成代码。

---

## 6. 错误处理

| 场景 | 处理方式 |
|------|---------|
| JX4 `getNodeByPos` 未实现 | `inspect_failed` 降级为坐标代码，与现有行为一致 |
| `LongClick`/`Swipe` 等 SDK 命令未注册 | `PocoProtocolError` 被捕获，`_on_inspect_failed` 降级，控制台打印警告 |
| 滑动距离太短（<10px 设备坐标） | 忽略，不生成代码，不执行操作 |
| 输入模式用户取消 QInputDialog | 不做任何事，回到待命状态 |
| 录制模式下切换 op_mode | 立即生效，下次鼠标操作用新模式，不影响已录制的代码 |
| 非录制模式下点击截图 | 根据当前 op_mode 生成对应操作类型的代码（单击/长按/滑动/输入） |

---

## 7. 测试策略

### 7.1 单元测试

| 测试文件 | 覆盖内容 |
|----------|---------|
| `tests/test_code_gen.py` | 新增：所有 `gen_*` 函数的路径生成、fallback、断言插入、各 op_mode |
| `tests/test_locator.py` | 扩展：确保 `generate_locator` 不受重构影响 |
| `tests/test_poco_client.py` | 扩展：`long_click`、`swipe`、`wait_for_node` 等新方法的请求格式 |
| `tests/test_jx4_protocol.py` | 扩展：METHOD_MAP 新映射、参数编码、`transform_result` |
| `tests/test_recorder.py` | 扩展：`RecordingPocoClient` 的新操作步骤录制 |
| `tests/test_record_controller.py` | 扩展：各 op_mode 下的代码生成 + 断言插入逻辑 |
| `tests/test_runtime.py` | 扩展：`wait_for`/`wait_for_gone` 辅助函数在 namespace 中存在 |

### 7.2 UI 集成测试

| 测试 | 验证点 |
|------|--------|
| `tests/test_threads.py` 扩展 | `PocoWorker.long_press`/`swipe` 信号发射正确 |
| `tests/test_device_panel.py` 新增 | op_mode 切换、滑动鼠标交互、轨迹线绘制 |
| `tests/test_main_window.py` 扩展 | 新信号链路连接、代码插入到编辑器 |

---

## 8. 变更文件清单

| 文件 | 变更类型 |
|------|---------|
| `core/code_gen.py` | **新增** |
| `core/locator.py` | 修改：移除 `generate_locator_code`，保留 `generate_locator` |
| `core/poco_client.py` | 修改：新增 6 个方法 |
| `sdks/jx4/protocol.py` | 修改：METHOD_MAP 扩充 |
| `runner/recorder.py` | 修改：新增 5 个操作录制方法 |
| `runner/runtime.py` | 修改：新增 `wait_for`/`wait_for_gone` |
| `ui/device_panel.py` | 修改：工具栏 + op_mode + 新信号 + 滑动交互 |
| `ui/threads.py` | 修改：PocoWorker 新增 3 个操作方法 + swipe_done 信号 |
| `ui/record_controller.py` | 修改：op_mode 参数 + 调用 code_gen |
| `ui/main_window.py` | 修改：新信号连接 + 槽函数 + op_mode 传递 |
