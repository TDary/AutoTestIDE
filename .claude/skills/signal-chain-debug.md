---
name: signal-chain-debug
description: AutoTestIDE 截图点击到代码插入的完整信号链路追踪与断线排查
metadata: 
  node_type: memory
  type: reference
  originSessionId: 4e0d1cb5-fe0f-4f90-89b6-fe79ed121e7e
---

# 信号链路调试

## 完整信号链（CLICK 模式，录制开启）

```
DevicePanel.mousePressEvent
  → DevicePanel.inspect_requested(x, y)
    → MainWindow._on_inspect_requested
      → PocoWorker.inspect(x, y)          # 启动 QThread
        → PocoClient.inspect_by_point()  # TCP 请求
        → PocoClient.screenshot()        # TCP 请求
      → PocoWorker.inspect_result(node, bytes)
        → MainWindow._on_inspect_result
          → DevicePanel.update_screenshot(bytes)
          → DevicePanel.highlight_region(bounds)
          → TreePanel.highlight_node(node_id)
          → PropertyPanel.show_properties(payload)
          → RecordController.on_inspect_result(node, x, y, op_mode, text=text)
            → gen_assert_exists() → code_generated.emit(assertion)
            → gen_click()        → code_generated.emit(code)
              → Editor.insert_locator_code(code)
```

## 其他模式链路差异

| 模式 | 信号 | Worker 方法 | 信号返回 | 编排 |
|------|------|-------------|---------|------|
| LONG_PRESS | `long_press_requested(x,y)` | `PocoWorker.long_press()` | `inspect_result` | 同 CLICK，调 gen_long_click |
| SWIPE | `swipe_requested(x1,y1,x2,y2)` | `PocoWorker.swipe()` | `swipe_done` | MainWindow._on_swipe_done → gen_swipe |
| INPUT | `input_text_requested(x,y)` | `PocoWorker.input_text()` | `inspect_result` | 同 CLICK，调 gen_input |

## 常见断线点

### 1. 代码没插入编辑器
- 检查 `RecordController.code_generated` 是否连接到 `Editor.insert_locator_code`
- 检查 `_on_inspect_result` 中 `is_recording` 分支是否走到
- 非录制模式：检查 `gen_*()` 返回值是否为空字符串

### 2. 截图没刷新/高亮没出现
- 检查 `PocoWorker.inspect_result` 是否连接到 `_on_inspect_result`
- 检查 `_on_inspect_result` 中 `bounds` 是否为空（节点无 `payload.pos`）
- 检查 `OverlayWidget.setGeometry` 是否在 `resizeEvent` 中调用

### 3. Worker 没启动
- 检查 `PocoWorker.isRunning()` — 同一时刻只能跑一个 task
- 检查 `_on_inspect_requested` 中 `self._poco_worker` 是否为 None
- 如果 Worker 上一轮卡死，`isRunning()` 会返回 True，请求被静默丢弃

### 4. 录制模式无断言
- `gen_assert_exists` 返回空 → 节点无路径（无 `payload.path` 且 `flat_nodes` 为空或不包含该节点）
- 检查 `_cached_flat` 是否在连接设备时正确填充
- 检查 `node_id` 在 `by_id` dict 中是否存在

### 5. 滑动没生成代码
- 滑动距离 <10px（设备坐标）会被防抖忽略
- 检查 `_on_swipe_done` 是否连接了 `PocoWorker.swipe_done`
- 检查 `_last_swipe_xy` 是否在 `_on_swipe_requested` 中正确保存

## 调试命令

```bash
# 快速验证信号连接
python -c "from autotest_ide.ui.main_window import MainWindow; \
  mw = MainWindow(); \
  print(mw.device_panel.receivers(mw.device_panel.inspect_requested))"  # 应 > 0

# 追踪 gen_* 输出
python -c "from autotest_ide.core.code_gen import gen_click; \
  print(repr(gen_click({'name':'X','type':'B','payload':{},'node_id':'1'}, [], 100, 200)))"
```

[[signal-chain-debug]]
