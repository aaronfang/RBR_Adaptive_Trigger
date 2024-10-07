import socket
import struct
import json
from enum import Enum
from ctypes import *
import serial
import time
import os

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

# Define UDP port
UDP_IP = "127.0.0.1"
UDP_PORT = 6778
UDP_DSX_PORT = 6969

# Create UDP socket
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((UDP_IP, UDP_PORT))
sock_dsx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# # serial port setup
# def open_serial_port():
#     while True:
#         try:
#             ser = serial.Serial('COM6', 115200, timeout=1, 
#                                 bytesize=serial.EIGHTBITS,
#                                 parity=serial.PARITY_NONE,
#                                 stopbits=serial.STOPBITS_ONE)
#             print(f"Serial port opened successfully: {ser}")
#             return ser
#         except serial.SerialException as e:
#             print(f"Failed to open serial port: {e}")
#             print("Retrying in 5 seconds...")
#             time.sleep(5)

# ser = open_serial_port()

# def read_serial_data(ser):
#     try:
#         # Clear input buffer
#         ser.reset_input_buffer()
        
#         # Read data with a timeout
#         line = ser.readline().decode('utf-8').strip()
        
#         if line:
#             print(f"Raw data received: {line}")
#             return line
#         else:
#             print("No data received within timeout period")
#             return None
#     except serial.SerialException as e:
#         print(f"Serial port error: {e}")
#         return None

# Define RPM threshold variables
RPM_GREEN_THRESHOLD = 50  # Below this percentage, color is green
RPM_RED_THRESHOLD = 80    # Below this percentage, color transitions from yellow to red. Above RPM_RED_THRESHOLD, color is fully red
RPM_YELLOW_THRESHOLD = (RPM_GREEN_THRESHOLD + RPM_RED_THRESHOLD) / 2  # Below this percentage, color transitions from green to yellow


def interpolate_color(start_color, end_color, factor):
    return [int(start + (end - start) * factor) for start, end in zip(start_color, end_color)]


dir_path = os.path.dirname(os.path.realpath(__file__)) + "\\haptics\\"

# Define RPM thresholds for haptic feedback
RPM_IDLE = 1000
RPM_LOW = 3000
RPM_MEDIUM = 5000
RPM_HIGH = 7000

# Initialize previous RPM
previous_rpm = 0

# Add these constants near the top of your file
LANDING_THRESHOLD = -5.0 # Adjust this value based on testing
LAST_LANDING_TIME = 0
LANDING_COOLDOWN = 0.5  # Cooldown in seconds to prevent multiple triggers

# Initialize previous gear
previous_gear = None

# Add these variables near the top of your file
landing_count = 0
landing_messages = []

