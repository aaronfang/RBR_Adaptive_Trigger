"""
AC DualSense Adapter - Assetto Corsa Series 自适应扳机与 DualSense 手柄适配
支持: Assetto Corsa / Assetto Corsa Competizione / Assetto Corsa Rally
Version 1.0.0
"""
import socket
import json
from enum import Enum
from ctypes import *
import time
import os
import sys
import configparser
import psutil
import mmap
import math
import tkinter as tk
from tkinter import ttk
from tkinter import font as tkfont
import threading
from collections import deque
import numpy as np
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

__version__ = '1.0.0'

# Try to import Windows-specific modules
try:
    import win32gui
    import win32con
    import win32process
    WINDOWS_API_AVAILABLE = True
except ImportError:
    print("Warning: PyWin32 library is not installed. Some features may be limited.")
    print("Install with: pip install pywin32")
    WINDOWS_API_AVAILABLE = False

###################################################################################
# AC Shared Memory Data Structures
###################################################################################

class ACPhysics(Structure):
    """AC/ACC/ACR Physics Shared Memory Structure"""
    _fields_ = [
        ("packetId", c_int),                    # 0
        ("gas", c_float),                       # 4: 油门 (0-1)
        ("brake", c_float),                     # 8: 刹车 (0-1)
        ("fuel", c_float),                      # 12: 燃油
        ("gear", c_int),                        # 16: 档位
        ("rpms", c_int),                        # 20: 转速
        ("steerAngle", c_float),                # 24: 方向盘角度
        ("speedKmh", c_float),                  # 28: 速度 km/h
        ("velocity", c_float * 3),              # 32: 速度向量 x,y,z
        ("accG", c_float * 3),                  # 44: G力 x,y,z
        ("wheelSlip", c_float * 4),             # 56: 四轮打滑 FL,FR,RL,RR
        ("wheelLoad", c_float * 4),             # 72: 轮胎负载
        ("wheelsPressure", c_float * 4),        # 88: 轮胎压力
        ("wheelAngularSpeed", c_float * 4),     # 104: 轮速
        ("tyreWear", c_float * 4),              # 120: 轮胎磨损
        ("tyreDirtyLevel", c_float * 4),        # 136: 轮胎脏污
        ("tyreCoreTemperature", c_float * 4),   # 152: 轮胎核心温度
        ("camberRAD", c_float * 4),             # 168: 外倾角
        ("suspensionTravel", c_float * 4),      # 184: 悬挂行程
        ("drs", c_float),                       # 200: DRS
        ("tc", c_float),                        # 204: 牵引力控制
        ("heading", c_float),                   # 208: 朝向
        ("pitch", c_float),                     # 212: 俯仰
        ("roll", c_float),                      # 216: 翻滚
        ("cgHeight", c_float),                  # 220: 重心高度
        ("carDamage", c_float * 5),             # 224: 车辆损伤
        ("numberOfTyresOut", c_int),            # 244: 出赛道轮胎数
        ("pitLimiterOn", c_int),                # 248: 维修区限速
        ("abs", c_float),                       # 252: ABS
    ]

class ACGraphics(Structure):
    """AC/ACC/ACR Graphics Shared Memory Structure"""
    _fields_ = [
        ("packetId", c_int),
        ("status", c_int),                      # 0=离线, 1=重放, 2=驾驶, 3=暂停
        ("session", c_int),
        ("currentTime", c_wchar * 15),
        ("lastTime", c_wchar * 15),
        ("bestTime", c_wchar * 15),
        ("split", c_wchar * 15),
        ("completedLaps", c_int),
        ("position", c_int),
        ("iCurrentTime", c_int),
        ("iLastTime", c_int),
        ("iBestTime", c_int),
        ("sessionTimeLeft", c_float),
        ("distanceTraveled", c_float),
        ("isInPit", c_int),
        ("currentSectorIndex", c_int),
        ("lastSectorTime", c_int),
        ("numberOfLaps", c_int),
        ("tyreCompound", c_wchar * 33),
        ("replayTimeMultiplier", c_float),
        ("normalizedCarPosition", c_float),
        ("carCoordinates", c_float * 3),
    ]

class ACStaticInfo(Structure):
    """AC/ACC/ACR Static Info Shared Memory Structure"""
    _fields_ = [
        ("_smVersion", c_wchar * 15),
        ("_acVersion", c_wchar * 15),
        ("numberOfSessions", c_int),
        ("numCars", c_int),
        ("carModel", c_wchar * 33),
        ("track", c_wchar * 33),
        ("playerName", c_wchar * 33),
        ("playerSurname", c_wchar * 33),
        ("playerNick", c_wchar * 33),
        ("sectorCount", c_int),
        ("maxTorque", c_float),
        ("maxPower", c_float),
        ("maxRpm", c_int),
        ("maxFuel", c_float),
        ("suspensionMaxTravel", c_float * 4),
        ("tyreRadius", c_float * 4),
    ]

###################################################################################
# Shared Memory Reader
###################################################################################

