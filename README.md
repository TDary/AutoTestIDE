# AutoTest IDE

跨平台游戏/应用 UI 自动化测试 IDE，基于 Poco UI 树协议直连设备——不依赖图像识别，不依赖截图匹配。使用 PyQt5 构建。

灵感来自 AirtestIDE，但专注于 Poco 协议，支持按游戏 SDK 扩展协议适配器。

## 功能特性

- **多协议架构** — 可插拔的 `PocoProtocol` 适配器，按游戏 SDK 加载。内置适配器：
  - `poco` — 标准 Poco 文本命令协议（Unity、Cocos、Android 原生）
  - `jx4` — AltrunUnityDriver 协议（分号分隔命令，`&` 终止符，base64 截图）
- **三种连接方式**
  - USB 安卓设备：通过 `adb forward` 端口转发（JX4 自动扫描远端端口）
  - 本地 TCP：直连 `127.0.0.1:13000` 等端口
  - IP 直连：不依赖 adb，连接任意 `host:port`
- **Pick-Point 检查流程** — 点击设备截图即可检查 UI 节点。命中节点在树中高亮、属性面板展示详情、定位代码自动插入编辑器。若 SDK 不支持 `getNodeByPos`，自动降级为 `auto.click(x, y)` 坐标点击
- **脚本录制** — 开启录制模式（Ctrl+R），点击截图自动生成 `auto.find_and_tap(...)` 或 `auto.click(x, y)` 代码。录制与运行互斥，不会冲突
- **设备实时预览** — 5 FPS 截图流，支持点击检查和区域高亮
- **UI 树浏览器** — 层级树视图，显示名称/类型/文本，右键菜单可复制路径或插入点击代码
- **属性面板** — 查看节点属性（bounds、text、type、component 等）
- **定位器生成** — 从选中节点自动生成 `poco(...)` 或 `auto.find_and_tap(...)` 代码
- **脚本编辑器** — Python 语法高亮，支持运行/保存/打开（F5 快捷键）
- **测试运行器** — 子进程运行 `.air` 脚本，注入运行命名空间（`auto`、`snapshot`、`assert_exists`、`log`），回放过程中截图同步回显到设备面板
- **HTML 测试报告** — 基于 `report.json` 渲染带截图的步骤报告（Jinja2 模板）
- **UI 树自动刷新** — 10 秒间隔定时刷新，保持 UI 层级同步
- **连接状态指示器** — 实时在线/离线状态徽章，心跳健康检查（连续 3 次失败 → 标记离线）
- **现代暗色主题** — Catppuccin Mocha 配色方案，全局 QSS 样式

## 安装

### 从源码安装

```bash
git clone <repo-url>
cd AutoTestIDE
pip install -e ".[dev]"
```

依赖要求：Python ≥ 3.10，PyQt5 ≥ 5.15，Jinja2，psutil，Pillow（PC 截图用）。安卓 USB 连接需 `adb` 在 PATH 中。

### 构建 Windows 可执行文件

```bash
pip install pyinstaller
python -m PyInstaller autotest-ide.spec --noconfirm
```

输出在 `dist/AutoTest IDE/`，运行 `AutoTest IDE.exe`。

### 构建 Python 包

```bash
pip install build
python -m build
```

生成 `dist/autotest_ide-0.1.0-py3-none-any.whl` 和 `.tar.gz`。

## 使用方法

### 启动

```bash
python -m autotest_ide
```

### 连接设备

1. 从下拉框选择设备（USB、本地、或 IP 直连）
2. 选择 SDK（Poco 标准协议 或 JX4）
3. 点击 **⚡ 连接**
4. 截图流和 UI 树将分别在左侧和右侧面板加载

### 检查与录制

- 点击设备截图上的任意位置，即可检查该坐标处的 UI 节点
- 命中节点在 UI 树中高亮，属性面板显示其详细属性
- 定位代码（`auto.find_and_tap(...)` 或 `auto.click(x, y)`）自动插入编辑器
- 开启 **录制** 模式（Ctrl+R），记录一系列操作
- 录制中点击截图自动生成操作代码
- 点击 **停录**（Ctrl+Shift+R）停止录制

### 运行脚本

1. 在编辑器中编写或打开 `.py` 脚本
2. 点击 **▶ 运行**（或 F5）
3. 输出流式打印到控制台；运行结束后自动打开 HTML 报告

脚本命名空间包含：
- `auto` — 带录制功能的 `PocoClient` 包装（`RecordingPocoClient`）
- `By` — 查找策略（`By.PATH`、`By.TAG`、`By.ID` 等）
- `snapshot()` — 截图步骤
- `assert_exists(locator, msg)` — 断言并记录
- `log(msg)` — 记录日志步骤

### 命令行运行脚本

```bash
python -m autotest_ide.runner.runtest test.air \
    --device-type android \
    --device_serial emulator-5554 \
    --poco-port 13000 \
    --protocol jx4 \
    --timeout 600
```

`--protocol` 接受注册名称（`poco`、`jx4`）或完整限定符 `包.模块:类名`。

## 架构

