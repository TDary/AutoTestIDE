# JX4 SDK 缺失接口清单

> 日期: 2026-07-02 | 对接版本: AltrunUnityDriver v2.4.0

---

## 1. 现状

IDE 需要与 JX4 AltrunUnityDriver 通过 TCP socket 通信。当前已实现和缺失的接口如下：

| # | IDE 功能 | 需要 SDK 接口 | 状态 | 说明 |
|---|---------|-------------|------|------|
| 1 | 连接 + 握手 | `getServerVersion` | 已有 | 连接后立即调用验证 |
| 2 | UI 树展示 | `getHierarchy` | 已有 | 返回 `{"objs": {"id":..., "name":..., "children":[...]}}` |
| 3 | 坐标点击 | `tapScreen` (tap;x;y;) | 已有 | 映射为 `PocoClient.click(x, y)` |
| 4 | 按名称查找并点击 | `findObjectAndTap` | 已有 | 映射为 `PocoClient.find_and_tap(name)` |
| 5 | 按坐标拾取节点 | `getNodeByPos` 或等效 | **缺失** | Unity 端未注册此命令 |
| 6 | 输入文本 | `setText` | 需确认 | 参数格式待对齐 |

---

## 2. 关键缺失：按坐标拾取节点

这是 IDE 最核心的交互：用户点击截图上某个按钮，IDE 需要识别该按钮的名称，自动生成 `poco.find_and_tap('BtnName')` 代码。

当前 `getNodeByPos` 在 Unity 端返回 `KeyNotFoundException`，说明该命令未注册。

### 2.1 当前 getHierarchy 返回格式

```json
{
  "objs": {
    "id": "root",
    "name": "root",
    "children": [
      {"id": -41830, "name": "Denglu_NanNv_New(Clone)", "children": [
        {"id": -41836, "name": "Juqing", "children": [
          {"id": -41840, "name": "Denglu_xinjianjuese", "children": []}
        ]}
      ]}
    ]
  }
}
```

**问题：节点没有坐标信息**（无 x/y/width/height），IDE 无法在本地按坐标查找命中的节点。

### 2.2 建议方案（三选一）

#### 方案 A：在 Unity 端注册 getNodeByPos 命令（推荐）

- 输入：`getNodeByPos;x;y;&`
- 输出：命中节点的 AltElement JSON，例如 `{"name":"BtnStart","id":-21912,"x":100,"y":200,"width":120,"height":40}`
- IDE 调用后直接拿到节点名称，插入代码
- **优点**：最准确，服务端直接做射线检测；SDK 改动最小只需注册一个命令
- **缺点**：需要 Unity 端开发

#### 方案 B：让 getHierarchy 返回节点坐标信息

- 在 `getHierarchy` 返回的每个节点中增加 `x`、`y`、`width`、`height`（或 `worldX`/`worldY` + 屏幕投影后的 bounds）
- IDE 缓存整棵树后在本地按坐标查找面积最小的命中节点
- **优点**：不需要新命令，一次 getHierarchy 拿到所有信息
- **缺点**：JSON 体积增大（当前 178KB → 预估 300KB+）；坐标精度取决于 Unity 端投影方式

#### 方案 C：提供 getRectTransformPoints 按名称查坐标

- 已有接口 `getRectTransformPoints`，传入路径返回矩形坐标
- IDE 遍历 UI 树所有叶子节点，逐个调用 `getRectTransformPoints` 获取坐标
- **优点**：不需要新命令
- **缺点**：5050 个节点 × 逐个查询 = 极慢，不可行

### 2.3 推荐

**方案 A** 最优 — 改动小、精度高、不影响现有接口。

如果方案 A 短期无法实现，**方案 B** 是备选 — 在 `getHierarchy` 返回值里加上坐标字段即可，IDE 侧已写好本地查找逻辑，对接即可用。

---

## 3. 输入文本接口确认

当前 `setText` 在协议文档中的格式为：

```
setText;text;alt_object_json;&
```

需要确认：

1. `alt_object_json` 的具体格式 — 是 `{"id":"-21912"}` 还是完整 AltElement JSON？
2. 对应的 `PocoClient.set_text(node_id, text)` 实现：当前传参为 `(node_id, text)`，JX4 映射为 `setText;text;node_id`，如果需要完整 JSON 则需要调整

建议 SDK 文档补充 `setText` 的 `alt_object_json` 示例。

---

## 4. IDE 端待对接的已有接口

以下 SDK 接口已存在但 IDE 尚未使用，后续可按需接入：

| SDK 命令 | IDE 潜在用途 |
|---------|------------|
| `findObject` | 按路径/Tag/Component 查找单个节点 |
| `findObjectAllChildren` | 查找某节点下所有同名子节点 |
| `findText` / `findAllText` | 文本搜索 |
| `getRectTransformPoints` | 获取节点矩形（用于高亮边框） |
| `getText` | 获取节点文本 |
| `objectExist` | 断言节点是否存在 |
| `getScreen` | 获取屏幕分辨率 |
| `dragObject` | 拖拽操作 |