class ACSharedMemoryReader:
    """AC系列游戏共享内存读取器"""
    
    def __init__(self):
        self.physics_shm = None
        self.graphics_shm = None
        self.static_shm = None
        self.last_physics_data = None
        self.last_error_time = 0
        
    def connect(self):
        """连接到AC共享内存"""
        try:
            # 尝试打开Physics共享内存
            self.physics_shm = mmap.mmap(
                -1, 
                sizeof(ACPhysics), 
                tagname="Local\\acpmf_physics"
            )
            return True
        except Exception as e:
            current_time = time.time()
            if current_time - self.last_error_time > 5:  # 每5秒打印一次错误
                print(f"Failed to connect to AC shared memory: {e}")
                self.last_error_time = current_time
            return False
    
    def read_physics(self):
        """读取Physics数据"""
        if not self.physics_shm:
            if not self.connect():
                return None
        
        try:
            self.physics_shm.seek(0)
            data_bytes = self.physics_shm.read(sizeof(ACPhysics))
            physics = ACPhysics.from_buffer_copy(data_bytes)
            
            # 验证数据有效性
            if physics.packetId <= 0:
                return None
                
            self.last_physics_data = physics
            return physics
            
        except Exception as e:
            current_time = time.time()
            if current_time - self.last_error_time > 5:
                print(f"Error reading physics data: {e}")
                self.last_error_time = current_time
            self.physics_shm = None
            return None
    
    def read_graphics(self):
        """读取Graphics数据"""
        try:
            if not self.graphics_shm:
                self.graphics_shm = mmap.mmap(
                    -1, 
                    sizeof(ACGraphics), 
                    tagname="Local\\acpmf_graphics"
                )
            
            self.graphics_shm.seek(0)
            data_bytes = self.graphics_shm.read(sizeof(ACGraphics))
            graphics = ACGraphics.from_buffer_copy(data_bytes)
            return graphics
            
        except:
            self.graphics_shm = None
            return None
    
    def read_static(self):
        """读取Static Info数据"""
        try:
            if not self.static_shm:
                self.static_shm = mmap.mmap(
                    -1, 
                    sizeof(ACStaticInfo), 
                    tagname="Local\\acpmf_static"
                )
            
            self.static_shm.seek(0)
            data_bytes = self.static_shm.read(sizeof(ACStaticInfo))
            static = ACStaticInfo.from_buffer_copy(data_bytes)
            return static
            
        except:
            self.static_shm = None
            return None
    
    def close(self):
        """关闭共享内存"""
        try:
            if self.physics_shm:
                self.physics_shm.close()
            if self.graphics_shm:
                self.graphics_shm.close()
            if self.static_shm:
                self.static_shm.close()
        except:
            pass

###################################################################################
# DualSense Controller Communication
###################################################################################

class InstructionType(Enum):
    """DSX指令类型"""
    Invalid = 0
    TriggerUpdate = 1
    RGBUpdate = 2
    PlayerLED = 3
    TriggerThreshold = 4
    MicLED = 5
    PlayerLEDNewRevision = 6
    ResetToUserSettings = 7
    HapticFeedback = 20

class Trigger(Enum):
    """扳机类型"""
    Invalid = 0
    Left = 1       # L2 - 刹车
    Right = 2      # R2 - 油门

class TriggerMode(Enum):
    """扳机模式"""
    Normal = 0
    GameCube = 1
    VerySoft = 2
    Soft = 3
    Hard = 4
    VeryHard = 5
    Hardest = 6
    Rigid = 7
    VibrateTrigger = 8
    Choppy = 9
    Medium = 10
    VibrateTriggerPulse = 11      # 脉冲振动 - 用于打滑反馈
    CustomTriggerValue = 12
    Resistance = 13
    Bow = 14
    Galloping = 15
    SemiAutomaticGun = 16
    AutomaticGun = 17
    Machine = 18

class Instruction:
    """DSX指令"""
    def __init__(self, instruction_type, parameters):
        # instruction_type 可以是整数或Enum,统一处理
        self.type = instruction_type if isinstance(instruction_type, int) else instruction_type.value
        self.parameters = parameters

class Packet:
    """DSX数据包"""
    def __init__(self, instructions):
        self.instructions = instructions

###################################################################################
# Utility Functions
###################################################################################

def get_process_by_name(name):
    """通过进程名查找进程"""
    for proc in psutil.process_iter(['pid', 'name']):
        if proc.info['name'].lower() == name.lower():
            return proc.info['pid']
    return None

def is_game_running():
    """检查AC系列游戏是否在运行"""
    game_processes = [
        "ac.exe",                    # Assetto Corsa
        "acs.exe",                   # Assetto Corsa (另一个可执行文件名)
        "AC2-Win64-Shipping.exe",    # Assetto Corsa Competizione
        "acr.exe",                   # Assetto Corsa Rally
    ]
    
    for proc_name in game_processes:
        if get_process_by_name(proc_name):
            return True
    return False

def get_game_name():
    """获取当前运行的游戏名称"""
    if get_process_by_name("acr.exe"):
        return "Assetto Corsa Rally"
    elif get_process_by_name("AC2-Win64-Shipping.exe"):
        return "Assetto Corsa Competizione"
    elif get_process_by_name("ac.exe") or get_process_by_name("acs.exe"):
        return "Assetto Corsa"
    return "Unknown"

