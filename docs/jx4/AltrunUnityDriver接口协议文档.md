# AltrunUnityDriver Socket 接口协议文档

> 版本: v1.0 | 日期: 2026-07-01 | 分支: PC_New

---

## 1. 连接协议

- **传输层**: TCP 长连接
- **默认地址**: `127.0.0.1:13000`
- **端口自增**: 连接失败时端口 +1 重试（13001→13002→...），最多 5 次
- **握手**: 连接成功后立即发送 `getServerVersion` 命令验证
- **超时**: `socket.settimeout(timeout)` 默认 60s（构造函数参数），读取超时默认 5 分钟

---

## 2. 帧协议

### 2.1 请求格式

```
CommandName;arg1;arg2;...;argN;&
```

| 字段 | 值 | 说明 |
|------|---|------|
| CommandName | 字符串 | 命令名，如 `findObject`、`gm`、`GMCmd` |
| 分隔符 | `;` | 分隔命令名与各参数 |
| 终止符 | `&` | 标识命令结束 |
| 换行符 | **无** | 整条命令为一行文本，不以 `\n` 结尾 |

**编码**: UTF-8（`data.encode('utf-8', 'ignore')`）

**示例**:
```
findObject;//BtnStart;path;&
tapScreen;100;200;;&
GMCmd;me:GetPlayer():AddLevel(5);&
gm;AddBuff;1000001;&
moveTo;1001;10;20;30;&
isAutoPath;&
setDlss;true;2;&
getCamera;&
```

### 2.2 响应格式

```
altstart::<payload>::altLog::<log>::altend
```

| 字段 | 说明 |
|------|------|
| 前缀 | `altstart::` |
| 后缀 | `::altend` |
| 日志分隔 | `::altLog::` |
| payload | 业务数据 |
| log | Unity 端日志输出 |

**提取方式**:
```python
data = received_text
data = data.split('altstart::')[1].split('::altend')[0]
parts = data.split('::altLog::')
payload = parts[0]    # 业务数据
log = parts[1]        # 日志（写入日志文件）
```

**读取方式**: 循环 `socket.recv(1024)` 拼接，直到数据以 `::altend` 结尾

**异常情况**: 若收到的数据不以 `altstart::` 开头或不含 `::altend`，返回空字符串 `''`

---

## 3. 参数格式

### 3.1 位置参数（非关键字）

所有参数按位置排列，以 `;` 分隔，**没有参数名**。

```
findObject;//BtnConfirm;path;&    ← 第2参数是路径值，第3参数是查找方式
```

### 3.2 类型序列化规则

| Python 类型 | 序列化为 | 代码写法 | 实际发送 |
|-------------|---------|---------|---------|
| `bool True` | 字符串 `"true"` | `tf = "true" if tf else "false"` | `true` |
| `bool False` | 字符串 `"false"` | 同上 | `false` |
| `int` | `str(int)` | `str(5)` | `5` |
| `str` | 原值 | 直接传 | `//BtnStart` |
| 空参数 | 空字符串 `""` | `camera_name=''` | 两个 `;;` 连续 |
| 坐标向量 | JSON 字符串 | `'{"x":1,"y":2}'` | 仅 drag 命令 |
| GMCmd 表达式 | f-string 拼接 | `f"me:AddLevel({degree})"` | `me:AddLevel(5)` |

### 3.3 布尔值对照表

本协议中布尔值表达**不统一**，需按命令区分：

| 接口 | True 表示 | False 表示 |
|------|----------|-----------|
| `enableLogging` | `"true"` | `"false"` |
| `setCameraControl` | `"true"` | `"false"` |
| `setDlss` | `"true"` | `"false"` |
| `findObjectAndTap` enabled | `"true"` | 不使用 |
| `openLogic` value | `"1"` (关闭) | `"0"` (开启) |
| `camera_observer` off | `"1"` | `"0"` |
| `objectExist` 返回值 | `"1"` | `"error:notFound"` |
| `isAutoPath` 返回值 | 字符串 `"True"` | 字符串 `"False"` |
| `isDevelopment` 返回值 | 字符串 `"True"` | 字符串 `"False"` |
| `HotMapState` 返回值 | 字符串 `"1"` | 字符串 `"0"` 或其他 |
| `needActive` 参数 | `"1"` | `"0"` |

