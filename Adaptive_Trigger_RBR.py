import socket
import struct
import json
from enum import Enum

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

UDP_IP = "127.0.0.1"
UDP_PORT = 6776
UDP_DSX_PORT = 6969

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((UDP_IP, UDP_PORT))
sock_dsx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

while True:  
    var, adress = sock.recvfrom(664) # buffer size is 664 bytes

    ControlThrottle = int(round(struct.unpack_from('<f', var , offset=28)[0] * 100))
    ControlBrake = int(round(struct.unpack_from('<f', var , offset=32)[0] * 100))
    ControlClutch = int(round(struct.unpack_from('<f', var , offset=40)[0] * 100))
    TotalSteps = struct.unpack_from('<l', var , offset=0)[0]
    StageRaceTime = struct.unpack_from('<f', var , offset=12)[0]
    RaceHr = int(StageRaceTime / 60 )
    RaceMin = (StageRaceTime / 60 - int(StageRaceTime / 60))*60
    ControlGear = struct.unpack_from('<l', var , offset=44)[0] - 1 # minus 1 because neutral is 1
    EngineCoolantTemperature = int(round(struct.unpack_from("<f", var , offset=144)[0] - 273.15)) # minus 273.15 to convert from kelvin
    RadiatorCoolantTemperature = int(round(struct.unpack_from("<f", var , offset=140)[0] - 273.15))
    LFBrakeDiskTemp = int(round(struct.unpack_from("<f", var , offset=188)[0] - 273.15))
    RFBrakeDiskTemp = int(round(struct.unpack_from("<f", var , offset=316)[0] - 273.15))
    LBBrakeDiskTemp = int(round(struct.unpack_from("<f", var , offset=444)[0] - 273.15))
    RBBrakeDiskTemp = int(round(struct.unpack_from("<f", var , offset=572)[0] - 273.15))
    EngineRpm = int(round(struct.unpack_from("<f", var , offset=136)[0]))

    
    print(chr(27) + "[2J") # clear screen using escape sequences
    print(chr(27) + "[H")  # return to home using escape sequences


    # Calculate vibration intensity based on throttle for left trigger
    left_vibration_intensity = int((ControlThrottle / 100) * 255)
    
    # Calculate vibration intensity based on brake for right trigger
    right_vibration_intensity = int((ControlBrake / 100) * 255)
    
    packet = Packet([
        Instruction(InstructionType.TriggerUpdate, [0, int(Trigger.Left.value), int(TriggerMode.VibrateTrigger.value), left_vibration_intensity]),
        Instruction(InstructionType.TriggerUpdate, [0, int(Trigger.Right.value), int(TriggerMode.VibrateTrigger.value), right_vibration_intensity])
    ])
    json_str = json.dumps(packet.to_dict())
    sock_dsx.sendto(bytes(json_str, "utf-8"), (UDP_IP, UDP_DSX_PORT))

    # if(EngineRpm > 1000):
    #     packet = Packet([
    #         Instruction(InstructionType.TriggerUpdate, [0, int(Trigger.Left.value), int(TriggerMode.Soft.value)]),
    #         Instruction(InstructionType.TriggerUpdate, [0, int(Trigger.Right.value), int(TriggerMode.Soft.value)])
    #     ])
    #     json_str = json.dumps(packet.to_dict())
    #     sock_dsx.sendto(bytes(json_str, "utf-8"), (UDP_IP, UDP_DSX_PORT))
        
    print("Total Steps: %s	Race Time: %s:%s" %(TotalSteps, RaceHr , RaceMin))
    print("Engine: %s RPM   Gear: %s   Throttle: %s   Brake: %s   Clutch: %s" %(EngineRpm , ControlGear, ControlThrottle , ControlBrake, ControlClutch))
    print("Coolant Temp: %s°C" % EngineCoolantTemperature)
    print("")
    print("Brake Disk Temp")
    print("LF: %s°C	RF: %s°C" % (LFBrakeDiskTemp , RFBrakeDiskTemp))
    print("LB: %s°C	RB: %s°C" % (LBBrakeDiskTemp , RBBrakeDiskTemp))


    
