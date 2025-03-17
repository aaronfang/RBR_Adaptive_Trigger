import socket
import json
from enum import Enum
from ctypes import *
import time
import os
import sys
import configparser
import psutil  # Add this import for process handling
import math
import tkinter as tk
from tkinter import ttk
from tkinter import font as tkfont
import threading
from collections import deque
import numpy as np
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

# 尝试导入 Windows 特定的模块，如果不可用则提供替代方案
try:
    import win32gui
    import win32con
    import win32api
    WINDOWS_API_AVAILABLE = True
except ImportError:
    print("警告: PyWin32 库未安装，游戏内覆盖层功能将不可用。")
    print("请使用 'pip install pywin32' 安装所需库。")
    WINDOWS_API_AVAILABLE = False

# Define memory reading functions
def get_process_by_name(name):
    for proc in psutil.process_iter(['pid', 'name']):
        if proc.info['name'].lower() == name.lower():
            return proc.info['pid']
    return None

class MemoryReader:
    def __init__(self, process_name="RichardBurnsRally_SSE.exe"):
        self.process_handle = None
        self.process_name = process_name
        self.base_address = None
        self.is_connected = False
        self.show_errors = True  # Add a flag to control error message display
        self._last_error_time = 0  # Track when the last error was shown
        self._error_cooldown = 5  # Cooldown in seconds between error messages
        
        # Initialize the memory reader
        self.connect()
    
    def connect(self):
        try:
            # Get the process ID
            pid = get_process_by_name(self.process_name)
            if not pid:
                if self.show_errors:
                    print(f"Process {self.process_name} not found")
                self.is_connected = False
                return False
            
            # Open the process with necessary access rights
            self.process_handle = windll.kernel32.OpenProcess(
                0x1F0FFF,  # PROCESS_ALL_ACCESS
                False,
                pid
            )
            
            if not self.process_handle:
                if self.show_errors:
                    print(f"Failed to open process {self.process_name}")
                self.is_connected = False
                return False
            
            # Get the base address of the process
            self.base_address = self._get_module_base_address(pid, self.process_name)
            if not self.base_address:
                if self.show_errors:
                    print(f"Failed to get base address for {self.process_name}")
                self.is_connected = False
                return False
            
            self.is_connected = True
            print(f"Connected to {self.process_name} (PID: {pid})")
            return True
        except Exception as e:
            if self.show_errors:
                print(f"Error connecting to process: {e}")
            self.is_connected = False
            return False
    
    def _get_module_base_address(self, pid, module_name):
        try:
            # This is a simplified approach - for a more robust solution, 
            # you might need to use more advanced Windows API calls
            import ctypes
            from ctypes import wintypes
            
            # Define necessary structures and constants
            class MODULEINFO(ctypes.Structure):
                _fields_ = [
                    ("lpBaseOfDll", ctypes.c_void_p),
                    ("SizeOfImage", wintypes.DWORD),
                    ("EntryPoint", ctypes.c_void_p)
                ]
            
            # Get a handle to the process
            h_process = windll.kernel32.OpenProcess(
                0x0400 | 0x0010,  # PROCESS_QUERY_INFORMATION | PROCESS_VM_READ
                False,
                pid
            )
            
            if not h_process:
                return None
            
            # Get a list of all modules in the process
            try:
                from ctypes.wintypes import HANDLE, DWORD, LPWSTR, BOOL
                from ctypes import byref, sizeof, create_string_buffer, Structure
                
                class MODULEENTRY32(Structure):
                    _fields_ = [
                        ("dwSize", DWORD),
                        ("th32ModuleID", DWORD),
                        ("th32ProcessID", DWORD),
                        ("GlblcntUsage", DWORD),
                        ("ProccntUsage", DWORD),
                        ("modBaseAddr", ctypes.POINTER(ctypes.c_byte)),
                        ("modBaseSize", DWORD),
                        ("hModule", HANDLE),
                        ("szModule", ctypes.c_char * 256),
                        ("szExePath", ctypes.c_char * 260)
                    ]
                
                # Take a snapshot of all modules in the process
                h_snapshot = windll.kernel32.CreateToolhelp32Snapshot(0x00000008, pid)  # TH32CS_SNAPMODULE
                
                if h_snapshot == -1:
                    windll.kernel32.CloseHandle(h_process)
                    return None
                
                module_entry = MODULEENTRY32()
                module_entry.dwSize = sizeof(MODULEENTRY32)
                
                # Get the first module
                if windll.kernel32.Module32First(h_snapshot, byref(module_entry)):
                    while True:
                        if module_entry.szModule.decode('utf-8').lower() == module_name.lower():
                            base_addr = ctypes.addressof(module_entry.modBaseAddr.contents)
                            windll.kernel32.CloseHandle(h_snapshot)
                            windll.kernel32.CloseHandle(h_process)
                            return base_addr
                        
                        if not windll.kernel32.Module32Next(h_snapshot, byref(module_entry)):
                            break
                
                windll.kernel32.CloseHandle(h_snapshot)
            finally:
                windll.kernel32.CloseHandle(h_process)
            
            return None
        except Exception as e:
            print(f"Error getting module base address: {e}")
            return None
    
    def read_memory(self, address, data_type):
        if not self.is_connected:
            return None
        
        try:
            buffer = create_string_buffer(sizeof(data_type))
            bytes_read = c_ulong(0)
            
            if not windll.kernel32.ReadProcessMemory(
                self.process_handle,
                address,
                buffer,
                sizeof(data_type),
                byref(bytes_read)
            ):
                # Only show error if show_errors is True and we're not in cooldown period
                current_time = time.time()
                if self.show_errors and (current_time - self._last_error_time) > self._error_cooldown:
                    print(f"Failed to read memory at address {hex(address)}")
                    self._last_error_time = current_time
                return None
            
            return cast(buffer, POINTER(data_type)).contents.value
        except Exception as e:
            current_time = time.time()
            if self.show_errors and (current_time - self._last_error_time) > self._error_cooldown:
                print(f"Error reading memory: {e}")
                self._last_error_time = current_time
            return None
    
    def read_float(self, address):
        return self.read_memory(address, c_float)
    
    def read_int(self, address):
        return self.read_memory(address, c_int)
    
    def read_byte(self, address):
        return self.read_memory(address, c_byte)
    
    def close(self):
        if self.process_handle:
            windll.kernel32.CloseHandle(self.process_handle)
            self.process_handle = None
        self.is_connected = False

# Define trigger modes
class TriggerMode():
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
    VibrateTriggerPulse = 11
    CustomTriggerValue = 12
    Resistance = 13
    Bow = 14
    Galloping = 15
    SemiAutomaticGun = 16
    AutomaticGun = 17
    Machine = 18

class CustomTriggerValueMode():
    OFF = 0
    Rigid = 1
    RigidA = 2
    RigidB = 3
    RigidAB = 4
    Pulse = 5
    PulseA = 6
    PulseB = 7
    PulseAB = 8
    VibrateResistance = 9
    VibrateResistanceA = 10
    VibrateResistanceB = 11
    VibrateResistanceAB = 12
    VibratePulse = 13
    VibratePulseA = 14
    VibratePulseB = 15
    VibratePulseAB = 16

class PlayerLEDNewRevision():
    One = 0
    Two = 1
    Three = 2
    Four = 3
    Five = 4  # Five is Also All On
    AllOff = 5

class MicLEDMode():
    On = 0
    Pulse = 1
    Off = 2

class Trigger():
    Invalid = 0
    Left = 1
    Right = 2

class InstructionType(Enum):
    Invalid = 0
    TriggerUpdate = 1
    RGBUpdate = 2
    PlayerLED = 3
    TriggerThreshold = 4
    MicLED = 5
    PlayerLEDNewRevision = 6
    ResetToUserSettings = 7
    HapticFeedback = 20
    EditAudio = 21

class AudioEditType(Enum):
    Pitch = 0
    Volume = 1
    Stop = 2
    StopAll = 3

class Instruction:
    def __init__(self, instruction_type, parameters):
        self.type = instruction_type
        self.parameters = parameters

    def to_dict(self):
        # 转换参数中的枚举值
        converted_params = []
        for param in self.parameters:
            if isinstance(param, Enum):
                converted_params.append(param.value)  # 使用枚举的值
            else:
                converted_params.append(param)

        return {
            "type": self.type.value,  # 使用枚举的值，而不是名称
            "parameters": converted_params
        }

    @classmethod
    def from_dict(cls, data):
        instruction_type = InstructionType[data["type"]]
        parameters = data["parameters"]
        return cls(instruction_type, parameters)

class Packet:
    def __init__(self, instructions):
        self.instructions = instructions

    def to_dict(self):
        return {
            "instructions": [instr.to_dict() for instr in self.instructions]
        }

    @classmethod
    def from_dict(cls, data):
        instructions = [Instruction.from_dict(instr) for instr in data["instructions"]]
        return cls(instructions)

class ServerResponse:
    def __init__(self, status, time_received, is_controller_connected, battery_level):
        self.Status = status
        self.TimeReceived = time_received
        self.isControllerConnected = is_controller_connected
        self.BatteryLevel = battery_level

    def to_dict(self):
        return {
            "Status": self.Status,
            "TimeReceived": self.TimeReceived,
            "isControllerConnected": self.isControllerConnected,
            "BatteryLevel": self.BatteryLevel
        }

    @classmethod
    def from_dict(cls, data):
        return cls(data["Status"], data["TimeReceived"], data["isControllerConnected"], data["BatteryLevel"])

# Define telemetry data structure
class TireSegment(Structure):
    _fields_ = [
        ("temperature", c_float),
        ("wear", c_float)
    ]

class Tire(Structure):
    _fields_ = [
        ("pressure", c_float),
        ("temperature", c_float),
        ("carcassTemperature", c_float),
        ("treadTemperature", c_float),
        ("currentSegment", c_uint32),
        ("segment1", TireSegment),
        ("segment2", TireSegment),
        ("segment3", TireSegment),
        ("segment4", TireSegment),
        ("segment5", TireSegment),
        ("segment6", TireSegment),
        ("segment7", TireSegment),
        ("segment8", TireSegment)
    ]

class BrakeDisk(Structure):
    _fields_ = [
        ("layerTemperature", c_float),
        ("temperature", c_float),
        ("wear", c_float)
    ]

class Wheel(Structure):
    _fields_ = [
        ("brakeDisk", BrakeDisk),
        ("tire", Tire)
    ]

class Damper(Structure):
    _fields_ = [
        ("damage", c_float),
        ("pistonVelocity", c_float)
    ]

class Suspension(Structure):
    _fields_ = [
        ("springDeflection", c_float),
        ("rollbarForce", c_float),
        ("springForce", c_float),
        ("damperForce", c_float),
        ("strutForce", c_float),
        ("helperSpringIsActive", c_int32),
        ("damper", Damper),
        ("wheel", Wheel)
    ]

class Engine(Structure):
    _fields_ = [
        ("rpm", c_float),
        ("radiatorCoolantTemperature", c_float),
        ("engineCoolantTemperature", c_float),
        ("engineTemperature", c_float)
    ]

class Motion(Structure):
    _fields_ = [
        ("surge", c_float),
        ("sway", c_float),
        ("heave", c_float),
        ("roll", c_float),
        ("pitch", c_float),
        ("yaw", c_float)
    ]

class Car(Structure):
    _fields_ = [
        ("index", c_int32),
        ("speed", c_float),
        ("positionX", c_float),
        ("positionY", c_float),
        ("positionZ", c_float),
        ("roll", c_float),
        ("pitch", c_float),
        ("yaw", c_float),
        ("velocities", Motion),
        ("accelerations", Motion),
        ("engine", Engine),
        ("suspensionLF", Suspension),
        ("suspensionRF", Suspension),
        ("suspensionLB", Suspension),
        ("suspensionRB", Suspension)
    ]

class Control(Structure):
    _fields_ = [
        ("steering", c_float),
        ("throttle", c_float),
        ("brake", c_float),
        ("handbrake", c_float),
        ("clutch", c_float),
        ("gear", c_int32),
        ("footbrakePressure", c_float),
        ("handbrakePressure", c_float)
    ]

class Stage(Structure):
    _fields_ = [
        ("index", c_int32),
        ("progress", c_float),
        ("raceTime", c_float),
        ("driveLineLocation", c_float),
        ("distanceToEnd", c_float)
    ]

class TelemetryData(Structure):
    _fields_ = [
        ("totalSteps", c_uint32),
        ("stage", Stage),
        ("control", Control),
        ("car", Car)
    ]

# Define RPM threshold variables
RPM_IDLE = 800
RPM_LOW = 3000
RPM_MEDIUM = 5000
RPM_HIGH = 6500

# Define RPM color threshold percentages
RPM_GREEN_THRESHOLD = 60  # Below this percentage, LED is green
RPM_YELLOW_THRESHOLD = 80  # Below this percentage, LED transitions from green to yellow
RPM_RED_THRESHOLD = 95    # Below this percentage, LED transitions from yellow to red

# Helper function for color interpolation
def interpolate_color(color1, color2, factor):
    """在两种颜色之间进行线性插值"""
    r1, g1, b1 = color1
    r2, g2, b2 = color2
    r = r1 + (r2 - r1) * factor
    g = g1 + (g2 - g1) * factor
    b = b1 + (b2 - b1) * factor
    return (int(r), int(g), int(b))

