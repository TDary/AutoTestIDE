---
name: add-op-mode
description: 如何为 AutoTestIDE 新增一种截图操作模式（如双击、缩放等）
metadata: 
  node_type: memory
  type: reference
  originSessionId: 4e0d1cb5-fe0f-4f90-89b6-fe79ed121e7e
---

# 新增操作模式流程

以新增"双击"模式为例，需改动 4 层：

## 1. 核心层 — code_gen.py

- 在 `OpMode` 枚举中新增值：`DOUBLE_CLICK = "double_click"`
- 新增 `gen_double_click(node, flat_nodes, x, y)` 函数
- 补充对应的单元测试 `tests/test_code_gen.py`

## 2. 协议层

- 标准 Poco：在 `protocol_poco.py` 的 `METHOD_MAP` 中映射 `"double_click" → "DoubleClick"`
- JX4：在 `sdks/jx4/protocol.py` 的 `METHOD_MAP` 中映射 `"double_click" → "DoubleTap"`
- PocoClient：新增 `double_click(x, y)` 方法，调用 `_request_json("double_click", x, y)`
- RecordingPocoClient：新增 `double_click(self, x, y)` 录制步骤（step_start/pass/fail 模式）
- 补充协议和客户端的单元测试

## 3. UI 层

- `device_panel.py`：在工具栏新增一个 QToolButton，`_set_op_mode` 中补充分支，更新按钮样式
- `device_panel.py`：如需特殊鼠标交互（如双击检测），改 `mousePressEvent` / `mouseReleaseEvent`
- `threads.py`：PocoWorker 新增对应方法，决定发哪个信号（复用 inspect_result 或新建信号）
- `record_controller.py`：`on_inspect_result` / `on_inspect_failed` 补充 `OpMode.DOUBLE_CLICK` 分支

## 4. 编排层

- `main_window.py`：如需新信号则连接，`_on_inspect_result` / `_on_inspect_failed` 补充 `OpMode.DOUBLE_CLICK` 分支调用对应 `gen_*` 函数
- `main_window.py`：如有新 worker 信号（如单独的 double_click_done），连接到新槽

## Checklist

- [ ] OpMode 枚举 + gen_* 函数 + 测试
- [ ] 协议 METHOD_MAP（Poco + JX4）+ 测试
- [ ] PocoClient 新方法 + RecordingPocoClient + 测试
- [ ] DevicePanel 按钮 + 交互 + 测试
- [ ] PocoWorker 方法 + 信号 + 测试
- [ ] RecordController 分支 + 测试
- [ ] MainWindow 编排 + 手动验证
- [ ] 更新 autotest-ide.spec hiddenimports
- [ ] 重新打包验证

[[add-op-mode]]