### 3.4 鼠标键位 (rml 参数)

| 值 | 含义 | 序列化 |
|----|------|--------|
| `-1` | 左键（默认） | 空字符串 `""` |
| `0` | 中键 | `"middle"` |
| `1` | 右键 | `"right"` |

---

## 4. By 枚举 — 查找方式

| By 值 | 整数 | set_path 生成 | 使用场景 |
|-------|------|---------------|---------|
| `By.NAME` | 1 | `"//" + value` | 按名称查找 |
| `By.TAG` | 2 | `"//*[@tag=" + value + "]"` | 按标签查找 |
| `By.LAYER` | 3 | `"//*[@layer=" + value + "]"` | 按层级查找 |
| `By.COMPONENT` | 4 | `"//*[@component=" + value + "]"` | 按组件查找 |
| `By.ID` | 5 | 直接传 value | 按 ID 查找 |
| `By.PATH` | 6 | 直接传 value | XPath 式路径 |
| `By.LEVEL` | 7 | 直接传 value | 按层级级别 |

---

## 5. 响应数据类型

| 接口类别 | 响应格式 | 示例 |
|---------|---------|------|
| 查找单个对象 | AltElement JSON | `{"name":"BtnStart","id":"123","x":"100","y":"200"}` |
| 查找多个对象 | JSON 数组 | `[{"name":"A",...},{"name":"B",...}]` |
| 布尔查询 | 字符串 `"True"` / `"False"` | `isAutoPath` |
| 存在性查询 | 字符串 `"1"` 或错误 | `objectExist` |
| GM 命令 | 字符串（通常 `"ok"`） | |
| 获取文本 | 文本字符串 | `getText` |
| 屏幕尺寸 | JSON `{"width":1920,"height":1080}` | `getScreen` |
| 内存快照 | JSON `{"result":"True","Reply_Content":"D:/path/file.snap"}` | `ProfilingMemory` |
| 性能采集 | JSON（Profile 数据） | `RecordProfile` / `checkProfile` |
| PerfEye | JSON | `GetPerfeyeInfo` |

---

## 6. 错误协议

所有错误以 `error:` 前缀标识，`handle_errors()` 方法解析后抛出对应异常：

| 错误字符串 | Python 异常类 | 说明 |
|-----------|-------------|------|
| `error:notFound` | `NotFoundException` | 对象未找到 |
| `error:propertyNotFound` | `PropertyNotFoundException` | 属性不存在 |
| `error:methodNotFound` | `MethodNotFoundException` | 方法不存在 |
| `error:componentNotFound` | `ComponentNotFoundException` | 组件不存在 |
| `error:couldNotPerformOperation` | `CouldNotPerformOperationException` | 操作无法执行 |
| `error:couldNotParseJsonString` | `CouldNotParseJsonStringException` | JSON 解析失败 |
| `error:incorrectNumberOfParameters` | `IncorrectNumberOfParametersException` | 参数数量不对 |
| `error:failedToParseMethodArguments` | `FailedToParseArgumentsException` | 参数解析失败 |
| `error:objectNotFound` | `ObjectWasNotFoundException` | 对象不存在 |
| `error:propertyCannotBeSet` | `PropertyNotFoundException` | 属性不可写 |
| `error:nullReferenceException` | `NullReferenceException` | 空引用 |
| `error:unknownError` | `UnknownErrorException` | 未知错误 |
| `error:formatException` | `FormatException` | 格式错误 |

---

## 7. 截图协议

### 7.1 屏幕尺寸获取

- 命令: `getScreen;&`
- 响应: `{"width":1920,"height":1080}`
- **此接口仅返回尺寸，不返回像素数据**

### 7.2 内存快照截图（实际截图方式）

通过 `ProfilingMemory` 命令间接获取截图：

1. SDK 发送: `ProfilingMemory;D:/path/uuid;&`
2. Unity 响应: `{"result":"True","Reply_Content":"D:/path/uuid/uuid.snap"}`
3. Unity 后台异步将 `.snap` 文件转为同目录 `.png`
4. SDK 轮询本地文件系统等待 `.png` 生成：
   ```python
   pngFilePath = os.path.splitext(res["Reply_Content"])[0] + ".png"
   while not os.path.exists(pngFilePath):
       time.sleep(1)
   ```
