import socket
import struct
import json
from enum import Enum
from ctypes import *
import serial
import time
import os
import sys

# Define trigger modes
class TriggerMode(Enum):
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

class CustomTriggerValueMode(Enum):
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

class PlayerLEDNewRevision(Enum):
    One = 0
    Two = 1
    Three = 2
    Four = 3
    Five = 4  # Five is Also All On
    AllOff = 5

class MicLEDMode(Enum):
    On = 0
    Pulse = 1
    Off = 2

class Trigger(Enum):
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
    HapticFeedback = 8

class Instruction:
    def __init__(self, instruction_type, parameters):
        self.type = instruction_type
        self.parameters = parameters

    def to_dict(self):
        return {
            "type": self.type.name,
            "parameters": self.parameters
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

# Define UDP port
UDP_IP = "127.0.0.1"
UDP_PORT = 6778
UDP_DSX_PORT = 6969

# Create UDP socket
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((UDP_IP, UDP_PORT))
sock_dsx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# Define RPM threshold variables
RPM_GREEN = 50  # Below this percentage, color is green
RPM_RED = 80    # Below this percentage, color transitions from yellow to red. Above RPM_RED, color is fully red
RPM_YELLOW = (RPM_GREEN + RPM_RED) / 2  # Below this percentage, color transitions from green to yellow


def interpolate_color(start_color, end_color, factor):
    return [int(start + (end - start) * factor) for start, end in zip(start_color, end_color)]

if getattr(sys, 'frozen', False):
    # 如果是打包后的可执行文件
    dir_path = os.path.join(sys._MEIPASS, "haptics")
else:
    # 如果是正常运行的脚本
    dir_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "haptics")

# Initialize previous RPM and last rumble time
last_rumble_time = 0
RUMBLE_INTERVAL = 0.5  # Interval in seconds for rumble effect

# Initialize previous gear
previous_gear = None

# serial port setup
def open_serial_port():
    while True:
        try:
            ser = serial.Serial('COM6', 115200, timeout=1, 
                                bytesize=serial.EIGHTBITS,
                                parity=serial.PARITY_NONE,
                                stopbits=serial.STOPBITS_ONE)
            # print(f"Serial port opened successfully: {ser}")
            return ser
        except serial.SerialException as e:
            print(f"Failed to open serial port: {e}")
            print("Retrying in 5 seconds...")
            time.sleep(5)

ser = open_serial_port()

def read_serial_data(ser):
    try:
        # Clear input buffer
        ser.reset_input_buffer()
        # Read raw bytes with a timeout
        raw_data = ser.read(36)
        
        if raw_data:
            # Try to decode as UTF-8, ignoring or replacing invalid bytes
            try:
                line = raw_data.decode('utf-8', errors='replace').strip()
                # print(f"Raw data received: {line}")
                return line
            except UnicodeDecodeError:
                print(f"Unable to decode data as UTF-8: {raw_data}")
                return None
        else:
            # print("No data received within timeout period")
            return None
    except serial.SerialException as e:
        print(f"Serial port error: {e}")
        return None

def get_telemetry_simhub(keys_to_print=None):
    while True: 
        # Read data from COM port
        line = read_serial_data(ser)
        
        if line:
            # print(line)
            # Split the line into individual data pairs
            data_pairs = line.split(';')
            
            # Create a dictionary to store the latest values
            telemetry_data = {}
            
            # Process each data pair
            for pair in data_pairs:
                if pair:  # Ensure the pair is not empty
                    key, value = pair.split(':')
                    telemetry_data[key] = value
            
            # Print the selected telemetry data
            # print("Selected Telemetry Data:")
            if keys_to_print:
                for key in keys_to_print:
                    if key in telemetry_data:
                        return (telemetry_data[key])
            # else:
            #     # If no keys specified, print all data
            #     for key, value in telemetry_data.items():
            #         print(f"{key}: {value}")

