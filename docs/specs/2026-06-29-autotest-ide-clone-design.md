# AirtestIDE 克隆产品 —— 设计文档

**日期**: 2026-06-29
**状态**: Draft
**范围**: Phase 1（IDE 骨架 + UI 检选点）

---

## 1. 背景与目标

打造一个类似 AirtestIDE 的桌面 IDE，用于游戏 / App 的 UI 自动化测试。与 AirtestIDE 的关键差异：

- **不做图像识别**（去掉 Airtest 的 aircv / opencv 路线）
- **自动化核心走 Poco 风格 UI 树协议**（JSON-RPC over TCP）
- **支持多引擎**：Unity、Cocos2d-x、Unreal Engine、自研 C++ 引擎

### 1.1 Phase 1 范围

- IDE 本体：PyQt5/6 桌面应用
- 被测端：Unity / Cocos / UE / 自研 C++ 引擎（spec 只设计协议，不实现 SDK）
- 脚本语言：Python
- 脚本生成方式：**仅 UI 检选点**（选中节点插入代码）
  - 实时录制：留待后续 spec
  - 可视化拖拽编程：留待后续 spec
- 设备连接：USB 直连手机 + PC 上运行的游戏进程
- 不支持：多设备并行、远程/云端设备、断点调试

### 1.2 非目标（Phase 1 明确不做）

- 实时录制（需要 SDK 侧事件上报协议，后续 spec）
- 可视化拖拽编程（Blockly 风格块编辑器，后续 spec）
- 断点调试
- 多脚本批量运行
- 报告历史对比
- macOS/Linux 打包（PyInstaller 配置留后续）
- 自动更新
- 插件系统

---

## 2. 总体架构

采用 **方案 A：PyQt 单进程 + 子进程脚本运行**。

```
PyQt 主进程（IDE）
├── UI 层（PyQt widgets）
├── 设备/连接层（Device + Forwarder）
├── PocoClient（主进程实例，用于检选点）
└── 脚本运行：spawn 子进程 runtest.py
                    └── 独立 PocoClient 实例 + RecordingPocoClient
```

**核心设计决策**：

1. **主进程和子进程用两套独立 PocoClient**。不复用连接。理由：子进程崩溃不影响 IDE；Windows 共享 socket 麻烦；Poco 服务设计上支持单连接多客户端。
2. **子进程通过命令行参数拿连接信息，不走 IPC**。Phase 1 子进程是"运行→结束"一次性模型，stdout 够用。后续做实时录制才引入 IPC。
3. **`core/` 完全无 PyQt 依赖**。可被 CLI、子进程、单元测试独立 import。

---

## 3. 统一 Poco 协议层

### 3.1 协议形态

- **传输**：TCP socket，游戏侧起监听端口（默认 `5001`，可配置）
- **编码**：UTF-8 JSON
- **帧化**：4 字节大端长度前缀 + payload（`len + payload`），避免粘包
- **连接方向**：IDE 永远是客户端，连 `127.0.0.1:port`
  - USB 直连手机：Android 用 `adb forward`，iOS 用 `iproxy`，把设备端口转到本地
  - PC 游戏进程：直连本地端口

### 3.2 协议方法（Phase 1 最小集）

| 方法 | 入参 | 返回 | 用途 |
|---|---|---|---|
| `hello` | `{client_version, protocols}` | `{server_version, protocol}` | 版本协商 |
| `get_root` | 无 | UI 树根节点 | UI 树面板加载 |
| `dump_hierarchy` | `{depth?: int}` | 序列化 UI 树 | 检选点拉取整树 |
| `get_screen_size` | 无 | `{w, h}` | 坐标系换算 + 心跳 |
| `get_attributes` | `{node_id}` | 节点属性 dict | 选中节点显示属性 |
| `inspect_by_point` | `{x, y}` | `{node_id, path}` | 检选点核心：点屏幕坐标 → 命中节点 |
| `screenshot` | 无 | 二进制帧（PNG） | 投屏画面 |
| `binary_read` | `{seq}` | 裸字节流 | screenshot 的二进制数据通道 |

**`inspect_by_point` 由 SDK 侧实现**，IDE 不做几何命中计算。精度责任落在 SDK。

### 3.3 Screenshot 走独立二进制帧

