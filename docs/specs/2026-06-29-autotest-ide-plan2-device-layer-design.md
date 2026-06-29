# Plan 2: Device / Connection Layer Design

**日期**: 2026-06-29
**状态**: Draft
**范围**: 里程碑 M3 —— Device + Forwarder + DeviceManager(设备/连接层)

**父 spec**: `docs/specs/2026-06-29-autotest-ide-clone-design.md` §4
**前置 plan**: `docs/plans/2026-06-29-autotest-ide-plan1-protocol-client.md`(M1+M2 已完成,PocoClient 可用)

---

## 1. 目标与范围

### 1.1 目标

实现 spec §4 的设备/连接层,把 Plan 1 的 `PocoClient`(裸 TCP 协议客户端)包装成可被 UI 使用的 `Device` 抽象:负责端口转发、连接生命周期、健康检查、状态机。提供 `DeviceManager` 做设备发现 + active device 管理 + 全局清理。

### 1.2 在范围内

- `PortForwarder` 抽象 + `AdbForwarder`(Android USB) + `LocalForwarder`(PC 直连)。
- `Device` 状态机(`disconnected → connecting → online ↔ offline → disconnected`)+ heartbeat 守护线程。
- `DeviceManager`:设备发现(`adb devices -l` 解析、本地端口探测)、active device 管理、`atexit` 全局清理。
- 异常体系扩展(`DeviceError` 树,与 `PocoError` 树并存)。
- mock + fake_server 单元测试;真机冒烟测试(默认 skip)。

### 1.3 不在范围内(留后续 plan)

