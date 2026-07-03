"""新手关测试脚本 —— 适配 AutoTest IDE 执行环境

在 IDE 中打开此脚本，点击 ▶ 运行 即可执行。
脚本命名空间自动注入: auto, By, snapshot, assert_exists, log
"""
import time

# ── IDE 注入的命名空间 ──────────────────────────────────────────────
# auto  — PocoClient (RecordingPocoClient 包装)
# By    — 查找策略 (By.PATH, By.TAG, By.ID, ...)
# snapshot()  — 截图步骤
# assert_exists(locator, msg)  — 断言步骤
# log(msg)    — 日志步骤


# ── 辅助函数 ─────────────────────────────────────────────────────────

def object_exists(auto, path: str, by: str = By.PATH) -> bool:
    """检查节点是否存在（不产生点击副作用）。"""
    try:
        # dump_hierarchy 后在树中查找，只读不点
        root = auto.dump_hierarchy()
        flat = _flatten_tree(root)
        return _find_node_by_path(flat, path) is not None
    except Exception:
        return False


def safe_find_and_tap(auto, path: str, by: str = By.PATH, timeout: float = 0):
    """找到并点击，找不到则跳过。timeout 为额外等待秒数。"""
    if timeout > 0:
        time.sleep(timeout)
    try:
        auto.find_and_tap(path, by=by)
        log(f"点击: {path}")
    except Exception:
        pass