- `screenshot` 方法返回一个 `seq`（JSON-RPC 响应）
- IDE 用同一连接发 `binary_read(seq)`，SDK 直接吐裸字节流（前缀 4 字节长度 + PNG bytes）
- 避免大图 base64 内存翻倍

### 3.4 UI 树节点 schema（协议级固化）

```json
{
  "node_id": "uuid-or-string",
  "name": "Button_Play",
  "type": "Button",
  "payload": {
    "visible": true,
    "visibleBounds": {"x": 100, "y": 200, "width": 80, "height": 40},
    "anchor": [0.5, 0.5],
    "text": "Play",
    "enabled": true,
    "attributes": { }
  },
  "children": [ ]
}
```

- `node_id`：每个 SDK 自己生成，IDE 不假设可读
- `payload.attributes`：引擎特有字段原样透传，IDE 不解释
- `visibleBounds`：引擎逻辑像素坐标系
- `anchor`：[0,1] 区间归一化锚点，决定点操作落点

### 3.5 版本协商

握手时 IDE 发 `hello`，SDK 回 `server_version` + `protocol`。版本不匹配则 IDE 拒连并提示用户。

### 3.6 错误约定

- **传输层**：连接断开 → IDE 标记设备离线，不抛异常给用户
- **协议层**：SDK 返回标准 JSON-RPC error，带 `code` + `message` + `data`；IDE 翻译成中英文提示
- **业务层**：节点已不存在（`inspect_by_point` 命中后 SDK 节点失效）→ IDE 重新拉树并提示

---

## 4. 设备 / 连接层

### 4.1 Device 抽象

```
Device
├── name           # 显示名，如 "Pixel 6" 或 "Unity-Editor"
├── device_type    # "android" | "ios" | "windows" | "unity_editor" | ...
├── status         # "disconnected" | "connecting" | "online" | "offline"
├── local_port     # 转发到本地的端口
└── methods
    ├── connect()
    ├── disconnect()
    ├── health_check()           # 周期性 ping，失败转 offline
    └── on_status_change         # 状态变更事件，UI 订阅
```

### 4.2 两种连接模式

**模式 A：USB 直连手机**

- Android：`adb forward tcp:{local_port} tcp:{poco_port}`
- iOS：调用 `iproxy` 二进制（参考 Airtest `airtest/core/ios/iproxy`）
- 设备发现：Android 用 `adb devices -l`，iOS 用 `idevice_id -l` 或 `tidevice`

**模式 B：PC 上运行的游戏进程**

- 游戏进程内嵌 Poco-SDK，监听 `127.0.0.1:{poco_port}`
- IDE 直连本地端口，不需要转发
- 设备发现：扫描本地端口 + 进程名匹配；或用户手动输入 `host:port`
- 多个游戏进程同时跑 → 多个独立 `Device` 实例

### 4.3 关键设计决策

1. **端口转发进程由 IDE 拥有**。`PortForwarder` 类管理 adb/iproxy 子进程，`start()`/`stop()`，析构时强制 kill，IDE 退出钩子注册全局清理。避免僵尸转发进程。
2. **本地端口动态分配**。游戏 SDK 写死监听 `5001`（可配置），IDE 在本地找空闲端口做转发目标，避免多设备端口冲突。
3. **健康检查而非长连接保活**。IDE 每 5 秒发 `get_screen_size`（最便宜的方法）做心跳。失败 3 次转 `offline`。不复用 TCP keepalive（跨平台行为不一致）。
4. **连接生命周期跟 IDE 会话绑定，不持久化**。Phase 1 不存"上次连接的设备"。理由：USB 序列号会变，游戏进程 PID 每次不同，持久化反而误导。后续做"最近连接列表"再加。

### 4.4 不在 Phase 1 范围

- 多设备并行（架构预留：`Device` 单实例，`DeviceManager` 可持多个；UI 只暴露一个 active device）
- 远程/云端设备（协议天然支持，UI 不做）

---

## 5. Poco 客户端层

### 5.1 PocoClient 类