5. 重命名文件为 UUID 命名

**结论: 截图需要二次拉取** — 先 socket 取路径，再本地文件系统读文件

---

## 8. 超时配置

`send_data()` 方法对部分命令硬编码了延长超时：

| 命令关键字 | recvall 超时 | 说明 |
|-----------|-------------|------|
| 默认 | 5 分钟 | `settimeout=300` |
| `closeConnection` | 不等待 | 直接返回空字符串 |
| `stopDebugMode` | 不等待 | 直接返回空字符串 |
| `pauseDebugMode` | 不等待 | 直接返回空字符串 |
| `SaveWarmupSVC` | 10 分钟 | Shader 变体保存 |
| `UpdateSVC` | 10 分钟 | 变体更新 |
| `SaveCurrentShaderVariantCollection` | 10 分钟 | 变体收集 |
| `ProfilingMemory` | 10 分钟 | 内存快照 |
| `CommitWarmupVariant` | 10 分钟 | 变体提交 |
| `SetSVNLog` | 10 分钟 | SVN 日志 |
| `AppendCharacterTreeGrassToPart1AndSplitAndroidWarmupSvc` | 30 分钟 | Android 预热 |
| `AppendCharacterTreeGrassToPart1AndSplitIOSWarmupSvc` | 30 分钟 | iOS 预热 |
| `AnalyzeMissingVariant_Android` | 30 分钟 | 缺失变体分析 |
| `AnalyzeMissingVariant_PC` | 30 分钟 | 缺失变体分析 |

---

## 9. 完整接口清单

### 9.1 基础命令

| # | SDK 方法 | 命令名 | 参数 (位置) | 响应类型 |
|---|---------|--------|------------|---------|
| 1 | `get_server_version()` | `getServerVersion` | 无 | 字符串 |
| 2 | `get_project_info()` | `getProjectInfo` | 无 | JSON |
| 3 | `get_unity_version()` | `getUnityVersion` | 无 | 字符串 |
| 4 | `get_Game_version()` | `getGameVersion` | 无 | 字符串 |
| 5 | `stop()` | `closeConnection` | 无 | 空 |
| 6 | `auto_fight(mode)` | `autoFight` | mode | 字符串 |
| 7 | `custom_interface(cmd, *args)` | cmd 本身 | *args | 字符串 |
| 8 | `get_screen()` | `getScreen` | 无 | JSON {width, height} |

### 9.2 对象查找

| # | SDK 方法 | 命令名 | 参数 (位置) | 响应类型 |
|---|---------|--------|------------|---------|
| 9 | `find_object(by, value)` | `findObject` / `findObjectByLevel` | path;方式 (By.PATH→`path`, By.LEVEL→`findObjectByLevel;path`, By.ID→`id`) | AltElement |
| 10 | `find_object_and_tap(by, value, camera, enabled, rml)` | `findObjectAndTap` | path;camera_name;"true";rml | AltElement |
| 11 | `find_all_objects(value)` | `findObjectAllChildren` | value | [AltElement] |
| 12 | `find_text(keyword)` | `findText` | keyword | 文本数据 |
| 13 | `find_all_text()` | `findAllText` | 无 | [文本元素] |
| 14 | `find_child(value)` | `findChild` | value(路径) | [子名] |
| 15 | `find_child_id(value)` | `findChild` | value(路径) | [子ID] |
| 16 | `get_hierarchy()` | `getHierarchy` | 无 | 字符串 |
| 17 | `get_inspector(id)` | `getInspector` | id | 字符串 |
| 18 | `get_object_rect(value)` | `getRectTransformPoints` | value | JSON |
| 19 | `get_value_on_component(path, comp, prop)` | `getValueOnComponent` | path;componentName;valueName | 字符串 |
| 20 | `object_exist(by, value)` | `objectExist` | path;"path" | `"1"` / error |

### 9.3 输入操作