while True: 

    current_time = time.time()

    ###################################################################################
    # Read Data from COM Port
    ###################################################################################

    lock = float(get_telemetry_simhub(['LOCK']))
    slip = float(get_telemetry_simhub(['SLIP']))
    rpmPercentage = float(get_telemetry_simhub(['RPM']))
    gear = get_telemetry_simhub(['GEAR'])

    ###################################################################################
    # Print Telemetry Data
    ###################################################################################

    # Print all telemetry data
    print(chr(27) + "[2J")  # clear screen using escape sequences
    print(chr(27) + "[H")   # return to home using escape sequences

    print(f"Lock: {lock}, Slip: {slip}, RPM: {rpmPercentage}, Gear: {gear}")

    # Use these values in your existing logic for adaptive triggers, LED lights, etc.

    ###################################################################################
    # Adaptive Trigger
    ###################################################################################

    # 创建packet
    packet = Packet([])
    
    # # Define thresholds for lock and slip
    # LOCK = 50  # Adjust this value based on your needs
    # SLIP = 50  # Adjust this value based on your needs

    # # Adjust left trigger based on lock
    # if lock > LOCK:
    #     left_mode = TriggerMode.VibrateTriggerPulse.value
    # else:
    #     left_mode = TriggerMode.Normal.value

    # # Adjust right trigger based on slip
    # if slip > SLIP:
    #     right_mode = TriggerMode.VibrateTriggerPulse.value
    # else:
    #     right_mode = TriggerMode.Normal.value

    # packet.instructions.append(Instruction(InstructionType.TriggerUpdate, [0, Trigger.Left.value, left_mode, 1, 0, 0]))
    # packet.instructions.append(Instruction(InstructionType.TriggerUpdate, [0, Trigger.Right.value, right_mode, 1, 0, 0]))

    ###################################################################################
    # LED Light
    ###################################################################################

    # Add RGB update instruction based on RPM
    if rpmPercentage < RPM_GREEN:
        color = [0, 255, 0]  # Green
    elif rpmPercentage < RPM_YELLOW:
        # Interpolate between green and yellow
        factor = (rpmPercentage - RPM_GREEN) / (RPM_YELLOW - RPM_GREEN)
        color = interpolate_color([0, 255, 0], [255, 255, 0], factor)
    elif rpmPercentage < RPM_RED:
        # Interpolate between yellow and red
        factor = (rpmPercentage - RPM_YELLOW) / (RPM_RED - RPM_YELLOW)
        color = interpolate_color([255, 255, 0], [255, 0, 0], factor)
    else:
        color = [255, 0, 0]  # Full red

    packet.instructions.append(Instruction(InstructionType.RGBUpdate, [0] + color))

    ###################################################################################
    # Haptic Feedback
    ###################################################################################

    # Define thresholds for lock and slip
    LOCK = 50  # Adjust this value based on your needs
    SLIP = 50  # Adjust this value based on your needs

    # Adjust left trigger based on lock
    if lock > LOCK:
        intensityL = 1
    else:
        intensityL = 0

    # Adjust right trigger based on slip
    if slip > SLIP:
        intensityR = 1
    else:
        intensityR = 0
            
    packet.instructions.append(Instruction(InstructionType.HapticFeedback, [
        0, # controller index
        os.path.join(dir_path, "rumble_mid.wav"), # path to wav
        intensityL, # left volume
        intensityR, # right volume
        1, # clear buffer flag
        1 # channel number
    ])) 

    # # Gear change
    # if gear != previous_gear and previous_gear is not None:
    #     packet.instructions.append(Instruction(InstructionType.HapticFeedback, [
    #         0, # controller index
    #         os.path.join(dir_path, "shift_high.wav"), # path to wav
    #         1, # left volume
    #         1, # right volume
    #         1, # clear buffer flag
    #         2 # channel number
    #     ])) 
    # # Update previous gear
    # previous_gear = gear

    # Send the packet to DualSense X
    json_str = json.dumps(packet.to_dict())
    sock_dsx.sendto(bytes(json_str, "utf-8"), (UDP_IP, UDP_DSX_PORT))

    