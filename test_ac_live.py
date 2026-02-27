#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AC Rally 实时遥测测试 - 简化版
基于诊断结果的最小化实现
"""

import mmap
import ctypes
import struct
import time
import sys

# 简化的Physics结构 - 只包含最关键的字段
class ACPhysicsSimple(ctypes.Structure):
    _fields_ = [
        ("packetId", ctypes.c_int),              # 0: Packet ID
        ("gas", ctypes.c_float),                 # 4: 油门 (0-1)
        ("brake", ctypes.c_float),               # 8: 刹车 (0-1)
        ("fuel", ctypes.c_float),                # 12: 燃油
        ("gear", ctypes.c_int),                  # 16: 档位
        ("rpms", ctypes.c_int),                  # 20: 转速
        ("steerAngle", ctypes.c_float),          # 24: 方向盘角度
        ("speedKmh", ctypes.c_float),            # 28: 速度 km/h
        ("velocity", ctypes.c_float * 3),        # 32: 速度向量 x,y,z
        ("accG", ctypes.c_float * 3),            # 44: G力 x,y,z
        ("wheelSlip", ctypes.c_float * 4),       # 56: 四轮打滑 FL,FR,RL,RR ⭐关键!
        ("wheelLoad", ctypes.c_float * 4),       # 72: 轮胎负载
        ("wheelsPressure", ctypes.c_float * 4),  # 88: 轮胎压力
        ("wheelAngularSpeed", ctypes.c_float * 4), # 104: 轮速
        ("tyreWear", ctypes.c_float * 4),        # 120: 轮胎磨损
        ("tyreDirtyLevel", ctypes.c_float * 4),  # 136: 轮胎脏污
        ("tyreCoreTemperature", ctypes.c_float * 4), # 152: 轮胎核心温度 ⭐关键!
        ("camberRAD", ctypes.c_float * 4),       # 168: 外倾角
        ("suspensionTravel", ctypes.c_float * 4), # 184: 悬挂行程
    ]

def read_ac_physics():
    """读取AC Physics共享内存"""
    try:
        # 打开共享内存 - 使用tagname参数(Windows正确方式)
        shm = mmap.mmap(-1, ctypes.sizeof(ACPhysicsSimple), tagname="Local\\acpmf_physics")
        
        # 读取数据
        data_bytes = shm.read(ctypes.sizeof(ACPhysicsSimple))
        physics = ACPhysicsSimple.from_buffer_copy(data_bytes)
        shm.close()
        
        return physics
    except Exception as e:
        print(f"[错误] 读取失败: {type(e).__name__}: {e}")
        return None

def print_telemetry(physics):
    """打印遥测数据"""
    print("\n" + "="*70)
    print(f"PacketID: {physics.packetId}")
    print("-"*70)
    
    # 基础数据
    print(f"速度: {physics.speedKmh:6.1f} km/h  |  转速: {physics.rpms:5d} RPM  |  档位: {physics.gear}")
    print(f"油门: {physics.gas:4.2f}  |  刹车: {physics.brake:4.2f}  |  方向盘: {physics.steerAngle:6.1f}°")
    
    # 四轮打滑 - 自适应扳机的核心数据!
    print("\n[四轮打滑 - WheelSlip] **自适应扳机关键数据**")
    print(f"  前左: {physics.wheelSlip[0]:6.3f}  |  前右: {physics.wheelSlip[1]:6.3f}")
    print(f"  后左: {physics.wheelSlip[2]:6.3f}  |  后右: {physics.wheelSlip[3]:6.3f}")
    
    # 计算平均打滑
    avg_front_slip = (abs(physics.wheelSlip[0]) + abs(physics.wheelSlip[1])) / 2
    avg_rear_slip = (abs(physics.wheelSlip[2]) + abs(physics.wheelSlip[3])) / 2
    
    print(f"\n[打滑分析]")
    print(f"  前轮平均: {avg_front_slip:.3f} -> 影响刹车扳机")
    print(f"  后轮平均: {avg_rear_slip:.3f} -> 影响油门扳机")
    
    # 扳机反馈建议
    if avg_rear_slip > 0.1:
        trigger_strength = min(avg_rear_slip * 10, 1.0)
        print(f"  [!] 后轮打滑! 建议油门扳机阻力: {trigger_strength:.2f}")
    if avg_front_slip > 0.1:
        trigger_strength = min(avg_front_slip * 10, 1.0)
        print(f"  [!] 前轮抱死! 建议刹车扳机阻力: {trigger_strength:.2f}")
    
    # 轮胎温度
    print(f"\n[轮胎核心温度]")
    print(f"  前: {physics.tyreCoreTemperature[0]:5.1f}°C  {physics.tyreCoreTemperature[1]:5.1f}°C")
    print(f"  后: {physics.tyreCoreTemperature[2]:5.1f}°C  {physics.tyreCoreTemperature[3]:5.1f}°C")

def main():
    print("="*70)
    print("AC Rally 实时遥测监控")
    print("="*70)
    print("游戏: Assetto Corsa Rally (acr.exe)")
    print("共享内存: Local\\acpmf_physics")
    print("="*70)
    
    # 测试单次读取
    print("\n[测试] 尝试读取共享内存...")
    physics = read_ac_physics()
    
    if physics is None:
        print("\n[失败] 无法读取共享内存")
        print("\n请确保:")
        print("  1. 游戏正在运行")
        print("  2. 在赛道上驾驶(不在菜单)")
        return
    
    if physics.packetId == 0:
        print("\n[警告] PacketID为0,游戏可能未在驾驶模式")
        print("请确保在赛道上实际驾驶!")
        return
    
    print("[成功] 共享内存读取成功!")
    print_telemetry(physics)
    
    # 询问是否进入实时监控
    print("\n" + "="*70)
    choice = input("是否进入实时监控模式? (y/n): ").strip().lower()
    
    if choice == 'y':
        print("\n[实时监控模式] 10Hz更新 - 按 Ctrl+C 退出")
        print("="*70)
        
        try:
            update_count = 0
            while True:
                physics = read_ac_physics()
                if physics and physics.packetId > 0:
                    print(f"\n[更新 #{update_count}]", end='')
                    print_telemetry(physics)
                    update_count += 1
                else:
                    print("[等待数据...]", end='\r')
                
                time.sleep(0.1)  # 10Hz
                
        except KeyboardInterrupt:
            print("\n\n[退出] 监控已停止")
    
    print("\n测试完成!")
    print("="*70)
    print("\n下一步: 如果数据正常,即可创建完整的自适应扳机程序!")

if __name__ == "__main__":
    main()