| # | SDK 方法 | 命令名 | 参数 (位置) | 响应类型 |
|---|---------|--------|------------|---------|
| 21 | `tap_at_coordinates(x, y, rml)` | `tapScreen` | x;y;rml | AltElement / None |
| 22 | `tap_by_id(id)` | `tapObject` (via AltElement) | alt_object_json;rml | AltElement |
| 23 | `drag_object(path, x1, y1, x2, y2)` | `dragObject` | path;px1;py1;[px2;py2] | 字符串 |

> 注: drag 的坐标参数先通过 `getScreen` 获取屏幕尺寸，将归一化比例 [0,1] 乘以宽高转为像素坐标

### 9.4 AltElement 对象操作

| # | SDK 方法 | 命令名 | 参数 (位置) | 响应类型 |
|---|---------|--------|------------|---------|
| 24 | `element.get_text()` | `getText` | alt_object_json | 字符串 |
| 25 | `element.set_text(text)` | `setText` | text;alt_object_json | AltElement |
| 26 | `element.tap(rml)` | `tapObject` | alt_object_json;rml | AltElement |
| 27 | `element.drag(x1, y1, x2, y2)` | `dragObject` | name;px1;py1;[px2;py2] | 字符串 |
| 28 | `element.find(value)` | `objectFind` | alt_object_json;"name";value | AltElement |
| 29 | `element.child_index(idx)` | `objectFind` | alt_object_json;"index";value | AltElement |
| 30 | `element.parent()` | `getParent` | alt_object_json | AltElement |

### 9.5 调试模式

| # | SDK 方法 | 命令名 | 参数 (位置) | 响应类型 |
|---|---------|--------|------------|---------|
| 31 | `debug_mode(path, async=False)` | `debugMode` | 0 (开启) | "Open Debug Mode" |
| 32 | `debug_mode_pause()` | `pauseDebugMode` | 无 | 无等待 |
| 33 | `debug_mode_resume()` | `resumeDebugMode` | 无 | 字符串 |
| 34 | `debug_mode_stop()` | `stopDebugMode` | 无 | 无等待 |
| 35 | `is_debug_mode_record()` | (线程状态) | 无 | bool |

> debugMode 有同步 (sync_record) 和异步 (async_record) 两种模式，异步模式下由后台线程持续接收 Unity 推送的操作事件

### 9.6 GM 命令

| # | SDK 方法 | 命令名 | arg1 (表达式) | 响应类型 |
|---|---------|--------|--------------|---------|
| 36 | `add_level(degree)` | `GMCmd` | `me:GetPlayer():AddLevel({degree})` | 字符串 |
| 37 | `add_gold_silve_coin(nums)` | `GMCmd` | 4 条命令: `me:AddRechargeGold` / `me:AddSilver` / `me:AddValueCoin(VALUE_COIN_EMERALD)` / `me:AddValueCoin(VALUE_COIN_BANGYU)` | 4 个响应 |
| 38 | `add_stack_item(id, np, nStar)` | `GMCmd` | `KItem.AddStackItem({id},{np},0,false,0)` 或面板模式 `KItem.AddStackItem({id},5,{i},{np},{nL},1,1)` | 字符串 |
| 39 | `add_green_crystal(id, degree, nums)` | `GMCmd` | `KItem.AddStackItem({id},5,1,2,{degree},{nums},1)` + `KItem.AddStackItem({id},5,1,3,{degree},{nums},1)` | 字符串 |
| 40 | `add_gongming_stone(id, nums)` | `GMCmd` | 循环5次 `KItem.AddStackItem({id},5,1,1,{i},{nums},1)` | 字符串 |
| 41 | `add_zhuhun_stone(id, nums)` | `GMCmd` | 循环9次 `KItem.AddStackItem({id},5,1,4,{i},{nums},1)` | 字符串 |
| 42 | `tpPosition(x, y, z)` | `GMCmd` | `pl:MoveToPosition({x}, {y}, {z})` | 字符串 |
| 43 | `levelOver()` | `LevelOver` | 无 arg1 | 字符串 |
| 44 | `add_family_contribution(nums)` | `GMCmd` | `me:AddValueCoin(VALUE_COIN_KIN_CONTRIBUTION, {nums}, 0)` | 字符串 |
| 45 | `goto_scene(id)` | `GMCmd` | `me:GMNewWorldAuto({id});` | 字符串 |
| 46 | `openGmPanel()` | `OpenOrCloseGm` | 通过 CustomInterface | 字符串 |
| 47 | `gm_cmd(cmd)` | `GMCmd` | 直接透传 cmd 字符串 | 字符串 |