###################################################################################
# Configuration
###################################################################################

# 默认配置
DEFAULT_CONFIG = {
    'Network': {
        'dsx_ip': '127.0.0.1',
        'dsx_port': '6969',
    },
    'Features': {
        'adaptive_trigger': 'True',
        'led_effect': 'True',
        'haptic_effect': 'False',
    },
    'Feedback': {
        'trigger_strength': '5.00',       # 扳机强度系数 (0.1-5.0)
        'wheel_slip_threshold': '0.500',  # 打滑阈值
        'trigger_threshold': '0.20',      # 扳机触发阈值
        'vibration_mode': 'continuous',   # pulse=脉冲(11) / continuous=连续(8) 连续模式通常更强烈
        'max_strength_override': '255',   # 0=使用DSX标准(1-8) / 255=实验性尝试硬件最大值
    },
    'GUI': {
        'fps': '60.0',
        'pause_updates': 'False',
    },
    'LED': {
        'rpm_green': '70',
        'rpm_yellow': '85',
        'rpm_red': '95',
    }
}

# 加载配置
config_file = 'config_ac.ini'
config = configparser.ConfigParser()

if os.path.exists(config_file):
    config.read(config_file)
else:
    # 创建默认配置文件
    for section, options in DEFAULT_CONFIG.items():
        config[section] = options
    with open(config_file, 'w') as f:
        config.write(f)
    print(f"Created default configuration file: {config_file}")

# 读取配置
DSX_IP = config.get('Network', 'dsx_ip', fallback='127.0.0.1')
DSX_PORT = config.getint('Network', 'dsx_port', fallback=6969)

adaptive_trigger_enabled = config.getboolean('Features', 'adaptive_trigger', fallback=True)
led_effect_enabled = config.getboolean('Features', 'led_effect', fallback=True)
haptic_effect_enabled = config.getboolean('Features', 'haptic_effect', fallback=False)

trigger_strength = config.getfloat('Feedback', 'trigger_strength', fallback=5.00)
wheel_slip_threshold = config.getfloat('Feedback', 'wheel_slip_threshold', fallback=0.500)
trigger_threshold = config.getfloat('Feedback', 'trigger_threshold', fallback=0.20)
vibration_mode = config.get('Feedback', 'vibration_mode', fallback='continuous')  # pulse / continuous
max_strength_override = int(config.get('Feedback', 'max_strength_override', fallback='255'))

# 确保参数在合理范围内
trigger_strength = max(0.1, min(5.0, trigger_strength))
wheel_slip_threshold = max(0.05, min(1.0, wheel_slip_threshold))
trigger_threshold = max(0.1, min(0.5, trigger_threshold))

# LED颜色阈值
RPM_GREEN_THRESHOLD = config.getfloat('LED', 'rpm_green', fallback=70.0)
RPM_YELLOW_THRESHOLD = config.getfloat('LED', 'rpm_yellow', fallback=85.0)
RPM_RED_THRESHOLD = config.getfloat('LED', 'rpm_red', fallback=95.0)

###################################################################################
# GUI Dashboard
###################################################################################