def wait_for_path(auto, path: str, timeout: float = 30, interval: float = 1) -> bool:
    """轮询等待节点出现，超时返回 False。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if object_exists(auto, path):
            return True
        time.sleep(interval)
    return False


def _flatten_tree(root: dict) -> list:
    """扁平化 UI 树，返回所有节点列表。"""
    result = []
    stack = [root]
    while stack:
        node = stack.pop()
        result.append(node)
        stack.extend(reversed(node.get("children", [])))
    return result


def _find_node_by_path(nodes: list, path: str) -> dict | None:
    """在扁平节点列表中按路径找到节点。"""
    parts = [p for p in path.split("/") if p]
    # 从后往前匹配：节点名 = 路径最后一段，父链对上
    for node in nodes:
        if node.get("name", "") == parts[-1]:
            return node
    return None


def find_child_text(auto, parent_path: str) -> str | None:
    """从父节点的子节点中读取文本（基于 dump_hierarchy 遍历）。"""
    try:
        root = auto.dump_hierarchy()
        flat = _flatten_tree(root)
        parent = _find_node_by_path(flat, parent_path)
        if parent and parent.get("children"):
            child = parent["children"][0]
            return child.get("payload", {}).get("text", "")
    except Exception:
        pass
    return None


# ── 业务流程 ─────────────────────────────────────────────────────────

def guide_finger(auto):
    """处理指引手指 UI。"""
    # 特殊指引
    safe_find_and_tap(auto, "/Main/UIRoot/RootCanvas/Main/UIGuide/Root/Guang", 1)

    # 右键按键手指指引
    if object_exists(auto, "/Main/UIRoot/RootCanvas/Secondary/UIGuideFingers/ScreenAdaption/BotR"):
        child_text = find_child_text(
            auto, "/Main/UIRoot/RootCanvas/Secondary/UIGuideFingers/ScreenAdaption/BotR"
        )
        if child_text:
            safe_find_and_tap(
                auto,
                f"/Main/UIRoot/RootCanvas/Secondary/UIGuideFingers/ScreenAdaption/BotR/{child_text}",
            )

    # 左边按键手指指引
    if object_exists(auto, "/Main/UIRoot/RootCanvas/Secondary/UIGuideFingers/ScreenAdaption/BotL"):
        child_text = find_child_text(
            auto, "/Main/UIRoot/RootCanvas/Secondary/UIGuideFingers/ScreenAdaption/BotL"
        )
        if child_text:
            safe_find_and_tap(
                auto,
                f"/Main/UIRoot/RootCanvas/Secondary/UIGuideFingers/ScreenAdaption/BotL/{child_text}",
            )


def simulator_auto_fight(auto, timeout_minutes: int = 5):
    """模拟自动战斗流程。"""
    log("开启自动战斗")
    safe_find_and_tap(auto, "/Main/UIRoot/RootCanvas/HUD/UIGuidePoint/ScreenAdaption/GuidePoint/01/Point", 2)

    start = time.perf_counter()
    while not object_exists(auto, "/Main/UIRoot/RootCanvas/HUD/UIGuidePoint/ScreenAdaption/GuidePoint/01/Point"):
        guide_finger(auto)
        time.sleep(1)

        # 复活
        safe_find_and_tap(auto, "/Main/UIRoot/RootCanvas/Secondary/UIMissionResult/Lose/Anniu/Anniu_3")

        if time.perf_counter() - start > timeout_minutes * 60:
            raise Exception(f"打怪超过{timeout_minutes}分钟，直接报错")

    time.sleep(2)
    log("停止自动战斗")


def main_flow(auto):
    """新手关主流程。"""
    # 命名 / 掷骰子 UI
    if object_exists(auto, "/Main/UIRoot/RootCanvas/Secondary/UIName/ScreenAdaption/Mid/Di/Mingzi_di/Button_Shaizi"):
        t0 = time.perf_counter()
        while object_exists(auto, "/Main/UIRoot/RootCanvas/Secondary/UIName/ScreenAdaption/Mid/Di/Mingzi_di/Button_Shaizi"):
            safe_find_and_tap(auto, "/Main/UIRoot/RootCanvas/Secondary/UIName/ScreenAdaption/Mid/Di/Mingzi_di/Button_Shaizi", 1)
            safe_find_and_tap(auto, "/Main/UIRoot/RootCanvas/Secondary/UIName/ScreenAdaption/Mid/Di/Button", 8)
            safe_find_and_tap(auto, "/Main/UIRoot/RootCanvas/Overlay/UIPopPanel/Box_Close", 1)
            if time.perf_counter() - t0 > 5 * 60:
                raise ValueError("掷骰子超时5分钟，主动抛出异常")

        # 镜头选择
        safe_find_and_tap(auto, "/Main/UIRoot/RootCanvas/Popup/UIJingtou/ScreenAdaption/Mid/Toggle01", 1)
        safe_find_and_tap(auto, "/Main/UIRoot/RootCanvas/Popup/UIJingtou/ScreenAdaption/Bot/Btn")

    # 主循环
    log("开始新手关主循环")
    task_start = time.time()
    TIMEOUT = 30 * 60  # 30 分钟总超时
    prev_task = ""
    repeat_count = 0

    while True:
        if time.time() - task_start > TIMEOUT:
            raise Exception("新手关超时 30 分钟")

        # 手指指引
        safe_find_and_tap(auto, "/Main/UIRoot/RootCanvas/Main/UIGuide/Root/Guang", 1)
        guide_finger(auto)

        # 地图动画关闭
        safe_find_and_tap(auto, "/Main/UIRoot/RootCanvas/Secondary/UIMap_Xinshou/ScreenAdaption/Mid/Close")

        # 出现自动战斗 UI → 退出主循环
        if object_exists(auto, "/Main/UIRoot/RootCanvas/HUD/UIGuidePoint/ScreenAdaption/GuidePoint/01/Point"):
            log("出现自动战斗UI，退出主循环")
            break

        # 读取新手任务名
        task_path_1 = "/Main/UIRoot/RootCanvas/Main/UITaskGuide/ScreenAdaption/MidL/MidL_D/Content/Renwu/Viewport/Grid/Item0/2"
        task_path_2 = "/Main/UIRoot/RootCanvas/Main/UIXinshouTaskGuide/ScreenAdaption/MidL/MidL_D/Content/Renwu/Viewport/Grid/template/2"
        task_name = ""

        if object_exists(auto, task_path_1):
            try:
                task_name = find_child_text(auto, task_path_1) or ""
            except Exception:
                pass
        elif object_exists(auto, task_path_2):
            try:
                task_name = find_child_text(auto, task_path_2) or ""
            except Exception:
                pass

        if "逃离玉衡山" in task_name or "速速返回宗门" in task_name:
            log(f"任务完成: {task_name}")
            break

        if "尝试使用飞檐" in task_name:
            log("尝试使用飞檐")
            guide_finger(auto)
            safe_find_and_tap(auto, "/Main/UIRoot/RootCanvas/Main/UIBaseSkillPad/ScreenAdaption/Battle/SkillButtons/FeiYan", 10)

        elif "击败天人众" in task_name or "击败蝎子" in task_name or "击败魔人" in task_name:
            log(f"进入战斗: {task_name}")
            simulator_auto_fight(auto)

        # 点击当前新手任务
        safe_find_and_tap(auto, "/Main/UIRoot/RootCanvas/Main/UIXinshouTaskGuide/ScreenAdaption/MidL/MidL_D/Content/Renwu/Viewport/Grid/template")

        # 重复任务检测
        if task_name == prev_task:
            repeat_count += 1
            if repeat_count > 10:
                raise Exception(f"任务名: {task_name} 重复10次，疑似卡流程")
        else:
            prev_task = task_name
            repeat_count = 0

        time.sleep(5)

    log("新手关流程结束")
    snapshot()


# ── 入口 ─────────────────────────────────────────────────────────────

# IDE 注入 auto / By / log / snapshot / assert_exists
main_flow(auto)