### 9.7 自定义游戏命令

| # | SDK 方法 | 命令名 | 参数 (位置) | 响应类型 |
|---|---------|--------|------------|---------|
| 48 | `get_scene_name()` | `getSceneName` | 无 | 字符串 |
| 49 | `get_player_location()` | `getPlrPos` | 无 | 字符串 |
| 50 | `get_player_id()` | `getPlayerID` | 无 | 字符串 |
| 51 | `is_auto_path()` | `isAutoPath` | 无 | bool (比较 `== "True"`) |
| 52 | `move_to_postion(sceneId, x, y, z)` | `moveTo` | sceneId;x;y;z | 字符串 |
| 53 | `set_CameraView(yaw, pitch)` | `setCamera` | yaw;pitch | 字符串 |
| 54 | `get_CameraView()` | `getCamera` | 无 | 字符串 |
| 55 | `camera_observer(off)` | `gm` | CameraObserver | "1"/"0" |
| 56 | `pressEsc()` | `ProcessExit` | 无 | 字符串 |
| 57 | `game_Language()` | `gameLanguage` | 无 | 字符串 |
| 58 | `getTextString(value)` | `getTextString` | value | 字符串(或原值) |
| 59 | `game_finish_state()` | `gm` | GameFinishState | 字符串 |
| 60 | `game_settling()` | `gm` | GameSettling | 字符串 |
| 61 | `isDebugBuild()` | `isDevelopment` | 无 | bool (比较 `== "True"`) |
| 62 | `dlss_api(tf, value)` | `setDlss` | "true"/"false";value | 字符串 |

### 9.8 战斗/机甲命令

| # | SDK 方法 | 命令名 | 参数 (位置) | 响应类型 |
|---|---------|--------|------------|---------|
| 63 | `god_mode()` | `gm` | GodMode | 字符串 |
| 64 | `kill_mecha()` | `gm` | Kill | 字符串 |
| 65 | `mecha_add_buff(value)` | `gm` | AddBuff;100000X | 字符串 |
| 66 | `mecha_add_ai(*meg)` | `addAI` | campId;displayName;AI_Type;Hard;Skill;aiBTreePath;mechaName;bornPointType;bornPos;parts | 字符串 |
| 67 | `exit_battlefield()` | `gm` | ExitBattlefield | 字符串 |
| 68 | `no_exit_battlefield()` | `gm` | NoEnd | 字符串 |
| 69 | `player_change_to_ai(value, targetid)` | `gm` | PlayerAIStart;value;targetid 或 PlayerAIStop | 字符串 |

### 9.9 渲染/性能命令

| # | SDK 方法 | 命令名 | 参数 (位置) | 响应类型 |
|---|---------|--------|------------|---------|
| 70 | `clean_all_view_pools()` | `gm` | cleanAllViewPools | 字符串 |
| 71 | `clean_all_view_pools_after_combat(value)` | `gm` | cleanAllViewPoolsAfterCombat;value | 字符串 |
| 72 | `mono_bvir_log()` | `gm` | MonoBvirLog | 字符串 |
| 73 | `frame_target_rate(value)` | `gm` | FrameTargetRate;value | 字符串 |
| 74 | `mechaLOD(value)` | `mechaLOD` | value | 字符串 |
| 75 | `mechaTest(cmd, value, value2)` | `mechaTest` | cmd;value;value2 | 字符串 |
| 76 | `go_Active(Value)` | `goActive` | Value | 字符串 |
| 77 | `global_max_lod_level(value)` | `gm` | GlobalMaxLODLevel;value | 字符串 |
| 78 | `particle_min_count(key)` | `gm` | ParticleMinCount;key | 字符串 |
| 79 | `particle_max_count(key)` | `gm` | ParticleMaxCount;key | 字符串 |
| 80 | `GetShaderVariants(value)` | `gm` | GatherShaderVariants;value | 字符串(10min超时) |

