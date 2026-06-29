# Plan 3: PyQt UI Layer Design (M4 + M5)

**日期**: 2026-06-29
**状态**: Draft
**范围**: 里程碑 M4(投屏骨架) + M5(检选点 + UI 树联动)

**父 spec**: `docs/specs/2026-06-29-autotest-ide-clone-design.md` §5, §6
**前置 plan**: Plan 1 (M1+M2), Plan 2 (M3) 已完成

---

## 1. 目标与范围

### 1.1 目标

实现 spec §5-§6 的 UI 层:PyQt 主窗口四面板布局、设备投屏(5 FPS 轮询截图)、检选点流程(点投屏→命中节点→属性面板+UI 树高亮+编辑器插入代码)。

### 1.2 在范围内

- **M4 — UI 骨架(无检选点)**:
  - `app.py` — QApplication 启动
  - `__main__.py` — `python -m autotest_ide` 入口
  - `ui/main_window.py` — 主窗口四面板布局 + 菜单栏 + 工具栏
  - `ui/device_panel.py` — 左侧投屏面板(5 FPS 轮询 screenshot)
  - `ui/editor.py` — 中央代码编辑器(QPlainTextEdit 兜底)
  - `ui/threads.py` — QThread 封装(ScreenshotWorker, PocoWorker, DeviceBridge)
  - `ui/tree_panel.py` — 右侧 UI 树面板(QTreeView)
  - `ui/property_panel.py` — 右侧属性面板(QTableWidget)
  - `ui/console.py` — 右侧控制台面板(QTextEdit)
  - 工具栏:设备连接下拉框 + 运行/停止按钮(仅 UI,逻辑留 Plan 4)
  - 状态栏:设备状态 + 协议版本 + 光标坐标

- **M5 — 检选点 + UI 树联动**:
  - `core/locator.py` — 定位器生成策略(纯 Python,无 Qt 依赖)
  - 投屏点击 → `inspect_by_point(x, y)` → 命中节点
  - 投屏叠加红色框(visibleBounds)
  - 属性面板填充 payload.attributes
  - UI 树面板高亮对应节点
  - 编辑器光标处插入 `poco(...)` 代码

### 1.3 不在范围内(留后续 plan)

- **脚本运行子进程** (M6, Plan 4)
- **实时录制**
- **断点调试**
- **QScintilla** — Phase 1 用 QPlainTextEdit 兜底
- **macOS/Linux 打包**
- **自动化 UI 测试** — spec §8 明确 "Phase 1 不做自动化 UI 测试，手动测"

### 1.4 关键决策(补 spec 开放项)

1. **PyQt5 优先** — PyQt5 生态成熟,Windows 打包稳定。PyQt6 作兼容层但 Phase 1 不主打。
2. **QPlainTextEdit 兜底编辑器** — spec §11 风险登记,QScintilla 版本兼容问题。Phase 1 先用 QPlainTextEdit + QSyntaxHighlighter,后续可升级。
3. **ScreenshotWorker 单独 QThread** — 5 FPS 轮询截图是独立高频任务,与检选点 PocoWorker 分开,避免互斥阻塞。
4. **DeviceBridge 订阅 Device.on_status_change** — Plan 2 中 Device 的回调是普通 `Callable`,DeviceBridge 在回调中发射 Qt 信号,供 UI 更新。这是 Plan 2 设计 §5.4 预览的实现。
5. **检选点坐标换算** — 投屏 QLabel 显示缩放后的截图,点击坐标需按缩放比反算到逻辑像素坐标,再传给 `inspect_by_point`。

---

## 2. 架构

```
┌─ QApplication (app.py) ──────────────────────────────────────────┐
│                                                                   │
│  MainWindow                                                       │
│  ┌──────────┬─────────────────────────┬────────────────────────┐ │
│  │ DevicePanel│  Editor (QPlainTextEdit)│  RightSidebar(QTabWidget)│
│  │ (QLabel)  │                         │  ├ PropertyPanel       │ │
│  │  投屏     │                         │  ├ TreePanel           │ │
│  │  叠加框   │                         │  └ Console            │ │
│  └──────────┴─────────────────────────┴────────────────────────┘ │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │ StatusBar: 设备状态 | 协议版本 | 坐标                         │ │
│  └──────────────────────────────────────────────────────────────┘ │
│                                                                   │
│  Threads (ui/threads.py):                                         │
│  ├── ScreenshotWorker — 5 FPS 轮询 screenshot → QPixmap → 设投屏 │
│  ├── PocoWorker — inspect_by_point + screenshot → 信号回主线程   │
│  └── DeviceBridge — Device.on_status_change → Qt 信号           │
└──────────────────────────────────────────────────────────────────┘
```

**核心设计原则**(沿用 spec §9.1):

1. **`core/` 完全无 PyQt 依赖** — 新增 `core/locator.py` 也不引入 Qt。
2. **`ui/` 只依赖 `core/` 的接口** — 所有跨线程 PocoClient 调用通过 `ui/threads.py` QThread 封装。
3. **UI 永远不直接碰 PocoClient** — 通过 worker 信号/槽通信。

---

## 3. core/locator.py — 定位器生成

### 3.1 接口

```python
def generate_locator(node: dict, all_nodes: list[dict] = None) -> str:
    """给定检选点命中的节点(+ 可选的全树做唯一性校验),返回 poco(...) 字符串。

    策略(spec §6.4):
    1. name 非空且唯一 → poco("Button_Play")
    2. name 非空但不唯一 → poco(name="Button_Play", type="Button")
    3. name 为空 → poco(text="Play", type="Button")
    4. text 也为空 → poco(type="Button")
    5. type 也为空 → poco(node_id="btn_play")
    """
```