```
src/autotest_ide/
├── app.py                  — QApplication 入口
├── core/
│   ├── protocol_base.py    — PocoProtocol 抽象基类 (send/read/handshake/create_connection)
│   ├── protocol_poco.py    — PocoTextProtocol 默认文本命令适配器
│   ├── protocol.py         — 线路层帧编解码 (encode_command, read_json_frame, ...)
│   ├── poco_client.py      — 同步 TCP 客户端，FIFO Future 请求/响应匹配
│   ├── device.py           — Device 状态机 (disconnected → online → offline)
│   ├── device_manager.py   — 设备发现 + 活跃设备生命周期管理
│   ├── forwarder.py        — PortForwarder 抽象: AdbForwarder / LocalForwarder / DirectForwarder
│   ├── locator.py          — 生成 poco(...) 和 auto.find_and_tap(...) 定位代码
│   ├── report_model.py     — ReportStep / ReportSummary 数据类
│   └── errors.py           — 类型化异常体系
├── sdks/
│   ├── poco/               — 重新导出 PocoTextProtocol
│   └── jx4/protocol.py     — JX4Protocol (AltrunUnityDriver 线路格式 + 层级转换)
├── runner/
│   ├── runtest.py          — 子进程入口, --protocol 参数, PROTOCOL_REGISTRY
│   ├── recorder.py         — RecordingPocoClient 包装 PocoClient 用于步骤上报
│   ├── reporter.py         — 步骤 pass/fail、截图保存、JSON 输出
│   └── runtime.py          — build_namespace() 注入脚本全局变量
├── report/
│   ├── __init__.py         — render_report() Jinja2 渲染
│   ├── template.html
│   ├── report.css
│   └── report.js
└── ui/
    ├── main_window.py      — QMainWindow, 工具栏, 分割布局, 信号连接
    ├── style.py             — DARK_STYLE 全局 QSS (Catppuccin Mocha)
    ├── icons.py             — 基于 SVG 的图标工厂
    ├── title_bar.py         — 自定义无边框标题栏
    ├── device_panel.py      — 截图标签 + 点击覆盖层
    ├── editor.py            — Python 语法高亮 + 定位代码插入
    ├── tree_panel.py        — QTreeView UI 层级 + 右键菜单
    ├── property_panel.py    — QTableWidget 属性查看器
    ├── console.py           — 彩色日志输出
    ├── threads.py           — ScreenshotWorker / PocoWorker / DeviceBridge (QThread)
    ├── run_controller.py    — 子进程生命周期 + stop event
    ├── record_controller.py — 录制状态机 + 代码生成
    └── report_view.py       — QWebEngineView 或浏览器回退
```

### 添加新的 SDK 适配器

1. 创建 `src/autotest_ide/sdks/<name>/__init__.py` 和 `protocol.py`
2. 实现 `PocoProtocol` 子类 — 覆写 `METHOD_MAP`（方法名映射）、`send_request`（发送请求）、`read_response`（读取响应）、`handshake`（握手），若需端口扫描还需覆写 `create_connection`
3. 若 SDK 返回格式与 Poco 标准不同（如 JX4 的扁平节点字典），需覆写 `transform_result`
4. 在 `runner/runtest.py:PROTOCOL_REGISTRY` 注册，使 CLI `--protocol <name>` 可用
5. 在 `ui/main_window.py:_init_toolbar` 的 SDK 下拉框中添加条目

`PocoClient` 采用组合模式——同一客户端代码适用于任意协议适配器。

### JX4 SDK 注意事项

AltrunUnityDriver（JX4）有以下特殊处理：

- **线路格式**：分号分隔命令，`altstart::payload::altLog::log::altend` 响应帧
- **连接方式**：端口扫描 13000–13004，短连接超时，成功后切换为长操作超时
- **getNodeByPos**：SDK v2.4 未实现 — `inspect_by_point` 降级为 `auto.click(x, y)` 坐标点击
- **截图方式**：PC 端通过 `Pillow.ImageGrab` 截屏（无 socket 命令可用）
- **层级转换**：JX4 扁平节点 → Poco 嵌套格式，由 `_convert_jx4_node()` 完成
- **安全断开**：发送 `CloseConnection` 告别 + `shutdown(SHUT_WR)` 半关闭 + 排空数据，防止 CLOSE_WAIT 僵尸连接

## 测试

```bash
pytest tests/ -v
```

154 个测试用例，覆盖协议适配器、PocoClient、Device 状态机、DeviceManager、端口转发、定位器生成、报告器、录制器、运行器集成、线程、运行控制器、录制控制器和 JX4 SDK。

真机冒烟测试默认跳过；启用需 `--run-real-device` 并设置 `AUTOTESTIDE_REAL_ANDROID_SERIAL=<序列号>`。

## 文档

- `docs/specs/2026-06-29-autotest-ide-clone-design.md` — 原始设计规格
- `docs/plans/` — 实现计划（协议、设备、UI、运行器）
- `docs/jx4/AltrunUnityDriver接口协议文档.md` — JX4 协议参考文档
- `docs/jx4/feature-gaps.md` — 功能差距跟踪

## License

MIT
