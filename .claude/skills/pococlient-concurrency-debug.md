---
name: pococlient-concurrency-debug
description: PocoClient FIFO/锁/接收线程的并发调试套路
metadata: 
  node_type: memory
  type: reference
  originSessionId: 4e0d1cb5-fe0f-4f90-89b6-fe79ed121e7e
---

# PocoClient 并发调试

## 核心机制

```
主线程                    _recv_loop (后台线程)
  │                         │
  ├─ _request_json()       │
  │   1. acquire _send_lock │
  │   2. 发送请求           │
  │   3. 创建 Future       │
  │   4. Future 放入 _pending deque
  │   5. release _send_lock │
  │   6. Future.result(timeout)  ←── 阻塞等待
  │                         │
  │                         ├─ 读到响应
  │                         ├  取出 _pending[0] (FIFO)
  │                         ├  future.set_result(data)
  │                         └─ 继续读下一个响应
```

## 常见问题

### 1. 响应串包（A 请求拿到 B 的响应）
**症状**：inspect 返回的是 dump_hierarchy 的数据
**原因**：`_recv_loop` 的 FIFO 匹配假设请求和响应严格按序到达
**定位**：
```python
# 在 _recv_loop 中临时加日志
logger.debug("pending=%d, response_type=%s", len(self._pending), type(data))
```
**修复**：确保 `_send_lock` 覆盖整个 发送+入队 过程，不留窗口

### 2. 超时后连接死掉
**症状**：第一次超时后所有后续请求都报 `PocoConnectionError`
**原因**：`Future.result(timeout)` 超时 → 调用 `self.close()` → socket 关闭 → `_recv_loop` 退出
**定位**：
```python
# 检查 close() 是否在 timeout 异常路径中被调用
grep -n "self.close()" src/autotest_ide/core/poco_client.py
```
**这是设计行为**：超时 = 连接不可靠，主动断开让用户重连

### 3. 缓存过期导致脏数据
**症状**：UI 树高亮一个不存在的节点
**原因**：`dump_hierarchy` 缓存 TTL 内 UI 已变化
**定位**：
```python
# 检查缓存 TTL 和过期逻辑
client = PocoClient(cache_ttl=0.3)  # 缩短 TTL 复现
```

### 4. heartbeat 线程和请求线程竞争
**症状**：间歇性 `PocoProtocolError`
**原因**：heartbeat 和用户请求同时发，`_pending` 队列交错
**定位**：heartbeat 走独立的 `_request_json("heartbeat")`，共享同一个 `_send_lock` 和 `_pending`
**注意**：heartbeat 的 Future 也在 `_pending` 中，`_recv_loop` 必须正确匹配

## 调试套路

1. **先看日志**：`src/logs/autotest_ide.log` 中搜 `PocoWorker` / `PocoClient` / `timeout`
2. **缩短 TTL 复现**：`PocoClient(cache_ttl=0)` 关闭缓存
3. **用 FakePocoServer 隔离**：`tests/fake_poco_server.py` 可设 `delay` 和 `drop_on_next`
4. **加追踪日志**：
   ```python
   import logging
   logging.getLogger("autotest_ide.core.poco_client").setLevel(logging.DEBUG)
   ```
5. **并发测试**：参照 `test_poco_client.py::test_concurrent_requests_return_correct_results`

[[pococlient-concurrency-debug]]