- **iOS / iproxy**:spec §4.2 模式 A 的 iOS 分支。iproxy 是长驻进程,生命周期与 adb forward 不同,留到后续 plan 加 `IosIproxyForwarder`,不动 `Device`。
- **PyQt UI / Qt 信号桥接**:Plan 3。`Device.on_status_change` 在 Plan 2 是普通回调;Plan 3 在 `ui/threads.py` 包 Qt 信号发射器订阅。
- **多设备并行 UI**:架构预留(`DeviceManager._devices: list`),UI 只暴露 `_active`(spec §4.4)。
- **持久化"上次连接的设备"**:spec §4.3.4 明确不做。
- **设备掉线自动重连**:决策为不自动重连(见 §1.4 决策 #2)。
- **进程名匹配**:spec §4.2 PC 设备发现提到端口扫描 + 进程名匹配;Plan 2 只做端口探测,进程名匹配留后续。

### 1.4 关键决策(补 spec 开放项)

1. **设备发现放 `DeviceManager`,不在 `Device`**。`Device` 只管单个已构造设备的连接生命周期;发现(list_android / list_local)是 `DeviceManager` 的职责。理由:发现是"找出有哪些可连的设备",Device 是"连上一个具体设备",职责分离让 Device 可独立测试。
2. **掉线不自动重连**。heartbeat 连续失败 3 次转 `offline` 后,heartbeat 线程退出,不再轮询。用户在 UI 点"重连"才走 `Device.reconnect()`。理由:沿用 spec §7.6 "不做自动恢复"的精神;设备掉线常是物理原因(USB 拔了 / 进程崩了),自动重连会反复打日志噪扰用户;状态机更简单可预测。
3. **AdbForwarder 用 `adb forward tcp:0`,不持有子进程**(见 §6 Deviations #1)。
4. **`core/` 零 PyQt 依赖**(沿用 Plan 1 偏差 #3)。状态变更通知走普通回调,Qt 信号桥接留 Plan 3。

---

## 2. 架构

```
┌──────────────────────────────────────────────────────────┐
│ DeviceManager                                            │
│ ├── list_android_devices()   # adb devices -l 解析      │
│ ├── list_local_devices()      # 本地端口探测             │
│ ├── connect_android(serial)   # → 构造 Device + 设 active │
│ ├── connect_local(host,port)  # → 构造 Device + 设 active │
│ ├── _active: Device           # 当前唯一活动设备         │
│ ├── _devices: list[Device]    # 历史设备(架构预留)      │
│ └── shutdown()                # atexit 钩子清理          │
└──────────────────────────────────────────────────────────┘
        │ 构造
        ▼
┌──────────────────────────────────────────────────────────┐
│ Device                                                   │
│ ├── forwarder: PortForwarder  # 端口转发                │
│ ├── poco: PocoClient          # Plan 1 的协议客户端     │
│ ├── _status: 状态机           # disconnected/connecting/ │
│ │                              # online/offline          │
│ ├── _heartbeat_thread         # 守护线程,5s 一次探活    │
│ ├── connect() / disconnect() / reconnect() / health_check() │
│ └── on_status_change(cb)      # 状态变更回调            │
└──────────────────────────────────────────────────────────┘
        │ 聚合
        ▼
┌────────────────────────────┐  ┌──────────────────────────┐
│ PortForwarder (ABC)        │  │ PocoClient (Plan 1)     │
│ ├── AdbForwarder            │  │ connect/close/heartbeat │
│ │   (adb forward tcp:0)    │  │ get_root/screenshot/...  │
│ └── LocalForwarder          │  └──────────────────────────┘
│     (no-op, PC 直连)       │
└────────────────────────────┘
```

**核心设计原则**:
- `Device` 聚合 `Forwarder` + `PocoClient`,状态机是这三个的协调者。
- `Forwarder` 可替换(ABC);加 iOS 时新增 `IosIproxyForwarder`,不动 `Device`。
- `Device` 不暴露业务方法(`inspect_by_point` 等),只暴露 `poco` 属性让调用方(Plan 3 的 PocoWorker QThread)自己调 —— Plan 1 "同步非流水线"约束自然满足,Device 层不引入并发。
- 边界:`ForwarderError` / `DeviceDiscoveryError` 是设备层异常;`PocoConnectionError`(Plan 1)是协议层异常,Device 层 catch 它翻译成状态机转 `offline`,不向上抛 PocoError。

### 2.1 状态机完整图

```
              connect()
disconnected ───────────> connecting
     ▲                        │
     │                  成功   │  失败
     │                        ▼     │
     │                      online  ▼
     │                        │   offline
     │     disconnect()       │     │
     └────────────────────────┘     │ reconnect()
                                    ▼
                                 connecting ──…
```

- `disconnect()` 从 online / offline / connecting 都能回 disconnected。
- `reconnect()` 只从 offline 走(从其他状态调 raise `DeviceError`)。

---

## 3. 异常体系

在 `src/autotest_ide/core/errors.py` 追加,不动 Plan 1 的 `PocoError` 树:

```
Exception
├── PocoError (Plan 1, 不动)
│   ├── PocoConnectionError
│   ├── PocoTimeoutError
│   ├── PocoProtocolError
│   ├── PocoRemoteError
│   └── PocoNodeNotFoundError
└── DeviceError                       # 设备层基类
    ├── ForwarderError                # adb forward 失败 / 清理失败 / adb 不在 PATH
    └── DeviceDiscoveryError          # adb devices 解析失败 / 端口探测失败
```

- `DeviceError`:设备层所有异常的基类。UI 层(Plan 3)catch `DeviceError` 翻译成用户可读消息。
- `ForwarderError`:`AdbForwarder.start()` 失败(adb 调用失败 / stdout 解析不出端口 / adb 返回错误)或 `stop()` 失败(忽略,只记日志)。
- `DeviceDiscoveryError`:`DeviceManager.list_android_devices()` 解析 `adb devices -l` 失败,或 `list_local_devices()` 全部端口探测超时。

`Device.connect()` 内部 catch `PocoConnectionError`(Plan 1,握手失败 / 连接断)和 `ForwarderError`,翻译成状态机转 `offline`,不向上抛。业务方法(`Device.poco` 属性访问)在非 online 状态 raise `DeviceError("device not online: <status>")`。

---

## 4. PortForwarder

### 4.1 ABC

```python
class PortForwarder(ABC):
    @property
    @abstractmethod
    def local_port(self) -> int:
        """转发到本地的端口。start() 之前访问 raise。"""

    @abstractmethod
    def start(self) -> None:
        """启动转发。失败 raise ForwarderError。"""

    @abstractmethod
    def stop(self) -> None:
        """停止转发。best-effort,不 raise(已停也返回)。"""
```

### 4.2 AdbForwarder

`adb_path` 是 `list[str]`(argv 前缀),默认 `["adb"]`。用 list 不用 str 的原因:测试要注入 `fake_adb.py`(Python 脚本),需要 `[sys.executable, "tests/fake_adb.py"]` 这种多元素 argv,单个 str 表达不了。生产用 `["adb"]`。

```python
class AdbForwarder(PortForwarder):
    def __init__(self, device_serial: str, remote_port: int = 5001,
                 adb_path: list[str] = None):
        self._device_serial = device_serial
        self._remote_port = remote_port
        self._adb_path = adb_path or ["adb"]
        self._local_port: Optional[int] = None

    @property
    def local_port(self) -> int:
        if self._local_port is None:
            raise ForwarderError("forwarder not started")
        return self._local_port

    def start(self) -> None:
        # subprocess.run(self._adb_path + ["-s", serial, "forward", "tcp:0",
        #                                  f"tcp:{remote_port}"], ...)
        # stdout 是分配的本地端口(纯数字),解析存 _local_port
        # adb 不在 PATH / 返回非零 / stdout 不是数字 → ForwarderError
        ...

    def stop(self) -> None:
        # subprocess.run(self._adb_path + ["-s", serial, "forward", "--remove",
        #                                  f"tcp:{local_port}"], ...)
        # best-effort:忽略所有错误,只记日志(避免析构时 raise 干扰 atexit)
        # _local_port 置 None
        ...
```

**`adb forward tcp:0`** 让 adb server 自动选空闲本地端口并打到 stdout(纯数字一行),IDE 解析拿到。这避免多设备端口冲突(spec §4.3.2)。

### 4.3 LocalForwarder

```python
class LocalForwarder(PortForwarder):
    def __init__(self, local_port: int = 5001):
        self._local_port = local_port

    @property
    def local_port(self) -> int:
        return self._local_port

    def start(self) -> None:
        pass  # no-op,PC 直连无需转发

    def stop(self) -> None:
        pass  # no-op
```

---

## 5. Device

### 5.1 接口

```python
class Device:
    def __init__(self, name: str, device_type: str, forwarder: PortForwarder):
        self._name = name
        self._device_type = device_type  # "android" | "windows" | "unity_editor" | ...
        self._forwarder = forwarder
        self._poco: Optional[PocoClient] = None
        self._status = "disconnected"
        self._heartbeat_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._heartbeat_failures = 0
        self._on_status_change: Callable[[str], None] = lambda s: None
        self._lock = threading.Lock()  # 保护 _status / _heartbeat_failures / _poco

    @property
    def name(self) -> str: ...
    @property
    def device_type(self) -> str: ...
    @property
    def status(self) -> str: ...

    @property
    def poco(self) -> PocoClient:
        if self._status != "online" or self._poco is None:
            raise DeviceError(f"device not online: status={self._status}")
        return self._poco

    def on_status_change(self, callback: Callable[[str], None]) -> None:
        self._on_status_change = callback

    def connect(self) -> None:
        # disconnected → connecting
        #   forwarder.start()
        #   PocoClient(host="127.0.0.1", port=forwarder.local_port).connect()
        #   (handshake 内含在 PocoClient.connect)
        #   成功 → online + 启动 heartbeat 线程
        #   失败(ForwarderError/PocoConnectionError)→ offline + forwarder.stop()
        # 从 connecting/online/offline 调用 raise DeviceError("already ...")
        # 注意:PocoClient 的 host/port 来自 forwarder,Device 不收 poco_port 参数

    def disconnect(self) -> None:
        # 任何状态 → disconnected
        #   _stop_event.set() 停 heartbeat
        #   poco.close() (if not None)
        #   forwarder.stop()
        #   join heartbeat 线程 (timeout=2s,daemon 兜底)

    def reconnect(self) -> None:
        # 只允许从 offline 调用,等价于 connect() 但起点是 offline
        # 其他状态 raise DeviceError

    def health_check(self) -> bool:
        # 同步探活,给 UI 主动调(不想等 5s heartbeat)
        # poco.heartbeat(),失败转 offline
        # online 时返回 True,否则 False;不 raise
```

**端口来源**:Device 不收 `poco_port` 参数。PocoClient 连的是 forwarder 转发后的本地端口(`forwarder.local_port`),host 永远是 `127.0.0.1`(Android 经 adb forward 转回本地;PC 直连本来就是本地)。`AdbForwarder.remote_port` 是设备侧 Poco 服务端口,由 Forwarder 自己持有,Device 不关心。

### 5.3 heartbeat 线程

```python
def _heartbeat_loop(self):
    while not self._stop_event.wait(timeout=5.0):  # 5s 一次(spec §4.3.3)
        if self._status != "online":
            return
        try:
            ok = self._poco.heartbeat()  # Plan 1 的 non-raising 探活
        except Exception:
            ok = False  # 防御:理论上 heartbeat 不 raise,但兜底
        with self._lock:
            if not ok:
                self._heartbeat_failures += 1
                if self._heartbeat_failures >= 3:
                    self._set_status("offline")  # 触发 on_status_change
                    return  # 线程退出,不再轮询
            else:
                self._heartbeat_failures = 0
```

- 用 `threading`(不是 QThread),匹配 Plan 1 偏差 #3。
- 守护线程(`daemon=True`),进程退出时自动死。
- `_stop_event.wait(timeout=5.0)` 既能定时又能响应 stop(比 `time.sleep` + 轮询 flag 干净)。
- 失败 3 次转 offline 后线程主动退出,不再轮询 —— 匹配决策 #2(不自动重连)。
- `PocoClient.heartbeat()` 本来就 non-raising(Plan 1 Task 15),所以 try/except 是兜底防御,正常路径走不到。

### 5.4 状态变更通知

`on_status_change` 是普通回调 `Callable[[str], None]`,默认 no-op。Plan 2 测试用 lambda 收集状态序列;Plan 3 在 `ui/threads.py` 里:

```python
# Plan 3 预览(不在本 plan 实现)
device.on_status_change(lambda s: self.status_changed.emit(s))  # Qt 信号
```

`_set_status` 在持有 `_lock` 时调用 callback,保证状态读取一致。callback 内禁止再调 Device 方法(会死锁)—— 文档里写明。

---

## 6. DeviceManager

### 6.1 接口

```python
class DeviceManager:
    def __init__(self, adb_path: list[str] = None):
        self._adb_path = adb_path or ["adb"]
        self._devices: list[Device] = []
        self._active: Optional[Device] = None
        self._atexit_registered = False

    # --- 发现(spec §4.2)---
    def list_android_devices(self) -> list[dict]:
        # subprocess.run(self._adb_path + ["devices", "-l"], ...)
        # 解析 stdout
        # 返回 [{"serial", "state", "model", "transport_id"}, ...]
        # 只返回 state == "device"(可用);offline/unauthorized 不返回
        # adb 失败 raise DeviceDiscoveryError

    def list_local_devices(self, ports: list[int] = None) -> list[dict]:
        # 默认扫 [5001, 5002, 5003](Poco 常用端口)
        # 对每个端口 socket.create_connection(("127.0.0.1", port), timeout=0.5)
        # 通即认为有 Poco 服务在监听
        # 返回 [{"host": "127.0.0.1", "port"}, ...]
        # 全部超时不算错(返回空 list);socket 层异常才算

    # --- active device 管理 ---
    def connect_android(self, serial: str, remote_port: int = 5001,
                       name: str = None) -> Device:
        # 构造 AdbForwarder(serial, remote_port, self._adb_path) + Device,connect(),设 _active
        # name 默认用 serial
        # 失败 raise DeviceError(由 Device.connect 内部状态决定,但 connect
        #   总会返回——失败时状态是 offline,Device 仍存在)
        # 懒注册 atexit(self.shutdown)

    def connect_local(self, port: int, name: str = None) -> Device:
        # PC 直连场景,spec §4.2 模式 B:游戏进程监听 127.0.0.1:{port}
        # 构造 LocalForwarder(port) + Device,connect(),设 _active
        # name 默认 f"localhost:{port}"
        # 懒注册 atexit(self.shutdown)
        # (host 固定 127.0.0.1,不收 host 参数 —— spec §4.2 明确"PC 上运行的游戏进程")

    @property
    def active(self) -> Optional[Device]: ...

    def disconnect_active(self) -> None:
        # _active.disconnect(),_active = None
        # _devices 保留(历史)

    def shutdown(self) -> None:
        # 遍历 _devices 调 disconnect(幂等:已 disconnected 的跳过)
        # _active = None
```

### 6.2 adb devices -l 解析

`adb devices -l` 输出示例:
```
List of devices attached
emulator-5554   device product:sdk_phone model:Pixel_6 device:emu transport_id:1
xxxxxxxx        offline transport_id:2
yyyyyyyy        unauthorized transport_id:3
```

解析逻辑:跳过 `List of devices attached` 行,每行 split 空白,第一列 serial,第二列 state,后续 token 形如 `key:value`,提取 `model`/`transport_id`。只返回 `state == "device"` 的。

### 6.3 atexit 钩子

首次 `connect_android` / `connect_local` 调用时懒注册 `atexit.register(self.shutdown)`,避免无设备时也注册。`shutdown` 幂等(已 disconnected 的 device 跳过 disconnect)。这是 spec §4.3.1 "IDE 退出钩子注册全局清理"的实现。

### 6.4 adb 调用约定

所有 adb 调用走 `subprocess.run(self._adb_path + [...args], capture_output=True, timeout=5, text=True)`:
- `adb_path` 是 `list[str]`,默认 `["adb"]`(假设在 PATH,匹配 spec §4.2 风险登记 "用户环境假设已装")。
- 测试注入:`adb_path=[sys.executable, "tests/fake_adb.py"]`,让 subprocess 跑 Python 解释器执行 fake_adb.py(跨平台,不靠 shebang / 文件关联)。
- 超时 5s(spec §4.3 + Plan 1 风格)。
- `subprocess.TimeoutExpired` → `ForwarderError` / `DeviceDiscoveryError`。
- 返回码非零 → 解析 stderr 包进异常 message。

---

## 7. 测试策略

| 层 | 方式 | 关键测试 |
|---|---|---|
| `PortForwarder` ABC | 仅契约 | 接口存在,无独立测试(抽象类)。 |
| `AdbForwarder` | `fake_adb.py` mock | `start` 解析 stdout 拿端口、`stop` 调 `forward --remove`、adb 不在 PATH raise ForwarderError、stdout 非数字 raise ForwarderError、`local_port` start 前访问 raise。 |
| `LocalForwarder` | 直接单测 | `start`/`stop` no-op 不 raise、`local_port` 返回构造值。 |
| `Device` 状态机 | 配 Plan 1 的 `fake_poco_server` + 真 `LocalForwarder` | disconnected→connecting→online、连接失败(fake_server 不启)转 offline、heartbeat 3 次失败(fake_server.drop_on_next)转 offline、reconnect 只从 offline 能调、`poco` 属性非 online 时 raise DeviceError、disconnect 幂等、on_status_change 回调被触发且顺序正确。 |
| `DeviceManager` 发现 | `fake_adb.py` mock | `adb devices -l` 多设备解析、state 过滤(只 device)、adb 失败 raise DeviceDiscoveryError、本地端口探测命中/未命中、active 切换、shutdown 幂等清理 forwarder。 |
| 真机冒烟 | `@pytest.mark.real_device`,默认 skip,`--run-real-device` 触发 | 连真 Android 设备:adb forward + PocoClient 握手 + heartbeat + screenshot。CI 不跑。 |

### 7.1 fake_adb.py

一个 Python 脚本(`tests/fake_adb.py`),根据 argv 模拟 adb 子集:
- `devices -l` → stdout 输出固定多设备文本(含 device/offline/unauthorized 各一)。
- `-s <serial> forward tcp:0 tcp:5001` → stdout 输出一个固定端口(如 12345)。
- `-s <serial> forward --remove tcp:12345` → 静默退出 0。
- 未知命令 → 退出 1 + stderr。

**注入方式**:`AdbForwarder(adb_path=[sys.executable, "tests/fake_adb.py"])`。subprocess 跑 `[python, fake_adb.py, -s, serial, forward, ...]`,argv 对齐真 adb。跨平台靠 `sys.executable`,不靠 shebang / 文件关联。Plan 2 不内嵌 adb 二进制(spec §9.2 明确不依赖)。

### 7.2 真机冒烟测试

`tests/test_real_device.py`,所有测试标 `@pytest.mark.real_device`。`conftest.py` 加:
```python
def pytest_addoption(parser):
    parser.addoption("--run-real-device", action="store_true", default=False)
def pytest_collection_modifyitems(config, items):
    if not config.getoption("--run-real-device"):
        skip = pytest.mark.skip(reason="need --run-real-device")
        for item in items:
            if "real_device" in item.keywords:
                item.add_marker(skip)
```

冒烟测试需要环境变量 `AUTOTESTIDE_REAL_ANDROID_SERIAL`(设备 serial),没设则 skip。测试内容:`DeviceManager.connect_android(serial)` → 等 online → `poco.get_screen_size()` 返回非空 → `screenshot()` 返回 PNG 头 → disconnect。

---

## 8. Deviations from spec

记录与 spec §4 的偏差,约束后续 plan:

1. **AdbForwarder 用 `adb forward tcp:0`,不持有子进程**。spec §4.3.1 说 "PortForwarder 类管理 adb/iproxy 子进程,析构时强制 kill"。但 `adb forward` 是一次性命令(adb server 持转发规则,IDE 不持有进程),所以 AdbForwarder 不持有子进程,`stop()` 走 `adb forward --remove` 清 adb server 侧规则。`IosIproxyForwarder`(后续 plan)才需要持有长驻子进程,届时再实现 kill 逻辑。这个偏差让 AdbForwarder 更干净,且不影响 spec §4.3.1 的核心目标("避免僵尸转发进程"——adb server 侧规则被 `--remove` 显式清,不靠进程死亡)。

2. **设备发现放 `DeviceManager`,不在 `Device`**(spec §4.1 Device 接口未列发现方法)。理由见 §1.4 决策 #1。

3. **掉线不自动重连**(spec §4.3.3 只说 "失败 3 次转 offline",没说后续)。理由见 §1.4 决策 #2。

---

## 9. 验证标准(M3)

来自 spec §10.1:

| 验证项 | 覆盖 |
|---|---|
| adb/iproxy 子进程管理 | AdbForwarder + atexit shutdown(mock 测试) |
| 状态机测试 | Device 状态机全路径测试(fake_server) |
| 连接真实 Android 设备能 forward + 连上 Poco | 真机冒烟测试(默认 skip,`--run-real-device` 触发) |

---

## 10. 文件结构

```
E:/AutoTestIDE/
├── src/autotest_ide/core/
│   ├── errors.py            # 扩展:DeviceError / ForwarderError / DeviceDiscoveryError
│   ├── forwarder.py         # 新:PortForwarder ABC + AdbForwarder + LocalForwarder
│   ├── device.py            # 新:Device 状态机 + heartbeat
│   └── device_manager.py    # 新:DeviceManager(发现 + active + atexit)
└── tests/
    ├── fake_adb.py          # 新:假 adb 二进制(mock subprocess)
    ├── test_forwarder.py    # 新
    ├── test_device.py        # 新
    ├── test_device_manager.py  # 新
    ├── test_real_device.py   # 新:真机冒烟(默认 skip)
    ├── conftest.py           # 扩展:--run-real-device 选项 + real_device marker
    └── (Plan 1 的文件保持不动)
```

---

**文档结束**
