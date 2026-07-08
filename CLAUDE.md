# AutoTestIDE

UI 自动化测试 IDE，基于 Poco 协议直连，无图像识别依赖。PyQt5 构建，Catppuccin Mocha 暗色主题。

## 项目结构

```
E:/AutoTestIDE/
├── src/autotest_ide/          # 主代码
│   ├── app.py                 # 入口
│   ├── core/                  # 无 Qt 依赖的核心层
│   │   ├── code_gen.py        # OpMode 枚举 + gen_* 代码生成函数
│   │   ├── locator.py         # poco(...) 定位字符串生成
│   │   ├── poco_client.py     # TCP 客户端（FIFO Future 匹配）
│   │   ├── protocol_base.py   # PocoProtocol 抽象基类
│   │   ├── protocol_poco.py   # 标准 Poco 文本协议适配
│   │   ├── device.py          # Device 状态机
│   │   ├── device_manager.py  # 设备发现与管理
│   │   ├── forwarder.py       # 端口转发（ADB/Local/Direct）
│   │   ├── errors.py          # 异常层级
│   │   ├── report_model.py    # ReportStep/ReportSummary
│   │   └── log.py             # 日志
│   ├── sdks/
│   │   └── jx4/protocol.py    # JX4 AltrunUnityDriver 协议适配
│   ├── runner/                # 子进程侧（无 Qt 依赖）
│   │   ├── runtest.py         # 脚本执行入口
│   │   ├── recorder.py        # RecordingPocoClient 操作录制
│   │   ├── reporter.py        # Reporter 步骤记录
│   │   └── runtime.py         # build_namespace() → auto, By, assert_exists, wait_for 等
│   ├── ui/                    # PyQt5 UI 层
│   │   ├── main_window.py     # 主窗口（4 面板布局 + 信号编排）
│   │   ├── device_panel.py    # 截图面板（OpMode 工具栏 + 滑动轨迹 + 高亮 Overlay）
│   │   ├── editor.py          # 代码编辑器（Python 语法高亮）
│   │   ├── tree_panel.py      # UI 层级树
│   │   ├── property_panel.py  # 节点属性表
│   │   ├── clickable_panel.py # 可点击节点筛选表
│   │   ├── record_controller.py # 录制状态机（op_mode + assert 插入）
│   │   ├── run_controller.py  # 脚本运行控制
│   │   ├── threads.py         # QThread Workers（截图/inspect/设备扫描/Poco操作）
│   │   ├── console.py         # 日志输出
│   │   └── style.py           # Catppuccin Mocha QSS 主题
│   └── report/                # Jinja2 报告模板
├── tests/                     # pytest 测试（231 个）
│   ├── conftest.py            # fake_server fixture
│   └── fake_poco_server.py    # 模拟 Poco 协议服务端
├── pages/jx4/                 # 页面对象示例
├── autotest-ide.spec          # PyInstaller 打包配置
└── dist/AutoTestIDE/          # 打包产物
```

## 开发命令

```bash
# 运行测试
python -m pytest tests/ -v --ignore=tests/test_real_device.py

# 运行单个测试文件
python -m pytest tests/test_code_gen.py -v

# 打包
python -m PyInstaller autotest-ide.spec --noconfirm

# 启动 IDE
python -m autotest_ide
```

## 架构要点

- **核心层无 Qt 依赖**：`core/` 和 `runner/` 可被子进程独立 import
- **协议适配器模式**：`PocoProtocol` ABC，标准 Poco 和 JX4 各实现一个适配器
- **FIFO 匹配**：PocoClient 用 `_pending` deque + `_send_lock` 保证并发请求响应不串
- **代码生成分层**：`locator.py` 只管 `poco(...)` 定位字符串，`code_gen.py` 管 `auto.*` 操作代码
- **录制断言**：录制模式下，有路径时自动在操作代码前插入 `assert_exists('路径')`

## 操作模式（DevicePanel 工具栏）

| 按钮 | OpMode | 交互 | 生成代码 |
|------|--------|------|---------|
| 🖱️ 点击 | CLICK | 单击 | `auto.find_and_tap('path')` |
| ✋ 长按 | LONG_PRESS | 单击 | `auto.long_click(x, y, duration=2.0)` |
| ↔️ 滑动 | SWIPE | 拖拽 | `auto.swipe(x1, y1, x2, y2)` |
| ⌨️ 输入 | INPUT | 单击+弹输入框 | `auto.set_text('path', 'text')` |

## 已知限制

- JX4 `getNodeByPos` Unity 端未实现，pick-point 降级为坐标点击（P0，等 SDK 修复）
- JX4 hierarchy 不含坐标/bounds，客户端几何命中测试不可用
- 无实时设备事件录制（仅拾取模式）

## 依赖

- Python >= 3.8, PyQt5 >= 5.15, Jinja2 >= 3.0, psutil >= 5.9
- 可选：Pillow（JX4 PC 截图）
- 开发：pytest >= 7.0, pytest-qt >= 4.0, ruff >= 0.1