```
PocoClient
├── 状态
│   ├── socket          # 跟设备 Poco 服务的 TCP 连接
│   ├── request_seq     # 自增序列号，匹配请求/响应
│   └── pending         # dict<seq, future> 等待中的请求
├── 方法（对应协议第 3 节）
│   ├── get_root()
│   ├── dump_hierarchy(depth=None)
│   ├── get_screen_size()
│   ├── get_attributes(node_id)
│   ├── inspect_by_point(x, y)
│   └── screenshot()     # 返回 bytes（PNG）
└── 内部
    ├── _send(method, params)  # 帧化并发送，返回 future
    ├── _recv_loop()          # 后台线程收响应，按 seq 唤醒 future
    └── _heartbeat()           # 复用 get_screen_size 做心跳
```

### 5.2 关键设计决策

1. **异步：Qt 信号 + Python future，不用 asyncio**。PyQt 事件循环和 asyncio 难干净融合。用 Qt 信号槽 + 收包后台 QThread：
   - `_send` 返回轻量手写 `Future`
   - 收包线程把响应投递回主线程通过信号（`response_received`），主线程槽函数唤醒对应 future
   - 调用方在 QThread 里 `future.result(timeout=5)` 阻塞等待
   - **绝不在 UI 主线程上调用 PocoClient 方法**

2. **线程模型明确分层**：
   ```
   UI 主线程        ← 通过 worker QThread 触发 PocoClient 调用
     │
     ├─ UI 树刷新 worker QThread     ← get_root / dump_hierarchy
     ├─ 检选点 worker QThread        ← inspect_by_point + screenshot
     └─ 收包后台 QThread (PocoClient 内部) ← recv + 分发
   ```

3. **请求超时统一 5 秒**。超时抛 `PocoTimeoutError`。心跳例外 —— 心跳超时不抛异常，只触发状态机转 offline。

4. **Screenshot 走独立二进制帧**（见第 3.3 节）。

5. **不在客户端层做重试**。网络抖动重试由调用方决定。客户端层保持纯粹：成功 / 失败 / 超时。

### 5.3 错误异常体系

```
PocoError                    # 基类
├── PocoConnectionError      # 连接断开/建立失败
├── PocoTimeoutError         # 请求超时
├── PocoProtocolError        # JSON 解析失败、版本不匹配
├── PocoRemoteError          # SDK 返回的 JSON-RPC error
└── PocoNodeNotFoundError    # 节点不存在（inspect 命中后失效）
```

UI 层捕获 `PocoError`，翻译成用户可读消息。

---

## 6. UI 层

### 6.1 主窗口布局

```
┌─────────────────────────────────────────────────────────────┐
│ 菜单栏（文件/运行/帮助） + 工具栏（连接设备 ▼ | 运行 | 停止） │
├──────────┬──────────────────────────────────┬──────────────┤
│  设备    │       脚本编辑器                  │  右侧栏      │
│  投屏    │       (QScintilla/CodeEditor)    │  (Tab 切换)  │
│ (触摸    │                                  │              │
│  交互)   │                                  │  ├ 属性面板  │
│          │                                  │  ├ UI 树面板 │
│          │                                  │  └ 控制台    │
├──────────┴──────────────────────────────────┴──────────────┤
│  底部状态栏（设备状态 | 协议版本 | 当前光标坐标）            │
└─────────────────────────────────────────────────────────────┘
```

### 6.2 四个面板的职责

**A. 设备投屏面板（左侧）**

- 实时显示设备屏幕（`screenshot` 周期性拉取，Phase 1 用 5 FPS 轮询，不做视频流）
- 鼠标点击 = 检选点触发：`inspect_by_point(x, y)`
- 命中节点后，投屏上叠加红色框标出 `visibleBounds`，右侧属性面板高亮
- 点击空白处 = 不命中，清空选中

**B. 脚本编辑器（中央）**

- `QScintilla`（PyQt 的 Scintilla 绑定）做 Python 语法高亮 + 自动补全
- 检选点命中后，光标位置自动插入一行代码（见 6.4 定位器策略）
- 脚本格式：`.air` 目录风格（Airtest 兼容）

**C. 右侧栏 Tab（三选一）**

- **属性面板**：选中节点的 `payload.attributes` 用属性表显示（key-value），值可复制
- **UI 树面板**：`dump_hierarchy` 结果用 `QTreeView` 显示，展开/折叠，跟投屏联动
- **控制台**：脚本运行的 stdout/stderr 实时输出

**D. 状态栏（底部）**

- 设备状态、协议版本、当前光标坐标

### 6.3 检选点流程

