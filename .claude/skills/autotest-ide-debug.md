---
name: autotest-ide-debug
description: AutoTestIDE 项目专用调试 skill，支持语法检查、逻辑验证、集成调试、性能分析四层调用
metadata:
  type: reference
---

# AutoTestIDE 调试 Skill

## 输入格式

```
{
  "layer": "L1|L2|L3|L4",
  "code": "string",                 // 被调试的代码片段（必填）
  "function_signature": "string",   // 函数签名（L2、L3选填）
  "input_example": "string",        // 输入示例（L2选填）
  "expected_output": "string",      // 预期输出（L2、L3选填）
  "error_log": "string",            // 错误日志（L3必填，其他选填）
  "runtime_data": "string",         // 运行时数据（L4选填）
}
```

## L1 语法检查 — 针对本项目常见语法陷阱

```
输出格式:
{
  "status": "pass|error|warning",
  "issues": [
    {
      "line": 行号,
      "type": "syntax|type|undefined|import|qt_signal",
      "description": "问题描述",
      "suggestion": "修复建议"
    }
  ]
}
```

本项目 L1 重点检查项：
- **pyqtSignal 声明位置**：必须在类体中声明，不能在 `__init__` 中赋值
- **QThread.run() 不能有参数**：`def run(self)` 不接受额外参数，参数通过 `_task` 属性传入
- **_build_parent_map 返回元组**：签名为 `(by_id, parent_of)` 但返回类型标注写了 `dict`（已知问题）
- **FakePocoServer._dispatch 的 method 参数**：是 Poco 协议解析后的命令名（如 `Click`），不是 IDE 内部方法名（如 `click`）
- **code_gen.py 的 _build_path 与 locator.py 的 _build_parent_map 重复逻辑**：修改路径生成逻辑时两边都要同步
- **PocoClient._request_json 参数展开**：`*pos_args` 中的 float 值会通过协议适配器转为字符串，JX4 用分号分隔所以 `2.0` 会变成 `LongClick;540;960;2.0;` 是正确的

## L2 逻辑验证 — 针对本项目核心逻辑

```
输出格式:
{
  "status": "pass|fail|inconclusive",
  "logic_issues": [
    {
      "condition": "触发条件描述",
      "expected": "预期行为",
      "actual": "实际行为（推测）",
      "fix": "修复建议"
    }
  ],
  "edge_cases": ["未处理的边界情况列表"]
}
```

本项目 L2 重点验证场景：

### PocoClient 并发
- 两个 `dump_hierarchy()` 同时到达：FIFO 匹配要求响应严格按序，如果服务端乱序会串包
- heartbeat 与用户请求交错：`_pending` 队列中 heartbeat Future 也会占位
- `close()` 期间 `_recv_loop` 的 finally 调用 `self.close()`：socket 可能已经是 None

### 代码生成
- `gen_click` 传入 `flat_nodes=[]`：无法构建路径，回退到 `payload.pos` 坐标，如果也没有 pos 则返回空字符串
- `gen_input` 的 text 参数含单引号：`auto.set_text('path', 'it's')` 会语法错误，需要转义
- `_build_path` 遇到 `name="root"` 跳过，但如果 root 下直接是目标节点（无中间层级），路径就是单段 `"Btn"`

### 设备状态机
- `connecting` 状态下收到 `offline`：应先触发连接失败，再转 offline
- heartbeat 超时后的重连：当前实现是直接断开，不会自动重连

### UI 线程安全
- `_recv_loop` 中直接 emit signal：PyQt5 的信号是线程安全的，这没问题
- 但 `_pending` deque 的操作不在 GIL 保护范围内：`append` 和 `popleft` 在 CPython 中是原子操作，但跨线程依赖 FIFO 语义需要 `_send_lock` 保护

## L3 集成调试 — 针对本项目典型错误链

```
输出格式:
{
  "root_cause": "问题根因",
  "location": "代码位置（文件名:行号）",
  "error_chain": "错误调用链",
  "unexpected_behavior": "非预期行为描述",
  "fix": "修复建议代码或步骤",
  "risk": "修复后可能引入的风险"
}
```

