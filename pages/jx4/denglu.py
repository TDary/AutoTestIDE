"""登录案例测试脚本 —— 适配 AutoTest IDE 执行环境

在 IDE 中打开此脚本，点击 ▶ 运行 即可执行。
脚本命名空间自动注入: auto, By, snapshot, assert_exists, log
"""
import time

from pages.jx4.helpers import (
    object_exists, safe_find_and_tap, wait_for, wait_for_gone,
    find_child_text, _get_children_names,
)


# ── 通用路径常量 ─────────────────────────────────────────────────────

RES_UPDATE_INFO = "/Main/UIRoot/RootCanvas/Secondary/UIResUpdate/InfoTxt"
LOGIN_BTN = "Main/UIRoot/RootCanvas/Secondary/UILogin/ScreenAdaption/Denglu/Anniu"
ACCOUNT_INPUT = "/Main/UIRoot/RootCanvas/Secondary/UILogin/ScreenAdaption/Denglu/Zhanghao"
RESOURCE_OPT_POPUP = "/Main/UIRoot/RootCanvas/Secondary/UILogin/ScreenAdaption/Pop_Ziyuanyouhua/Content/Bot/Btn_Knows"
FAMILY_LIST_BTN = "/Main/UIRoot/RootCanvas/Secondary/UIFamilyList/ScreenAdaption/BotR/btn"
OPEN_MENU = "/Main/UIRoot/RootCanvas/Main/UIJoystick/UIMenu/ScreenAdaption/MenuBg/Btn"


# ── 选服 ─────────────────────────────────────────────────────────────

def select_server(auto, server: str):
    log(f"选服: {server}")
    safe_find_and_tap(auto, "/Main/UIRoot/RootCanvas/Secondary/UILogin/ScreenAdaption/Xuanfu", 2)
    time.sleep(1)
    try:
        auto.find_and_tap(
            f"/Main/UIRoot/RootCanvas/Secondary/UILogin/ScreenAdaption/Xuanfu/ScreenAdaption/Mid/ScrollView/Viewport/Content/{server}"
        )
        log(f"选中服务器: {server}")
    except Exception:
        log(f"未找到服务器 {server}，使用默认")
    time.sleep(1)


# ── 选择角色 ────────────────────────────────────────────────────────

def select_role(auto, parameters: dict):
    """创建角色并选择。"""
    log("进入创角界面")
    sex_list = _get_children_names(auto, "/Main/UIRoot/RootCanvas/Secondary/UICreateRoleSex/ScreenAdaption/Sex/Mid/")

    for sex_id in sex_list:
        sex_name = "男"
        safe_find_and_tap(
            auto,
            f"/Main/UIRoot/RootCanvas/Secondary/UICreateRoleSex/ScreenAdaption/Sex/Mid/{sex_id}",
            10,
        )
        if sex_id == "2":
            sex_name = "女"

        safe_find_and_tap(auto, "/Main/UIRoot/RootCanvas/Secondary/UICreateRoleSex/ScreenAdaption/Sex/BotR/Btn_Xiayibu", 5)

        wait_for(auto, "/Main/UIRoot/RootCanvas/Secondary/UICreateRoleSex/ScreenAdaption/UICreateRole/MidL/Mask/Menpai/01", timeout=15)
        time.sleep(2)

        menpai_list = _get_children_names(auto, "/Main/UIRoot/RootCanvas/Secondary/UICreateRoleSex/ScreenAdaption/UICreateRole/MidL/Mask/Menpai")

        for menpai_id in menpai_list:
            safe_find_and_tap(
                auto,
                f"/Main/UIRoot/RootCanvas/Secondary/UICreateRoleSex/ScreenAdaption/UICreateRole/MidL/Mask/Menpai/{menpai_id}",
                5,
            )
            wait_for(auto, "/Main/UIRoot/RootCanvas/Secondary/UICreateRoleSex/ScreenAdaption/UICreateRole/MidL/Mask/Menpai/01", timeout=10)
            time.sleep(2)

            menpai_name = find_child_text(
                auto,
                f"/Main/UIRoot/RootCanvas/Secondary/UICreateRoleSex/ScreenAdaption/UICreateRole/MidL/Mask/Menpai/{menpai_id}/Imagedi/Text",
            ) or menpai_id

            log(f"性别: {sex_name}, 门派: {menpai_name}")
            snapshot()

            try:
                auto.find_and_tap("/Main/UIRoot/RootCanvas/Secondary/UICreateRoleSex/ScreenAdaption/UICreateRole/BotR/Btn_EnterGame")
                log("点击进入游戏")
            except Exception:
                pass

            time.sleep(3)
            safe_find_and_tap(auto, "/Main/UIRoot/RootCanvas/Secondary/UICreateRoleSex/ScreenAdaption/UICreateRole/TopL/Anniu_Fanhui", 3)
            safe_find_and_tap(auto, "/Main/UIRoot/RootCanvas/Secondary/UICreateRoleSex/ScreenAdaption/Sex/TopL/Anniu_Fanhui", 2)
            safe_find_and_tap(auto, LOGIN_BTN, 2)
            wait_for(auto, "/Main/UIRoot/RootCanvas/Secondary/UICreateRoleSex/ScreenAdaption/Sex/Mid/1", timeout=30)
            time.sleep(1)

        if sex_id != "2":
            safe_find_and_tap(auto, "/Main/UIRoot/RootCanvas/Secondary/UICreateRoleSex/ScreenAdaption/UICreateRole/TopL/Anniu_Fanhui", 5)


# ── 重新登录验证 ──────────────────────────────────────────────────

def login_judge(auto, max_retries: int = 3) -> bool:
    """登录后验证是否成功进入，失败则重试。"""
    for i in range(max_retries):
        time.sleep(5)
        if not object_exists(auto, LOGIN_BTN):
            return True
        log(f"登录验证失败，第{i+1}次重试")
        safe_find_and_tap(auto, LOGIN_BTN, 2)
    return False


# ── 登录主流程 ──────────────────────────────────────────────────

def login_flow(auto, user: str = "", server: str = "385"):
    """登录主流程。"""
    start = time.time()
    wait_for_gone(auto, RES_UPDATE_INFO, timeout=30 * 60)
    log("资源更新完成")

    wait_for(auto, ACCOUNT_INPUT, timeout=20 * 60)
    log(f"从启动到登录界面耗时: {round(time.time() - start, 2)}s")
    snapshot()

    safe_find_and_tap(auto, RESOURCE_OPT_POPUP, 2)

    try:
        auto.find_and_tap(ACCOUNT_INPUT)
        time.sleep(0.5)
        log(f"输入账号: {user}")
    except Exception:
        log("账号输入框不可用")
    time.sleep(2)

    if server:
        select_server(auto, server)
    time.sleep(2)

    safe_find_and_tap(auto, LOGIN_BTN)
    log("点击登录")
    time.sleep(10)

    if object_exists(auto, FAMILY_LIST_BTN):
        safe_find_and_tap(auto, FAMILY_LIST_BTN, 5)
    elif object_exists(auto, LOGIN_BTN):
        if not login_judge(auto):
            log("游戏登录异常")
            raise Exception("游戏登录异常")
        safe_find_and_tap(auto, FAMILY_LIST_BTN, 5)
    else:
        log("账号无角色，进入创角")
        select_role(auto, {})

    log("登录成功")
    snapshot()

    wait_for(auto, OPEN_MENU, timeout=60)
    log("已进入游戏主界面")
    snapshot()


# ── 入口 ─────────────────────────────────────────────────────────────

login_flow(auto, user="cszh10", server="385")