```
用户点击投屏 (x, y)
  ↓
DevicePanel → 发信号 inspect_requested(x, y)
  ↓
PocoWorker QThread → poco_client.inspect_by_point(x, y)
  ↓ 返回 {node_id, path}
PocoWorker → 同时调 screenshot() 拿当前画面
  ↓
主线程收到信号 inspect_result(node, screenshot)
  ↓
  ├─ 投屏叠加红色框（visibleBounds）
  ├─ 属性面板填充 payload.attributes
  ├─ UI 树面板高亮对应节点
  └─ 编辑器光标处插入 poco(...) 代码
```

### 6.4 定位器生成策略

检选点命中后，编辑器光标处插入代码。定位器策略：

**优先 name，降级到 text/type 组合**

1. 优先用 `name`：`poco("Button_Play").click()`
2. `name` 为空或不唯一时，降级到属性组合：`poco(text="Play", type="Button").click()`

降级逻辑放 IDE 侧（检选点时生成代码就用降级后的定位器）。SDK 不参与定位器生成。

### 6.5 运行 / 报告

- **运行**：工具栏"运行"按钮 → 启动 `runtest.py` 子进程，参数传脚本路径 + 设备连接信息
- **停止**：发 SIGTERM（Windows 用 `taskkill`），3 秒不退就 SIGKILL（`taskkill /F`）。用 `psutil` kill 整个进程树。
- **报告**：子进程写 `report.json` + 步骤截图到 `.air` 目录，IDE 运行结束后读 `report.json` 渲染 HTML（Jinja2 模板）
- **运行中 UI**：运行时禁用检选点（避免和脚本同时操作设备），编辑器只读，控制台实时滚动

### 6.6 不在 Phase 1 范围

- 实时录制
- 可视化拖拽编程
- 断点调试
- 多脚本项目管理（Phase 1 只支持单脚本）

---

## 7. 脚本运行子进程

### 7.1 运行架构

```
PyQt 主进程（IDE）                    Python 子进程（runtest.py）
─────────────────                    ─────────────────────────
点"运行" ──spawn──>                 runtest.py <air_dir> --device-type <t> --device-serial <s> --poco-port <p>
                                       │
                                       ├─ 加载 .air/script.py
                                       ├─ 创建 PocoClient（独立实例）
                                       ├─ 执行脚本（顶部注入 poco 全局）
                                       ├─ 每个 step 写 report.json + 截图
                                       └─ 进程退出（0 成功 / 非0 失败）
   <──stdout/stderr pipe──           实时日志输出
   <──exit code──                    最终状态
   读 report.json 渲染 HTML 报告
```

### 7.2 子进程职责边界

子进程只做 3 件事：

1. 加载并执行用户的 `.air/script.py`
2. 把每个 Poco 操作（点击/查找/断言）记成一条 step，写 `report.json` + 截图
3. 把 stdout/stderr 实时吐到管道

子进程不做：UI 渲染、设备连接 UI、状态管理。

### 7.3 runtest.py 运行时上下文

用户脚本顶部不需要写 import，子进程注入全局命名空间：

```python
namespace = {
    "poco": poco_client,          # 已连上设备的 PocoClient 实例
    "device": device_handle,      # 设备元信息
    "snapshot": snapshot_func,    # 截图并记入报告
    "assert_exists": assert_func, # 断言节点存在，失败写报告并抛异常
    "log": step_logger,           # 把字符串记入报告
}
exec(compile(script_src, script_path, "exec"), namespace)
```

注入的全局函数（`snapshot` / `assert_exists` / `log`）的具体签名在 `runner/runtime.py` 中实现，Phase 1 至少包含：
- `snapshot()` → 截当前屏幕，记入报告
- `assert_exists(locator, msg="")` → 断言节点存在，失败抛 `AssertionError` 并标红报告
- `log(msg)` → 把字符串记入报告 step

用户脚本里直接 `poco("Button_Play").click()` 就能跑。

### 7.4 步骤记录

子进程的 PocoClient 实例包一层 `RecordingPocoClient`：

```python
class RecordingPocoClient:
    def __init__(self, inner, reporter):
        self._inner = inner
        self._reporter = reporter

    def click(self, locator):
        self._reporter.step_start(f"click {locator}")
        try:
            self._inner.click(locator)
            self._reporter.step_pass(screenshot=self._inner.screenshot())
        except Exception as e:
            self._reporter.step_fail(error=str(e), screenshot=...)
            raise
```