while True: 
    # # Read data from COM port
    # line = read_serial_data(ser)
    
    # if line:
    #     try:
    #         telemetry_simhub = json.loads(line)
    #     except json.JSONDecodeError as e:
    #         print(f"Error decoding JSON data: {e}")
    #         continue
    # else:
    #     print("No valid data available on serial port")
    #     continue 

    # customSerialDeviceData = telemetry_simhub


    data, address = sock.recvfrom(664)  # buffer size is 664 bytes
    telemetry = TelemetryData.from_buffer_copy(data)

    # Process all telemetry data
    total_steps = telemetry.totalSteps

    # Stage data
    stage_index = telemetry.stage.index
    stage_progress = round(telemetry.stage.progress * 0.01, 2)
    race_time = telemetry.stage.raceTime
    race_hr = int(race_time / 3600)
    race_min = int((race_time % 3600) / 60)
    race_sec = int(race_time % 60)
    drive_line_location = round(telemetry.stage.driveLineLocation, 2)
    distance_to_end = round(telemetry.stage.distanceToEnd, 2)

    # Control data
    steering = round(telemetry.control.steering, 4)
    throttle = round(telemetry.control.throttle * 100)
    brake = round(telemetry.control.brake * 100)
    handbrake = round(telemetry.control.handbrake * 100)
    clutch = round(telemetry.control.clutch * 100)
    gear = telemetry.control.gear - 1  # minus 1 because neutral is 1
    footbrake_pressure = round(telemetry.control.footbrakePressure, 2)
    handbrake_pressure = round(telemetry.control.handbrakePressure, 2)

    # Car data
    car_index = telemetry.car.index
    car_speed = round(telemetry.car.speed, 2)  # km/h
    position_x = round(telemetry.car.positionX, 2)
    position_y = round(telemetry.car.positionY, 2)
    position_z = round(telemetry.car.positionZ, 2)
    car_roll = round(telemetry.car.roll, 2)
    car_pitch = round(telemetry.car.pitch, 2)
    car_yaw = round(telemetry.car.yaw, 2)

    # Motion data
    velocities = telemetry.car.velocities
    accelerations = telemetry.car.accelerations

    # Engine data
    engine_rpm = round(telemetry.car.engine.rpm)
    max_rpm = 8000  # Assuming max RPM is 8000, adjust if needed
    rpm_percentage = (engine_rpm / max_rpm) * 100
    radiator_coolant_temp = round(telemetry.car.engine.radiatorCoolantTemperature - 273.15, 1)
    engine_coolant_temp = round(telemetry.car.engine.engineCoolantTemperature - 273.15, 1)
    engine_temp = round(telemetry.car.engine.engineTemperature - 273.15, 1)

    # Suspension data (for all four wheels)
    suspensions = [telemetry.car.suspensionLF, telemetry.car.suspensionRF, 
                   telemetry.car.suspensionLB, telemetry.car.suspensionRB]
    suspension_data = []

    for susp in suspensions:
        suspension_data.append({
            'spring_deflection': round(susp.springDeflection, 3),
            'rollbar_force': round(susp.rollbarForce, 2),
            'spring_force': round(susp.springForce, 2),
            'damper_force': round(susp.damperForce, 2),
            'strut_force': round(susp.strutForce, 2),
            'helper_spring_active': susp.helperSpringIsActive,
            'damper_damage': round(susp.damper.damage, 2),
            'damper_piston_velocity': round(susp.damper.pistonVelocity, 2),
            'brake_disk_layer_temp': round(susp.wheel.brakeDisk.layerTemperature - 273.15, 1),
            'brake_disk_temp': round(susp.wheel.brakeDisk.temperature - 273.15, 1),
            'brake_disk_wear': round(susp.wheel.brakeDisk.wear, 4),
            'tire_pressure': round(susp.wheel.tire.pressure / 1000, 2),  # Convert to bar
            'tire_temp': round(susp.wheel.tire.temperature - 273.15, 1),
            'tire_carcass_temp': round(susp.wheel.tire.carcassTemperature - 273.15, 1),
            'tire_tread_temp': round(susp.wheel.tire.treadTemperature - 273.15, 1),
            'tire_current_segment': susp.wheel.tire.currentSegment,
            'tire_segments': [
                {'temp': round(segment.temperature - 273.15, 1), 'wear': round(segment.wear, 4)}
                for segment in [susp.wheel.tire.segment1, susp.wheel.tire.segment2, 
                                susp.wheel.tire.segment3, susp.wheel.tire.segment4, 
                                susp.wheel.tire.segment5, susp.wheel.tire.segment6, 
                                susp.wheel.tire.segment7, susp.wheel.tire.segment8]
            ]
        })

    print(chr(27) + "[2J")  # clear screen using escape sequences
    print(chr(27) + "[H")   # return to home using escape sequences


    # Adjust these factors to change vibration intensity (0.0 to 1.0)
    throttle_factor = 1
    brake_factor = 1
    
    # Use the throttle and brake to adjust your trigger effects
    left_intensity = int(brake * 2.55 * throttle_factor)  # Scale to 0-255
    right_intensity = int(throttle * 2.55 * brake_factor)

    packet = Packet([
        Instruction(InstructionType.TriggerUpdate, [0, Trigger.Left.value, TriggerMode.CustomTriggerValue.value, CustomTriggerValueMode.OFF.value, 0,left_intensity]),
        Instruction(InstructionType.TriggerUpdate, [0, Trigger.Right.value, TriggerMode.CustomTriggerValue.value, CustomTriggerValueMode.OFF.value, 0,right_intensity])
    ])

    # # Continuous base rumble effect
    # if engine_rpm > RPM_IDLE:
    #     base_intensity = min(0.5, (engine_rpm - RPM_IDLE) / (RPM_HIGH - RPM_IDLE))
    #     packet.instructions.append(Instruction(InstructionType.HapticFeedback, [0, dir_path + "rumble.wav", 0, base_intensity, base_intensity, 0.1]))

    # Add haptic feedback based on RPM
    if engine_rpm > RPM_HIGH and previous_rpm <= RPM_HIGH:
        packet.instructions.append(Instruction(InstructionType.HapticFeedback, [0, dir_path + "rumble2.wav", 0, 1, 1, 0.5]))
    elif RPM_MEDIUM < engine_rpm <= RPM_HIGH and (previous_rpm <= RPM_MEDIUM or previous_rpm > RPM_HIGH):
        packet.instructions.append(Instruction(InstructionType.HapticFeedback, [0, dir_path + "rumble2.wav", 0, 0.5, 0.5, 1]))
    elif RPM_LOW < engine_rpm <= RPM_MEDIUM and (previous_rpm <= RPM_LOW or previous_rpm > RPM_MEDIUM):
        packet.instructions.append(Instruction(InstructionType.HapticFeedback, [0, dir_path + "rumble2.wav", 0, 0.2, 0.2, 1]))
    elif RPM_IDLE < engine_rpm <= RPM_LOW and (previous_rpm <= RPM_IDLE or previous_rpm > RPM_LOW):
        packet.instructions.append(Instruction(InstructionType.HapticFeedback, [0, dir_path + "rumble2.wav", 0, 0.1, 0.1, 1]))

    # Update previous RPM
    previous_rpm = engine_rpm

    # Add RGB update instruction based on RPM
    if rpm_percentage < RPM_GREEN_THRESHOLD:
        color = [0, 255, 0]  # Green
    elif rpm_percentage < RPM_YELLOW_THRESHOLD:
        # Interpolate between green and yellow
        factor = (rpm_percentage - RPM_GREEN_THRESHOLD) / (RPM_YELLOW_THRESHOLD - RPM_GREEN_THRESHOLD)
        color = interpolate_color([0, 255, 0], [255, 255, 0], factor)
    elif rpm_percentage < RPM_RED_THRESHOLD:
        # Interpolate between yellow and red
        factor = (rpm_percentage - RPM_YELLOW_THRESHOLD) / (RPM_RED_THRESHOLD - RPM_YELLOW_THRESHOLD)
        color = interpolate_color([255, 255, 0], [255, 0, 0], factor)
    else:
        color = [255, 0, 0]  # Full red

    packet.instructions.append(Instruction(InstructionType.RGBUpdate, [0] + color))

    # # Jump detection
    # current_time = time.time()

    # # Check for landing condition
    # if (accelerations.heave < LANDING_THRESHOLD and 
    #     current_time - LAST_LANDING_TIME > LANDING_COOLDOWN):
    #     # Landing detected
    #     LAST_LANDING_TIME = current_time
    #     landing_count += 1
    #     # Add haptic feedback for landing
    #     packet.instructions.append(Instruction(InstructionType.HapticFeedback, 
    #         [0, dir_path + "landing.wav", 0, 1, 1, 1]))
    #     message = f"Landing detected! Haptic feedback triggered. (Count: {landing_count})"
    #     landing_messages.append(message)
    #     print(message)

    # # Gear change detection and haptic feedback
    # if gear != previous_gear and previous_gear is not None:
    #     # Gear has changed, trigger haptic feedback
    #     packet.instructions.append(Instruction(InstructionType.HapticFeedback, [0, dir_path + "shift.wav", 0, 1, 1, 1]))
    #     # print(f"Gear change detected: {previous_gear} -> {gear}")

    # # Update previous gear
    # previous_gear = gear

    # Send the packet to DualSense X
    json_str = json.dumps(packet.to_dict())
    sock_dsx.sendto(bytes(json_str, "utf-8"), (UDP_IP, UDP_DSX_PORT))


    # Print all telemetry data

    # print(f"Custom Serial Device Data: {customSerialDeviceData}")

    print(f"Left Trigger: {left_intensity}, Right Trigger: {right_intensity}")

    # Print landing messages
    print("Landing Events:")
    for msg in landing_messages[-5:]:  # Show last 5 landing events
        print(msg)
    print(f"Total landings: {landing_count}")
    print("\n")  # Add a blank line for separation

    print(f"Total Steps: {total_steps}")
    print(f"\nStage Data:")
    print(f"Index: {stage_index}, Progress: {stage_progress}%, Race Time: {race_hr:02d}:{race_min:02d}:{race_sec:02d}")
    print(f"Drive Line Location: {drive_line_location} m, Distance to End: {distance_to_end} m")

    print(f"\nControl Data:")
    print(f"Steering: {steering}, Throttle: {throttle}%, Brake: {brake}%, Handbrake: {handbrake}%")
    print(f"Clutch: {clutch}%, Gear: {gear}, Footbrake Pressure: {footbrake_pressure}, Handbrake Pressure: {handbrake_pressure}")

    print(f"\nCar Data:")
    print(f"Index: {car_index}, Speed: {car_speed} km/h")
    print(f"Position: X={position_x}, Y={position_y}, Z={position_z}")
    print(f"Orientation: Roll={car_roll}, Pitch={car_pitch}, Yaw={car_yaw}")

    print(f"\nMotion Data:")
    print(f"Velocities: Surge={velocities.surge:.2f}, Sway={velocities.sway:.2f}, Heave={velocities.heave:.2f}, Roll={velocities.roll:.2f}, Pitch={velocities.pitch:.2f}, Yaw={velocities.yaw:.2f}")
    print(f"Accelerations: Surge={accelerations.surge:.2f}, Sway={accelerations.sway:.2f}, Heave={accelerations.heave:.2f}, Roll={accelerations.roll:.2f}, Pitch={accelerations.pitch:.2f}, Yaw={accelerations.yaw:.2f}")
    print(f"Vertical Acceleration (Heave): {accelerations.heave:.2f}")  # Add this line

    print(f"\nEngine Data:")
    print(f"RPM: {engine_rpm} ({rpm_percentage:.1f}%), Radiator Coolant Temp: {radiator_coolant_temp}°C")
    print(f"Engine Coolant Temp: {engine_coolant_temp}°C, Engine Temp: {engine_temp}°C")
    print(f"Controller LED Color: RGB{tuple(color)}")

    # for i, susp in enumerate(['LF', 'RF', 'LB', 'RB']):
    #     print(f"\nSuspension {susp}:")
    #     sd = suspension_data[i]
    #     print(f"Spring Deflection: {sd['spring_deflection']} m, Rollbar Force: {sd['rollbar_force']} N")
    #     print(f"Spring Force: {sd['spring_force']} N, Damper Force: {sd['damper_force']} N")
    #     print(f"Strut Force: {sd['strut_force']} N, Helper Spring Active: {sd['helper_spring_active']}")
    #     print(f"Damper Damage: {sd['damper_damage']}, Damper Piston Velocity: {sd['damper_piston_velocity']} m/s")
    #     print(f"Brake Disk: Layer Temp={sd['brake_disk_layer_temp']}°C, Temp={sd['brake_disk_temp']}°C, Wear={sd['brake_disk_wear']}")
    #     print(f"Tire: Pressure={sd['tire_pressure']} bar, Temp={sd['tire_temp']}°C")
    #     print(f"Tire Carcass Temp: {sd['tire_carcass_temp']}°C, Tread Temp: {sd['tire_tread_temp']}°C")
    #     print(f"Current Segment: {sd['tire_current_segment']}")
    #     for j, seg in enumerate(sd['tire_segments']):
    #         print(f"  Segment {j+1}: Temp={seg['temp']}°C, Wear={seg['wear']}")
