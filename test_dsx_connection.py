#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DSX Connection Test Tool
测试与DSX的UDP连接是否正常
"""

import socket
import json
import time
from enum import Enum

# DSX配置
DSX_IP = '127.0.0.1'
DSX_PORT = 6969

class InstructionType(Enum):
    Invalid = 0
    TriggerUpdate = 1
    RGBUpdate = 2

class Trigger(Enum):
    Invalid = 0
    Left = 1
    Right = 2

class TriggerMode(Enum):
    Normal = 0
    VibrateTriggerPulse = 11  # 脉冲振动

class Instruction:
    def __init__(self, instruction_type, parameters):
        # instruction_type 现在已经是整数值了
        self.type = instruction_type if isinstance(instruction_type, int) else instruction_type.value
        self.parameters = parameters

class Packet:
    def __init__(self, instructions):
        self.instructions = instructions

def send_to_dsx(packet):
    """发送数据包到DSX"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        message = json.dumps(packet, default=lambda o: o.__dict__)
        sock.sendto(message.encode(), (DSX_IP, DSX_PORT))
        sock.close()
        return True
    except Exception as e:
        print(f"[ERROR] Failed to send: {e}")
        return False

def test_rgb():
    """测试RGB LED"""
    print("\n[Test 1/3] Testing RGB LED...")
    colors = [
        (255, 0, 0, "Red"),
        (0, 255, 0, "Green"),
        (0, 0, 255, "Blue"),
    ]
    
    for r, g, b, name in colors:
        packet = Packet([
            Instruction(InstructionType.RGBUpdate.value, [0, r, g, b])
        ])
        if send_to_dsx(packet):
            print(f"  Sent: {name} color")
        else:
            print(f"  Failed to send {name}")
        time.sleep(1)
    
    # 关闭LED
    packet = Packet([Instruction(InstructionType.RGBUpdate.value, [0, 0, 0, 0])])
    send_to_dsx(packet)
    print("  RGB test complete")

def test_triggers():
    """测试扳机反馈"""
    print("\n[Test 2/3] Testing Adaptive Triggers...")
    
    tests = [
        (Trigger.Left, "Left (L2) - Brake"),
        (Trigger.Right, "Right (R2) - Throttle"),
    ]
    
    for trigger, name in tests:
        print(f"\n  Testing {name}...")
        
        # 发送振动模式
        for strength in [2, 4, 6, 8]:
            packet = Packet([
                Instruction(InstructionType.TriggerUpdate.value, 
                          [0, trigger.value, TriggerMode.VibrateTriggerPulse.value, strength, 0, 0])
            ])
            if send_to_dsx(packet):
                print(f"    Strength {strength}/8 - Should feel vibration!")
            time.sleep(1)
        
        # 恢复正常
        packet = Packet([
            Instruction(InstructionType.TriggerUpdate.value, 
                       [0, trigger.value, TriggerMode.Normal.value, 1, 0, 0])
        ])
        send_to_dsx(packet)
        time.sleep(0.5)

def test_continuous():
    """持续测试模式"""
    print("\n[Test 3/3] Continuous trigger test (5 seconds)...")
    print("  Both triggers should pulse repeatedly")
    
    start_time = time.time()
    while time.time() - start_time < 5:
        packet = Packet([
            Instruction(InstructionType.TriggerUpdate.value, 
                       [0, Trigger.Left.value, TriggerMode.VibrateTriggerPulse.value, 6, 0, 0]),
            Instruction(InstructionType.TriggerUpdate.value, 
                       [0, Trigger.Right.value, TriggerMode.VibrateTriggerPulse.value, 6, 0, 0])
        ])
        send_to_dsx(packet)
        time.sleep(0.1)
    
    # 恢复正常
    packet = Packet([
        Instruction(InstructionType.TriggerUpdate.value, 
                   [0, Trigger.Left.value, TriggerMode.Normal.value, 1, 0, 0]),
        Instruction(InstructionType.TriggerUpdate.value, 
                   [0, Trigger.Right.value, TriggerMode.Normal.value, 1, 0, 0])
    ])
    send_to_dsx(packet)
    print("  Continuous test complete")

def main():
    print("="*70)
    print("DSX Connection Test Tool")
    print("="*70)
    print(f"Target: {DSX_IP}:{DSX_PORT}")
    print("="*70)
    
    print("\n[IMPORTANT] Before running this test:")
    print("  1. Make sure DSX is running")
    print("  2. Make sure DualSense controller is connected to DSX")
    print("  3. Make sure DSX UDP server is enabled on port 6969")
    print("="*70)
    
    input("\nPress ENTER to start test...")
    
    try:
        # Test RGB
        test_rgb()
        
        print("\n" + "="*70)
        print("Did you see the LED change colors? (Red -> Green -> Blue)")
        response = input("(y/n): ").strip().lower()
        
        if response != 'y':
            print("\n[PROBLEM] LED did not work!")
            print("\nPossible causes:")
            print("  1. DSX is not running")
            print("  2. DSX UDP server is not enabled")
            print("  3. Wrong IP/Port configuration")
            print("  4. Firewall blocking UDP")
            print("\nPlease check DSX settings and try again.")
            return
        
        print("\n[OK] LED test passed! DSX connection is working.")
        
        # Test triggers
        print("\n" + "="*70)
        test_triggers()
        
        print("\n" + "="*70)
        print("Did you feel the triggers vibrate?")
        response = input("(y/n): ").strip().lower()
        
        if response != 'y':
            print("\n[PROBLEM] Triggers did not work!")
            print("\nPossible causes:")
            print("  1. Controller is not properly connected to DSX")
            print("  2. DSX trigger feature is disabled")
            print("  3. Controller firmware needs update")
            print("  4. Controller is in wrong mode")
            print("\nTry:")
            print("  - Reconnect controller to DSX")
            print("  - Restart DSX")
            print("  - Update DualSense firmware")
            return
        
        print("\n[OK] Trigger test passed!")
        
        # Continuous test
        print("\n" + "="*70)
        test_continuous()
        
        print("\n" + "="*70)
        print("[SUCCESS] All tests passed!")
        print("\nYour DSX connection is working correctly.")
        print("If AC Adapter still doesn't work, the issue is with the game data.")
        print("="*70)
        
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    except Exception as e:
        print(f"\n[ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