用户脚本不用关心报告生成，所有 Poco 操作自动入报告。

### 7.5 超时和停止

- **整体超时**：命令行 `--timeout 600`（默认 10 分钟），超时主进程 SIGTERM
- **用户点停止**：主进程发 SIGTERM（Windows: `taskkill /PID`），3 秒不退就 SIGKILL（`taskkill /F`）
- **脚本异常**：子进程不捕获，让异常冒泡到顶层，`runtest.py` 捕获后写 final error 到 report.json + 退出码 1

### 7.6 错误处理分层

| 层 | 错误类型 | 处理 |
|---|---|---|
| 协议层（第 3 节） | 连接断开 / 超时 / JSON 解析失败 | `PocoError` 异常体系 |
| 客户端层（第 5 节） | 节点不存在 / 远端 error | 抛 `PocoNodeNotFoundError` 等 |
| 脚本运行层 | 脚本 Python 异常 | 子进程捕获，写报告，退出码 1 |
| IDE 主进程 | 子进程崩溃 / 子进程超时 | UI 弹错误对话框 + 控制台标红 |
| 设备连接层（第 4 节） | forward 失败 / 设备掉线 | 状态机转 offline，UI 灰显 |

**原则：错误不静默**。任何一个 Poco 操作失败，要么写到报告标红，要么弹给用户。Phase 1 不做"重试"和"自动恢复"。

---

## 8. 测试策略

| 层 | 测试方式 |
|---|---|
| 协议帧化 | 单元测试：发请求收响应，验证长度前缀和 JSON 解析 |
| PocoClient | 用 mock socket 测请求/响应匹配、超时、断连 |
| 设备/连接层 | mock `adb`/`iproxy` 子进程，测 forward 生命周期和状态机 |
| 检选点逻辑 | mock PocoClient 返回固定 UI 树，测定位器降级策略 |
| 定位器生成 | 单元测试：给定节点属性，验证生成的 `poco(...)` 字符串 |
| 子进程 runtest.py | 集成测试：用假 Poco 服务（mock SDK），跑最小脚本，验证 report.json 结构 |
| UI 层 | Phase 1 不做自动化 UI 测试，手动测 |

**真实 SDK 集成测试**：Phase 1 写 `tests/fake_poco_server.py`，实现第 3 节协议的假服务端，所有集成测试打它，不依赖真机/真引擎。

---

## 9. 项目结构

```
autotest-ide-clone/
├── pyproject.toml
├── README.md
├── requirements.txt                  # 运行依赖
├── requirements-dev.txt               # 开发依赖
├── docs/
│   └── superpowers/specs/             # 设计文档
├── src/
│   └── autotest_ide/
│       ├── __init__.py
│       ├── __main__.py                # python -m autotest_ide 入口
│       ├── app.py                     # QApplication 启动
│       │
│       ├── core/                      # 无 UI 依赖的核心层
│       │   ├── protocol.py            # JSON-RPC 帧化
│       │   ├── poco_client.py         # PocoClient
│       │   ├── errors.py              # PocoError 体系
│       │   ├── device.py              # Device + DeviceManager
│       │   ├── forwarder.py            # adb/iproxy 端口转发
│       │   ├── locator.py             # 定位器降级策略
│       │   └── reporter.py            # RecordingPocoClient + report.json
│       │
│       ├── runner/                    # 子进程侧
│       │   ├── runtest.py             # 子进程入口
│       │   └── runtime.py             # 注入 poco/snapshot/assert 全局命名空间
│       │
│       ├── ui/                        # PyQt UI 层
│       │   ├── main_window.py
│       │   ├── device_panel.py        # 左侧投屏 + 检选点
│       │   ├── editor.py              # QScintilla 编辑器
│       │   ├── tree_panel.py          # UI 树 QTreeView
│       │   ├── property_panel.py      # 属性表
│       │   ├── console.py             # 控制台 stdout
│       │   ├── report_view.py         # HTML 报告渲染
│       │   └── threads.py             # PocoWorker QThread 封装
│       │
│       └── report/                    # 报告模板
│           ├── template.html          # Jinja2 模板
│           ├── report.css
│           └── report.js
│
├── tests/
│   ├── test_protocol.py
│   ├── test_poco_client.py
│   ├── test_device.py
│   ├── test_locator.py
│   ├── test_runner.py
│   └── fake_poco_server.py            # 假 SDK 服务端
│
└── playground/
    └── demo.air/                      # 示例脚本 + 假服务端配套
        └── script.py
```