class TelemetryOverlay:
    """游戏画面上的遥测数据覆盖层"""
    def __init__(self):
        self.window = None
        self.canvas = None
        self.visible = False
        self.telemetry_data = {}
        self.font_size = 14
        self.text_color = "#00FF00"  # 绿色文字
        self.bg_color = "#000000"  # 黑色背景
        self.bg_opacity = 70  # 背景透明度 (0-255)，增加一点不透明度
        self.position = "top-right"  # 位置: top-left, top-right, bottom-left, bottom-right
        self.padding = 10
        # 调整窗口大小，只适合显示水温信息
        self.width = 200
        self.height = 30
        # 保存自定义位置
        self.custom_x = None
        self.custom_y = None
        # 位置是否已更改标志
        self.position_changed = False
        # 保存配置的回调函数
        self.save_callback = None
        
    def create_window(self):
        """创建覆盖窗口"""
        if self.window:
            return
            
        # 创建一个无边框窗口
        self.window = tk.Toplevel()
        self.window.overrideredirect(True)  # 移除标题栏和边框
        self.window.attributes('-topmost', True)  # 保持在最上层
        self.window.attributes('-alpha', 0.7)  # 设置整体透明度为0.7，使其更适合游戏内显示
        self.window.attributes('-transparentcolor', '')  # 设置透明色
        
        # 设置窗口样式为工具窗口，这样它不会出现在任务栏中
        if WINDOWS_API_AVAILABLE:
            try:
                hwnd = win32gui.GetParent(self.window.winfo_id())
                style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
                style = style | win32con.WS_EX_TOOLWINDOW | win32con.WS_EX_LAYERED
                win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, style)
            except Exception as e:
                print(f"设置窗口样式时出错: {e}")
        
        # 创建画布
        self.canvas = tk.Canvas(self.window, bg=self.bg_color, highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        # 设置初始大小和位置
        self.update_position()
        
        # 绑定鼠标事件，允许拖动窗口
        self.canvas.bind("<ButtonPress-1>", self.start_move)
        self.canvas.bind("<ButtonRelease-1>", self.stop_move)
        self.canvas.bind("<B1-Motion>", self.do_move)
        
        self.moving = False
        self.x = 0
        self.y = 0
        
    def start_move(self, event):
        """开始拖动窗口"""
        self.moving = True
        self.x = event.x
        self.y = event.y
        
    def stop_move(self, event):
        """停止拖动窗口"""
        self.moving = False
        # 如果位置已更改，通知主窗口保存配置
        if self.position_changed and hasattr(self, 'save_callback') and self.save_callback:
            self.save_callback()
    
    def do_move(self, event):
        """拖动窗口"""
        if self.moving:
            x = self.window.winfo_x() + (event.x - self.x)
            y = self.window.winfo_y() + (event.y - self.y)
            self.window.geometry(f"+{x}+{y}")
            # 保存自定义位置
            self.custom_x = x
            self.custom_y = y
            # 通知需要保存配置
            self.position_changed = True
    
    def update_position(self):
        """更新窗口位置"""
        screen_width = self.window.winfo_screenwidth()
        screen_height = self.window.winfo_screenheight()
        
        # 如果有自定义位置，优先使用
        if self.custom_x is not None and self.custom_y is not None:
            x, y = self.custom_x, self.custom_y
        # 否则使用预设位置
        elif self.position == "top-left":
            x, y = self.padding, self.padding
        elif self.position == "top-right":
            x, y = screen_width - self.width - self.padding, self.padding
        elif self.position == "bottom-left":
            x, y = self.padding, screen_height - self.height - self.padding
        elif self.position == "bottom-right":
            x, y = screen_width - self.width - self.padding, screen_height - self.height - self.padding
        else:  # 默认右上角
            x, y = screen_width - self.width - self.padding, self.padding
            
        self.window.geometry(f"{self.width}x{self.height}+{x}+{y}")
    
    def show(self):
        """显示覆盖窗口"""
        if not self.window:
            self.create_window()
        self.window.deiconify()
        self.visible = True
        
    def hide(self):
        """隐藏覆盖窗口"""
        if self.window:
            self.window.withdraw()
        self.visible = False
        
    def toggle_visibility(self):
        """切换可见性"""
        if self.visible:
            self.hide()
        else:
            self.show()
            
    def update_data(self, data):
        """更新遥测数据并重绘"""
        if not self.visible or not self.window:
            return
            
        self.telemetry_data = data
        self.redraw()
        
    def redraw(self):
        """重绘覆盖窗口内容"""
        if not self.visible or not self.window:
            return
            
        self.canvas.delete("all")
        
        # 绘制半透明背景
        self.canvas.create_rectangle(0, 0, self.width, self.height, fill=self.bg_color, outline="")
        
        # 如果没有数据，显示等待消息
        if not self.telemetry_data:
            self.canvas.create_text(
                self.width // 2, 
                self.height // 2, 
                text="等待数据...", 
                fill=self.text_color,
                font=("Arial", self.font_size)
            )
            return
            
        # 只显示水温
        if 'water_temp' in self.telemetry_data:
            water_temp = self.telemetry_data['water_temp']
            # 根据温度改变颜色
            temp_color = self.text_color
            if water_temp > 105:  # 过热
                temp_color = "#FF0000"  # 红色
            elif water_temp > 95:  # 偏高
                temp_color = "#FFFF00"  # 黄色
                
            temp_text = f"WaterTemp: {water_temp:.1f} °C"
            self.canvas.create_text(
                self.width // 2, 
                self.height // 2, 
                text=temp_text, 
                fill=temp_color,
                font=("Arial", self.font_size)
            )
    
    def destroy(self):
        """销毁覆盖窗口"""
        if self.window:
            self.window.destroy()
            self.window = None
            self.canvas = None
            self.visible = False
    
    def load_position(self, config):
        """从配置加载位置"""
        if 'UI' in config and 'overlay_x' in config['UI'] and 'overlay_y' in config['UI']:
            try:
                self.custom_x = int(config['UI']['overlay_x'])
                self.custom_y = int(config['UI']['overlay_y'])
                print(f"已加载悬浮窗位置: x={self.custom_x}, y={self.custom_y}")
            except (ValueError, TypeError):
                self.custom_x = None
                self.custom_y = None
                print("悬浮窗位置格式错误，使用默认位置")
        else:
            self.custom_x = None
            self.custom_y = None
            
    def save_position(self, config):
        """保存位置到配置"""
        if self.position_changed and self.custom_x is not None and self.custom_y is not None:
            if 'UI' not in config:
                config['UI'] = {}
            config['UI']['overlay_x'] = str(self.custom_x)
            config['UI']['overlay_y'] = str(self.custom_y)
            self.position_changed = False
            return True
        return False

# Create a class for the telemetry dashboard
class TelemetryDashboard:
    def __init__(self, root):
        self.root = root
        self.root.title("RBR Telemetry Dashboard")
        self.root.geometry("830x460")
        
        # 初始化游戏内覆盖层
        if WINDOWS_API_AVAILABLE:
            self.overlay = TelemetryOverlay()
            # 从配置加载悬浮窗位置
            self.overlay.load_position(config)
            # 设置保存配置的回调函数
            self.overlay.save_callback = self.save_config
            
            # 根据配置决定是否显示悬浮窗
            self.show_overlay = tk.BooleanVar(value=config.getboolean('UI', 'show_overlay', fallback=False))
            if self.show_overlay.get():
                self.overlay.show()
        else:
            self.overlay = None
            self.show_overlay = tk.BooleanVar(value=False)
            print("游戏内覆盖层功能不可用，因为 PyWin32 库未安装。")
        
        # 设置窗口图标和任务栏图标
        try:
            if getattr(sys, 'frozen', False):
                # 如果是打包后的exe
                icon_path = os.path.join(sys._MEIPASS, "icon.ico")
            else:
                # 如果是直接运行python脚本
                icon_path = "icon.ico"
            
            if os.path.exists(icon_path):
                self.root.iconbitmap(icon_path)
                # 设置任务栏图标
                import ctypes
                myappid = 'rbr.dualsense.adapter.1.0'  # 任意字符串，作为应用程序ID
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
                self.root.iconbitmap(default=icon_path)
        except Exception as e:
            print(f"Failed to set window icon: {e}")
        
        # Set up fonts - 移到最前面
        self.title_font = tkfont.Font(family="Arial", size=12, weight="bold")
        self.value_font = tkfont.Font(family="Arial", size=11)
        
        # 添加反馈强度参数
        self.trigger_strength = tk.DoubleVar(value=trigger_strength)
        self.haptic_strength = tk.DoubleVar(value=haptic_strength)
        self.wheel_slip_threshold = tk.DoubleVar(value=wheel_slip_threshold)
        self.trigger_threshold = tk.DoubleVar(value=trigger_threshold)
        
        # 添加功能开关变量
        self.adaptive_trigger_enabled = tk.BooleanVar(value=adaptive_trigger_enabled)
        self.haptic_effect_enabled = tk.BooleanVar(value=haptic_effect_enabled)
        self.led_effect_enabled = tk.BooleanVar(value=led_effect_enabled)
        
        # 添加主题配置
        self.is_dark_theme = tk.BooleanVar(value=False)
        self.theme_colors = {
            'light': {
                'bg': '#F0F0F0',
                'fg': 'black',
                'canvas_bg': '#FFFFFF',
                'grid_color': '#CCCCCC'
            },
            'dark': {
                'bg': '#2B2B2B',
                'fg': '#FFFFFF',
                'canvas_bg': '#1E1E1E',
                'grid_color': '#404040'
            }
        }
        
        # 添加暂停更新的标志和FPS控制变量 - 移到前面初始化，在create_control_panel()之前
        self.pause_updates = config.getboolean('GUI', 'pause_updates', fallback=False)
        fps_value = min(config.getfloat('GUI', 'fps', fallback=60.0), 60.0)  # 确保不超过60
        self.fps_value = tk.DoubleVar(value=fps_value)
        self.update_interval = 1.0 / self.fps_value.get()  # 计算更新间隔
        
        # 配置初始主题样式
        style = ttk.Style()
        style.configure("Theme.TFrame", background=self.theme_colors['light']['bg'])
        style.configure("Theme.TLabel", background=self.theme_colors['light']['bg'], foreground=self.theme_colors['light']['fg'])
        style.configure("Theme.TCheckbutton", background=self.theme_colors['light']['bg'], foreground=self.theme_colors['light']['fg'])
        style.configure("Theme.Horizontal.TScale", background=self.theme_colors['light']['bg'])
        
        self.root.configure(bg=self.theme_colors['light']['bg'])
        self.root.resizable(True, True)
        
        # 设置窗口半透明
        self.root.attributes('-alpha', 1.0)
        
        # Initialize time tracking and data structures
        self.start_time = time.time()
        
        # Initialize data queues
        self.time_data = deque(maxlen=1000)
        self.throttle_data = deque(maxlen=1000)
        self.brake_data = deque(maxlen=1000)
        self.slip_time_data = deque(maxlen=1000)
        self.fl_slip_data = deque(maxlen=1000)
        self.fr_slip_data = deque(maxlen=1000)
        self.rl_slip_data = deque(maxlen=1000)
        self.rr_slip_data = deque(maxlen=1000)
        
        # Fill initial data
        for _ in range(100):
            self.time_data.append(0)
            self.throttle_data.append(0)
            self.brake_data.append(0)
            self.slip_time_data.append(0)
            self.fl_slip_data.append(0)
            self.fr_slip_data.append(0)
            self.rl_slip_data.append(0)
            self.rr_slip_data.append(0)
        
        # Add wheel slip tracking variables
        self.current_fl_slip = 0
        self.current_fr_slip = 0
        self.current_rl_slip = 0
        self.current_rr_slip = 0
        
        # 添加置顶按钮和透明度控制
        self.create_control_panel()
        
        # 配置行和列的权重，使得窗口调整大小时内容也随之调整
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(0, weight=1)
        
        # Create main frame
        self.main_frame = ttk.Frame(self.root, padding=10)
        self.main_frame.grid(row=0, column=0, sticky="nsew")
        
        # 配置main_frame的行和列权重
        self.main_frame.grid_columnconfigure(0, weight=1)
        # 移除行权重配置，让分组使用其自然高度
        # 最后一行设置权重为1，以吸收多余的空间
        self.main_frame.grid_rowconfigure(3, weight=1)
        
        # Create style for progress bars and widgets
        style = ttk.Style()
        style.theme_use('default')
        style.configure("green.Horizontal.TProgressbar", background='green')
        style.configure("yellow.Horizontal.TProgressbar", background='yellow')
        style.configure("red.Horizontal.TProgressbar", background='red')
        style.configure("blue.Horizontal.TProgressbar", background='blue')
        
        # 创建反向进度条样式（从右向左）
        style.configure("Reverse.Horizontal.TProgressbar", background='#4a6984')
        
        style.configure("TLabel", background='#F0F0F0', foreground='black')
        style.configure("TFrame", background='#F0F0F0')
        style.configure("TLabelframe", background='#F0F0F0')
        style.configure("TLabelframe.Label", background='#F0F0F0', foreground='black')
        
        # 添加折叠按钮的自定义样式
        style.configure("Collapse.TButton", 
                      padding=0,
                      relief="flat",
                      font=('Arial', 8),  # 使用更小的字体
                      width=2,
                      background=self.theme_colors['light']['bg'])
        
        # 添加状态栏
        self.status_bar = ttk.Label(self.root, text="Ready", relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.grid(row=1, column=0, sticky="ew")
        
        # Create sections with collapsible frames in the new order
        self.create_wheel_slip_graphs_section()  # 第一个：轮胎打滑状态图表
        self.create_vibration_graphs_section()   # 第二个：震动强度图表
        self.create_car_info_section()          # 第三个：车辆信息
        self.create_control_inputs_section()    # 第四个：控制输入
        
        # Initialize values
        self.update_values({
            'car_speed': 0, 'ground_speed': 0, 'rpm': 0, 'gear': 'N',
            'water_temp': 0, 'turbo_pressure': 0, 'race_time': 0,
            'wheel_fl': 0, 'wheel_fr': 0, 'wheel_rl': 0, 'wheel_rr': 0,
            'slip_fl': 0, 'slip_fr': 0, 'slip_rl': 0, 'slip_rr': 0,
            'throttle': 0, 'brake': 0, 'handbrake': 0, 'clutch': 0, 'steering': 0,
            'throttle_vibration': 0, 'brake_vibration': 0
        })
        
        self.update_thread = None
        self.update_thread_running = False
        self.last_update_time = time.time()
        self.update_timeout = 5.0  # Seconds before considering the update thread stuck
    
    def create_collapsible_frame(self, parent, text, row, column, columnspan=1):
        """创建可折叠的框架"""
        # 创建一个容器框架来包含折叠按钮和主框架
        container = ttk.Frame(parent, style='Theme.TFrame')
        container.grid(row=row, column=column, columnspan=columnspan, padx=5, pady=(0, 5), sticky="new")  # 修改sticky为"new"并调整padding
        container.grid_columnconfigure(1, weight=1)  # 让主框架可以横向扩展
        
        # 添加折叠按钮 - 放在左上角，使用自定义样式
        toggle_btn = ttk.Button(container, text="▼", style="Collapse.TButton",
                              command=lambda: self.toggle_frame(frame, toggle_btn, container))
        toggle_btn.grid(row=0, column=0, sticky="nw", padx=(0, 2))
        
        # 添加标题标签
        title_label = ttk.Label(container, text=text, style='Theme.TLabel', font=self.title_font)
        title_label.grid(row=0, column=1, sticky="w")
        
        # 创建主框架
        frame = ttk.Frame(container, style='Theme.TFrame', padding=(15, 5, 5, 5))
        frame.grid(row=1, column=0, columnspan=2, sticky="new", pady=(2, 0))  # 修改sticky为"new"
        
        # 存储引用
        frame.container = container
        frame.toggle_btn = toggle_btn
        frame.is_collapsed = False
        
        return frame, frame
    
    def toggle_frame(self, frame, btn, container):
        """切换框架的折叠状态"""
        if frame.is_collapsed:
            # 展开
            frame.grid()
            btn.configure(text="▼")
            frame.is_collapsed = False
            container.grid_configure(pady=(0, 5))  # 保持一致的间距
        else:
            # 折叠
            frame.grid_remove()
            btn.configure(text="▶")
            frame.is_collapsed = True
            container.grid_configure(pady=(0, 5))  # 保持一致的间距
        
        # 强制更新布局
        self.root.update_idletasks()
    
    def create_control_panel(self):
        """创建控制面板，包含置顶按钮和透明度控制"""
        self.control_panel = ttk.Frame(self.root, style='Theme.TFrame')
        self.control_panel.grid(row=2, column=0, sticky="ew", padx=5, pady=5)
        
        # 置顶按钮
        self.always_on_top = tk.BooleanVar(value=False)
        always_on_top_cb = ttk.Checkbutton(
            self.control_panel, 
            text="Pin Window", 
            variable=self.always_on_top,
            command=self.toggle_always_on_top,
            style='Theme.TCheckbutton'
        )
        always_on_top_cb.pack(side=tk.LEFT, padx=5)
        
        # 标题栏切换按钮
        self.show_title_bar = tk.BooleanVar(value=True)
        title_bar_cb = ttk.Checkbutton(
            self.control_panel,
            text="Show Title Bar",
            variable=self.show_title_bar,
            command=self.toggle_title_bar,
            style='Theme.TCheckbutton'
        )
        title_bar_cb.pack(side=tk.LEFT, padx=5)
        
        # 游戏内覆盖层切换按钮
        overlay_cb = ttk.Checkbutton(
            self.control_panel,
            text="游戏内显示",
            variable=self.show_overlay,
            command=self.toggle_overlay,
            style='Theme.TCheckbutton'
        )
        overlay_cb.pack(side=tk.LEFT, padx=5)
        
        # 如果 PyWin32 不可用，禁用覆盖层切换按钮
        if not WINDOWS_API_AVAILABLE:
            overlay_cb.configure(state='disabled')
            self.show_overlay.set(False)
        
        # 主题切换按钮
        theme_cb = ttk.Checkbutton(
            self.control_panel,
            text="Dark Theme",
            variable=self.is_dark_theme,
            command=self.toggle_theme,
            style='Theme.TCheckbutton'
        )
        theme_cb.pack(side=tk.LEFT, padx=5)
        
        # 透明度控制
        ttk.Label(self.control_panel, text="Transparency:", style='Theme.TLabel').pack(side=tk.LEFT, padx=(10, 0))
        self.transparency_scale = ttk.Scale(
            self.control_panel, 
            from_=0.3, 
            to=1.0, 
            orient=tk.HORIZONTAL, 
            length=100,
            value=1.0,
            command=self.change_transparency,
            style='Theme.Horizontal.TScale'
        )
        self.transparency_scale.pack(side=tk.LEFT, padx=5)
        
        # 创建反馈控制面板
        self.feedback_frame, content = self.create_collapsible_frame(
            self.root, 
            "Feedback Controls", 
            3, 
            0, 
            columnspan=1
        )
        
        # 配置列权重，使进度条可以均匀扩展
        content.grid_columnconfigure(0, weight=1)  # 让整个内容区域可以扩展
        
        # 添加功能开关控制
        features_frame = ttk.Frame(content, style='Theme.TFrame')
        features_frame.grid(row=0, column=0, sticky="ew", padx=5, pady=2)
        features_frame.grid_columnconfigure(0, weight=1)
        
        # 创建功能开关标题
        # features_label = ttk.Label(features_frame, text="Feature Toggles:", style='Theme.TLabel', font=self.title_font)
        # features_label.grid(row=0, column=0, sticky="w", pady=(0, 5))
        
        # 创建功能开关子框架 - 将所有开关放在同一行
        toggles_frame = ttk.Frame(features_frame, style='Theme.TFrame')
        toggles_frame.grid(row=1, column=0, sticky="ew", padx=5)
        
        # 自适应扳机开关
        adaptive_trigger_cb = ttk.Checkbutton(
            toggles_frame,
            text="Adaptive Triggers",
            variable=self.adaptive_trigger_enabled,
            command=self.update_feature_toggles,
            style='Theme.TCheckbutton'
        )
        adaptive_trigger_cb.pack(side=tk.LEFT, padx=(0, 15))
        
        # 震动反馈开关
        haptic_effect_cb = ttk.Checkbutton(
            toggles_frame,
            text="Haptic Feedback",
            variable=self.haptic_effect_enabled,
            command=self.update_feature_toggles,
            style='Theme.TCheckbutton'
        )
        haptic_effect_cb.pack(side=tk.LEFT, padx=(0, 15))
        
        # LED效果开关
        led_effect_cb = ttk.Checkbutton(
            toggles_frame,
            text="LED Effects",
            variable=self.led_effect_enabled,
            command=self.update_feature_toggles,
            style='Theme.TCheckbutton'
        )
        led_effect_cb.pack(side=tk.LEFT)
        
        # 添加分隔线
        separator = ttk.Separator(content, orient="horizontal")
        separator.grid(row=1, column=0, sticky="ew", padx=5, pady=10)
        
        # 自适应扳机强度控制
        trigger_frame = ttk.Frame(content, style='Theme.TFrame')
        trigger_frame.grid(row=2, column=0, sticky="ew", padx=5, pady=2)
        trigger_frame.grid_columnconfigure(1, weight=1)  # 让进度条可以扩展
        
        ttk.Label(trigger_frame, text="Trigger Strength:", style='Theme.TLabel', width=20, anchor="e").grid(row=0, column=0, padx=(0,5))
        trigger_scale = ttk.Scale(
            trigger_frame,
            from_=0.1,
            to=2.0,
            orient=tk.HORIZONTAL,
            variable=self.trigger_strength,
            command=lambda x: self.update_feedback_strength(format_target=self.trigger_value_label),
            style='Theme.Horizontal.TScale'
        )
        trigger_scale.grid(row=0, column=1, sticky="ew", padx=(0,5))
        self.trigger_value_label = ttk.Label(trigger_frame, style='Theme.TLabel', width=5, anchor="e")
        self.trigger_value_label.grid(row=0, column=2)
        
        # Haptic震动强度控制
        haptic_frame = ttk.Frame(content, style='Theme.TFrame')
        haptic_frame.grid(row=3, column=0, sticky="ew", padx=5, pady=2)
        haptic_frame.grid_columnconfigure(1, weight=1)  # 让进度条可以扩展
        
        ttk.Label(haptic_frame, text="Haptic Strength:", style='Theme.TLabel', width=20, anchor="e").grid(row=0, column=0, padx=(0,5))
        haptic_scale = ttk.Scale(
            haptic_frame,
            from_=0,
            to=1.0,
            orient=tk.HORIZONTAL,
            variable=self.haptic_strength,
            command=lambda x: self.update_feedback_strength(format_target=self.haptic_value_label),
            style='Theme.Horizontal.TScale'
        )
        haptic_scale.grid(row=0, column=1, sticky="ew", padx=(0,5))
        self.haptic_value_label = ttk.Label(haptic_frame, style='Theme.TLabel', width=5, anchor="e")
        self.haptic_value_label.grid(row=0, column=2)
        
        # 轮胎打滑检测阈值控制
        slip_frame = ttk.Frame(content, style='Theme.TFrame')
        slip_frame.grid(row=4, column=0, sticky="ew", padx=5, pady=2)
        slip_frame.grid_columnconfigure(1, weight=1)  # 让进度条可以扩展
        
        ttk.Label(slip_frame, text="Trigger Slip Threshold:", style='Theme.TLabel', width=20, anchor="e").grid(row=0, column=0, padx=(0,5))
        slip_scale = ttk.Scale(
            slip_frame,
            from_=1.0,
            to=20.0,
            orient=tk.HORIZONTAL,
            variable=self.wheel_slip_threshold,
            command=lambda x: self.update_feedback_strength(format_target=self.slip_value_label),
            style='Theme.Horizontal.TScale'
        )
        slip_scale.grid(row=0, column=1, sticky="ew", padx=(0,5))
        self.slip_value_label = ttk.Label(slip_frame, style='Theme.TLabel', width=5, anchor="e")
        self.slip_value_label.grid(row=0, column=2)
        
        # 触发阈值控制
        trigger_threshold_frame = ttk.Frame(content, style='Theme.TFrame')
        trigger_threshold_frame.grid(row=5, column=0, sticky="ew", padx=5, pady=2)
        trigger_threshold_frame.grid_columnconfigure(1, weight=1)  # 让进度条可以扩展
        
        ttk.Label(trigger_threshold_frame, text="Haptic Slip Threshold:", style='Theme.TLabel', width=20, anchor="e").grid(row=0, column=0, padx=(0,5))
        threshold_scale = ttk.Scale(
            trigger_threshold_frame,
            from_=1.0,
            to=20.0,
            orient=tk.HORIZONTAL,
            variable=self.trigger_threshold,
            command=lambda x: self.update_feedback_strength(format_target=self.threshold_value_label),
            style='Theme.Horizontal.TScale'
        )
        threshold_scale.grid(row=0, column=1, sticky="ew", padx=(0,5))
        self.threshold_value_label = ttk.Label(trigger_threshold_frame, style='Theme.TLabel', width=5, anchor="e")
        self.threshold_value_label.grid(row=0, column=2)
        
        # 初始化所有值的显示
        self.update_all_value_labels()
        
        # 添加暂停更新按钮
        self.pause_button = ttk.Button(
            self.control_panel, 
            text="Resume Update" if self.pause_updates else "Pause Update", 
            command=self.toggle_pause_updates,
            style="Control.TButton"
        )
        self.pause_button.pack(side=tk.RIGHT, padx=5)
        
        # 添加FPS控制
        fps_frame = ttk.Frame(self.control_panel, style='Theme.TFrame')
        fps_frame.pack(side=tk.RIGHT, padx=5)
        
        ttk.Label(fps_frame, text="FPS:", style='Theme.TLabel').pack(side=tk.LEFT)
        fps_scale = ttk.Scale(
            fps_frame,
            from_=10.0,
            to=60.0,  # 将最大值从120改为60
            orient=tk.HORIZONTAL,
            length=80,
            variable=self.fps_value,
            command=self.update_fps,
            style='Theme.Horizontal.TScale'
        )
        fps_scale.pack(side=tk.LEFT, padx=2)
        
        self.fps_label = ttk.Label(fps_frame, text=f"{min(self.fps_value.get(), 60.0):.0f}", style='Theme.TLabel', width=3)
        self.fps_label.pack(side=tk.LEFT)
    
    def update_all_value_labels(self):
        """更新所有数值标签的显示"""
        self.trigger_value_label.config(text=f"{self.trigger_strength.get():.1f}")
        self.haptic_value_label.config(text=f"{self.haptic_strength.get():.1f}")
        self.slip_value_label.config(text=f"{self.wheel_slip_threshold.get():.1f}")
        self.threshold_value_label.config(text=f"{self.trigger_threshold.get():.1f}")
    
    def toggle_pause_updates(self):
        """切换暂停/恢复更新状态"""
        self.pause_updates = not self.pause_updates
        if self.pause_updates:
            self.pause_button.config(text="Resume Update")
            self.status_bar.config(text="Update Paused")
        else:
            self.pause_button.config(text="Pause Update")
            self.status_bar.config(text="Update Resumed")
        
        # 更新配置文件
        if 'GUI' not in config:
            config['GUI'] = {}
        config['GUI']['pause_updates'] = str(self.pause_updates)
        self.save_config()
    
    def update_fps(self, *args):
        """更新FPS设置"""
        fps = min(self.fps_value.get(), 60.0)  # 确保不超过60
        self.update_interval = 1.0 / fps
        self.fps_label.config(text=f"{fps:.0f}")
        
        # 更新配置文件
        if 'GUI' not in config:
            config['GUI'] = {}
        config['GUI']['fps'] = f"{fps:.1f}"
        self.save_config()
    
    def save_config(self):
        """保存配置到文件"""
        try:
            # 保存覆盖层设置
            if hasattr(self, 'show_overlay') and WINDOWS_API_AVAILABLE:
                if 'UI' not in config:
                    config['UI'] = {}
                config['UI']['show_overlay'] = str(self.show_overlay.get())
                
                # 保存悬浮窗位置
                if hasattr(self, 'overlay') and self.overlay is not None:
                    self.overlay.save_position(config)
                
            with open(config_path, 'w', encoding='utf-8') as configfile:
                config.write(configfile)
        except Exception as e:
            print(f"Error saving config: {e}")
    
    def update_feedback_strength(self, format_target=None, *args):
        """更新反馈强度参数"""
        global trigger_strength, haptic_strength, wheel_slip_threshold, trigger_threshold
        
        # 更新全局变量
        trigger_strength = self.trigger_strength.get()
        haptic_strength = self.haptic_strength.get()
        wheel_slip_threshold = self.wheel_slip_threshold.get()
        trigger_threshold = self.trigger_threshold.get()
        
        # 更新显示的数值
        if format_target is not None:
            if format_target == self.trigger_value_label:
                format_target.config(text=f"{trigger_strength:.1f}")
            elif format_target == self.haptic_value_label:
                format_target.config(text=f"{haptic_strength:.1f}")
            elif format_target == self.slip_value_label:
                format_target.config(text=f"{wheel_slip_threshold:.1f}")
            elif format_target == self.threshold_value_label:
                format_target.config(text=f"{trigger_threshold:.1f}")
        
        # 更新配置文件
        config['Feedback'] = {
            'trigger_strength': f"{trigger_strength:.1f}",
            'haptic_strength': f"{haptic_strength:.1f}",
            'wheel_slip_threshold': f"{wheel_slip_threshold:.1f}",
            'trigger_threshold': f"{trigger_threshold:.1f}"
        }
        
        self.save_config()
    
    def update_feature_toggles(self):
        """更新功能开关状态"""
        global adaptive_trigger_enabled, haptic_effect_enabled, led_effect_enabled
        
        # 更新全局变量
        adaptive_trigger_enabled = self.adaptive_trigger_enabled.get()
        haptic_effect_enabled = self.haptic_effect_enabled.get()
        led_effect_enabled = self.led_effect_enabled.get()
        
        # 更新配置文件
        config['Features'] = {
            'adaptive_trigger': str(adaptive_trigger_enabled),
            'led_effect': str(led_effect_enabled),
            'haptic_effect': str(haptic_effect_enabled),
            'print_telemetry': str(print_telemetry_enabled),
            'use_gui_dashboard': str(use_gui_dashboard)
        }
        
        try:
            with open(config_path, 'w', encoding='utf-8') as configfile:
                config.write(configfile)
        except Exception as e:
            print(f"Error saving config: {e}")
    
    def toggle_always_on_top(self):
        """切换窗口置顶状态"""
        self.root.attributes('-topmost', self.always_on_top.get())
    
    def toggle_title_bar(self):
        """切换标题栏显示状态"""
        if self.show_title_bar.get():
            self.root.overrideredirect(False)
        else:
            self.root.overrideredirect(True)
            
    def toggle_overlay(self):
        """切换游戏内覆盖层显示状态"""
        if not hasattr(self, 'overlay') or self.overlay is None:
            print("游戏内覆盖层功能不可用，因为 PyWin32 库未安装。")
            self.show_overlay.set(False)
            return
            
        if self.show_overlay.get():
            # 如果勾选了显示，但悬浮窗还没有显示，则显示它
            if not self.overlay.visible:
                self.overlay.show()
        else:
            # 如果取消了勾选，但悬浮窗还在显示，则隐藏它
            if self.overlay.visible:
                self.overlay.hide()
                
        # 保存配置
        self.save_config()
    
    def change_transparency(self, value):
        """改变窗口透明度"""
        self.root.attributes('-alpha', float(value))
    
    def toggle_theme(self):
        """切换深色/浅色主题"""
        theme = 'dark' if self.is_dark_theme.get() else 'light'
        colors = self.theme_colors[theme]
        
        # 更新根窗口和主框架背景
        self.root.configure(bg=colors['bg'])
        self.main_frame.configure(style='Theme.TFrame')
        
        # 更新所有标签和框架的样式
        style = ttk.Style()
        style.configure("Theme.TFrame", background=colors['bg'])
        style.configure("Theme.TLabel", background=colors['bg'], foreground=colors['fg'])
        style.configure("Theme.TLabelframe", background=colors['bg'])
        style.configure("Theme.TLabelframe.Label", background=colors['bg'], foreground=colors['fg'])
        
        # 更新折叠按钮样式
        style.configure("Collapse.TButton", 
                      background=colors['bg'],
                      foreground=colors['fg'])
        
        # 更新状态栏样式
        style.configure("Theme.TLabel", background=colors['bg'], foreground=colors['fg'])
        self.status_bar.configure(style='Theme.TLabel')
        
        # 更新控制面板和反馈控制面板样式
        for panel in [self.control_panel, self.feedback_frame]:
            panel.configure(style='Theme.TFrame')
            for child in panel.winfo_children():
                if isinstance(child, ttk.Frame):
                    child.configure(style='Theme.TFrame')
                    for subchild in child.winfo_children():
                        if isinstance(subchild, ttk.Label):
                            subchild.configure(style='Theme.TLabel')
                        elif isinstance(subchild, ttk.Scale):
                            style.configure("Theme.Horizontal.TScale", background=colors['bg'])
                            subchild.configure(style='Theme.Horizontal.TScale')
                        elif isinstance(subchild, ttk.Checkbutton):
                            style.configure("Theme.TCheckbutton", background=colors['bg'], foreground=colors['fg'])
                            subchild.configure(style='Theme.TCheckbutton')
                        elif isinstance(subchild, ttk.Frame):
                            subchild.configure(style='Theme.TFrame')
                            for grandchild in subchild.winfo_children():
                                if isinstance(grandchild, ttk.Label):
                                    grandchild.configure(style='Theme.TLabel')
                                elif isinstance(grandchild, ttk.Checkbutton):
                                    grandchild.configure(style='Theme.TCheckbutton')
                                elif isinstance(grandchild, ttk.Scale):
                                    grandchild.configure(style='Theme.Horizontal.TScale')
                                elif isinstance(grandchild, ttk.Separator):
                                    style.configure("TSeparator", background=colors['fg'])
                elif isinstance(child, ttk.Label):
                    child.configure(style='Theme.TLabel')
                elif isinstance(child, ttk.Checkbutton):
                    style.configure("Theme.TCheckbutton", background=colors['bg'], foreground=colors['fg'])
                    child.configure(style='Theme.TCheckbutton')
                elif isinstance(child, ttk.Scale):
                    style.configure("Theme.Horizontal.TScale", background=colors['bg'])
                    child.configure(style='Theme.Horizontal.TScale')
                elif isinstance(child, ttk.Separator):
                    style.configure("TSeparator", background=colors['fg'])
        
        # 更新三个主要信息框的样式
        self.car_frame.configure(style='Theme.TLabelframe')
        self.control_frame.configure(style='Theme.TLabelframe')
        
        # 更新每个框架内的所有子控件
        for frame in [self.car_frame, self.control_frame]:
            for child in frame.winfo_children():
                if isinstance(child, ttk.Label):
                    # 特殊处理水温标签
                    if child == self.water_temp_label:
                        # 获取当前水温值
                        try:
                            water_temp = float(child.cget("text").split()[0])
                            # 根据水温和当前主题设置颜色
                            if water_temp >= 120:
                                child.configure(foreground='#FF4444')  # 明亮的红色
                            elif water_temp >= 100:
                                child.configure(foreground='#FFA500')  # 明亮的橙色
                            else:
                                child.configure(foreground=colors['fg'])  # 使用主题对应的文字颜色
                        except (ValueError, IndexError):
                            child.configure(foreground=colors['fg'])  # 如果解析失败，使用默认颜色
                    else:
                        child.configure(style='Theme.TLabel')
                elif isinstance(child, ttk.Frame):
                    child.configure(style='Theme.TFrame')
                    # 更新嵌套框架内的控件
                    for subchild in child.winfo_children():
                        if isinstance(subchild, ttk.Label):
                            subchild.configure(style='Theme.TLabel')
                        elif isinstance(subchild, tk.Canvas):
                            subchild.configure(bg=colors['bg'])
        
        # 更新图表颜色 - 添加错误检查
        try:
            # 更新震动强度图表
            if hasattr(self, 'fig_vibration'):
                self.fig_vibration.patch.set_facecolor(colors['bg'])
                self.ax_vibration.set_facecolor(colors['canvas_bg'])
                self.ax_vibration.grid(True, linestyle='--', alpha=0.7, color=colors['grid_color'])
                
                # 更新文字颜色
                self.ax_vibration.tick_params(colors=colors['fg'])
                self.ax_vibration.title.set_color(colors['fg'])
                self.ax_vibration.xaxis.label.set_color(colors['fg'])
                self.ax_vibration.yaxis.label.set_color(colors['fg'])
                
                # 更新图例颜色
                legend = self.ax_vibration.get_legend()
                if legend:
                    for text in legend.get_texts():
                        text.set_color(colors['fg'])
                    legend.get_frame().set_facecolor(colors['bg'])
                    legend.get_frame().set_edgecolor(colors['fg'])
                
                # 重绘图表
                self.canvas_vibration.draw()
            
            # 更新轮胎打滑图表
            if hasattr(self, 'fig_slip'):
                self.fig_slip.patch.set_facecolor(colors['bg'])
                self.ax_slip.set_facecolor(colors['canvas_bg'])
                self.ax_slip.grid(True, linestyle='--', alpha=0.7, color=colors['grid_color'])
                
                # 更新文字颜色
                self.ax_slip.tick_params(colors=colors['fg'])
                self.ax_slip.title.set_color(colors['fg'])
                self.ax_slip.xaxis.label.set_color(colors['fg'])
                self.ax_slip.yaxis.label.set_color(colors['fg'])
                
                # 更新图例颜色
                legend_slip = self.ax_slip.get_legend()
                if legend_slip:
                    for text in legend_slip.get_texts():
                        text.set_color(colors['fg'])
                    legend_slip.get_frame().set_facecolor(colors['bg'])
                    legend_slip.get_frame().set_edgecolor(colors['fg'])
                
                # 重绘图表
                self.canvas_slip.draw()
        except Exception as e:
            print(f"更新图表主题时出错: {e}")
        
        # 更新方向盘指示器背景
        if hasattr(self, 'steering_left_canvas'):
            self.steering_left_canvas.configure(bg=colors['bg'])
        if hasattr(self, 'steering_right_canvas'):
            self.steering_right_canvas.configure(bg=colors['bg'])
    
    def create_car_info_section(self):
        # Car info frame with collapsible feature
        self.car_frame, content = self.create_collapsible_frame(self.main_frame, "Car Information", 2, 0, columnspan=1)
        # Remove the column weight configuration that was causing the stretching
        # content.grid_columnconfigure(1, weight=1)  # This line is removed
        
        # Speed and RPM
        ttk.Label(content, text="Car Speed:", style='Theme.TLabel').grid(row=0, column=0, sticky="w", padx=5, pady=2)
        self.car_speed_label = ttk.Label(content, text="0 km/h", font=self.value_font, width=10, style='Theme.TLabel')
        self.car_speed_label.grid(row=0, column=1, sticky="w", padx=5, pady=2)
        
        ttk.Label(content, text="Ground Speed:", style='Theme.TLabel').grid(row=1, column=0, sticky="w", padx=5, pady=2)
        self.ground_speed_label = ttk.Label(content, text="0 km/h", font=self.value_font, width=10, style='Theme.TLabel')
        self.ground_speed_label.grid(row=1, column=1, sticky="w", padx=5, pady=2)
        
        # RPM section with label, value, and progress bar all adjacent
        ttk.Label(content, text="RPM:", style='Theme.TLabel').grid(row=2, column=0, sticky="w", padx=5, pady=2)
        self.rpm_label = ttk.Label(content, text="0", font=self.value_font, width=10, style='Theme.TLabel')
        self.rpm_label.grid(row=2, column=1, sticky="w", padx=(5, 0), pady=2)  # Reduce right padding
        
        # Add RPM progress bar immediately after the RPM value
        self.rpm_bar = ttk.Progressbar(content, orient="horizontal", length=200, mode="determinate")
        self.rpm_bar.grid(row=2, column=2, padx=(0, 5), pady=2, sticky="w")
        
        ttk.Label(content, text="Gear:", style='Theme.TLabel').grid(row=3, column=0, sticky="w", padx=5, pady=2)
        self.gear_label = ttk.Label(content, text="N", font=self.value_font, width=10, style='Theme.TLabel')
        self.gear_label.grid(row=3, column=1, sticky="w", padx=5, pady=2)
        
        ttk.Label(content, text="Water Temp:", style='Theme.TLabel').grid(row=4, column=0, sticky="w", padx=5, pady=2)
        self.water_temp_label = ttk.Label(content, text="0 °C", font=self.value_font, width=10, style='Theme.TLabel')
        self.water_temp_label.grid(row=4, column=1, sticky="w", padx=5, pady=2)
        
        ttk.Label(content, text="Turbo Pressure:", style='Theme.TLabel').grid(row=5, column=0, sticky="w", padx=5, pady=2)
        self.turbo_pressure_label = ttk.Label(content, text="0 bar", font=self.value_font, width=10, style='Theme.TLabel')
        self.turbo_pressure_label.grid(row=5, column=1, sticky="w", padx=5, pady=2)
        
        ttk.Label(content, text="Race Time:", style='Theme.TLabel').grid(row=6, column=0, sticky="w", padx=5, pady=2)
        self.race_time_label = ttk.Label(content, text="0.00 s", font=self.value_font, width=10, style='Theme.TLabel')
        self.race_time_label.grid(row=6, column=1, sticky="w", padx=5, pady=2)
    
    def create_control_inputs_section(self):
        # Control inputs frame with collapsible feature
        self.control_frame, content = self.create_collapsible_frame(self.main_frame, "Control Inputs", 3, 0, columnspan=1)
        content.grid_columnconfigure(1, weight=1)  # 让内容区域可以横向扩展
        
        # Throttle - 绿色
        ttk.Label(content, text="Throttle:", style='Theme.TLabel').grid(row=0, column=0, sticky="w", padx=5, pady=2)
        self.throttle_bar = ttk.Progressbar(content, orient="horizontal", length=200, mode="determinate", style="green.Horizontal.TProgressbar")
        self.throttle_bar.grid(row=0, column=1, padx=5, pady=2, sticky="ew")
        self.throttle_label = ttk.Label(content, text="0%", font=self.value_font, width=8, style='Theme.TLabel')
        self.throttle_label.grid(row=0, column=2, sticky="w", padx=5, pady=2)
        
        # Brake - 红色
        ttk.Label(content, text="Brake:", style='Theme.TLabel').grid(row=1, column=0, sticky="w", padx=5, pady=2)
        self.brake_bar = ttk.Progressbar(content, orient="horizontal", length=200, mode="determinate", style="red.Horizontal.TProgressbar")
        self.brake_bar.grid(row=1, column=1, padx=5, pady=2, sticky="ew")
        self.brake_label = ttk.Label(content, text="0%", font=self.value_font, width=8, style='Theme.TLabel')
        self.brake_label.grid(row=1, column=2, sticky="w", padx=5, pady=2)
        
        # Handbrake - 蓝色
        ttk.Label(content, text="Handbrake:", style='Theme.TLabel').grid(row=2, column=0, sticky="w", padx=5, pady=2)
        self.handbrake_bar = ttk.Progressbar(content, orient="horizontal", length=200, mode="determinate", style="blue.Horizontal.TProgressbar")
        self.handbrake_bar.grid(row=2, column=1, padx=5, pady=2, sticky="ew")
        self.handbrake_label = ttk.Label(content, text="0%", font=self.value_font, width=8, style='Theme.TLabel')
        self.handbrake_label.grid(row=2, column=2, sticky="w", padx=5, pady=2)
        
        # Clutch
        ttk.Label(content, text="Clutch:", style='Theme.TLabel').grid(row=3, column=0, sticky="w", padx=5, pady=2)
        self.clutch_bar = ttk.Progressbar(content, orient="horizontal", length=200, mode="determinate")
        self.clutch_bar.grid(row=3, column=1, padx=5, pady=2, sticky="ew")
        self.clutch_label = ttk.Label(content, text="0%", font=self.value_font, width=8, style='Theme.TLabel')
        self.clutch_label.grid(row=3, column=2, sticky="w", padx=5, pady=2)
        
        # Steering - 从中间开始的特殊进度条
        ttk.Label(content, text="Steering:", style='Theme.TLabel').grid(row=4, column=0, sticky="w", padx=5, pady=2)
        
        # 创建一个框架来容纳方向盘指示器
        steering_frame = ttk.Frame(content, style='Theme.TFrame')
        steering_frame.grid(row=4, column=1, padx=5, pady=2, sticky="ew")
        steering_frame.grid_columnconfigure(0, weight=1)  # 左侧进度条可以横向扩展
        steering_frame.grid_columnconfigure(2, weight=1)  # 右侧进度条可以横向扩展
        
        # 左侧进度条（负值）- 使用Canvas实现反向进度条
        self.steering_left_canvas = tk.Canvas(steering_frame, height=20, bg=self.theme_colors['light']['bg'], highlightthickness=0)
        self.steering_left_canvas.grid(row=0, column=0, sticky="ew")
        
        # 中心标记 - 使用Frame确保宽度一致
        center_frame = ttk.Frame(steering_frame, width=2, style='Theme.TFrame')
        center_frame.grid(row=0, column=1)
        center_frame.grid_propagate(False)  # 防止Frame被内容压缩
        center_mark = ttk.Label(center_frame, text="|", font=self.value_font, style='Theme.TLabel')
        center_mark.place(relx=0.5, rely=0.5, anchor="center")  # 居中放置
        
        # 右侧进度条（正值）
        self.steering_right_canvas = tk.Canvas(steering_frame, height=20, bg=self.theme_colors['light']['bg'], highlightthickness=0)
        self.steering_right_canvas.grid(row=0, column=2, sticky="ew")
        
        # 创建进度条 - 初始状态
        self.steering_left_bar = self.steering_left_canvas.create_rectangle(0, 0, 0, 20, fill='#4a6984', width=0)
        self.steering_right_bar = self.steering_right_canvas.create_rectangle(0, 0, 0, 20, fill='#4a6984', width=0)
        
        # 绑定大小调整事件
        self.steering_left_canvas.bind('<Configure>', self.on_steering_canvas_resize)
        self.steering_right_canvas.bind('<Configure>', self.on_steering_canvas_resize)
        
        self.steering_label = ttk.Label(content, text="0", font=self.value_font, width=8, style='Theme.TLabel')
        self.steering_label.grid(row=4, column=2, sticky="w", padx=5, pady=2)
    
    def on_steering_canvas_resize(self, event):
        """处理方向盘Canvas大小调整事件"""
        # 更新Canvas的宽度
        canvas = event.widget
        canvas.configure(width=event.width)
        
        # 重新绘制进度条
        if canvas == self.steering_left_canvas:
            self.steering_left_canvas.coords(self.steering_left_bar, event.width, 0, event.width, 20)
        elif canvas == self.steering_right_canvas:
            self.steering_right_canvas.coords(self.steering_right_bar, 0, 0, 0, 20)
    
    def create_vibration_graphs_section(self):
        """创建震动强度图表部分"""
        # Create frame for vibration graph with collapsible feature
        self.vibration_frame, content = self.create_collapsible_frame(self.main_frame, "Vibration Intensity", 1, 0, columnspan=1)
        content.grid_columnconfigure(0, weight=1)  # 让内容区域可以横向扩展
        
        # Create figure with adjusted parameters
        self.fig_vibration = Figure(figsize=(10, 2), dpi=100)
        self.fig_vibration.patch.set_facecolor(self.theme_colors['light']['bg'])
        
        # Adjust subplot parameters to reduce margins
        self.fig_vibration.subplots_adjust(left=0.05, right=0.98, top=0.95, bottom=0.15)
        
        # Create subplot for vibration intensity
        self.ax_vibration = self.fig_vibration.add_subplot(111)
        self.ax_vibration.set_facecolor(self.theme_colors['light']['canvas_bg'])
        self.ax_vibration.grid(True, linestyle='--', alpha=0.7, color=self.theme_colors['light']['grid_color'])
        
        # Set labels and title
        # self.ax_vibration.set_title('Real-time Trigger Vibration Intensity')
        # self.ax_vibration.set_xlabel('Time (seconds)')
        # self.ax_vibration.set_ylabel('Intensity')
        
        # Set axis limits
        self.ax_vibration.set_ylim(0, 1)
        self.ax_vibration.set_xlim(0, 10)
        
        # Create empty lines for vibration
        self.throttle_line, = self.ax_vibration.plot([], [], 'g-', 
            label=f'Throttle (Threshold: {wheel_slip_threshold:.1f}, Strength: {trigger_strength:.1f})', 
            linewidth=1.5)
        self.brake_line, = self.ax_vibration.plot([], [], 'r-', 
            label=f'Brake (Threshold: {wheel_slip_threshold:.1f}, Strength: {trigger_strength:.1f})', 
            linewidth=1.5)
        
        # Add legend with customized appearance
        legend = self.ax_vibration.legend(loc='upper right', fontsize='x-small')
        legend.get_frame().set_alpha(0.7)
        legend.get_frame().set_edgecolor('none')
        
        # Create canvas with improved layout
        self.canvas_vibration = FigureCanvasTkAgg(self.fig_vibration, master=content)
        self.canvas_vibration.draw()
        canvas_widget = self.canvas_vibration.get_tk_widget()
        canvas_widget.grid(row=0, column=0, sticky="nsew", padx=(0, 0))  # Remove horizontal padding
    
    def create_wheel_slip_graphs_section(self):
        """创建轮胎打滑图表部分"""
        # Create frame for wheel slip graph with collapsible feature
        self.slip_frame, content = self.create_collapsible_frame(self.main_frame, "Wheel Slip/Lock Status", 0, 0, columnspan=1)
        content.grid_columnconfigure(0, weight=1)  # 让内容区域可以横向扩展
        
        # Create figure with adjusted parameters
        self.fig_slip = Figure(figsize=(10, 2), dpi=100)
        self.fig_slip.patch.set_facecolor(self.theme_colors['light']['bg'])
        
        # Adjust subplot parameters to reduce margins
        self.fig_slip.subplots_adjust(left=0.05, right=0.98, top=0.95, bottom=0.15)
        
        # Create subplot for wheel slip
        self.ax_slip = self.fig_slip.add_subplot(111)
        self.ax_slip.set_facecolor(self.theme_colors['light']['canvas_bg'])
        self.ax_slip.grid(True, linestyle='--', alpha=0.7, color=self.theme_colors['light']['grid_color'])
        
        # Set labels and title
        # self.ax_slip.set_title('Wheel Slip/Lock Status')
        # self.ax_slip.set_xlabel('Time (seconds)')
        # self.ax_slip.set_ylabel('Slip/Lock %')
        
        # Set axis limits
        self.ax_slip.set_ylim(-100, 100)
        self.ax_slip.set_xlim(0, 10)
        
        # Add horizontal line at y=0
        self.ax_slip.axhline(y=0, color='k', linestyle='-', alpha=0.3)
        
        # Create empty lines for wheel slip
        self.fl_line, = self.ax_slip.plot([], [], color='#4169E1', label='Front Left', linewidth=1.5)
        self.fr_line, = self.ax_slip.plot([], [], color='#00BFFF', label='Front Right', linewidth=1.5)
        self.rl_line, = self.ax_slip.plot([], [], color='#FF4500', label='Rear Left', linewidth=1.5)
        self.rr_line, = self.ax_slip.plot([], [], color='#FFA500', label='Rear Right', linewidth=1.5)
        
        # Add legend with customized appearance
        legend_slip = self.ax_slip.legend(loc='upper right', ncol=2, fontsize='x-small')
        legend_slip.get_frame().set_alpha(0.7)
        legend_slip.get_frame().set_edgecolor('none')
        
        # Create canvas with improved layout
        self.canvas_slip = FigureCanvasTkAgg(self.fig_slip, master=content)
        self.canvas_slip.draw()
        canvas_widget = self.canvas_slip.get_tk_widget()
        canvas_widget.grid(row=0, column=0, sticky="nsew", padx=(0, 0))  # Remove horizontal padding
    
    def update_vibration_graphs(self, throttle_vibration, brake_vibration):
        """更新震动强度和轮胎打滑图表"""
        current_time = time.time() - self.start_time
        
        # Update vibration data
        self.time_data.append(current_time)
        self.throttle_data.append(throttle_vibration)
        self.brake_data.append(brake_vibration)
        
        # Update wheel slip data
        self.slip_time_data.append(current_time)
        self.fl_slip_data.append(self.current_fl_slip)
        self.fr_slip_data.append(self.current_fr_slip)
        self.rl_slip_data.append(self.current_rl_slip)
        self.rr_slip_data.append(self.current_rr_slip)
        
        # Convert to numpy arrays
        times = np.array(self.time_data)
        throttle_values = np.array(self.throttle_data)
        brake_values = np.array(self.brake_data)
        
        slip_times = np.array(self.slip_time_data)
        fl_values = np.array(self.fl_slip_data)
        fr_values = np.array(self.fr_slip_data)
        rl_values = np.array(self.rl_slip_data)
        rr_values = np.array(self.rr_slip_data)
        
        # Update vibration lines
        self.throttle_line.set_data(times, throttle_values)
        self.brake_line.set_data(times, brake_values)
        
        # Update wheel slip lines
        self.fl_line.set_data(slip_times, fl_values)
        self.fr_line.set_data(slip_times, fr_values)
        self.rl_line.set_data(slip_times, rl_values)
        self.rr_line.set_data(slip_times, rr_values)
        
        # Update x-axis limits to show last 10 seconds
        if len(times) > 0:
            current = times[-1]
            self.ax_vibration.set_xlim(max(0, current - 10), max(10, current))
            self.ax_slip.set_xlim(max(0, current - 10), max(10, current))
        
        # Redraw both canvases
        self.canvas_vibration.draw_idle()
        self.canvas_slip.draw_idle()
    
    def update_values(self, data):
        try:
            # 更新最后更新时间，防止watchdog重启线程
            self.last_update_time = time.time()
            
            # 无论GUI是否暂停，始终更新游戏内覆盖层
            if hasattr(self, 'overlay') and self.overlay is not None and self.show_overlay.get():
                # 如果悬浮窗应该显示但还没有显示，则显示它
                if not self.overlay.visible:
                    self.overlay.show()
                # 更新悬浮窗数据
                self.overlay.update_data(data)
            
            # 如果更新被暂停，则不更新GUI
            if hasattr(self, 'pause_updates') and self.pause_updates:
                return
                
            # Get current theme colors
            theme = 'dark' if self.is_dark_theme.get() else 'light'
            colors = self.theme_colors[theme]
            
            # Update car info
            self.car_speed_label.config(text=f"{data['car_speed']:.2f} km/h")
            self.ground_speed_label.config(text=f"{data['ground_speed']:.2f} km/h")
            self.rpm_label.config(text=f"{data['rpm']:.0f}")
            self.gear_label.config(text=f"{data['gear']}")
            
            # 更新水温并根据温度和主题改变颜色
            water_temp = data['water_temp']
            self.water_temp_label.config(text=f"{water_temp:.1f} °C")
            
            # 根据水温和当前主题设置颜色警告
            if water_temp >= 120:
                self.water_temp_label.config(foreground='#FF4444')  # 明亮的红色，适合两种主题
            elif water_temp >= 100:
                self.water_temp_label.config(foreground='#FFA500')  # 明亮的橙色，适合两种主题
            else:
                self.water_temp_label.config(foreground=colors['fg'])  # 使用主题对应的文字颜色
                
            self.turbo_pressure_label.config(text=f"{data['turbo_pressure']:.2f} bar")
            self.race_time_label.config(text=f"{data['race_time']:.2f} s")
            
            # 更新RPM进度条
            rpm_percentage = min(100, data['rpm'] / 8000 * 100)
            self.rpm_bar['value'] = rpm_percentage
            
            # 更新方向盘进度条
            steering = data['steering']  # 范围从-1到1
            self.steering_label.config(text=f"{steering:.2f}")
            
            # 获取当前Canvas的宽度
            left_width = self.steering_left_canvas.winfo_width()
            right_width = self.steering_right_canvas.winfo_width()
            
            # 重置两侧进度条
            self.steering_left_canvas.coords(self.steering_left_bar, left_width, 0, left_width, 20)
            self.steering_right_canvas.coords(self.steering_right_bar, 0, 0, 0, 20)
            
            # 更新方向盘进度条
            if steering < 0:  # 左转
                left_value = abs(steering) * left_width
                self.steering_left_canvas.coords(self.steering_left_bar, 
                    left_width - left_value, 0,  # 从右侧开始向左延伸
                    left_width, 20)
            elif steering > 0:  # 右转
                right_value = steering * right_width
                self.steering_right_canvas.coords(self.steering_right_bar,
                    0, 0,  # 从左侧开始向右延伸
                    right_value, 20)
            
            # Update control inputs with colored progress bars
            self.throttle_bar["value"] = data['throttle']
            self.throttle_label.config(text=f"{data['throttle']:.1f}%")
            
            self.brake_bar["value"] = data['brake']
            self.brake_label.config(text=f"{data['brake']:.1f}%")
            
            self.handbrake_bar["value"] = data['handbrake']
            self.handbrake_label.config(text=f"{data['handbrake']:.1f}%")
            
            self.clutch_bar["value"] = data['clutch']
            self.clutch_label.config(text=f"{data['clutch']:.1f}%")
            
            # Update vibration graphs if data is available
            if 'throttle_vibration' in data and 'brake_vibration' in data:
                self.update_vibration_graphs(data['throttle_vibration'], data['brake_vibration'])
            
            # 更新状态栏
            self.status_bar.config(text=f"Last update: {time.strftime('%H:%M:%S')} | FPS: {1/self.update_interval:.1f}")
            
            # 确保GUI更新
            if self.root.winfo_exists():  # 检查窗口是否仍然存在
                self.root.update_idletasks()
            
            # Store current slip values for graph updates
            self.current_fl_slip = data['slip_fl']
            self.current_fr_slip = data['slip_fr']
            self.current_rl_slip = data['slip_rl']
            self.current_rr_slip = data['slip_rr']
            
        except Exception as e:
            print(f"Error in update_values: {e}")
            import traceback
            traceback.print_exc()  # 打印完整的错误堆栈
            # Continue execution despite errors
    
    def start_dashboard(self):
        try:
            root = tk.Tk()
            app = TelemetryDashboard(root)
            
            # 创建一个事件标志，用于通知所有线程退出
            app.exit_event = threading.Event()
            
            # Create a watchdog thread to monitor the update thread
            def watchdog_thread():
                while not app.exit_event.is_set():
                    time.sleep(1.0)  # Check every second
                    if app.update_thread_running and time.time() - app.last_update_time > app.update_timeout:
                        print("Update thread appears to be stuck, restarting...")
                        app.update_thread_running = False
                        if app.update_thread and app.update_thread.is_alive():
                            # Cannot forcefully terminate thread in Python, but we can start a new one
                            pass
                        # Start a new update thread
                        if not app.exit_event.is_set():  # 确保在退出前不启动新线程
                            app.update_thread = threading.Thread(target=update_thread_function, daemon=True)
                            app.update_thread.start()
            
            # Start the watchdog thread
            watchdog = threading.Thread(target=watchdog_thread, daemon=True)
            watchdog.start()
            
            # Define the update thread function
            def update_thread_function():
                app.update_thread_running = True
                memory_reader = None
                
                try:
                    memory_reader = MemoryReader()
                    connected = memory_reader.connect()
                    
                    if not connected:
                        print("Failed to connect to the game process")
                        app.update_thread_running = False
                        return
                    
                    # Get the base address for telemetry data
                    base_address = memory_reader._get_module_base_address(memory_reader.process.pid, "RichardBurnsRally_SSE.exe")
                    if not base_address:
                        print("Failed to get base address")
                        app.update_thread_running = False
                        return
                    
                    # Offset to telemetry data structure
                    telemetry_offset = 0x6F8B60  # This offset might need to be updated based on the game version
                    
                    while app.update_thread_running and root.winfo_exists() and not app.exit_event.is_set():
                        try:
                            if not is_game_running():
                                print("Game process not found, waiting...")
                                time.sleep(1)
                                continue
                            
                            # 即使暂停更新，也继续读取数据，但不发送到GUI
                            # Read telemetry data
                            telemetry_address = base_address + telemetry_offset
                            telemetry_data = memory_reader.read_memory(telemetry_address, TelemetryData)
                            
                            # 只有在未暂停且窗口存在时才更新GUI
                            if telemetry_data and root.winfo_exists():
                                if not hasattr(app, 'pause_updates') or not app.pause_updates:
                                    # Use after method to update GUI from the main thread
                                    root.after(0, lambda td=telemetry_data: app.update_values(td))
                                else:
                                    # 即使暂停也更新最后更新时间，防止watchdog重启线程
                                    app.last_update_time = time.time()
                            
                            # 如果暂停了，可以降低更新频率以减少CPU使用
                            if hasattr(app, 'pause_updates') and app.pause_updates:
                                time.sleep(0.1)  # 暂停时降低到约10FPS
                            else:
                                # 使用用户设置的更新间隔
                                update_interval = getattr(app, 'update_interval', 0.016)  # 默认约60FPS
                                time.sleep(update_interval)
                        except Exception as e:
                            print(f"Error in update loop: {e}")
                            import traceback
                            traceback.print_exc()  # 打印完整的错误堆栈
                            time.sleep(0.5)  # Avoid tight error loop
                except Exception as e:
                    print(f"Critical error in update thread: {e}")
                    import traceback
                    traceback.print_exc()  # 打印完整的错误堆栈
                finally:
                    if memory_reader:
                        try:
                            memory_reader.close()
                        except:
                            pass
                    app.update_thread_running = False
                    print("Update thread has exited")
            
            # Start the update thread
            app.update_thread = threading.Thread(target=update_thread_function, daemon=True)
            app.update_thread.start()
            
            # Handle window close event
            def on_closing():
                print("Window closing, shutting down threads...")
                app.exit_event.set()  # 通知所有线程退出
                app.update_thread_running = False
                
                # 销毁游戏内覆盖层
                if hasattr(app, 'overlay') and app.overlay is not None:
                    app.overlay.destroy()
                
                # 给线程一些时间来清理
                time.sleep(0.2)
                
                # 确保安全销毁窗口
                try:
                    root.destroy()
                except:
                    pass
                
                print("Application shutdown complete")
            
            root.protocol("WM_DELETE_WINDOW", on_closing)
            
            # 设置窗口标题
            root.title("RBR Telemetry Dashboard")
            
            # 启动主循环
            root.mainloop()
            
        except Exception as e:
            print(f"Critical error in main application: {e}")
            import traceback
            traceback.print_exc()  # 打印完整的错误堆栈

# Determine the application path and resource path
if getattr(sys, 'frozen', False):
    # If the application is run as a bundle
    application_path = os.path.dirname(sys.executable)
    resource_path = sys._MEIPASS
else:
    # If the application is run as a script
    application_path = os.path.dirname(os.path.abspath(__file__))
    resource_path = application_path

# Construct the paths
config_path = os.path.join(application_path, 'config.ini')
haptics_path = os.path.join(resource_path, 'haptics')

# Read configuration
config = configparser.ConfigParser()

# Check if external config file exists, if not use the default one
if os.path.exists(config_path):
    config.read(config_path)
else:
    # Use default configuration
    config['Features'] = {
        'adaptive_trigger': 'True',
        'led_effect': 'True',
        'haptic_effect': 'True',
        'print_telemetry': 'True',
        'use_gui_dashboard': 'True'  
    }
    config['Network'] = {
        'udp_port': '6776'
    }
    # 添加新的配置部分：反馈强度设置
    config['Feedback'] = {
        'trigger_strength': '1.5',      # 自适应扳机强度系数 (0.1-2.0)
        'haptic_strength': '0.5',       # Haptic震动反馈强度系数 (0-1.0)
        'wheel_slip_threshold': '10.0',  # 轮胎侧滑检测的灵敏度。值越小，越容易检测到侧滑。 (1.0-20.0)
        'trigger_threshold': '10.0'      # 触发Haptic震动的侧滑阈值 (1.0-20.0)
    }
    # 添加GUI设置
    config['GUI'] = {
        'fps': '60.0',                  # GUI更新帧率 (10-60)
        'pause_updates': 'False'        # 是否暂停GUI更新
    }
    # 添加UI设置
    config['UI'] = {
        'show_overlay': 'False',        # 是否显示游戏内覆盖层
        'overlay_x': '',                # 悬浮窗X坐标（空表示使用默认位置）
        'overlay_y': ''                 # 悬浮窗Y坐标（空表示使用默认位置）
    }
    # Write the default configuration to an external file with comments
    with open(config_path, 'w', encoding='utf-8') as configfile:
        # Write Features section with comments
        configfile.write("[Features]\n")
        configfile.write("adaptive_trigger = True\n")
        configfile.write("led_effect = True\n")
        configfile.write("haptic_effect = True\n")
        configfile.write("print_telemetry = True\n")
        configfile.write("use_gui_dashboard = True\n")
        configfile.write("\n")
        
        # Write Network section with comments
        configfile.write("[Network]\n")
        configfile.write("udp_port = 6776\n")
        configfile.write("\n")
        
        # Write Feedback section with detailed comments
        configfile.write("[Feedback]\n")
        configfile.write("trigger_strength = 1.5\n")
        configfile.write("haptic_strength = 0.5\n")
        configfile.write("wheel_slip_threshold = 10.0\n")
        configfile.write("trigger_threshold = 10.0\n")
        configfile.write("\n")
        
        # Write GUI section with comments
        configfile.write("[GUI]\n")
        configfile.write("fps = 60.0\n")
        configfile.write("pause_updates = False\n")
    
    print(f"Created default configuration file at {config_path}")

# Get feature settings
adaptive_trigger_enabled = config.getboolean('Features', 'adaptive_trigger', fallback=True)
led_effect_enabled = config.getboolean('Features', 'led_effect', fallback=True)
haptic_effect_enabled = config.getboolean('Features', 'haptic_effect', fallback=True)
print_telemetry_enabled = config.getboolean('Features', 'print_telemetry', fallback=True)
use_gui_dashboard = config.getboolean('Features', 'use_gui_dashboard', fallback=True)

# 获取反馈强度设置
trigger_strength = config.getfloat('Feedback', 'trigger_strength', fallback=1.0)
haptic_strength = config.getfloat('Feedback', 'haptic_strength', fallback=1.0)
wheel_slip_threshold = config.getfloat('Feedback', 'wheel_slip_threshold', fallback=10.0)
trigger_threshold = config.getfloat('Feedback', 'trigger_threshold', fallback=1.0)

# 确保值在合理范围内
trigger_strength = max(0.1, min(2.0, trigger_strength))
haptic_strength = max(0, min(1.0, haptic_strength))
wheel_slip_threshold = max(1.0, min(20.0, wheel_slip_threshold))
trigger_threshold = max(1.0, min(20.0, trigger_threshold))

# Get network settings
UDP_PORT = config.getint('Network', 'udp_port', fallback=6778)

# Define UDP port
UDP_IP = "127.0.0.1"
UDP_DSX_PORT = 6969

# Initialize the dashboard if GUI is enabled
if use_gui_dashboard:
    # Create a separate thread for the Tkinter GUI
    def start_dashboard():
        global dashboard
        root = tk.Tk()
        dashboard = TelemetryDashboard(root)
        root.mainloop()
    
    dashboard_thread = threading.Thread(target=start_dashboard, daemon=True)
    dashboard_thread.start()
    print("Telemetry dashboard started in GUI mode")
else:
    print("Telemetry dashboard running in console mode")

# Initialize memory reader
rbr_memory_reader = None
try:
    rbr_memory_reader = MemoryReader()
except Exception as e:
    print(f"Failed to initialize memory reader: {e}")
    print("Telemetry data will not be available")

# Create UDP socket for DSX controller
sock_dsx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# Initialize variables for telemetry data
car_speed = 0
rpm = 0
water_temp = 0
turbo_pressure = 0
distance_from_start = 0
distance_travelled = 0
distance_to_finish = 0
race_time = 0
session_time = 0
stage_progress = 0
wrong_way = False
split1_done = False
split2_done = False
race_ended = False
split1_time = 0
split2_time = 0
gear_id = 0
false_start = False
stage_start_countdown = 0
engine_on = False
x_spin = 0
y_spin = 0
z_spin = 0
x_speed = 0
y_speed = 0
z_speed = 0
x_pos = 0
y_pos = 0
z_pos = 0
roll = 0
pitch = 0
yaw = 0
steering = 0
throttle = 0
brake = 0
handbrake = 0
clutch = 0
ffb_value = 0
wheel_speed_fl = 0
wheel_speed_fr = 0
wheel_speed_rl = 0
wheel_speed_rr = 0
ground_speed = 0

# Initialize previous RPM and last rumble time
previous_rpm = 0
last_rumble_time = 0
RUMBLE_INTERVAL = 2.79  # Interval in seconds for rumble effect

# Initialize haptic feedback state variables
wheel_slip_rumble_active = False

# Initialize previous gear
previous_gear = None

# Add these new functions and variables

best_records = {}
current_record = []
last_record_time = 0
RECORD_INTERVAL = 0.2  # 200ms

def load_best_records():
    if os.path.exists('best_records.json'):
        with open('best_records.json', 'r') as f:
            return json.load(f)
    return {}

def save_best_records(records):
    with open('best_records.json', 'w') as f:
        json.dump(records, f)

def calculate_time_difference(current_record, best_record):
    if not best_record or not current_record:
        return None
    
    current_distance = current_record[-1][0]
    
    for i, (distance, time) in enumerate(best_record):
        if distance >= current_distance:
            if i > 0:
                # Interpolate between the two closest points
                prev_distance, prev_time = best_record[i-1]
                fraction = (current_distance - prev_distance) / (distance - prev_distance)
                interpolated_time = prev_time + fraction * (time - prev_time)
            else:
                interpolated_time = time
            
            return current_record[-1][1] - interpolated_time
    
    return None

# Load best records at the start of the script
best_records = load_best_records()

current_stage = -1
current_record = []

# Add wheel speed variables
wheel_speed_fl = 0
wheel_speed_fr = 0
wheel_speed_rl = 0
wheel_speed_rr = 0

# Add variables for heartbeat detection
last_valid_telemetry_time = 0
telemetry_timeout = 0.5  # seconds - if no valid telemetry for this duration, assume game is paused/loading
force_stop_vibration = False

# Add this function to check if the game is running
def is_game_running(process_name="RichardBurnsRally_SSE.exe"):
    return get_process_by_name(process_name) is not None

# Initialize dashboard
dashboard = None
dashboard_update_interval = 1/60  # 刷新率改成60
last_dashboard_update = 0

# Modify the main loop to handle game exit and restart better
while True:
    current_time = time.time()
    
    # Check if game is running
    game_running = is_game_running()
    
    # If game is not running, reset memory reader and wait
    if not game_running:
        if rbr_memory_reader and rbr_memory_reader.is_connected:
            rbr_memory_reader.show_errors = False  # Suppress error messages during shutdown
            print("Game has exited. Waiting for restart...")
            rbr_memory_reader.close()
            rbr_memory_reader = None  # Completely release the memory reader
        
        # Set default values for telemetry data
        rpm = 0
        car_speed = 0
        gear_id = 0
        # Reset other telemetry variables as needed
        
        # Send a packet to reset controller - avoid using ResetToUserSettings
        reset_packet = Packet([
            # Instead of ResetToUserSettings, use individual reset instructions
            Instruction(InstructionType.TriggerUpdate, [0, Trigger.Left, TriggerMode.Normal, 0, 0, 0]),
            Instruction(InstructionType.TriggerUpdate, [0, Trigger.Right, TriggerMode.Normal, 0, 0, 0]),
            Instruction(InstructionType.RGBUpdate, [0, 0, 0, 0])
        ])
        
        try:
            sock_dsx.sendto(json.dumps(reset_packet.to_dict()).encode(), (UDP_IP, UDP_DSX_PORT))
        except Exception as e:
            print(f"Error sending reset data to controller: {e}")
        
        # Wait before checking again
        time.sleep(2)
        continue
    
    # Try to connect if not connected or if memory reader is None
    if rbr_memory_reader is None:
        # Create a new memory reader instance
        rbr_memory_reader = MemoryReader(process_name="RichardBurnsRally_SSE.exe")
        print("Game detected. Creating new memory reader...")
    elif not rbr_memory_reader.is_connected:
        print("Game detected. Attempting to connect...")
        rbr_memory_reader.show_errors = True  # Re-enable error messages when reconnecting
        if rbr_memory_reader.connect():
            print("Successfully reconnected to the game!")
        else:
            print("Failed to connect. Will retry...")
            time.sleep(1)
            continue
    
    # Instead of waiting for UDP data, we'll read directly from memory
    if rbr_memory_reader and rbr_memory_reader.is_connected:
        try:
            # Get base addresses as in Read_RBRData.cs
            num = rbr_memory_reader.read_int(23460968)
            num2 = rbr_memory_reader.read_int(8301640)
            num3 = rbr_memory_reader.read_int(9369184)
            num4 = rbr_memory_reader.read_int(23433604)
            adress = rbr_memory_reader.read_int(8301640) + 3076 if num2 else None
            num5 = rbr_memory_reader.read_int(rbr_memory_reader.base_address + 4796472) if rbr_memory_reader.base_address else None
            
            if num5:
                num5 = rbr_memory_reader.read_int(num5 + 1032)
                if num5:
                    num5 = rbr_memory_reader.read_int(num5 + 64)
            
            # Read game state to check if we're in race
            game_state_id = rbr_memory_reader.read_byte(num2 + 1848 - 16) if num2 else 0
            
            # Only read telemetry if we're in race state and all addresses are valid
            if game_state_id > 0 and num and num2 and num3:  # Check that addresses are valid
                # Read wheel speeds
                if num5:
                    wheel_speed_fl = rbr_memory_reader.read_float(num5 + 988) * 3.6  # Convert to km/h
                    wheel_speed_fr = rbr_memory_reader.read_float(num5 + 1676) * 3.6
                    wheel_speed_rl = rbr_memory_reader.read_float(num5 + 2364) * 3.6
                    wheel_speed_rr = rbr_memory_reader.read_float(num5 + 3052) * 3.6
                
                # Read car info
                if num:
                    car_speed = rbr_memory_reader.read_float(num + 12)
                    rpm = rbr_memory_reader.read_float(num + 16)
                    water_temp = rbr_memory_reader.read_float(num + 20)
                    turbo_pressure = rbr_memory_reader.read_float(num + 24) / 1000 / 100  # Convert to bar
                    distance_from_start = rbr_memory_reader.read_float(num + 32)
                    distance_travelled = rbr_memory_reader.read_float(num + 36)
                    distance_to_finish = rbr_memory_reader.read_float(num + 40)
                    stage_progress = rbr_memory_reader.read_float(num + 0x13C)
                    race_time = rbr_memory_reader.read_float(num + 0x140)
                    race_ended = rbr_memory_reader.read_int(num + 0x144) == 1
                    wrong_way = rbr_memory_reader.read_int(num + 0x150) == 1
                    gear_id = rbr_memory_reader.read_int(num + 0x170) - 1  # Adjust gear value
                    stage_start_countdown = rbr_memory_reader.read_float(num + 0x244)
                    false_start = rbr_memory_reader.read_int(num + 0x248) == 1
                    split1_done = rbr_memory_reader.read_int(num + 0x254) >= 1
                    split2_done = rbr_memory_reader.read_int(num + 0x254) >= 2
                    split1_time = rbr_memory_reader.read_float(num + 0x258)
                    split2_time = rbr_memory_reader.read_float(num + 0x25C)
                    race_ended = rbr_memory_reader.read_int(num + 0x2C4) == 1
                    
                    # Update heartbeat timestamp when valid telemetry data is received
                    last_valid_telemetry_time = current_time
                
                # Read car movement data
                if num3:
                    x_spin = rbr_memory_reader.read_float(num3 + 400)
                    y_spin = rbr_memory_reader.read_float(num3 + 404)
                    z_spin = rbr_memory_reader.read_float(num3 + 408)
                    x_speed = rbr_memory_reader.read_float(num3 + 448)
                    y_speed = rbr_memory_reader.read_float(num3 + 452)
                    z_speed = rbr_memory_reader.read_float(num3 + 456)
                    x_pos = rbr_memory_reader.read_float(num3 + 320)
                    y_pos = rbr_memory_reader.read_float(num3 + 324)
                    z_pos = rbr_memory_reader.read_float(num3 + 328)
                    
                    # Calculate angles
                    sin_a = rbr_memory_reader.read_float(num3 + 272)
                    cos_a = rbr_memory_reader.read_float(num3 + 276)
                    num6 = rbr_memory_reader.read_float(num3 + 280)
                    num7 = rbr_memory_reader.read_float(num3 + 292)
                    
                    # These calculations are approximations of the C# code
                    roll = -(num6 * 180) / 3.14159
                    pitch = -(num7 * 180) / 3.14159
                    # For yaw, we need to implement SinCos2AngleRadian
                    yaw = -(math.atan2(sin_a, cos_a) * 180) / 3.14159
                    
                    # Calculate ground speed
                    ground_speed = math.sqrt(x_speed**2 + y_speed**2 + z_speed**2)
                
                # Read control inputs
                if num2:
                    steering = rbr_memory_reader.read_float(num2 + 1848 + 92)
                    throttle = rbr_memory_reader.read_float(num2 + 1848 + 96) * 100  # Convert to percentage
                    brake = rbr_memory_reader.read_float(num2 + 1848 + 100) * 100
                    handbrake = rbr_memory_reader.read_float(num2 + 1848 + 104) * 100
                    clutch = rbr_memory_reader.read_float(num2 + 1848 + 108) * 100
                
                # Read FFB value
                if adress:
                    ffb_value = rbr_memory_reader.read_float(adress)
                
                # Print debug info or update dashboard
                current_time = time.time()
                
                if use_gui_dashboard and dashboard and current_time - last_dashboard_update >= dashboard_update_interval:
                    # Update the dashboard with current telemetry data
                    if ground_speed * 3.6 > 5:  # Convert to km/h for comparison
                        # Calculate wheel slip percentages if car is moving
                        ground_speed_kmh = ground_speed * 3.6
                        fl_slip = ((wheel_speed_fl / ground_speed_kmh) - 1) * 100
                        fr_slip = ((wheel_speed_fr / ground_speed_kmh) - 1) * 100
                        rl_slip = ((wheel_speed_rl / ground_speed_kmh) - 1) * 100
                        rr_slip = ((wheel_speed_rr / ground_speed_kmh) - 1) * 100
                    else:
                        fl_slip = fr_slip = rl_slip = rr_slip = 0
                    
                    # Calculate vibration intensities
                    throttle_vibration = 0
                    brake_vibration = 0
                    
                    if ground_speed * 3.6 > 5:  # Only calculate when moving faster than 5 km/h
                        # Calculate throttle vibration based on wheel spin
                        if throttle > 50:
                            # Calculate maximum wheel spin using configured threshold
                            max_spin = max(
                                fl_slip if fl_slip > wheel_slip_threshold else 0,
                                fr_slip if fr_slip > wheel_slip_threshold else 0,
                                rl_slip if rl_slip > wheel_slip_threshold else 0,
                                rr_slip if rr_slip > wheel_slip_threshold else 0
                            )
                            
                            # Apply vibration if spin exceeds trigger threshold
                            if max_spin > trigger_threshold:
                                # Calculate the intensity based on the maximum slip or lock
                                max_slip_intensity = max(
                                    min(1.0, (max_spin - trigger_threshold) / 50),
                                    min(1.0, (max_spin - trigger_threshold) / 50)
                                )
                                # Apply the user's haptic strength setting
                                final_intensity = max_slip_intensity * haptic_strength
                                
                                throttle_vibration = min(1.0, final_intensity)
                        
                        # Calculate brake vibration based on wheel lock
                        if brake > 30:
                            # Calculate maximum wheel lock using configured threshold
                            max_lock = max(
                                abs(fl_slip) if fl_slip < -wheel_slip_threshold else 0,
                                abs(fr_slip) if fr_slip < -wheel_slip_threshold else 0,
                                abs(rl_slip) if rl_slip < -wheel_slip_threshold else 0,
                                abs(rr_slip) if rr_slip < -wheel_slip_threshold else 0
                            )
                            
                            # Apply vibration if lock exceeds trigger threshold
                            if max_lock > trigger_threshold:
                                # Calculate the intensity based on the maximum slip or lock
                                max_slip_intensity = max(
                                    min(1.0, (max_lock - trigger_threshold) / 50),
                                    min(1.0, (max_lock - trigger_threshold) / 50)
                                )
                                # Apply the user's haptic strength setting
                                final_intensity = max_slip_intensity * haptic_strength
                                
                                brake_vibration = min(1.0, final_intensity)
                    
                    # Update dashboard with all telemetry data
                    dashboard.update_values({
                        'car_speed': car_speed,
                        'ground_speed': ground_speed * 3.6,
                        'rpm': rpm,
                        'gear': gear_id,
                        'water_temp': water_temp,
                        'turbo_pressure': turbo_pressure,
                        'race_time': race_time,
                        'wheel_fl': wheel_speed_fl,
                        'wheel_fr': wheel_speed_fr,
                        'wheel_rl': wheel_speed_rl,
                        'wheel_rr': wheel_speed_rr,
                        'slip_fl': fl_slip,
                        'slip_fr': fr_slip,
                        'slip_rl': rl_slip,
                        'slip_rr': rr_slip,
                        'throttle': throttle,
                        'brake': brake,
                        'handbrake': handbrake,
                        'clutch': clutch,
                        'steering': steering,
                        'throttle_vibration': throttle_vibration,  # Add vibration data
                        'brake_vibration': brake_vibration  # Add vibration data
                    })
                    last_dashboard_update = current_time
                
                elif print_telemetry_enabled and not use_gui_dashboard:
                    # Only print to console if GUI dashboard is disabled
                    print(chr(27) + "[2J")  # clear screen
                    print(chr(27) + "[H")   # return to home
                    print(f"Car Speed: {car_speed:.2f} km/h")
                    print(f"Ground Speed: {ground_speed*3.6:.2f} km/h")
                    print(f"RPM: {rpm:.0f}")
                    print(f"Gear: {gear_id}")
                    print(f"Water Temp: {water_temp:.1f}°C")
                    print(f"Turbo Pressure: {turbo_pressure:.2f} bar")
                    print(f"Race Time: {race_time:.2f} s")
                    print(f"Throttle: {throttle:.1f}%")
                    print(f"Brake: {brake:.1f}%")
                    print(f"Handbrake: {handbrake:.1f}%")
                    print(f"Clutch: {clutch:.1f}%")
                    print(f"Steering: {steering:.2f}")
                    
                    print(f"\nWheel Speeds:")
                    print(f"Front Left: {wheel_speed_fl:.2f} km/h")
                    print(f"Front Right: {wheel_speed_fr:.2f} km/h")
                    print(f"Rear Left: {wheel_speed_rl:.2f} km/h")
                    print(f"Rear Right: {wheel_speed_rr:.2f} km/h")
            
        except Exception as e:
            print(f"Error reading memory: {e}")
            # If we encounter an error, check if the game is still running
            if not is_game_running():
                print("Game has exited.")
                if rbr_memory_reader:
                    rbr_memory_reader.show_errors = False  # Suppress errors during shutdown
                    rbr_memory_reader.close()
                    rbr_memory_reader = None  # Completely release the memory reader
            else:
                # Try to reconnect if we lost connection but game is still running
                print("Lost connection to game. Attempting to reconnect...")
                if rbr_memory_reader:
                    rbr_memory_reader.connect()
            
            # Set default values for telemetry
            rpm = 0
            car_speed = 0
            # Reset other telemetry variables as needed
            time.sleep(1)  # Add a small delay to avoid spamming errors
            continue  # Skip the rest of the loop
    else:
        # Try to connect to RBR process
        if rbr_memory_reader is None:
            # Create a new memory reader instance
            rbr_memory_reader = MemoryReader(process_name="RichardBurnsRally_SSE.exe")
        else:
            rbr_memory_reader.connect()
        time.sleep(1)  # Don't spam reconnection attempts
        continue  # Skip the rest of the loop if not connected
    
    # define packet for DualSense controller
    packet = Packet([])

    ###################################################################################
    # Adaptive Trigger
    ###################################################################################
    
    if adaptive_trigger_enabled:
        # Default trigger modes
        left_mode = TriggerMode.Normal
        right_mode = TriggerMode.Normal
        
        # Default strength parameters - 应用配置的强度系数
        left_strength = 1 * trigger_strength
        right_strength = 1 * trigger_strength
        
        # Only apply effects when car is moving at a reasonable speed
        if ground_speed * 3.6 > 5:  # Convert to km/h for comparison
            # Convert ground_speed from m/s to km/h for consistent units
            ground_speed_kmh = ground_speed * 3.6
            
            # Calculate wheel slip percentages - same as in telemetry display
            fl_slip = ((wheel_speed_fl / ground_speed_kmh) - 1) * 100
            fr_slip = ((wheel_speed_fr / ground_speed_kmh) - 1) * 100
            rl_slip = ((wheel_speed_rl / ground_speed_kmh) - 1) * 100
            rr_slip = ((wheel_speed_rr / ground_speed_kmh) - 1) * 100
            
            # Check for front wheel lock (for left trigger - brake)
            if (fl_slip < -wheel_slip_threshold or fr_slip < -wheel_slip_threshold) and brake > 30:
                # Front wheel lock detected - provide feedback on left trigger
                left_mode = TriggerMode.VibrateTriggerPulse
                # Increase strength based on how severe the lock is
                max_lock = min(fl_slip, fr_slip)
                left_strength = min(8, 2 + abs(max_lock) / 10) * trigger_strength  # 应用配置的强度系数
            
            # Check for wheel spin on any wheel when throttle is applied
            # This handles FWD, RWD, and AWD vehicles
            if throttle > 50:
                max_spin = max(fl_slip if fl_slip > wheel_slip_threshold else 0, 
                              fr_slip if fr_slip > wheel_slip_threshold else 0,
                              rl_slip if rl_slip > wheel_slip_threshold else 0,
                              rr_slip if rr_slip > wheel_slip_threshold else 0)
                
                if max_spin > wheel_slip_threshold:  # Any wheel is spinning
                    # Wheel spin detected - provide feedback on right trigger
                    right_mode = TriggerMode.VibrateTriggerPulse
                    # Increase strength based on how severe the spin is
                    right_strength = min(8, 2 + max_spin / 10) * trigger_strength  # 应用配置的强度系数
            
            # Check for rear wheel lock with handbrake
            elif (rl_slip < -wheel_slip_threshold or rr_slip < -wheel_slip_threshold) and (handbrake > 30 or brake > 80) and throttle > 30:
                # Rear wheel lock with handbrake + throttle scenario
                right_mode = TriggerMode.VibrateTriggerPulse
                # Increase strength based on how severe the lock is
                max_lock = min(rl_slip, rr_slip)
                right_strength = min(8, 2 + abs(max_lock) / 10) * trigger_strength  # 应用配置的强度系数

        packet.instructions.append(Instruction(InstructionType.TriggerUpdate, [0, Trigger.Left, left_mode, left_strength, 0, 0]))
        packet.instructions.append(Instruction(InstructionType.TriggerUpdate, [0, Trigger.Right, right_mode, right_strength, 0, 0]))

    ###################################################################################
    # LED Effect
    ###################################################################################
    
    if led_effect_enabled:
        # Calculate RPM percentage - use car-specific max RPM
        # Different cars have different redlines, so adjust this value based on the car
        max_rpm = 7500  # Increased from 7000 to better match RBR cars
        
        # Ensure RPM is valid before calculating percentage
        if rpm > 0 and game_running and game_state_id > 0:  # Only process when in race with valid RPM
            rpm_percentage = min(100, (rpm / max_rpm) * 100)
            
            # Determine LED color based on RPM
            if rpm_percentage < RPM_GREEN_THRESHOLD:
                # Green
                r, g, b = 0, 255, 0
            elif rpm_percentage < RPM_YELLOW_THRESHOLD:
                # Green to Yellow transition
                factor = (rpm_percentage - RPM_GREEN_THRESHOLD) / (RPM_YELLOW_THRESHOLD - RPM_GREEN_THRESHOLD)
                r, g, b = interpolate_color([0, 255, 0], [255, 255, 0], factor)
            elif rpm_percentage < RPM_RED_THRESHOLD:
                # Yellow to Red transition
                factor = (rpm_percentage - RPM_YELLOW_THRESHOLD) / (RPM_RED_THRESHOLD - RPM_YELLOW_THRESHOLD)
                r, g, b = interpolate_color([255, 255, 0], [255, 0, 0], factor)
            else:
                # Red - at or near redline
                r, g, b = 255, 0, 0
            
            # Send RGB update instruction
            packet.instructions.append(Instruction(InstructionType.RGBUpdate, [0, r, g, b]))
        else:
            # If RPM is invalid or not in race, set LED to off/dim
            packet.instructions.append(Instruction(InstructionType.RGBUpdate, [0, 0, 0, 0]))

    ###################################################################################
    # Haptic Effect
    ###################################################################################
    
    if haptic_effect_enabled:
        # Add traction loss feedback based on wheel slip
        if ground_speed * 3.6 > 5:  # Only when car is moving at a reasonable speed
            # Calculate wheel slip percentages - same as in telemetry display
            if 'fl_slip' in locals() and 'fr_slip' in locals() and 'rl_slip' in locals() and 'rr_slip' in locals():
                # Check for significant wheel slip (either spin or lock)
                max_spin = max(fl_slip if fl_slip > wheel_slip_threshold else 0,
                              fr_slip if fr_slip > wheel_slip_threshold else 0, 
                              rl_slip if rl_slip > wheel_slip_threshold else 0, 
                              rr_slip if rr_slip > wheel_slip_threshold else 0)
                
                max_lock = max(abs(fl_slip) if fl_slip < -wheel_slip_threshold else 0,
                              abs(fr_slip) if fr_slip < -wheel_slip_threshold else 0, 
                              abs(rl_slip) if rl_slip < -wheel_slip_threshold else 0, 
                              abs(rr_slip) if rr_slip < -wheel_slip_threshold else 0)
                
                # Determine if we have significant traction loss
                if max_spin > trigger_threshold or max_lock > trigger_threshold:
                    # Calculate the intensity based on the maximum slip or lock
                    max_slip_intensity = max(
                        min(1.0, (max_spin - trigger_threshold) / 50),
                        min(1.0, (max_lock - trigger_threshold) / 50)
                    )
                    # Apply the user's haptic strength setting
                    final_intensity = max_slip_intensity * haptic_strength
                    
                    # Start wheel slip rumble if not already active
                    if not wheel_slip_rumble_active:
                        packet.instructions.append(Instruction(InstructionType.HapticFeedback, [
                            os.path.join(haptics_path, "rumble_mid_4c.wav"), True, True
                        ]))
                        wheel_slip_rumble_active = True
                    
                    # Use the calculated intensity
                    packet.instructions.append(Instruction(InstructionType.EditAudio, [
                        os.path.join(haptics_path, "rumble_mid_4c.wav"), AudioEditType.Volume, final_intensity
                    ]))
                    
                    # Add extra rumble effect for severe slip conditions
                    if (max_spin > 40 or max_lock > 40) and (current_time - last_rumble_time > 0.3):
                        packet.instructions.append(Instruction(InstructionType.HapticFeedback, [
                            os.path.join(haptics_path, "rumble_mid_4c.wav"), False, False
                        ]))
                        last_rumble_time = current_time
                else:
                    # Stop wheel slip rumble if active
                    if wheel_slip_rumble_active:
                        packet.instructions.append(Instruction(InstructionType.EditAudio, [
                            os.path.join(haptics_path, "rumble_mid_4c.wav"), AudioEditType.Stop, 0
                        ]))
                        wheel_slip_rumble_active = False
        elif wheel_slip_rumble_active:
            # Stop wheel slip rumble if car is not moving fast enough
            packet.instructions.append(Instruction(InstructionType.EditAudio, [
                os.path.join(haptics_path, "rumble_mid_4c.wav"), AudioEditType.Stop, 0
            ]))
            wheel_slip_rumble_active = False

    # Update previous values for next iteration
    previous_gear = gear_id
    previous_rpm = rpm
    
    # Check if we need to force stop vibration due to timeout (game paused or loading)
    if current_time - last_valid_telemetry_time > telemetry_timeout:
        if wheel_slip_rumble_active and not force_stop_vibration:
            # Game might be paused or in loading screen, stop all vibrations
            force_stop_packet = Packet([
                Instruction(InstructionType.EditAudio, [
                    os.path.join(haptics_path, "rumble_mid_4c.wav"), AudioEditType.Stop, 0
                ]),
                # Also reset triggers to normal mode
                Instruction(InstructionType.TriggerUpdate, [0, Trigger.Left, TriggerMode.Normal, 0, 0, 0]),
                Instruction(InstructionType.TriggerUpdate, [0, Trigger.Right, TriggerMode.Normal, 0, 0, 0])
            ])
            try:
                sock_dsx.sendto(json.dumps(force_stop_packet.to_dict()).encode(), (UDP_IP, UDP_DSX_PORT))
                wheel_slip_rumble_active = False
                force_stop_vibration = True
                print("Game paused or loading detected - stopping vibration")
            except Exception as e:
                print(f"Error sending stop vibration command: {e}")
    else:
        # Reset force stop flag when valid telemetry is received again
        force_stop_vibration = False
    
    # Send packet to DualSense controller (only if not in force stop mode)
    if not force_stop_vibration:
        try:
            sock_dsx.sendto(json.dumps(packet.to_dict()).encode(), (UDP_IP, UDP_DSX_PORT))
        except Exception as e:
            print(f"Error sending data to controller: {e}")
    
    # Sleep to maintain update rate
    try:
        time.sleep(max(0, 0.01 - (time.time() - current_time)))  # Target 100Hz update rate
    except ValueError:
        # Handle case where sleep time calculation is negative
        pass