本项目 L3 典型场景速查：

### 场景1：点击截图无反应
```
错误链：
DevicePanel.mousePressEvent → _widget_to_device 返回 None
→ 因为点击在截图区域外（_offset 范围外）

定位：device_panel.py:mousePressEvent → _widget_to_device
修复：确保点击在 scaled_w/scaled_h 范围内才 emit，否则静默返回（已经是这样，检查是否被意外触发）
```

### 场景2：代码生成总是 auto.click 而非 find_and_tap
```
错误链：
RecordController.on_inspect_result → gen_click(node, flat_nodes, x, y)
→ _build_path(node, flat_nodes) 返回 ""
→ 因为 _cached_flat 为空或不包含该 node_id

定位：main_window.py:_connect_selected_device 中 _cached_flat 填充
修复：确认 _flatten_tree(get_root()) 返回的列表包含所有节点（包括深层子节点）
```

### 场景3：JX4 设备 inspect 总是失败
```
错误链：
PocoWorker.run → poco.inspect_by_point(x, y)
→ JX4Protocol.send_request("getNodeByPos", x, y)
→ Unity 返回 KeyNotFoundException
→ inspect_failed.emit("KeyNotFoundException", x, y)

定位：这是 P0 已知问题，Unity SDK 未实现 getNodeByPos
临时方案：IDE 端添加 _cached_flat 几何命中测试 fallback（待实现）
```

### 场景4：滑动操作后截图没更新
```
错误链：
DevicePanel.mouseReleaseEvent → swipe_requested(x1,y1,x2,y2)
→ MainWindow._on_swipe_requested → PocoWorker.swipe()
→ PocoWorker.run → poco.swipe() + screenshot()
→ swipe_done.emit(bytes)
→ MainWindow._on_swipe_done → device_panel.update_screenshot(bytes)

断线点：swipe_done 信号是否连接？检查 _connect_selected_device / _connect_ip_device
定位：main_window.py 中搜索 swipe_done.connect
```

### 场景5：打包后运行闪退
```
错误链：
PyInstaller → autotest-ide.spec → 缺少 hiddenimport 或 data file
→ 启动时 ImportError 或 FileNotFoundError
→ console=False 模式下无错误输出

定位方法：临时改 console=True，重新打包，查看错误
常见缺失：code_gen.py、record_controller.py 未加入 hiddenimports
          report/template.html 未加入 datas
```

## L4 性能/安全分析 — 针对本项目

```
输出格式:
{
  "category": "performance|security|both",
  "findings": [
    {
      "severity": "high|medium|low",
      "location": "代码位置",
      "description": "问题描述",
      "impact": "潜在影响",
      "recommendation": "优化/修复建议"
    }
  ]
}
```

本项目 L4 重点：

### 性能
- **dump_hierarchy 缓存 TTL**：默认 0.3s，快速连续 pick-point 时可能拿到过时树
- **ScreenshotWorker 轮询间隔**：1/5s = 200ms，高频截图对 TCP 和 UI 线程都有压力
- **_flatten_tree 递归深度**：大型游戏 UI 树可能有 1000+ 节点，每次 pick-point 都重新遍历
- **OverlayWidget 重绘**：mouseMoveEvent 每次 move 都触发 update()，滑动模式下高频重绘

### 安全
- **TCP 无认证**：PocoClient 直连设备端口，无握手验证外的身份校验
- **set_text 明文传输**：用户输入的文本通过 TCP 明文发给设备
- **runtest 子进程**：以当前用户权限执行任意 .py 脚本，无沙箱

## 使用原则

1. **只传相关代码片段**：不传整个文件，只传被调试的函数
2. **优先 L1→L2**：语法和逻辑问题不需要到 L3
3. **L3 必须带 error_log**：没有错误日志的集成调试靠猜，效率低
4. **参考场景速查**：L3 先查上方典型场景，命中直接用，未命中再走通用分析
5. **L4 按需**：只有出现卡顿或安全审计时才调

[[autotest-ide-debug]] [[signal-chain-debug]] [[pococlient-concurrency-debug]]