### 9.1 关键设计原则

1. **`core/` 完全无 PyQt 依赖**。只用标准库 + 裸 socket。可被 CLI、子进程、单元测试独立 import，不引入 Qt。
2. **`ui/` 只依赖 `core/` 的接口**。所有跨线程调用通过 `ui/threads.py` 的 `PocoWorker` 封装，UI 永远不直接碰 PocoClient。
3. **`runner/` 独立可执行**。`python -m autotest_ide.runner.runtest` 可独立运行，开发期可直接命令行调试。

### 9.2 依赖清单

**运行依赖**（`requirements.txt`）：

```
PyQt5>=5.15            # 或 PyQt6，后续可切
QScintilla>=2.13       # PyQt 的 Scintilla 绑定
Jinja2>=3.0            # 报告模板
psutil>=5.9            # 子进程管理（跨平台 kill）
```

**开发依赖**（`requirements-dev.txt`）：

```
pytest>=7.0
pytest-qt>=4.0         # PyQt 测试辅助（可选）
ruff>=0.1              # linter
```

**Phase 1 不依赖**：opencv、numpy、Pillow、内嵌 adb 二进制、tidevice、facebook-wda（不做图像识别，adb/iproxy 调用系统已有的，用户环境假设已装）。

---

## 10. 里程碑与交付计划

### 10.1 Phase 1 拆成 6 个里程碑

| # | 里程碑 | 验证标准 | 依赖 |
|---|---|---|---|
| M1 | 协议层 + 假服务端 | `fake_poco_server.py` 跑起来，客户端能 `get_root` 拿到固定 UI 树 | 无 |
| M2 | PocoClient + 单元测试 | mock socket 测试全绿，覆盖超时/断连/节点不存在 | M1 |
| M3 | Device + Forwarder | adb/iproxy 子进程管理，状态机测试，连接真实 Android 设备能 forward + 连上 Poco | M2 |
| M4 | UI 骨架（无检选点） | PyQt 主窗口 4 面板布局，设备连接下拉，投屏显示截图 | M3 |
| M5 | 检选点 + UI 树联动 | 点投屏 → 命中节点 → 属性面板 + UI 树高亮 → 编辑器插入代码 | M4 |
| M6 | 脚本运行 + 报告 | `runtest.py` 子进程跑 `.air` 脚本，生成 HTML 报告 | M5 |

### 10.2 writing-plans 拆分建议

`writing-plans` 阶段按里程碑拆成多个实现 plan：

- **Plan 1**：M1+M2（协议层 + 客户端，纯后端，可独立交付）
- **Plan 2**：M3（设备层）
- **Plan 3**：M4+M5（UI 层，Qt 工作量大）
- **Plan 4**：M6（运行器 + 报告）

每个 plan 独立验证、独立 commit，避免一个巨大 PR。

---

## 11. 风险登记

| 风险 | 影响 | 缓解 |
|---|---|---|
| QScintilla 跟 PyQt5/6 版本不兼容 | 编辑器无法用 | Phase 1 先用 `QPlainTextEdit` 兜底，后续升级 |
| 各引擎 SDK 协议不统一 | 客户端要写多套适配 | 第 3 节已固化协议，SDK 侧必须遵守；不遵守的引擎 Phase 1 不支持 |
| Windows 下子进程 kill 不干净 | 僵尸进程 | 用 `psutil` 而非 `os.kill`，kill 整个进程树 |
| Poco 服务在游戏侧监听端口冲突 | 连接失败 | Forwarder 动态分配本地端口（第 4.3 节） |
| 用户环境未装 adb/iproxy | 设备连接失败 | IDE 启动时检测 `adb`/`iproxy` 是否在 PATH，缺失则提示安装指引 |

---

## 12. 开放问题（待 Phase 2 解决）

- 实时录制的事件上报协议设计（SDK 侧需要新增 `subscribe_events` 方法）
- 可视化拖拽编程的块定义和 Python AST 映射
- 多设备并行的 UI 交互模型（多 tab 还是多窗口）
- 报告历史对比的存储格式
- 远程/云端设备的鉴权和连接管理

---

**文档结束**
