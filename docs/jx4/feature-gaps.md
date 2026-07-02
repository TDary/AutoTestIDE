# AutoTestIDE 功能缺口清单

> 更新日期: 2026-07-02

### 1. ~~Pick-Point 检查流程未连通~~ — 已完成

已串联 PocoWorker → inspect_result → highlight_region/highlight_node/show_properties/generate_locator_code。

### 2. JX4 `getNodeByPos` 接口缺失

Unity 侧 AltrunUnityDriver 的 `getNodeByPos` 返回 `KeyNotFoundException`，
导致 JX4 设备上 pick-point 流程无法获取命中节点。

**影响:** JX4 上只能用坐标点击 (`auto.click(x, y)`)，无法生成路径定位代码

**依赖:** 需要 Unity SDK 侧修复，IDE 侧无法独立解决

**降级方案:** JX4 设备点击截图时保持当前坐标点击行为，
标准 Poco SDK 设备应走完整 inspect 流程

详见 [sdk-missing-interfaces.md](sdk-missing-interfaces.md)

---

## 中优先级 — 功能缺口

### 3. HTML 报告模板缺失

`report/__init__.py` 有 Jinja2 渲染逻辑，但缺少 `.html` 模板文件，
报告查看功能实际不可用。

**需要:**
- 创建 `report/templates/report.html` Jinja2 模板
- 模板需展示: 摘要信息、步骤列表(含截图)、通过/失败状态

**涉及文件:**
- `src/autotest_ide/report/__init__.py` — render_report() 已实现
- `src/autotest_ide/ui/report_view.py` — ReportView 已实现

### 4. 设置/偏好持久化

SDK 选择、设备选择、窗口布局等不跨会话保存。

**需要:**
- QSettings 或 JSON 配置文件持久化
- 保存项: SDK 选择、上次连接的设备、窗口几何/布局、编辑器字体大小
- 启动时恢复上次会话状态

### 5. JX4 SDK 方法覆盖不足

METHOD_MAP 只映射了 8 个方法（Dump、Click、FindAndTap 等），
常用操作未暴露。

**待映射方法 (来自 AltrunUnityDriver):**
- `LongClick` — 长按
- `Swipe` — 滑动
- `WaitForNode` — 等待节点出现
- `WaitForNodeDisappear` — 等待节点消失
- `GetScreen` — SDK 原生截图（当前用 PIL ImageGrab 替代）
- `SetText` — 输入文本（参数格式待确认: `str(int)` vs `str`）
- `GetNodeByPath` — 按路径查询节点
- `GetNodeByPos` — 按坐标查询节点（被 Unity 侧阻塞）

**涉及文件:**
- `src/autotest_ide/sdks/jx4/protocol.py` — METHOD_MAP 扩充
- `src/autotest_ide/core/poco_client.py` — 对应操作方法
- `src/autotest_ide/runner/recorder.py` — 录制步骤

---

## 低优先级 — Phase 2 规划

### 6. ~~脚本录制~~ — 已完成

已实现 RecordController + 录制/停录按钮 + Ctrl+R/Ctrl+Shift+R 快捷键。
录制模式下点击截图自动生成 `auto.find_and_tap('path')` 或降级为 `auto.click(x, y)`。

### 7. 多设备并行执行
同时连接多台设备，并行跑不同脚本或同一脚本。
需 DeviceManager 支持多 active 设备 + RunController 多实例管理。

### 8. 云设备集成
远程设备接入（WebSocket 代理），无需本地 USB 连接。

### 9. AIR 包导入/导出
脚本 + 资源打包为 .air 目录，支持导入已有 Airtest 项目。

### 10. Poco SDK 版本管理/自动更新
检测设备上 Poco SDK 版本，提示升级或自动推送新版本。

---

## 已完成功能

| 功能 | 状态 | 关键文件 |
|------|------|----------|
| Protocol ABC + Poco 适配器 | 完成 | `core/protocol_base.py`, `core/protocol_poco.py` |
| JX4 协议适配器 | 完成 | `sdks/jx4/protocol.py` |
| PocoClient (connect/close/dump/click/screenshot) | 完成 | `core/poco_client.py` |
| 设备状态机 + 心跳 | 完成 | `core/device.py` |
| 端口转发 (ADB/Direct/Local) | 完成 | `core/forwarder.py` |
| DeviceManager | 完成 | `core/device_manager.py` |
| 错误层级体系 | 完成 | `core/errors.py` |
| UI 树面板 + 右键菜单 | 完成 | `ui/tree_panel.py` |
| UI 属性面板 + 按钮检测 | 完成 | `ui/property_panel.py` |
| UI 设备面板 + 截图高亮 | 完成 | `ui/device_panel.py` |
| UI 编辑器 + 语法高亮 | 完成 | `ui/editor.py` |
| UI 控制台 + 日志颜色 | 完成 | `ui/console.py` |
| RunController (subprocess + in-process) | 完成 | `ui/run_controller.py` |
| Reporter + RecordingPocoClient | 完成 | `runner/reporter.py`, `runner/recorder.py` |
| 脚本运行 + 步骤截图同步 | 完成 | `runner/runtest.py`, `ui/run_controller.py` |
| 连接状态指示器 | 完成 | `ui/main_window.py` |
| auto 命名空间 + By 类 | 完成 | `runner/runtime.py` |
| UI 树自动刷新 (10s) | 完成 | `ui/main_window.py` |
| 键盘快捷键 | 完成 | `ui/main_window.py` |
| Pick-Point 检查流程 | 完成 | `ui/main_window.py`, `ui/threads.py`, `core/locator.py` |
| 脚本录制 | 完成 | `ui/record_controller.py`, `ui/main_window.py` |