### 9.10 摄像机命令

| # | SDK 方法 | 命令名 | 参数 (位置) | 响应类型 |
|---|---------|--------|------------|---------|
| 81 | `switch_camera_follow()` | `gm` | SwitchCameraFollow | 字符串 |
| 82 | `set_cameraControl(value)` | `setCameraControl` | "true"/"false" | 字符串 |
| 83 | `open_logic(value)` | `gm` | OpenLogic;value | 字符串 |
| 84 | `forward_world_time(value)` | `gm` | ForwardWorldTime;value | 字符串 |

### 9.11 热力图命令

| # | SDK 方法 | 命令名 | 参数 (位置) | 响应类型 |
|---|---------|--------|------------|---------|
| 85 | `run_hot_map(pra, rd)` | `gm` | RunHotMap;pra;rd | 字符串 |
| 86 | `run_hot_map_state()` | `gm` | HotMapState | bool (比较 `== "1"`) |
| 87 | `upload_hot_map(pra)` | `gm` | HotMapID;pra | ID 字符串 |

### 9.12 自定义 API (Custom_Api) — 通用透传

`custom_api(*key)` 方法统一走 `gm` 命令名，子命令作为后续位置参数：

| # | 子命令 | 实际发送 | SDK 调用 |
|---|--------|---------|---------|
| 88 | `DisablePingCheck` | `gm;DisablePingCheck;value;&` | `open_logic(value)` |
| 89 | `GodMode` | `gm;GodMode;&` | `god_mode()` |
| 90 | `Kill` | `gm;Kill;&` | `kill_mecha()` |
| 91 | `ExitBattlefield` | `gm;ExitBattlefield;&` | `exit_battlefield()` |
| 92 | `NoEnd` | `gm;NoEnd;&` | `no_exit_battlefield()` |
| 93 | `CameraObserver` | `gm;CameraObserver;&` | `camera_observer()` |
| 94 | `cleanAllViewPools` | `gm;cleanAllViewPools;&` | `clean_all_view_pools()` |
| 95 | `cleanAllViewPoolsAfterCombat` | `gm;cleanAllViewPoolsAfterCombat;value;&` | `clean_all_view_pools_after_combat(val)` |
| 96 | `MonoBvirLog` | `gm;MonoBvirLog;&` | `mono_bvir_log()` |
| 97 | `SwitchCameraFollow` | `gm;SwitchCameraFollow;&` | `switch_camera_follow()` |
| 98 | `FrameTargetRate` | `gm;FrameTargetRate;value;&` | `frame_target_rate(val)` |
| 99 | `OpenLogic` | `gm;OpenLogic;value;&` | `open_logic(val)` |
| 100 | `GlobalMaxLODLevel` | `gm;GlobalMaxLODLevel;value;&` | `global_max_lod_level(val)` |
| 101 | `PlayerAIStart` | `gm;PlayerAIStart;value;targetid;&` | `player_change_to_ai(v,id)` |
| 102 | `PlayerAIStop` | `gm;PlayerAIStop;&` | `player_change_to_ai("")` |
| 103 | `AddBuff` | `gm;AddBuff;100000X;&` | `mecha_add_buff(val)` |
| 104 | `RunHotMap` | `gm;RunHotMap;pra;rd;&` | `run_hot_map(pra,rd)` |
| 105 | `HotMapState` | `gm;HotMapState;&` | `run_hot_map_state()` |
| 106 | `HotMapID` | `gm;HotMapID;pra;&` | `upload_hot_map(pra)` |
| 107 | `GatherShaderVariants` | `gm;GatherShaderVariants;value;&` | `GetShaderVariants(val)` |
| 108 | `ParticleMinCount` | `gm;ParticleMinCount;key;&` | `particle_min_count(key)` |
| 109 | `ParticleMaxCount` | `gm;ParticleMaxCount;key;&` | `particle_max_count(key)` |

### 9.13 自定义透传 (CustomInterface)

`custom_interface(cmd, *args)` 直接以 cmd 作为 CommandName：