class ACTelemetryDashboard:
    """AC遥测仪表盘"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("AC DualSense Adapter - Assetto Corsa Series")
        self.root.geometry("800x600")
        
        # 设置窗口图标
        try:
            if getattr(sys, 'frozen', False):
                icon_path = os.path.join(sys._MEIPASS, "icon.ico")
            else:
                icon_path = "icon.ico"
            
            if os.path.exists(icon_path):
                self.root.iconbitmap(icon_path)
        except Exception as e:
            print(f"Failed to set window icon: {e}")
        
        # 字体设置
        self.title_font = tkfont.Font(family="Arial", size=12, weight="bold")
        self.value_font = tkfont.Font(family="Arial", size=11)
        
        # 参数变量
        self.trigger_strength = tk.DoubleVar(value=trigger_strength)
        self.wheel_slip_threshold = tk.DoubleVar(value=wheel_slip_threshold)
        self.trigger_threshold = tk.DoubleVar(value=trigger_threshold)
        self.vibration_mode = tk.StringVar(value=vibration_mode)
        self.max_strength_override = tk.IntVar(value=max_strength_override)
        
        # 功能开关
        self.adaptive_trigger_enabled = tk.BooleanVar(value=adaptive_trigger_enabled)
        self.led_effect_enabled = tk.BooleanVar(value=led_effect_enabled)
        self.haptic_effect_enabled = tk.BooleanVar(value=haptic_effect_enabled)
        
        # FPS控制
        fps_value = min(config.getfloat('GUI', 'fps', fallback=60.0), 60.0)
        self.fps_value = tk.DoubleVar(value=fps_value)
        self.update_interval = 1.0 / self.fps_value.get()
        
        # 暂停更新标志
        self.pause_updates = config.getboolean('GUI', 'pause_updates', fallback=False)
        
        # 主题颜色
        self.theme_colors = {
            'bg': '#F0F0F0',
            'fg': 'black',
            'canvas_bg': '#FFFFFF',
            'grid_color': '#CCCCCC'
        }
        
        # 配置窗口
        self.root.configure(bg=self.theme_colors['bg'])
        self.root.resizable(True, True)
        
        # 数据队列
        self.time_data = deque(maxlen=1000)
        self.wheel_slip_data = {
            'FL': deque(maxlen=1000),
            'FR': deque(maxlen=1000),
            'RL': deque(maxlen=1000),
            'RR': deque(maxlen=1000),
        }
        
        # 初始化数据
        for _ in range(100):
            self.time_data.append(0)
            for key in self.wheel_slip_data:
                self.wheel_slip_data[key].append(0)
        
        # 当前轮胎打滑值
        self.current_wheel_slip = {'FL': 0, 'FR': 0, 'RL': 0, 'RR': 0}
        
        # 创建UI
        self.create_ui()
        
        # 线程控制
        self.update_thread_running = False
        self.exit_event = threading.Event()
        self.last_update_time = time.time()
    
    def create_ui(self):
        """创建用户界面"""
        # 主容器
        main_frame = ttk.Frame(self.root, padding=10)
        main_frame.grid(row=0, column=0, sticky="nsew")
        
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(0, weight=1)
        main_frame.grid_columnconfigure(0, weight=1)
        main_frame.grid_rowconfigure(3, weight=1)
        
        # 1. 游戏状态区域
        self.create_game_status_section(main_frame)
        
        # 2. 车辆信息区域
        self.create_car_info_section(main_frame)
        
        # 3. 轮胎打滑可视化
        self.create_wheel_slip_section(main_frame)
        
        # 4. 控制面板
        self.create_control_panel(main_frame)
        
        # 状态栏
        self.status_bar = ttk.Label(self.root, text="Ready", relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.grid(row=1, column=0, sticky="ew")
    
    def create_game_status_section(self, parent):
        """创建游戏状态区域"""
        frame = ttk.LabelFrame(parent, text="Game Status", padding=10)
        frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        frame.grid_columnconfigure(1, weight=1)
        
        # 游戏名称
        ttk.Label(frame, text="Game:", font=self.title_font).grid(row=0, column=0, sticky="w", padx=5)
        self.game_name_label = ttk.Label(frame, text="Waiting...", font=self.value_font)
        self.game_name_label.grid(row=0, column=1, sticky="w", padx=5)
        
        # 连接状态
        ttk.Label(frame, text="Status:", font=self.title_font).grid(row=0, column=2, sticky="w", padx=5)
        self.connection_status_label = ttk.Label(frame, text="Disconnected", font=self.value_font, foreground="red")
        self.connection_status_label.grid(row=0, column=3, sticky="w", padx=5)
    
    def create_car_info_section(self, parent):
        """创建车辆信息区域"""
        frame = ttk.LabelFrame(parent, text="Vehicle Telemetry", padding=10)
        frame.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        
        # 创建信息网格
        info_frame = ttk.Frame(frame)
        info_frame.pack(fill=tk.BOTH, expand=True)
        
        # 速度
        ttk.Label(info_frame, text="Speed:", font=self.title_font).grid(row=0, column=0, sticky="w", padx=5)
        self.speed_label = ttk.Label(info_frame, text="0 km/h", font=self.value_font)
        self.speed_label.grid(row=0, column=1, sticky="w", padx=5)
        
        # 转速
        ttk.Label(info_frame, text="RPM:", font=self.title_font).grid(row=0, column=2, sticky="w", padx=5)
        self.rpm_label = ttk.Label(info_frame, text="0", font=self.value_font)
        self.rpm_label.grid(row=0, column=3, sticky="w", padx=5)
        
        # 档位
        ttk.Label(info_frame, text="Gear:", font=self.title_font).grid(row=0, column=4, sticky="w", padx=5)
        self.gear_label = ttk.Label(info_frame, text="N", font=self.value_font)
        self.gear_label.grid(row=0, column=5, sticky="w", padx=5)
        
        # 油门
        ttk.Label(info_frame, text="Throttle:", font=self.title_font).grid(row=1, column=0, sticky="w", padx=5)
        self.throttle_label = ttk.Label(info_frame, text="0%", font=self.value_font)
        self.throttle_label.grid(row=1, column=1, sticky="w", padx=5)
        
        # 刹车
        ttk.Label(info_frame, text="Brake:", font=self.title_font).grid(row=1, column=2, sticky="w", padx=5)
        self.brake_label = ttk.Label(info_frame, text="0%", font=self.value_font)
        self.brake_label.grid(row=1, column=3, sticky="w", padx=5)
        
        # 方向盘
        ttk.Label(info_frame, text="Steering:", font=self.title_font).grid(row=1, column=4, sticky="w", padx=5)
        self.steering_label = ttk.Label(info_frame, text="0°", font=self.value_font)
        self.steering_label.grid(row=1, column=5, sticky="w", padx=5)
    
    def create_wheel_slip_section(self, parent):
        """创建轮胎打滑可视化区域"""
        frame = ttk.LabelFrame(parent, text="Wheel Slip (Adaptive Trigger Data)", padding=10)
        frame.grid(row=2, column=0, sticky="nsew", pady=(0, 10))
        parent.grid_rowconfigure(2, weight=1)
        
        # 创建轮胎显示网格
        wheels_frame = ttk.Frame(frame)
        wheels_frame.pack(fill=tk.BOTH, expand=True)
        
        # 前轮
        front_frame = ttk.Frame(wheels_frame)
        front_frame.pack(fill=tk.X, pady=5)
        
        # 前左
        fl_frame = ttk.Frame(front_frame)
        fl_frame.pack(side=tk.LEFT, expand=True, fill=tk.BOTH, padx=5)
        ttk.Label(fl_frame, text="Front Left", font=self.title_font).pack()
        self.fl_slip_label = ttk.Label(fl_frame, text="0.000", font=("Arial", 16))
        self.fl_slip_label.pack()
        self.fl_temp_label = ttk.Label(fl_frame, text="Temp: 0°C")
        self.fl_temp_label.pack()
        
        # 前右
        fr_frame = ttk.Frame(front_frame)
        fr_frame.pack(side=tk.LEFT, expand=True, fill=tk.BOTH, padx=5)
        ttk.Label(fr_frame, text="Front Right", font=self.title_font).pack()
        self.fr_slip_label = ttk.Label(fr_frame, text="0.000", font=("Arial", 16))
        self.fr_slip_label.pack()
        self.fr_temp_label = ttk.Label(fr_frame, text="Temp: 0°C")
        self.fr_temp_label.pack()
        
        # 后轮
        rear_frame = ttk.Frame(wheels_frame)
        rear_frame.pack(fill=tk.X, pady=5)
        
        # 后左
        rl_frame = ttk.Frame(rear_frame)
        rl_frame.pack(side=tk.LEFT, expand=True, fill=tk.BOTH, padx=5)
        ttk.Label(rl_frame, text="Rear Left", font=self.title_font).pack()
        self.rl_slip_label = ttk.Label(rl_frame, text="0.000", font=("Arial", 16))
        self.rl_slip_label.pack()
        self.rl_temp_label = ttk.Label(rl_frame, text="Temp: 0°C")
        self.rl_temp_label.pack()
        
        # 后右
        rr_frame = ttk.Frame(rear_frame)
        rr_frame.pack(side=tk.LEFT, expand=True, fill=tk.BOTH, padx=5)
        ttk.Label(rr_frame, text="Rear Right", font=self.title_font).pack()
        self.rr_slip_label = ttk.Label(rr_frame, text="0.000", font=("Arial", 16))
        self.rr_slip_label.pack()
        self.rr_temp_label = ttk.Label(rr_frame, text="Temp: 0°C")
        self.rr_temp_label.pack()
        
        # 扳机反馈状态
        trigger_status_frame = ttk.Frame(frame)
        trigger_status_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(trigger_status_frame, text="Trigger Feedback:", font=self.title_font).pack(side=tk.LEFT, padx=5)
        self.trigger_status_label = ttk.Label(trigger_status_frame, text="Normal", font=self.value_font)
        self.trigger_status_label.pack(side=tk.LEFT, padx=5)
    
    def create_control_panel(self, parent):
        """创建控制面板"""
        frame = ttk.LabelFrame(parent, text="Settings", padding=10)
        frame.grid(row=3, column=0, sticky="ew", pady=(0, 10))
        
        # 功能开关
        features_frame = ttk.Frame(frame)
        features_frame.pack(fill=tk.X, pady=5)
        
        ttk.Checkbutton(
            features_frame, 
            text="Adaptive Triggers", 
            variable=self.adaptive_trigger_enabled,
            command=self.save_config
        ).pack(side=tk.LEFT, padx=10)
        
        ttk.Checkbutton(
            features_frame, 
            text="LED Effect", 
            variable=self.led_effect_enabled,
            command=self.save_config
        ).pack(side=tk.LEFT, padx=10)
        
        # 参数调节
        params_frame = ttk.Frame(frame)
        params_frame.pack(fill=tk.X, pady=5)
        
        # 扳机强度 (扩展至5.0以获得更强震动)
        ttk.Label(params_frame, text="Trigger Strength:").grid(row=0, column=0, sticky="w", padx=5)
        trigger_scale = ttk.Scale(
            params_frame,
            from_=0.1,
            to=5.0,
            variable=self.trigger_strength,
            orient=tk.HORIZONTAL,
            command=self.on_parameter_change
        )
        trigger_scale.grid(row=0, column=1, sticky="ew", padx=5)
        self.trigger_value_label = ttk.Label(params_frame, text=f"{self.trigger_strength.get():.1f}")
        self.trigger_value_label.grid(row=0, column=2, padx=5)
        
        # 震动模式: 连续模式通常比脉冲更强烈
        ttk.Label(params_frame, text="Vibration Mode:").grid(row=2, column=0, sticky="w", padx=5)
        vib_mode_combo = ttk.Combobox(params_frame, textvariable=self.vibration_mode, 
                                      values=["pulse", "continuous"], state="readonly", width=12)
        vib_mode_combo.grid(row=2, column=1, sticky="w", padx=5)
        vib_mode_combo.bind("<<ComboboxSelected>>", self.on_parameter_change)
        
        # 实验性: 最大强度覆盖 (尝试发送255以获得硬件最大震动)
        self.max_strength_var = tk.BooleanVar(value=(max_strength_override == 255))
        ttk.Checkbutton(
            params_frame,
            text="Experimental: Max Strength (255)",
            variable=self.max_strength_var,
            command=self.on_parameter_change
        ).grid(row=3, column=0, columnspan=2, sticky="w", padx=5)
        
        # 打滑阈值
        ttk.Label(params_frame, text="Slip Threshold:").grid(row=1, column=0, sticky="w", padx=5)
        slip_scale = ttk.Scale(
            params_frame,
            from_=0.05,
            to=1.0,
            variable=self.wheel_slip_threshold,
            orient=tk.HORIZONTAL,
            command=self.on_parameter_change
        )
        slip_scale.grid(row=1, column=1, sticky="ew", padx=5)
        self.slip_value_label = ttk.Label(params_frame, text=f"{self.wheel_slip_threshold.get():.2f}")
        self.slip_value_label.grid(row=1, column=2, padx=5)
        
        params_frame.grid_columnconfigure(1, weight=1)
    
    def on_parameter_change(self, event=None):
        """参数变化回调"""
        self.trigger_value_label.config(text=f"{self.trigger_strength.get():.1f}")
        self.slip_value_label.config(text=f"{self.wheel_slip_threshold.get():.2f}")
        self.save_config()
    
    def save_config(self):
        """保存配置"""
        global adaptive_trigger_enabled, led_effect_enabled, haptic_effect_enabled
        global trigger_strength, wheel_slip_threshold, trigger_threshold
        global vibration_mode, max_strength_override
        
        # 更新全局变量
        adaptive_trigger_enabled = self.adaptive_trigger_enabled.get()
        led_effect_enabled = self.led_effect_enabled.get()
        haptic_effect_enabled = self.haptic_effect_enabled.get()
        trigger_strength = self.trigger_strength.get()
        wheel_slip_threshold = self.wheel_slip_threshold.get()
        trigger_threshold = self.trigger_threshold.get()
        vibration_mode = self.vibration_mode.get()
        max_strength_override = 255 if self.max_strength_var.get() else 0
        
        # 保存到配置文件
        config['Features']['adaptive_trigger'] = str(adaptive_trigger_enabled)
        config['Features']['led_effect'] = str(led_effect_enabled)
        config['Features']['haptic_effect'] = str(haptic_effect_enabled)
        config['Feedback']['trigger_strength'] = f"{trigger_strength:.2f}"
        config['Feedback']['wheel_slip_threshold'] = f"{wheel_slip_threshold:.3f}"
        config['Feedback']['trigger_threshold'] = f"{trigger_threshold:.3f}"
        config['Feedback']['vibration_mode'] = vibration_mode
        config['Feedback']['max_strength_override'] = str(max_strength_override)
        
        with open(config_file, 'w') as f:
            config.write(f)
    
    def update_values(self, physics_data):
        """更新显示值"""
        if not physics_data:
            return
        
        try:
            # 更新游戏状态
            game_name = get_game_name()
            self.game_name_label.config(text=game_name)
            self.connection_status_label.config(text="Connected", foreground="green")
            
            # 更新车辆信息
            self.speed_label.config(text=f"{physics_data.speedKmh:.1f} km/h")
            self.rpm_label.config(text=f"{physics_data.rpms}")
            
            gear_text = "R" if physics_data.gear == 0 else ("N" if physics_data.gear == 1 else str(physics_data.gear - 1))
            self.gear_label.config(text=gear_text)
            
            self.throttle_label.config(text=f"{physics_data.gas * 100:.0f}%")
            self.brake_label.config(text=f"{physics_data.brake * 100:.0f}%")
            self.steering_label.config(text=f"{physics_data.steerAngle:.1f}°")
            
            # 更新轮胎打滑
            wheel_slip = physics_data.wheelSlip
            self.current_wheel_slip['FL'] = wheel_slip[0]
            self.current_wheel_slip['FR'] = wheel_slip[1]
            self.current_wheel_slip['RL'] = wheel_slip[2]
            self.current_wheel_slip['RR'] = wheel_slip[3]
            
            # 更新打滑显示
            self.update_wheel_slip_display(physics_data)
            
            # 更新扳机状态
            self.update_trigger_status(physics_data)
            
            self.last_update_time = time.time()
            
        except Exception as e:
            print(f"Error updating values: {e}")
    
    def update_wheel_slip_display(self, physics_data):
        """更新轮胎打滑显示"""
        wheel_slip = physics_data.wheelSlip
        temps = physics_data.tyreCoreTemperature
        
        # 前左
        self.fl_slip_label.config(text=f"{wheel_slip[0]:.3f}")
        self.fl_temp_label.config(text=f"Temp: {temps[0]:.1f}°C")
        self.fl_slip_label.config(foreground=self.get_slip_color(wheel_slip[0]))
        
        # 前右
        self.fr_slip_label.config(text=f"{wheel_slip[1]:.3f}")
        self.fr_temp_label.config(text=f"Temp: {temps[1]:.1f}°C")
        self.fr_slip_label.config(foreground=self.get_slip_color(wheel_slip[1]))
        
        # 后左
        self.rl_slip_label.config(text=f"{wheel_slip[2]:.3f}")
        self.rl_temp_label.config(text=f"Temp: {temps[2]:.1f}°C")
        self.rl_slip_label.config(foreground=self.get_slip_color(wheel_slip[2]))
        
        # 后右
        self.rr_slip_label.config(text=f"{wheel_slip[3]:.3f}")
        self.rr_temp_label.config(text=f"Temp: {temps[3]:.1f}°C")
        self.rr_slip_label.config(foreground=self.get_slip_color(wheel_slip[3]))
    
    def get_slip_color(self, slip_value):
        """根据打滑值返回颜色"""
        abs_slip = abs(slip_value)
        if abs_slip < wheel_slip_threshold:
            return "green"
        elif abs_slip < trigger_threshold:
            return "orange"
        else:
            return "red"
    
    def update_trigger_status(self, physics_data):
        """更新扳机反馈状态"""
        if not adaptive_trigger_enabled:
            self.trigger_status_label.config(text="Disabled", foreground="gray")
            return
        
        wheel_slip = physics_data.wheelSlip
        gas = physics_data.gas
        brake = physics_data.brake
        
        # 计算前后轮打滑 (max兼容前驱/后驱/四驱)
        front_slip = (abs(wheel_slip[0]) + abs(wheel_slip[1])) / 2
        rear_slip = (abs(wheel_slip[2]) + abs(wheel_slip[3])) / 2
        max_slip = max(front_slip, rear_slip)
        
        status_text = "Normal"
        status_color = "green"
        
        # 油门过大导致滑移(右扳机)
        if gas > 0.3 and max_slip > wheel_slip_threshold:
            status_text = f"Throttle Slip! (R2: {min(max_slip * 10, 1.0):.2f})"
            status_color = "red"
        
        # 刹车抱死导致滑移(左扳机)
        elif brake > 0.3 and max_slip > wheel_slip_threshold:
            status_text = f"Brake Lock! (L2: {min(max_slip * 10, 1.0):.2f})"
            status_color = "red"
        
        self.trigger_status_label.config(text=status_text, foreground=status_color)

###################################################################################
# Main Loop - Telemetry and Controller Feedback
###################################################################################

def send_to_dsx(packet):
    """发送数据包到DSX"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        message = json.dumps(packet, default=lambda o: o.__dict__)
        sock.sendto(message.encode(), (DSX_IP, DSX_PORT))
        sock.close()
        return True
    except Exception as e:
        # 只在第一次失败时打印错误,避免刷屏
        if not hasattr(send_to_dsx, '_error_printed'):
            print(f"[WARNING] Failed to send to DSX ({DSX_IP}:{DSX_PORT}): {e}")
            print("Please check:")
            print("  1. DSX is running")
            print("  2. DualSense controller is connected")
            print("  3. DSX UDP server is enabled")
            send_to_dsx._error_printed = True
        return False

