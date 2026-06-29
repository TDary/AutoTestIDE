# Plan 4: Script Runner + HTML Report Design (M6)

**日期**: 2026-06-29
**状态**: Draft
**范围**: 里程碑 M6 —— 脚本运行子进程 + HTML 报告

**父 spec**: `docs/specs/2026-06-29-autotest-ide-clone-design.md` §7, §6.5
**前置 plan**: Plan 1-3 (M1-M5) 已完成

---

## 1. 目标与范围

### 1.1 目标

实现 spec §7 的脚本运行架构:IDE 主进程 spawn `runtest.py` 子进程执行用户的 `.air` 脚本,子进程注入 `poco`/`snapshot`/`assert_exists`/`log` 全局命名空间,所有 Poco 操作自动记录 step 到 `report.json` + 截图,主进程读 `report.json` 用 Jinja2 渲染 HTML 报告。

### 1.2 在范围内

- `runner/runtest.py` — 子进程入口,接收命令行参数(脚本路径、设备类型、设备 serial、poco port)
- `runner/runtime.py` — 注入全局命名空间 (`poco`, `snapshot`, `assert_exists`, `log`)
- `runner/recorder.py` — `RecordingPocoClient` 包装 PocoClient,拦截所有操作自动记 step
- `runner/reporter.py` — `Reporter` 类,管理 `report.json` 写入 + 步骤截图保存
- `core/report_model.py` — 报告数据模型 (`ReportStep`, `ReportSummary`),纯 Python,无 Qt
- `report/template.html` + `report/report.css` + `report/report.js` — Jinja2 HTML 报告模板
- `ui/run_controller.py` — 主进程侧:spawn 子进程,管理 stdin/stdout/stderr 管道,超时/停止逻辑
- `ui/report_view.py` — HTML 报告渲染 (QWebEngineView 或简单打开浏览器)
- 集成测试:用 fake_poco_server 跑最小脚本,验证 report.json 结构 + HTML 报告输出

### 1.3 不在范围内(留后续)

- 实时录制 (spec §12 开放问题)
- 断点调试
- 多脚本批量运行
- 报告历史对比
- macOS/Linux 打包 (PyInstaller)
- 自动更新

### 1.4 关键决策

1. **QWebEngineView 渲染报告** — Phase 1 用 QWebEngineView 在 IDE 内嵌显示报告。若 WebEngine 体积过大则回退到 `webbrowser.open()`。优先尝试 QWebEngineView。
2. **report.json 格式** — 每个步骤一条记录,数组形式,追加写入。子进程结束时写 summary 头。
3. **RecordingPocoClient 只记录"操作型"方法** — `click`/`click_on`/`set_text`/`swipe` 等用户主动触发的操作记入报告。`get_root`/`dump_hierarchy`/`inspect_by_point` 等查询型方法不记录(它们是 IDE 内部用,不算用户测试步骤)。
4. **子进程用同一 `PocoClient`** — 不走 Qt 线程模型,子进程是纯 Python 进程,直接用 `PocoClient` 同步调用。`RecordingPocoClient` 包装它。
5. **截图存 .air 目录** — 每个步骤截图保存为 `step_N.png` 在 `.air/` 目录下,report.json 引用相对路径。

---

## 2. 架构

```
主进程 (IDE)                              子进程 (runtest.py)
─────────────                             ───────────────────
RunController                             runtest.py <air_dir>
├── spawn subprocess ──────────>          │
├── stdout/stderr pipe <────────          ├─ 加载 script.py
├── exit code <────────────────           ├─ 创建 PocoClient (独立连接)
├── 超时 → SIGTERM/taskkill               ├─ RecordingPocoClient(inner, reporter)
├── 读 report.json                        ├─ 注入 namespace {poco, snapshot, ...}
├── 渲染 HTML 报告                         ├─ exec(script, namespace)
└── QWebEngineView 显示                    ├─ 每步: reporter.step_start/pass/fail
                                          ├─ 写 report.json + step_N.png
                                          └─ exit(0 或 1)
```

---

## 3. core/report_model.py — 报告数据模型

```python
@dataclass
class ReportStep:
    index: int
    name: str
    status: str          # "pass" | "fail"
    screenshot: str      # 相对路径 "step_1.png" 或 ""
    error: str           # 错误消息,fail 时填写
    timestamp: float     # time.time()

@dataclass
class ReportSummary:
    script: str          # 脚本路径
    device_type: str
    device_serial: str
    start_time: float
    end_time: float
    total_steps: int
    passed: int
    failed: int
    status: str          # "pass" | "fail"
```

report.json 格式:
```json
{
  "summary": { ...ReportSummary as dict... },
  "steps": [ ...ReportStep as dict... ]
}
```

---

## 4. runner/recorder.py — RecordingPocoClient

```python
class RecordingPocoClient:
    """Wraps PocoClient, intercepts user-facing operations for step recording."""

    def __init__(self, inner: PocoClient, reporter: Reporter):
        self._inner = inner
        self._reporter = reporter

    # 透传查询型方法(不计步骤)
    def get_root(self): return self._inner.get_root()
    def dump_hierarchy(self, depth=None): return self._inner.dump_hierarchy(depth)
    def get_screen_size(self): return self._inner.get_screen_size()
    def get_attributes(self, node_id): return self._inner.get_attributes(node_id)
    def inspect_by_point(self, x, y): return self._inner.inspect_by_point(x, y)
    def screenshot(self): return self._inner.screenshot()
    def heartbeat(self): return self._inner.heartbeat()
    def close(self): return self._inner.close()

    # 操作型方法(记步骤)
    def click(self, x, y):
        self._reporter.step_start(f"click({x}, {y})")
        try:
            self._inner.click(x, y)  # 注:PocoClient当前没有click方法,这里先设计接口
            self._reporter.step_pass(screenshot=self._inner.screenshot())
        except Exception as e:
            self._reporter.step_fail(error=str(e), screenshot=self._inner.screenshot())
            raise
```

