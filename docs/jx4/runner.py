import os
import socket
import time,requests
from u3driver.commands.GMCmd import *
from u3driver.custom import *
from u3driver.altElement import AltElement
from u3driver.commands import *
from u3driver.commands.record_profile import RecordProfile
from u3driver.commands.record_profile_new import RecordProfile as RecordProfile_new
from u3driver.stuck_control import Stuck_block

BUFFER_SIZE = 1024
class AltrunUnityDriver(object):
    
    def __init__(self, appium_driver,  platform, TCP_IP='127.0.0.1',TCP_PORT=13000, timeout=60,request_separator=';',request_end='&',device_id="",log_flag=False):
        self.TCP_PORT = TCP_PORT
        self.TCP_IP = TCP_IP
        self.request_separator=request_separator
        self.request_end=request_end
        self.log_flag=log_flag
        self.appium_driver=None
        self.connect = False
        self.pause = False
        self.debug_handler = None
        self.profiler_handler = None
        self.perfeye_handler = None
        self.Map_state=True
        self.Map_ID=None
        Stuck_block().InjectionHotKey()# 开始进行按键监控

        if (appium_driver != None):
            self.appium_driver = appium_driver

        while timeout > 0:
            try:
                self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

                # self.socket.setb
                for _ in range(5):
                    try:
                        self.socket.connect((TCP_IP, TCP_PORT))
                        self.socket.settimeout(timeout)
                        break
                    except ConnectionRefusedError:
                        print(f"连接{TCP_PORT}失败 尝试连接{TCP_PORT+1}")
                        TCP_PORT+=1
                # print("Get server Version")
                GetServerVersion(self.socket, self.request_separator, self.request_end).execute()
                self.connect = True
                break
            except Exception as e:
                print(e)
                print('AltUnityServer not running on port ' + str(self.TCP_PORT) +
                      ', retrying (timing out in ' + str(timeout) + ' secs)...')
                timeout -= timeout
                # time.sleep(timeout)

        if timeout <= 0:
            raise Exception('Could not connect to AltUnityServer on: '+ TCP_IP +':'+ str(self.TCP_PORT))

    
    def set_stuck_control(self,whether=True):
        Stuck_block().set_state(whether)

    
    def set_isedit_control(self,whether=True):
        Stuck_block().set_isEdit(whether)

    
    def NeedPause(self):
        while self.pause:
            time.sleep(1)
            print("[Info]udriver is pausing!")

    
    def Pause(self,pause):
        self.pause = pause

    
    def stop(self):
        self.pause = False
        CloseConnection(self.socket,self.request_separator,self.request_end).execute()

    
    def find_object(self,by,value,image_url = None):
        self.NeedPause()
        return FindObject(self.socket,self.request_separator,self.request_end,self.appium_driver,by,value,image_url).execute()

    
    def tap_at_coordinates(self,x,y,rml=-1):
        self.NeedPause()
        return TapAtCoordinates(self.socket,self.request_separator,self.request_end,self.appium_driver,x,y,rml).execute()

    
    def find_object_and_tap(self,by,value,camera_name='',enabled=True,rml=-1):
        self.NeedPause()
        return FindObjectAndTap(self.socket,self.request_separator,self.request_end,self.appium_driver,by,value,camera_name,enabled,rml).execute()

    
    def object_exist(self, by,value):
        self.NeedPause()
        return ObjectExist(self.socket,self.request_separator,self.request_end,self.appium_driver,by,value).execute()

    
    def get_screen(self):
        self.NeedPause()
        return GetScreen(self.socket,self.request_separator,self.request_end,self.appium_driver).execute()

    
    def find_child(self,value):
        self.NeedPause()
        return FindChild(self.socket,self.request_separator,self.request_end,self.appium_driver,value).execute()

    
    def find_child_id(self,value):
        self.NeedPause()
        return FindChildId(self.socket,self.request_separator,self.request_end,self.appium_driver,value).execute()

    
    def get_object_rect(self,value):
        self.NeedPause()
        return GetObjectRect(self.socket,self.request_separator,self.request_end,self.appium_driver,value).execute()

    
    def find_all_objects(self,value):
        self.NeedPause()
        return FindAllObjects(self.socket,self.request_separator,self.request_end,self.appium_driver,value).execute()


    #调用格式如下：组件名必须是完整的，而且要带上模块名称
    #udriver.get_value_on_component("//Canvas","Test,Assembly-CSharp","test1")
    #udriver.get_value_on_component("//Canvas","UnityEngine.UI.Text,UnityEngine.UI","text")
    
    def get_value_on_component(self,path,component_name,value_name):
        self.NeedPause()
        return GetValueOnComponent(self.socket,self.request_separator,self.request_end,self.appium_driver,path,component_name,value_name).execute()

    
    def debug_mode(self,file_path = None, is_async=False):
        if self.debug_handler:
            # try:
            #     self.debug_handler.stop()
            # except:
            #     pass
            self.debug_handler = None
        
        self.debug_handler = DebugMode(self.socket,self.request_separator,self.request_end,file_path)
        if is_async:
            return self.debug_handler.async_record()
        else:
            return self.debug_handler.sync_record()
        # return DebugMode(self.socket,self.request_separator,self.request_end,file_path).execute()

    
    def debug_mode_pause(self):
        if self.debug_handler:
            return self.debug_handler.pause()

    
    def debug_mode_resume(self):
        if self.debug_handler:
            return self.debug_handler.resume()

    
    def debug_mode_stop(self):
        ret=True
        if self.debug_handler:
            ret = self.debug_handler.stop()
        self.debug_handler = None
        return ret

    
    def is_debug_mode_record(self):
        if self.debug_handler:
            return self.debug_handler.is_record()

    
    def drag_object(self,path,x1,y1,x2 = None,y2 = None):
        self.NeedPause()
        return Drag(self.socket,self.request_separator,self.request_end,path,x1,y1,x2,y2).execute()

    
    def tap_by_id(self,id):
        # json.dumps({"id",id})
        self.NeedPause()
        return AltElement(CommandReturningAltElements(self.socket,self.request_separator,self.request_end,self.appium_driver),self.appium_driver,'{"name":"","id":"'+ id +'"}').tap()

    
    def find_text(self, keyword):
        return FindText(self.socket,self.request_separator,self.request_end,self.appium_driver,keyword).execute()

    
    def find_all_text(self):
        self.NeedPause()
        return FindAllText(self.socket,self.request_separator,self.request_end,self.appium_driver).execute()

    
    def get_hierarchy(self):
        self.NeedPause()
        return GetHierarchy(self.socket,self.request_separator,self.request_end,self.appium_driver).execute()

    
    def get_inspector(self, id):
        self.NeedPause()
        return GetInspector(self.socket,self.request_separator,self.request_end,self.appium_driver, id).execute()

    
    def get_server_version(self):
        return GetServerVersion(self.socket, self.request_separator, self.request_end).execute()
    
    '''
    record = 0 停止打点
    record = 1 开始打点
    '''
    #profile
    
    def record_profile(self,record='',collection={},GC_Alloc_switch = "0"):
        if self.profiler_handler == None:
            if record=='':
                self.profiler_handler = RecordProfile_new(self.socket,self.request_separator,self.request_end,collection,GC_Alloc_switch)
            else:
                self.profiler_handler = RecordProfile(self.socket,self.request_separator,self.request_end,record,collection)
            return self.profiler_handler.start()
        else:
            raise Exception("profiler is recording")

    
    def profile_stop(self):
        if self.profiler_handler != None:
            return self.profiler_handler.stop()

    
    def profile_check(self):
        if self.profiler_handler != None:
            return self.profiler_handler.check()

    
    def del_profile(self):
        if self.profiler_handler != None:
            self.profiler_handler=None
        if self.perfeye_handler != None:
            self.perfeye_handler=None

    #是否上传
    
    def profile_abandon_or_upload(self,ab_or_up):
        intab_or_up="2" if ab_or_up else "-1"
        return self.profiler_handler.abandon_or_upload(intab_or_up)

        #深度采集接口

    
    def profiling_memory(self,value=""):
        return ProfilingMemory(self.socket,self.request_separator,self.request_end,value).execute()

    #perfeye
    
    def record_perfeye(self,file_path):
        if self.perfeye_handler == None:
            self.perfeye_handler = RecordPerfeye(self.socket,self.request_separator,self.request_end,file_path)
            return self.perfeye_handler.start()
        else:
            raise Exception("Perfeye is recording")

    
    def perfeye_stop(self):
        if self.perfeye_handler != None:
            return self.perfeye_handler.stop()

    
    def perfeye_check(self):
        if self.perfeye_handler != None:
            return self.perfeye_handler.check()

    
    def del_perfeye(self):
        if self.perfeye_handler != None:
            self.perfeye_handler=None

    
    def get_unity_version(self):
        return GetUnityVersion(self.socket, self.request_separator, self.request_end).execute()

    
    def get_Game_version(self):
        return GetGameVersion(self.socket, self.request_separator, self.request_end).execute()
    
    '''
    adb shell dumpsys window | findstr mCurrentFocus
    获取当前正在活动的app
    '''

    
    def get_current_app_pagename(self):
        res = os.popen(f"adb -s {self.appium_driver} shell dumpsys window | findstr mCurrentFocus").read()
        return "com" + res.split("com")[1].split("/")[0]

    
    def interrupt(self):
        raise "Interrupt"

    
    def custom_interface(self, command, *args):
        return CustomInterface(self.socket, self.request_separator, self.request_end, command, *args).execute()

    def get_project_info(self):
        return GetProjectInfo(self.socket, self.request_separator, self.request_end).execute()
    #项目自定接口

    def get_scene_name(self):
        """获取场景名"""
        return GetSceneName(self.socket, self.request_separator, self.request_end).execute()

    def get_player_location(self):
        """获得玩家位置"""
        return GetPlayerLocation(self.socket, self.request_separator, self.request_end).execute()

    def move_to_postion(self,sceneId,x,y,z):
        """移动到指定位置"""
        return MoveToPostion(self.socket,self.request_separator,self.request_end,self.appium_driver,sceneId,x,y,z).execute()

    def is_auto_path(self):
        """判断是否正在寻路"""
        return IsAutoPath(self.socket,self.request_separator,self.request_end).execute()

    def set_CameraView(self,yaw,pitch):
        """设置摄像机位置"""
        return Set_CameraView(self.socket, self.request_separator, self.request_end,self.appium_driver,yaw,pitch).execute()

    def get_CameraView(self):
        return GetCameraView(self.socket, self.request_separator, self.request_end,self.appium_driver).execute()

    def goto_scene(self, id):
        return GotoScene(self.socket,self.request_separator,self.request_end, id).execute()

    def get_player_id(self):
        """获取玩家id"""
        return GetPlayerID(self.socket, self.request_separator, self.request_end).execute()


    
    def game_finish_state(self):
        """游戏状态"""
        return GameFinishState(self.socket, self.request_separator, self.request_end).execute()

    
    def player_change_to_ai(self,value="",targetid=0):
        """设置AI"""
        return Player_Change_To_AI(self.socket, self.request_separator, self.request_end,self.appium_driver,value,targetid).execute()

    
    def switch_camera_follow(self):
        """角色跟随镜头"""
        return Switch_Camera_Follow(self.socket, self.request_separator, self.request_end,self.appium_driver).execute()

    
    def camera_observer(self,off=True):
        """角色观察镜头"""
        tf="1" if off else "0"
        data= Camera_Observer(self.socket, self.request_separator, self.request_end,self.appium_driver).execute()
        if data!=tf:
            data= Camera_Observer(self.socket, self.request_separator, self.request_end,self.appium_driver).execute()
        return data

    
    def reset_camera(self):
        """对局结束后关闭 角色观察镜头"""
        return Custom_Api("ResetCamera")

    
    def kill_mecha(self):
        """秒杀"""
        return Kill_Mecha(self.socket, self.request_separator, self.request_end,self.appium_driver).execute()

    
    def mecha_add_buff(self,value):
        data=["十倍伤害","清除cd","无限能量","不死","五倍移速","隐身","嘲讽","全套"]
        value="100000"+str(data.index(value)+1)
        return Mecha_Add_Buff(self.socket, self.request_separator, self.request_end,self.appium_driver,value).execute()

    
    def clean_all_view_pools(self):
        """清空表现对象缓存池"""
        return cleanAllViewPools(self.socket, self.request_separator, self.request_end,self.appium_driver).execute()

    
    def clean_all_view_pools_after_combat(self,value):
        """战斗结束后清空表现对象缓存池"""
        return cleanAllViewPoolsAfterCombat(self.socket, self.request_separator, self.request_end,self.appium_driver,value).execute()

    
    def mono_bvir_log(self):
        """开启内存日志"""
        return MonoBvirLog(self.socket, self.request_separator, self.request_end,self.appium_driver).execute()

    
    def frame_target_rate(self,value="0"):
        """关闭限帧"""
        return FrameTargetRate(self.socket, self.request_separator, self.request_end,self.appium_driver,value).execute()

    
    def exit_battlefield(self):
        """结束战斗"""
        return Exit_Battlefield(self.socket, self.request_separator, self.request_end,self.appium_driver).execute()

    
    def no_exit_battlefield(self):
        """对局不结束"""
        return No_Exit_Battlefield(self.socket, self.request_separator, self.request_end,self.appium_driver).execute()

    
    def god_mode(self):
        """上帝模式"""
        return God_Mode(self.socket, self.request_separator, self.request_end,self.appium_driver).execute()

    
    def run_hot_map(self,pra="",rd=0):
        """执行热力图"""
        return Run_Hot_Map(self.socket, self.request_separator, self.request_end,self.appium_driver,pra,rd).execute()

    
    def upload_hot_map(self,pra=""):
        """上传热力图数据"""
        if not self.Map_state:
            self.Map_ID=Upload_Hot_Map(self.socket, self.request_separator, self.request_end,self.appium_driver,pra).execute()
        else:
            print("未开始采集/结束异常 不需要进行上传数据")
        return ""

    
    def Map_Report_ID(self,perfeyeid=None):
        """绑定perfeye数据到热力图ID"""
        if perfeyeid:
            ret=requests.post("http://10.11.66.69/api/file/report/perfeye-url/update",json={"reportId": self.Map_ID,"perfeyeUid": perfeyeid})
            return ret.text

    
    def run_hot_map_state(self):
        """执行热力图是否进行中"""
        self.Map_state=Run_Hot_Map_State(self.socket, self.request_separator, self.request_end,self.appium_driver).execute()
        return self.Map_state

    
    def open_logic(self,value="1"):
        """关闭逻辑
            1: 关闭
            0: 开启
        """
        self.custom_api("DisablePingCheck",value)
        return OpenLogic(self.socket, self.request_separator, self.request_end,self.appium_driver,value).execute()

    
    def custom_api(self,*key):
        """自定义接口"""
        return Custom_Api(self.socket, self.request_separator, self.request_end,self.appium_driver,*key).execute()

    
    def mecha_add_ai(self,*meg):
        """添加机器人
        阵营
        玩家名字
        类型0通用对战 1 技能测试 2 自定义AI
        强度
        技能
        行为树
        机甲名称
        0 面前 1 世界坐标 2 相对坐标
        0,0,0#坐标 , 分隔
        武装ID
        """
        return Mecha_Add_AI(self.socket, self.request_separator, self.request_end,self.appium_driver,meg).execute()

    
    def dlss_api(self,tf,value):
        """Dlss接口"""
        tf = "true"if tf else "false"
        return Dlss_Api(self.socket, self.request_separator, self.request_end,self.appium_driver,tf,value).execute()

    
    def particle_min_count(self,key):
        """粒子数量最少接口"""
        return Particle_Min_Count(self.socket, self.request_separator, self.request_end,self.appium_driver,key).execute()

    
    def particle_max_count(self,key):
        """粒子数量最多接口"""
        return Particle_Max_Count(self.socket, self.request_separator, self.request_end,self.appium_driver,key).execute()

    
    def global_max_lod_level(self,key):
        """最大lod"""
        return Global_Max_LOD_Level(self.socket, self.request_separator, self.request_end,self.appium_driver,key).execute()

    
    def go_Active(self,Value):
        """屏蔽UI"""
        return GO_Active(self.socket, self.request_separator, self.request_end,self.appium_driver,Value).execute()

    
    def mechaLOD(self,value):
        """设备LOD距离"""
        return Mecha_LOD(self.socket, self.request_separator, self.request_end,self.appium_driver,value).execute()

    
    def mechaTest(self,cmd,value,value2):
        """ 机甲测试"""
        if cmd in ["InitCamera","Arround","Top","SetDistince"]:
            return mechaTest(self.socket, self.request_separator, self.request_end,self.appium_driver,cmd,value,value2).execute()
        else:
            raise Exception("GM输入有误")

    
    def set_cameraControl(self,value):
        """设置镜头"""
        value= "true" if value else "false"
        return Set_CameraControl(self.socket, self.request_separator, self.request_end,self.appium_driver,value).execute()

    
    def forward_world_time(self,value):#开启逻辑
        """长途列车护卫模式场景使用"""
        return ForwardWorldTime(self.socket, self.request_separator, self.request_end,self.appium_driver,value).execute()

    
    def forceDisableReplay(self):
        """关闭死亡回放"""
        return Custom_Api(self.socket, self.request_separator, self.request_end,self.appium_driver,"forceDisableReplay").execute()

    
    def isDebugBuild(self):
        """判断是否为debug包体"""
        return IsDebugBuild(self.socket, self.request_separator, self.request_end,self.appium_driver).execute()

    
    def GetShaderVariants(self,value):
        """收集shader变体使用的是: GatherShaderVariants"""
        return Get_Shader_Variants(self.socket, self.request_separator, self.request_end,self.appium_driver,value).execute()

    
    def game_Language(self):
        """多语言适配"""
        return GameLanguage(self.socket, self.request_separator, self.request_end,self.appium_driver).execute()

    
    def getTextString(self,value):
        """自动识别语言"""
        return GetTextString(self.socket, self.request_separator, self.request_end,self.appium_driver,value).execute()

    

    def game_settling(self):
        """检测是否处于结算界面"""
        return GameSettling(self.socket, self.request_separator, self.request_end).execute()


    """
    新增加接口
    """

    def add_level(self,degree):
        """"升级"""
        return AddLevel(self.socket, self.request_separator, self.request_end,degree).execute()

    #开启自动战斗
    def auto_fight(self, mode: str = "1"):
        return AutoFight(self.socket,self.request_separator,self.request_end,mode).execute()

    def add_gold_silve_coin(self,nums):
        """"增加元宝银票翠玉"""
        return AddGoldSilverCoin(self.socket, self.request_separator, self.request_end,nums).execute()

    def add_stack_item(self,id,np,nStar):
        """"增加装备，有两种，一种是GM面板，一种是输入框"""
        return AddStackItem(self.socket, self.request_separator, self.request_end,id,np,nStar).execute()
    def add_green_crystal(self,id,degree,nums):
        """"添玄晶和魂石 degree 默认为1 """
        return AddGreenCrystal(self.socket, self.request_separator, self.request_end,id,degree,nums).execute()

    def add_gongming_stone(self,id,nums):
        """"添加共鸣石一套"""
        return AddGongmingStone(self.socket, self.request_separator, self.request_end,id,nums).execute()

    def add_zhuhun_stone(self,id,nums):
        """"添加铸魂石一套"""
        return AddZhuhunStone(self.socket, self.request_separator, self.request_end,id,nums).execute()

    def pressEsc(self):
        return PressEsc(self.socket, self.request_separator, self.request_end).execute()

    def levelOver(self):
        return LevelOver(self.socket, self.request_separator, self.request_end).execute()

    def tpPosition(self,x,y,z):
        return TpPosition(self.socket, self.request_separator, self.request_end,x,y,z).execute()

    def add_family_contribution(self,nums):
        """家族贡献"""
        return FamilyContribution(self.socket, self.request_separator, self.request_end,nums).execute()

    def openGmPanel(self):
        return self.custom_interface('OpenOrCloseGm')

    def gm_cmd(self,cmd):
        return self.custom_interface('GMCmd',cmd)

    # 支持录制回放
    def startReplayRecord(self):
        return self.custom_interface('startReplayRecord')
    def stopReplayRecord(self):
        return self.custom_interface('stopReplayRecord')
    def startReplay(self,file_name):
        return self.custom_interface('startReplay',file_name)
    def isReplaying(self):
        return self.custom_interface('isReplaying')
    def stopReplay(self):
        return self.custom_interface('stopReplay')
    def replayResult(self):
        return self.custom_interface('ReplayResult')