| # | SDK 调用 | 实际发送 | 说明 |
|---|---------|---------|------|
| 110 | `custom_interface("OpenOrCloseGm")` | `OpenOrCloseGm;&` | 打开/关闭 GM 面板 |
| 111 | `custom_interface("startReplayRecord")` | `startReplayRecord;&` | 开始录制 |
| 112 | `custom_interface("stopReplayRecord")` | `stopReplayRecord;&` | 停止录制 |
| 113 | `custom_interface("startReplay", file_name)` | `startReplay;file_name;&` | 开始回放 |
| 114 | `custom_interface("isReplaying")` | `isReplaying;&` | 查询回放状态 |
| 115 | `custom_interface("stopReplay")` | `stopReplay;&` | 停止回放 |
| 116 | `custom_interface("ReplayResult")` | `ReplayResult;&` | 获取回放结果 |
| 117 | `custom_interface("ResetCamera")` | `ResetCamera;&` | 重置摄像机 |
| 118 | `custom_interface("forceDisableReplay")` | `forceDisableReplay;&` | 关闭死亡回放 |

### 9.14 性能采集命令

| # | SDK 方法 | 命令名 | 参数 (位置) | 响应类型 |
|---|---------|--------|------------|---------|
| 119 | `record_profile(record='', collection={})` | `RecordProfile` | record+"1";collection (旧版) | 字符串 |
| 120 | `record_profile(collection={}, GC_Alloc_switch="0")` | `RecordProfile` | "1";collection;GC_Alloc_switch (新版) | JSON |
| 121 | `profile_stop()` | `RecordProfile` | record+"0" | JSON |
| 122 | `profile_check()` | `checkProfile` | [record] (ubox 模式) | JSON |
| 123 | `profile_abandon_or_upload(ab)` | `RecordProfile` | "2"(上传) / "-1"(放弃) | JSON |
| 124 | `profiling_memory(value)` | `ProfilingMemory` | value(文件路径) | JSON {result, Reply_Content} |
| 125 | `record_perfeye(file_path)` | `consolePerfEye` | "StartPerfeye";file_path | 字符串 |
| 126 | `perfeye_stop()` | `consolePerfEye` | "StopPerfeye" | 字符串 |
| 127 | `perfeye_check()` | `consolePerfEye` | "GetPerfeyeInfo" | JSON |

---

## 10. 两条透传链路的区别

本工程有**两套透传机制**，命名相似但行为不同：

### 10.1 `Custom_Api` → 命令名固定为 `gm`

```python
# SDK 签名
def custom_api(self, *key):
    return Custom_Api(socket, sep, end, appium, *key).execute()

# 内部实现
class Custom_Api:
    def execute(self):
        data = self.send_data(self.create_command("gm", *self.value))
        return data
```

- **CommandName 永远是 `gm`**
- 子命令作为 arg1, arg2... 依次排列
- 适用于游戏内 GM 指令类操作

### 10.2 `CustomInterface` → 命令名由用户传入

```python
# SDK 签名
def custom_interface(self, command, *args):
    return CustomInterface(socket, sep, end, command, *args).execute()

# 内部实现
class CustomInterface(BaseCommand):
    def execute(self):
        data = self.send_data(self.create_command(self.command, *self.args))
        return data
```

- **CommandName 就是用户传入的字符串**
- 后续参数作为 arg1, arg2...
- 适用于新增的独立命令

---

## 11. 特殊行为

### 11.1 发送后不等待响应

以下命令 `send_data()` 发送后直接返回空字符串，不调用 `recvall()`：

- `closeConnection`
- `stopDebugMode`
- `pauseDebugMode`

### 11.2 send_data_block

另有 `send_data_block()` 方法，与 `send_data()` 区别仅在于 `recvall(settimeout=None)` 即无限等待，用于不确定耗时的场景。

### 11.3 缓存清理

每次 `recvall()` 结束后会调用 `clear_recv()`，将 socket 设为非阻塞模式，尝试最多 5 次 `recvfrom(2048)` 清空残留数据，然后恢复阻塞模式。

### 11.4 卡死监控

`recvall()` 中若 `socket.timeout` 且 `Stuck_block().get_stat()` 为 True（卡死），会发送飞书通知并无限等待数据。否则直接 `close` socket 并抛出 `ConnectionError`。
