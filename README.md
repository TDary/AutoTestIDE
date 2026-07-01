# AutoTest IDE

A modern cross-platform UI automation IDE for games and apps. Connects to devices over the Poco UI-tree protocol — no image recognition, no fragile screenshots. Built with PyQt5.

Inspired by AirtestIDE but focused on the Poco protocol and extensible per-game SDK adapters.

## Features

- **Multi-protocol architecture** — Pluggable `PocoProtocol` adapters per game SDK. Bundled adapters:
  - `poco` — standard Poco text-command protocol (Unity, Cocos, Android原生)
  - `jx4` — AltrunUnityDriver protocol (semicolon-separated, `&`-terminated, base64 screenshots)
- **Three connection modes**
  - USB Android via `adb forward` (with remote port scanning for JX4)
  - Local TCP (`127.0.0.1:13000` etc.)
  - Direct IP — connect to any `host:port` without adb
- **Live device preview** — screenshot streaming at 5 FPS with click-to-inspect
- **UI tree explorer** — hierarchical tree with payload visibility
- **Property panel** — inspect node attributes (visibleBounds, text, type, ...)
- **Locator generator** — auto-generates `poco(...)` Python code from picked nodes
- **Script editor** — Python syntax highlighting, run/save/open
- **Test runner** — spawns a subprocess to run `.air` scripts with an injected namespace (`poco`, `snapshot`, `assert_exists`, `log`)
- **HTML reports** — step-by-step report with screenshots, rendered from `report.json`
- **Heartbeat health checks** — 3 consecutive failures flips device to offline
- **Modern dark theme** — Catppuccin Mocha palette via global QSS

## Installation

### From source

```bash
git clone <repo-url>
cd AutoTestIDE
pip install -e ".[dev]"
```

Requirements: Python ≥ 3.8, PyQt5 ≥ 5.15, Jinja2, psutil. For Android USB connections, `adb` must be on PATH.

### Build Windows executable

```bash
pip install pyinstaller
python -m PyInstaller autotest-ide.spec --noconfirm
```

Output lands in `dist/AutoTest IDE/`. Launch `AutoTest IDE.exe`.

## Usage

### Launch

```bash
python -m autotest_ide
```

### Connect a device

1. Pick a device from the dropdown (USB, local, or IP直连)
2. Pick the SDK (Poco standard or JX4)
3. Click **⚡ 连接**
4. The screenshot stream and UI tree populate on the left and right panels

### Inspect and record

- Click anywhere on the device screenshot to inspect that point
- The matching UI node highlights in the tree and its properties show in the属性 panel
- A `poco(...).click()` line is auto-inserted into the editor

### Run a script

1. Write or open a `.py` script in the editor
2. Click **▶ 运行** (or F5)
3. Output streams to the console; on completion, an HTML report opens

The script namespace includes:
- `poco` — wrapped `PocoClient` with recording
- `snapshot()` — capture a screenshot step
- `assert_exists(locator, msg)` — assert and record
- `log(msg)` — record a log step

### Run scripts from CLI

```bash
python -m autotest_ide.runner.runtest test.air \
    --device-type android \
    --device_serial emulator-5554 \
    --poco-port 13000 \
    --protocol poco \
    --timeout 600
```

`--protocol` accepts either a registry name (`poco`, `jx4`) or a fully-qualified `package.module:ClassName` spec.

## Architecture

```
src/autotest_ide/
├── app.py                  — QApplication entry point
├── core/
│   ├── protocol_base.py    — PocoProtocol ABC (send/read/handshake/create_connection)
│   ├── protocol_poco.py    — PocoTextProtocol (default text-command adapter)
│   ├── protocol.py         — wire framing (encode_command, read_json_frame, ...)
│   ├── poco_client.py      — sync TCP client with FIFO request/response matching
│   ├── device.py           — Device state machine (disconnected → online → offline)
│   ├── device_manager.py   — discovery + active device lifecycle
│   ├── forwarder.py        — PortForwarder ABC: AdbForwarder / LocalForwarder / DirectForwarder
│   ├── locator.py          — generate poco(...) locator strings
│   ├── report_model.py     — ReportStep / ReportSummary dataclasses
│   └── errors.py           — typed exception hierarchy
├── sdks/
│   ├── poco/               — re-export PocoTextProtocol
│   └── jx4/protocol.py     — JX4Protocol (AltrunUnityDriver)
├── runner/
│   ├── runtest.py          — subprocess entry, --protocol flag, PROTOCOL_REGISTRY
│   ├── recorder.py         — RecordingPocoClient wraps PocoClient for reports
│   ├── reporter.py         — step pass/fail, screenshot save, JSON output
│   └── runtime.py          — build_namespace() for injected script globals
├── report/
│   ├── __init__.py         — render_report() Jinja2
│   ├── template.html
│   ├── report.css
│   └── report.js
└── ui/
    ├── main_window.py      — QMainWindow, toolbar, splitter layout
    ├── style.py            — DARK_STYLE global QSS
    ├── device_panel.py     — screenshot + click overlay
    ├── editor.py           — Python syntax highlighter
    ├── tree_panel.py       — QTreeView UI hierarchy
    ├── property_panel.py   — QTableWidget payload
    ├── console.py          — QTextEdit log
    ├── threads.py          — ScreenshotWorker / PocoWorker / DeviceBridge
    ├── run_controller.py   — subprocess lifecycle
    └── report_view.py      — QWebEngineView or browser fallback
```

### Adding a new SDK adapter

1. Create `src/autotest_ide/sdks/<name>/__init__.py` and `protocol.py`
2. Implement a `PocoProtocol` subclass — override `METHOD_MAP`, `send_request`, `read_response`, `handshake`, and (if needed) `create_connection` for port scanning
3. Register it in `runner/runtest.py:PROTOCOL_REGISTRY` so the CLI `--protocol <name>` works
4. Add an entry to the SDK combo box in `ui/main_window.py:_init_toolbar`

The `PocoClient` is composition-over-inheritance — same client code works with any protocol.

## Testing

```bash
pytest tests/ -v
```

125 tests covering protocol adapters, PocoClient, Device state machine, DeviceManager, forwarders, locator generation, reporter, recorder, runner integration, and JX4 SDK.

Real-device smoke tests are skipped by default; enable with `--run-real-device` and `AUTOTESTIDE_REAL_ANDROID_SERIAL=<serial>`.

## Documentation

- `docs/specs/2026-06-29-autotest-ide-clone-design.md` — original design spec
- `docs/plans/` — implementation plans (protocol, device, UI, runner)
- `docs/jx4/AltrunUnityDriver接口协议文档.md` — JX4 protocol reference

## License

MIT
