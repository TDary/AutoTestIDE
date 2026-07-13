# AutoTest IDE

跨平台游戏/应用 UI 自动化测试 IDE，基于 Poco UI 树协议直连设备——不依赖图像识别，不依赖截图匹配。使用 PyQt5 构建，Catppuccin Mocha 暗色主题。

灵感来自 AirtestIDE，但专注于 Poco 协议，支持按游戏 SDK 扩展协议适配器。

## 功能特性

- **多协议架构** — 可插拔的 `PocoProtocol` 适配器，按游戏 SDK 加载。内置适配器：
  - `poco` — 标准 Poco 文本命令协议（Unity、Cocos、Android 原生）
  - `jx4` — AltrunUnityDriver 协议（分号分隔命令，`&` 终止符，base64 截图）
- **三种连接方式**
  - USB 安卓设备：通过 `adb forward` 端口转发（JX4 自动扫描远端端口）
  - 本地 TCP：直连 `127.0.0.1:13000` 等端口
  - IP 直连：不依赖 adb，连接任意 `host:port`
- **Pick-Point 检查** — 点击截图上的 UI 元素，自动定位节点、获取属性、高亮区域
- **四种操作模式** — 点击 / 长按 / 滑动 / 输入，工具栏一键切换
- **脚本录制** — 点击截图自动生成 Python 脚本代码（`auto.find_and_tap()`、`assert_exists()` 等），录制模式下自动插入断言
- **可点击节点面板** — 自动筛选 UI 树中所有 Button/Toggle 节点，双击直接插入点击代码
- **UI 树浏览器** — 展示完整 UI 层级，双击节点插入代码，右键复制路径
- **脚本运行** — 进程内执行（JX4）或子进程执行，控制台实时输出，完成后自动打开 HTML 报告
- **连接诊断** — 握手失败时自动提示常见原因（SDK 选错、端口不对等）
- **截图状态反馈** — 截图失败时 overlay 提示"截图失败"，录制中绿边框、运行中红边框
- **悬停坐标** — 鼠标在截图上移动时状态栏实时显示设备坐标

## 快速开始

### 安装依赖

```bash
pip install -r requirements.txt
```

### 运行

```bash
# 从源码运行
python -m autotest_ide.app

# 或使用打包版本
dist/AutoTestIDE/AutoTestIDE.exe
```

### 打包

```bash
python -m PyInstaller autotest-ide.spec --noconfirm
```

## 使用流程

1. **连接设备** — 选择 SDK（Poco / JX4），在设备列表中选择设备或输入 IP:端口，点击"连接"
2. **浏览 UI** — 连接后自动加载 UI 树，截图实时刷新，可点击节点面板列出所有可交互元素
3. **录制脚本** — 点击"录制"按钮，然后点击截图上的目标元素，自动生成代码到编辑器
4. **运行脚本** — 点击"运行"按钮执行脚本，控制台实时输出，完成后自动打开 HTML 报告

## 脚本 API

用户脚本可用以下 API：

```python
# 点击
auto.find_and_tap('Panel/Btn_Play')  # 按路径定位点击
auto.click(100, 200)                   # 按坐标点击

# 长按
auto.long_click(100, 200, duration=2.0)

# 滑动
auto.swipe(100, 500, 100, 200)

# 输入文本
auto.set_text('Panel/InputField', 'hello')

# 断言与等待
assert_exists('Panel/Btn_Play')
wait_for('Panel/Loading', timeout=10)
wait_for_gone('Panel/Loading', timeout=10)

# 截图与日志
snapshot()
log('测试步骤完成')
```

## 项目结构

```
E:/AutoTestIDE/
├── src/autotest_ide/          # 主代码
│   ├── app.py                 # 入口
│   ├── core/                  # 无 Qt 依赖的核心层
│   │   ├── code_gen.py        # OpMode 枚举 + gen_* 代码生成 + _build_all_paths
│   │   ├── locator.py         # poco(...) 定位字符串生成
│   │   ├── network.py         # TCP 探测 + 连接诊断
│   │   ├── poco_client.py     # TCP 客户端（FIFO Future 匹配，线程安全）
│   │   ├── protocol_base.py   # PocoProtocol 抽象基类
│   │   ├── protocol_poco.py   # 标准 Poco 协议实现
│   │   ├── device.py          # Device 状态机 + 心跳
│   │   ├── device_manager.py  # 设备发现与管理
│   │   ├── forwarder.py       # 端口转发（本地 / adb / 直连）
│   │   ├── errors.py          # 异常层级
│   │   └── log.py             # 日志配置
│   ├── sdks/                  # SDK 适配层
│   │   └── jx4/
│   │       ├── protocol.py    # JX4 协议（O(n) 响应读取，BitBlt PC 截图）
│   │       └── helpers.py     # JX4 hierarchy → 标准 Poco 节点转换
│   ├── ui/                    # Qt UI 层
│   │   ├── main_window.py     # 主窗口（信号编排）
│   │   ├── connection_controller.py  # 连接生命周期管理
│   │   ├── device_panel.py    # 截图面板 + OpMode 工具栏 + 状态边框
│   │   ├── tree_panel.py      # UI 树浏览器（双击插入代码）
│   │   ├── clickable_panel.py # 可点击节点面板（tooltip + 后台验证）
│   │   ├── property_panel.py  # 节点属性面板
│   │   ├── editor.py          # 脚本编辑器（语法高亮）
│   │   ├── console.py         # 控制台输出
│   │   ├── code_gen_service.py # 录制状态 + 代码生成服务
│   │   ├── run_controller.py  # 脚本运行控制（进程内/子进程）
│   │   ├── threads.py         # QThread workers（截图/扫描/Poco 操作）
│   │   ├── style.py           # Catppuccin Mocha QSS 主题
│   │   └── report_view.py     # HTML 报告查看器
│   └── runner/                # 脚本执行运行时
│       ├── runtest.py         # 入口
│       ├── runtime.py         # build_namespace + auto/By/assert_exists/wait_for
│       ├── recorder.py        # RecordingPocoClient（步骤记录）
│       └── reporter.py        # Reporter（HTML 报告生成）
├── tests/                     # pytest 测试
├── docs/                      # 设计文档与协议参考
└── autotest-ide.spec          # PyInstaller 打包规格
```

## 已知限制

- JX4 `getNodeByPos` Unity 端未实现，pick-point 降级为坐标点击（P0，等 SDK 修复）
- JX4 hierarchy 不含坐标/bounds，客户端几何命中测试不可用
- 无实时设备事件录制（仅拾取模式）

## 测试

```bash
# 运行全部测试（排除需要真实设备的测试）
python -m pytest tests/ --ignore=tests/test_real_device.py

# 仅运行 PocoClient 测试
python -m pytest tests/test_poco_client.py -v

# 真机测试（需要设备连接）
AUTOTESTIDE_REAL_ANDROID_SERIAL=<序列号> python -m pytest tests/test_real_device.py
```

## 依赖

- Python >= 3.8, PyQt5 >= 5.15, Jinja2 >= 3.0, psutil >= 5.9
- 可选：Pillow（JX4 PC 截图）
- 开发：pytest >= 7.0, pytest-qt >= 4.0, ruff >= 0.1

## 文档

- `docs/specs/2026-06-29-autotest-ide-clone-design.md` — 原始设计规格
- `docs/plans/` — 实现计划（协议、设备、UI、运行器）
- `docs/jx4/AltrunUnityDriver接口协议文档.md` — JX4 协议参考文档
- `docs/jx4/feature-gaps.md` — 功能差距跟踪

## License

MIT