**注意**: 当前 `PocoClient` 只实现了 spec §3.2 的查询型方法(Phase 1 最小集)。`click`/`set_text`/`swipe` 等操作型方法是 M6 的新增,需要在 `PocoClient` 中扩展协议方法。

---

## 5. PocoClient 协议扩展 (M6 新增方法)

| 方法 | 入参 | 返回 | 用途 |
|---|---|---|---|
| `click` | `{x, y}` | 无 | 点击坐标 |
| `set_text` | `{node_id, text}` | 无 | 设置节点文本 |
| `swipe` | `{x1, y1, x2, y2, duration}` | 无 | 滑动操作 |

这些是 SDK 侧应该实现的 JSON-RPC 方法。IDE 侧只负责发送请求和记录步骤。

---

## 6. runner/reporter.py — Reporter

```python
class Reporter:
    def __init__(self, air_dir: Path, device_type: str, device_serial: str):
        self._air_dir = air_dir
        self._device_type = device_type
        self._device_serial = device_serial
        self._steps: list[ReportStep] = []
        self._start_time = time.time()
        self._current_step: Optional[ReportStep] = None

    def step_start(self, name: str):
        self._current_step = ReportStep(index=len(self._steps)+1, name=name, ...)

    def step_pass(self, screenshot: bytes = b""):
        # 保存截图,设状态 pass,加入 steps

    def step_fail(self, error: str, screenshot: bytes = b""):
        # 保存截图,设状态 fail,加入 steps

    def finish(self, status: str):
        # 写 report.json (summary + steps)

    def _save_screenshot(self, step_index: int, data: bytes) -> str:
        path = self._air_dir / f"step_{step_index}.png"
        path.write_bytes(data)
        return path.name
```

---

## 7. runner/runtest.py — 子进程入口

```
python -m autotest_ide.runner.runtest <air_dir> --device-type <t> --device-serial <s> --poco-port <p> [--timeout <seconds>]
```

逻辑:
1. 解析命令行参数
2. 创建 `PocoClient(host="127.0.0.1", port=poco_port)` 并 `connect()`
3. 创建 `Reporter(air_dir, device_type, device_serial)`
4. 创建 `RecordingPocoClient(poco, reporter)`
5. 构建注入命名空间:
   ```python
   namespace = {
       "poco": recorder,
       "snapshot": lambda: reporter.step_pass(screenshot=recorder.screenshot()),
       "assert_exists": ...,
       "log": lambda msg: reporter.step_start(f"log: {msg}"); reporter.step_pass(),
   }
   ```
6. `exec(compile(script_src, script_path, "exec"), namespace)`
7. 异常时 `reporter.step_fail(error=...)`; `reporter.finish("fail")`; `sys.exit(1)`
8. 正常结束 `reporter.finish("pass")`; `sys.exit(0)`

---

## 8. ui/run_controller.py — 主进程侧运行管理

```python
class RunController(QObject):
    output_received = pyqtSignal(str, bool)   # (text, is_error)
    run_finished = pyqtSignal(int, str)       # (exit_code, report_path)
    run_started = pyqtSignal()
    run_stopped = pyqtSignal()

    def start(self, air_dir: Path, device_type: str, device_serial: str, poco_port: int, timeout: int = 600):
        cmd = [sys.executable, "-m", "autotest_ide.runner.runtest", str(air_dir),
               "--device-type", device_type, "--device-serial", device_serial,
               "--poco-port", str(poco_port), "--timeout", str(timeout)]
        self._process = subprocess.Popen(cmd, stdout=PIPE, stderr=STDOUT, text=True)
        self._reader_thread = threading.Thread(target=self._read_output, daemon=True)
        self._reader_thread.start()

    def stop(self):
        # psutil kill process tree

    def _read_output(self):
        for line in self._process.stdout:
            self.output_received.emit(line, False)
        self._process.wait()
        report_path = str(air_dir / "report.json")
        self.run_finished.emit(self._process.returncode, report_path)
```

---

## 9. 报告渲染

子进程结束后,主进程读 `report.json`,用 Jinja2 渲染 `template.html` 生成最终 HTML 报告,在 `QWebEngineView` 中显示(回退:用 `webbrowser.open()` 打开)。

---

## 10. Deviations from spec

1. **QWebEngineView 优先,webbrowser 回退** — spec 没明确报告显示方式,Phase 1 在 IDE 内嵌入显示更佳体验。
2. **追加写入 report.json** — spec §7.4 说 "每个 step 写 report.json",实际实现为步骤在内存中累积,脚本结束时一次性写(更高效,避免频繁 IO)。若子进程崩溃则步骤丢失——这是可接受的(崩溃本身就是 fail)。
3. **RecordingPocoClient 不记录查询方法** — spec §7.4 的 `RecordingPocoClient` 示例只记 `click`,我们扩展为只记操作型方法(用户主动触发的测试步骤),查询型方法不计入报告。

---

## 11. 验证标准(M6)

| 验证项 | 覆盖 |
|---|---|
| `runtest.py` 能执行最小脚本 | 集成测试 (fake_server) |
| 步骤自动记入 report.json | Reporter 单元测试 + 集成测试 |
| report.json 结构正确 | report_model 单元测试 |
| HTML 报告可渲染 | 手动验证 |
| 子进程超时/停止能正常终止 | RunController 单元测试 |
| core/ 无 PyQt 依赖 | import 检查 |

---

**文档结束**
