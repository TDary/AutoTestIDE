---
name: add-sdk-protocol
description: 如何为 AutoTestIDE 新增一个 SDK 协议适配器
metadata: 
  node_type: memory
  type: reference
  originSessionId: 4e0d1cb5-fe0f-4f90-89b6-fe79ed121e7e
---

# 新增 SDK 协议适配流程

以新增"标准 Poco SDK"为例，现有 JX4 作为参照。

## 1. 协议类

创建 `src/autotest_ide/sdks/<sdk_name>/protocol.py`，继承 `PocoProtocol`：

```python
from autotest_ide.core.protocol_base import PocoProtocol

class PocoSDKProtocol(PocoProtocol):
    METHOD_MAP = {
        "dump_hierarchy": "Dump",
        "get_attributes": "GetNodeAttr",
        "inspect_by_point": "Inspect",
        "click": "Click",
        "find_and_tap": "findObjectAndTap",
        "set_text": "SetText",
        # ...
    }

    def resolve_method(self, method: str) -> str:
        return self.METHOD_MAP.get(method, method)

    def send_request(self, sock, method, *args):
        # 实现线格式编码（参考 protocol_poco.py 或 jx4/protocol.py）
        ...

    def read_response(self, sock, expect_binary=False):
        # 实现响应解码
        ...

    def handshake(self, sock) -> tuple:
        # 返回 (server_version, protocol_version)
        ...

    def transform_result(self, method, raw):
        # 将 SDK 原始返回转换为统一节点格式
        ...

    def capture_screenshot(self, sock=None):
        # 返回 PNG bytes，如 SDK 不支持则返回 None 让 PocoClient 走 PIL
        ...
```

关键差异点：
- **线格式**：标准 Poco 用空格分隔 + 换行终止 + 长度前缀 JSON；JX4 用分号 + `;&` 终止 + `altstart::...::altend`
- **hierarchy 格式**：标准 Poco 返回 `{name, type, payload, children}`；JX4 返回 `{id, name, children}` 需 `_convert_jx4_node` 转换
- **inspect 返回**：标准 Poco 返回节点 dict；JX4 返回路径字符串需 `_path_to_node` 转换
- **截图方式**：标准 Poco 走 socket 二进制；JX4 走 PIL ImageGrab 或 base64

## 2. 注册

在 `src/autotest_ide/sdks/__init__.py` 的 `PROTOCOL_REGISTRY` 中添加：

```python
PROTOCOL_REGISTRY = {
    "jx4": "autotest_ide.sdks.jx4.protocol:JX4Protocol",
    "poco": "autotest_ide.sdks.poco.protocol:PocoSDKProtocol",
}
```

这样 MainWindow 的 SDK 下拉框会自动出现新选项，`_load_protocol()` 会动态加载。

## 3. 测试

- `tests/test_<sdk_name>_protocol.py` — 参照 `test_jx4_protocol.py`：
  - `test_method_map_*` — 验证 resolve_method 映射
  - `test_encode_request_*` — 验证线格式编码
  - `test_read_response_*` — 验证响应解码（用 `socket.socketpair()`）
  - `test_transform_result_*` — 验证 hierarchy/inspect 结果转换
  - `test_capture_screenshot_*` — 验证截图返回

## 4. 集成验证

1. 启动对应 SDK 的设备
2. IDE 选择新 SDK → 连接 → 验证 UI 树加载、截图刷新、pick-point 高亮
3. 验证各操作模式代码生成正确
4. 验证脚本运行 + 报告生成

## Checklist

- [ ] 协议类实现（继承 PocoProtocol，实现所有抽象方法）
- [ ] PROTOCOL_REGISTRY 注册
- [ ] 单元测试（映射、编码、解码、转换、截图）
- [ ] 真机集成验证
- [ ] 更新 autotest-ide.spec hiddenimports
- [ ] 更新 CLAUDE.md 依赖/已知限制

[[add-sdk-protocol]] [[add-op-mode]]