def interpolate_color(color1, color2, factor):
    """颜色插值"""
    return [
        int(color1[0] + (color2[0] - color1[0]) * factor),
        int(color1[1] + (color2[1] - color1[1]) * factor),
        int(color1[2] + (color2[2] - color1[2]) * factor)
    ]

def main_telemetry_loop(app, root):
    """主遥测循环"""
    print("Starting AC telemetry thread...")
    
    ac_reader = ACSharedMemoryReader()
    last_static_info_time = 0
    static_info = None
    max_rpm = 7000  # 默认最大转速
    
    while app.update_thread_running and root.winfo_exists() and not app.exit_event.is_set():
        try:
            # 检查游戏是否运行
            if not is_game_running():
                time.sleep(1)
                continue
            
            # 读取Physics数据
            physics = ac_reader.read_physics()
            
            if not physics or physics.packetId <= 0:
                time.sleep(0.1)
                continue
            
            # 更新GUI
            if not app.pause_updates and root.winfo_exists():
                root.after(0, lambda p=physics: app.update_values(p))
            
            # 读取静态信息(每5秒一次)
            current_time = time.time()
            if current_time - last_static_info_time > 5:
                static_info = ac_reader.read_static()
                if static_info and static_info.maxRpm > 0:
                    max_rpm = static_info.maxRpm
                last_static_info_time = current_time
            
            ###################################################################################
            # 扳机反馈逻辑
            ###################################################################################
            
            packet = Packet([])
            
            # 自适应扳机
            if adaptive_trigger_enabled:
                left_mode = TriggerMode.Normal
                right_mode = TriggerMode.Normal
                left_strength = 1 * trigger_strength
                right_strength = 1 * trigger_strength
                
                # 选择震动模式: continuous=连续震动(通常更强烈) / pulse=脉冲震动
                vib_mode = TriggerMode.VibrateTrigger if vibration_mode == 'continuous' else TriggerMode.VibrateTriggerPulse
                max_strength = 255 if max_strength_override == 255 else 8
                
                # 只在车辆运动时应用效果
                if physics.speedKmh > 5:
                    wheel_slip = physics.wheelSlip
                    
                    # 计算前后轮打滑
                    front_slip = (abs(wheel_slip[0]) + abs(wheel_slip[1])) / 2
                    rear_slip = (abs(wheel_slip[2]) + abs(wheel_slip[3])) / 2
                    # 折中方案: 取前后轮较大值, 兼容前驱/后驱/四驱
                    # 前驱:油门过大会前轮打滑 | 后驱:后轮打滑 | 四驱:任一轴打滑
                    max_slip = max(front_slip, rear_slip)
                    
                    # 强度公式: 2 + slip*30 (打滑较小时强度偏低)
                    # 左扳机(L2): 刹车抱死导致滑移 - 任意轮抱死
                    if physics.brake > 0.3 and max_slip > wheel_slip_threshold:
                        left_mode = vib_mode
                        left_strength = min(max_strength, 2 + max_slip * 30) * trigger_strength
                    
                    # 右扳机(R2): 油门过大导致滑移 - 任意驱动轮打滑
                    if physics.gas > 0.3 and max_slip > wheel_slip_threshold:
                        right_mode = vib_mode
                        right_strength = min(max_strength, 2 + max_slip * 30) * trigger_strength
                
                # 转换为整数, 实验模式下可发送最高255
                left_strength_int = max(1, min(max_strength, int(round(left_strength))))
                right_strength_int = max(1, min(max_strength, int(round(right_strength))))
                
                packet.instructions.append(
                    Instruction(InstructionType.TriggerUpdate.value, 
                               [0, Trigger.Left.value, left_mode.value, left_strength_int, 0, 0])
                )
                packet.instructions.append(
                    Instruction(InstructionType.TriggerUpdate.value, 
                               [0, Trigger.Right.value, right_mode.value, right_strength_int, 0, 0])
                )
            
            # LED效果
            if led_effect_enabled and physics.rpms > 0:
                rpm_percentage = min(100, (physics.rpms / max_rpm) * 100)
                
                if rpm_percentage < RPM_GREEN_THRESHOLD:
                    r, g, b = 0, 255, 0
                elif rpm_percentage < RPM_YELLOW_THRESHOLD:
                    factor = (rpm_percentage - RPM_GREEN_THRESHOLD) / (RPM_YELLOW_THRESHOLD - RPM_GREEN_THRESHOLD)
                    r, g, b = interpolate_color([0, 255, 0], [255, 255, 0], factor)
                elif rpm_percentage < RPM_RED_THRESHOLD:
                    factor = (rpm_percentage - RPM_YELLOW_THRESHOLD) / (RPM_RED_THRESHOLD - RPM_YELLOW_THRESHOLD)
                    r, g, b = interpolate_color([255, 255, 0], [255, 0, 0], factor)
                else:
                    r, g, b = 255, 0, 0
                
                packet.instructions.append(Instruction(InstructionType.RGBUpdate.value, [0, r, g, b]))
            
            # 发送到DSX
            if packet.instructions:
                send_to_dsx(packet)
            
            # 控制更新频率
            time.sleep(app.update_interval)
            
        except Exception as e:
            print(f"Error in telemetry loop: {e}")
            time.sleep(0.5)
    
    # 清理
    ac_reader.close()
    print("Telemetry thread exited")

