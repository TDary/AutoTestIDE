"""新手关测试脚本 —— 适配 AutoTest IDE 执行环境

在 IDE 中打开此脚本，点击 ▶ 运行 即可执行。
脚本命名空间自动注入: auto, By, snapshot, assert_exists, log
"""
import time

from pages.jx4.helpers import (
    object_exists, safe_find_and_tap, wait_for,
    find_child_text,
)


# ── 业务流程 ─────────────────────────────────────────────────────────

def guide_finger(auto):
    """处理指引手指 UI。"""
    safe_find_and_tap(auto, "/Main/UIRoot/RootCanvas/Main/UIGuide/Root/Guang", 1)

    if object_exists(auto, "/Main/UIRoot/RootCanvas/Secondary/UIGuideFingers/ScreenAdaption/BotR"):
        child_text = find_child_text(
            auto, "/Main/UIRoot/RootCanvas/Secondary/UIGuideFingers/ScreenAdaption/BotR"
        )
        if child_text:
            safe_find_and_tap(
                auto,
                f"/Main/UIRoot/RootCanvas/Secondary/UIGuideFingers/ScreenAdaption/BotR/{child_text}",
            )

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

        safe_find_and_tap(auto, "/Main/UIRoot/RootCanvas/Secondary/UIMissionResult/Lose/Anniu/Anniu_3")

        if time.perf_counter() - start > timeout_minutes * 60:
            raise Exception(f"打怪超过{timeout_minutes}分钟，直接报错")

    time.sleep(2)
    log("停止自动战斗")


def main_flow(auto):
    """新手关主流程。"""
    if object_exists(auto, "/Main/UIRoot/RootCanvas/Secondary/UIName/ScreenAdaption/Mid/Di/Mingzi_di/Button_Shaizi"):
        t0 = time.perf_counter()
        while object_exists(auto, "/Main/UIRoot/RootCanvas/Secondary/UIName/ScreenAdaption/Mid/Di/Mingzi_di/Button_Shaizi"):
            safe_find_and_tap(auto, "/Main/UIRoot/RootCanvas/Secondary/UIName/ScreenAdaption/Mid/Di/Mingzi_di/Button_Shaizi", 1)
            safe_find_and_tap(auto, "/Main/UIRoot/RootCanvas/Secondary/UIName/ScreenAdaption/Mid/Di/Button", 8)
            safe_find_and_tap(auto, "/Main/UIRoot/RootCanvas/Overlay/UIPopPanel/Box_Close", 1)
            if time.perf_counter() - t0 > 5 * 60:
                raise ValueError("掷骰子超时5分钟，主动抛出异常")

        safe_find_and_tap(auto, "/Main/UIRoot/RootCanvas/Popup/UIJingtou/ScreenAdaption/Mid/Toggle01", 1)
        safe_find_and_tap(auto, "/Main/UIRoot/RootCanvas/Popup/UIJingtou/ScreenAdaption/Bot/Btn")

    log("开始新手关主循环")
    task_start = time.time()
    TIMEOUT = 30 * 60
    prev_task = ""
    repeat_count = 0

    while True:
        if time.time() - task_start > TIMEOUT:
            raise Exception("新手关超时 30 分钟")

        safe_find_and_tap(auto, "/Main/UIRoot/RootCanvas/Main/UIGuide/Root/Guang", 1)
        guide_finger(auto)

        safe_find_and_tap(auto, "/Main/UIRoot/RootCanvas/Secondary/UIMap_Xinshou/ScreenAdaption/Mid/Close")

        if object_exists(auto, "/Main/UIRoot/RootCanvas/HUD/UIGuidePoint/ScreenAdaption/GuidePoint/01/Point"):
            log("出现自动战斗UI，退出主循环")
            break

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

        safe_find_and_tap(auto, "/Main/UIRoot/RootCanvas/Main/UIXinshouTaskGuide/ScreenAdaption/MidL/MidL_D/Content/Renwu/Viewport/Grid/template")

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

main_flow(auto)