### 3.2 降级逻辑

| 条件 | 生成 | 例子 |
|---|---|---|
| name 非空 + 唯一 | `poco("{name}")` | `poco("Button_Play")` |
| name 非空 + 不唯一 | `poco(name="{name}", type="{type}")` | `poco(name="Btn", type="Button")` |
| name 空 + text 非空 | `poco(text="{text}", type="{type}")` | `poco(text="Play", type="Button")` |
| name+text 空 | `poco(type="{type}")` | `poco(type="Button")` |
| name+text+type 空 | `poco(node_id="{node_id}")` | `poco(node_id="btn_play")` |

---

## 4. ui/threads.py — QThread 封装

### 4.1 ScreenshotWorker

```python
class ScreenshotWorker(QThread):
    screenshot_ready = pyqtSignal(QPixmap)  # 截图帧 → 主线程设到 DevicePanel

    def __init__(self, device: Device, fps: int = 5):
        self._device = device
        self._fps = fps
        self._stop = threading.Event()

    def run(self):
        while not self._stop.wait(timeout=1.0/self._fps):
            if self._device.status != "online":
                continue
            try:
                png_bytes = self._device.poco.screenshot()
                pixmap = QPixmap()
                pixmap.loadFromData(png_bytes)
                self.screenshot_ready.emit(pixmap)
            except Exception:
                pass  # 单帧失败不中断

    def stop(self):
        self._stop.set()
```

### 4.2 PocoWorker

```python
class PocoWorker(QThread):
    inspect_result = pyqtSignal(dict, QPixmap)  # (命中节点, 当前截图)
    inspect_failed = pyqtSignal(str)             # 错误消息

    def __init__(self, device: Device):
        self._device = device
        self._task = None  # ("inspect", x, y) or ("screenshot",)

    def inspect(self, x: int, y: int):
        self._task = ("inspect", x, y)
        self.start()

    def run(self):
        if self._task[0] == "inspect":
            x, y = self._task[1], self._task[2]
            try:
                result = self._device.poco.inspect_by_point(x, y)
                shot = self._device.poco.screenshot()
                pixmap = QPixmap(); pixmap.loadFromData(shot)
                self.inspect_result.emit(result, pixmap)
            except Exception as e:
                self.inspect_failed.emit(str(e))
```

### 4.3 DeviceBridge

```python
class DeviceBridge(QObject):
    status_changed = pyqtSignal(str)  # 设备状态 → UI 更新

    def __init__(self, device: Device):
        self._device = device
        device.on_status_change(lambda s: self.status_changed.emit(s))
```

---

## 5. DevicePanel — 投屏 + 检选点

### 5.1 截图显示

- QLabel 承载 QPixmap, 保持宽高比缩放(`setScaledContents(False)` + `setPixmap(pixmap.scaled(size, KeepAspectRatio))`)
- ScreenshotWorker.screenshot_ready → 主线程槽 `update_screenshot(pixmap)`

### 5.2 点击检选点

- 重写 `mousePressEvent` → 算出缩放比 → 反算逻辑坐标 `(x, y)` → 发信号 `inspect_requested(x, y)` → MainWindow 调度 PocoWorker

### 5.3 命中框叠加

- 检选点命中后,在 QLabel 之上叠加一个透明 QWidget 画红色虚线框(visibleBounds 缩放后坐标)
- 下次点击时清除

---

## 6. TreePanel — UI 树

### 6.1 数据模型

- `QStandardItemModel`, 节点 → `QStandardItem`
- `dump_hierarchy` 返回的树递归填充
- 列: name | type | text

### 6.2 联动

- 检选点命中 → 树中搜索 node_id → 选中并展开到该节点
- 树节点点击 → 属性面板更新 + 投屏高亮对应区域

---

## 7. PropertyPanel — 属性表

- `QTableWidget` 两列: key | value
- 选中节点 → 填充 `payload` 所有字段(含 visibleBounds, text 等)
- value 单元格可选中复制

---

## 8. Editor — 代码编辑器

- `QPlainTextEdit` + `QSyntaxHighlighter` (Python 关键字高亮)
- 检选点命中后 → `generate_locator(node)` → 在光标位置插入一行:
  ```
  poco("Button_Play").click()
  ```

---

## 9. Deviations from spec

1. **QPlainTextEdit 代替 QScintilla** — spec §11 风险登记,Phase 1 兜底。QScintilla 版本兼容风险高。
2. **PyQt5 优先** — spec §9.2 写 "PyQt5>=5.15 或 PyQt6",Plan 3 选 PyQt5 作主线路。
3. **ScreenshotWorker 和 PocoWorker 分离** — spec §5.2 的线程模型只有 "PocoWorker",但 5 FPS 截图轮询是高频独立任务,单独线程避免与检选点互斥。

---

## 10. 验证标准(M4 + M5)

| 验证项 | 覆盖 |
|---|---|
| 主窗口四面板布局可见 | 手动验证 |
| 设备连接后投屏正常显示 | 手动 + ScreenshotWorker 单元测试 |
| 点投屏→命中节点→红色框+属性+树高亮+代码插入 | 手动 + locator.py 单元测试 |
| UI 不直接调用 PocoClient | 代码审查 |
| core/ 无 PyQt 依赖 | import 检查脚本 |

---

**文档结束**