###################################################################################
# Main Entry Point
###################################################################################

def main():
    """主函数"""
    print("="*70)
    print("AC DualSense Adapter - Assetto Corsa Series")
    print(f"Version {__version__}")
    print("="*70)
    print("Supported Games:")
    print("  - Assetto Corsa")
    print("  - Assetto Corsa Competizione")
    print("  - Assetto Corsa Rally")
    print("="*70)
    print(f"DSX Server: {DSX_IP}:{DSX_PORT}")
    print(f"Config File: {config_file}")
    print("="*70)
    
    # 检查游戏是否运行
    if is_game_running():
        print(f"Detected: {get_game_name()}")
    else:
        print("Warning: No AC game detected. Please start the game first.")
    
    print("="*70)
    
    # 创建GUI
    root = tk.Tk()
    app = ACTelemetryDashboard(root)
    
    # 启动遥测线程
    app.update_thread_running = True
    app.update_thread = threading.Thread(
        target=main_telemetry_loop, 
        args=(app, root),
        daemon=True
    )
    app.update_thread.start()
    
    # 窗口关闭事件
    def on_closing():
        print("Shutting down...")
        app.exit_event.set()
        app.update_thread_running = False
        time.sleep(0.2)
        try:
            root.destroy()
        except:
            pass
        print("Shutdown complete")
    
    root.protocol("WM_DELETE_WINDOW", on_closing)
    
    # 启动主循环
    root.mainloop()

if __name__ == "__main__":
    main()
