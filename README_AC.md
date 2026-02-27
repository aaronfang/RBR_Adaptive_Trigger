# AC DualSense Adapter

**Assetto Corsa系列自适应扳机与DualSense手柄适配工具**

为 Assetto Corsa / Assetto Corsa Competizione / Assetto Corsa Rally 提供真实的DualSense自适应扳机反馈!

---

## 🎮 支持的游戏

- ✅ **Assetto Corsa** (原版AC)
- ✅ **Assetto Corsa Competizione** (ACC)
- ✅ **Assetto Corsa Rally** (ACR)

---

## ✨ 核心功能

### 🎯 自适应扳机反馈
- **油门扳机 (R2)**: 根据后轮打滑提供阻力反馈
  - 后轮空转时自动增加扳机阻力
  - 实时调节,帮助控制牵引力
  
- **刹车扳机 (L2)**: 根据前轮锁死提供振动反馈
  - 前轮抱死时触发脉冲振动
  - 防止刹车过度

### 💡 LED灯光效果
- **转速指示**: 根据RPM变化LED颜色
  - 绿色 (0-70%)
  - 黄色 (70-85%)
  - 红色 (85%+) - 接近断油区

### 📊 实时遥测显示
- 速度、转速、档位
- 油门、刹车、方向盘角度
- 四轮打滑实时监控
- 轮胎温度显示

---

## 🚀 快速开始

### 前置要求

1. **Python 3.7+**
2. **DSX (DualSenseX)** - DualSense手柄驱动程序
   - 下载: [DSX GitHub](https://github.com/Paliverse/DualSenseX)
   - 启动DSX并确保UDP服务器运行在 `127.0.0.1:6969`

3. **Python依赖库**:
```bash
pip install psutil numpy matplotlib pywin32
```

### 使用步骤

1. **启动DSX**
   - 运行DSX程序
   - 连接DualSense手柄

2. **启动游戏**
   - 运行 AC / ACC / ACR
   - 进入赛道开始驾驶

3. **运行适配器**
```bash
python Adaptive_Trigger_AC.py
```

4. **享受游戏!**
   - 自适应扳机会自动工作
   - 在GUI中调整参数

---

## ⚙️ 配置说明

程序首次运行会自动创建 `config_ac.ini` 配置文件。

### 主要参数

#### 扳机反馈
- **Trigger Strength** (0.1-3.0): 扳机反馈强度系数
  - 推荐值: 1.5-2.0
  - 数值越大,反馈越强烈

- **Slip Threshold** (0.05-0.5): 打滑触发阈值
  - 推荐值: 0.15-0.20
  - 数值越小,越敏感

#### 功能开关
- **Adaptive Triggers**: 启用/禁用自适应扳机
- **LED Effect**: 启用/禁用LED转速指示
- **Haptic Effect**: 启用/禁用振动反馈 (实验性)

---

## 📋 技术原理

### 数据获取方式
程序通过读取AC系列游戏的**共享内存(Shared Memory)**获取遥测数据:

```
游戏 → 共享内存 → Python程序 → DSX → DualSense手柄
```

### 核心共享内存
- `Local\acpmf_physics` - 物理数据(速度、打滑、G力等)
- `Local\acpmf_graphics` - 游戏状态
- `Local\acpmf_static` - 静态信息(车辆、赛道等)

### 扳机反馈算法

**后轮打滑检测 (油门扳机)**:
```python
rear_slip = (abs(wheel_slip[2]) + abs(wheel_slip[3])) / 2
if gas > 0.3 and rear_slip > threshold:
    trigger_strength = min(8, 2 + rear_slip * 30) * strength_factor
```

**前轮锁死检测 (刹车扳机)**:
```python
front_slip = (abs(wheel_slip[0]) + abs(wheel_slip[1])) / 2
if brake > 0.3 and front_slip > threshold:
    trigger_strength = min(8, 2 + front_slip * 30) * strength_factor
```

---

## 🔧 故障排除

### 问题: "No AC game detected"
**原因**: 游戏未运行或未在赛道上驾驶

**解决**:
1. 确保游戏已启动
2. 进入赛道开始驾驶(不要停留在菜单)
3. 重启适配器程序

---

### 问题: 扳机没有反馈
**原因**: DSX未运行或配置错误

**解决**:
1. 检查DSX是否运行
2. 确认DualSense手柄已连接
3. 检查DSX的UDP服务器设置 (默认 `127.0.0.1:6969`)
4. 在GUI中确认"Adaptive Triggers"已启用

---

### 问题: 数据不更新
**原因**: 游戏共享内存未启用

**解决**:
- **对于ACC**: 可能需要在游戏设置中启用"Broadcasting"功能
- **对于AC/ACR**: 共享内存默认启用,无需额外设置

---

## 📝 配置文件示例 (config_ac.ini)

```ini
[Network]
dsx_ip = 127.0.0.1
dsx_port = 6969

[Features]
adaptive_trigger = True
led_effect = True
haptic_effect = False

[Feedback]
trigger_strength = 1.5
wheel_slip_threshold = 0.15
trigger_threshold = 0.20

[GUI]
fps = 60.0
pause_updates = False

[LED]
rpm_green = 70
rpm_yellow = 85
rpm_red = 95
```

---

## 🎯 使用技巧

### 1. 调整扳机灵敏度
- 在拉力赛中,建议使用较低的阈值 (0.10-0.15)
- 在赛道赛中,可使用较高的阈值 (0.15-0.20)

### 2. 扳机强度建议
- **新手**: 1.0-1.5 (温和反馈,不影响操作)
- **进阶**: 1.5-2.0 (明显反馈,辅助控制)
- **专家**: 2.0-3.0 (强烈反馈,挑战极限)

### 3. LED转速指示
根据不同车辆调整LED阈值:
- 高转速赛车 (GT3等): 保持默认值
- 拉力赛车: 可能需要降低阈值

---

## 🆚 与RBR版本的对比

| 特性 | RBR版本 | AC版本 |
|------|---------|--------|
| 数据获取 | 直接内存读取 | 共享内存 |
| 稳定性 | 需要特定版本 | 更稳定 |
| 支持游戏 | 仅RBR | AC/ACC/ACR |
| 数据丰富度 | 高 | 非常高 |
| 配置复杂度 | 中等 | 简单 |

---

## 🔗 相关链接

- **DSX (DualSenseX)**: https://github.com/Paliverse/DualSenseX
- **AC Shared Memory文档**: [各种社区资源]
- **原项目 (RBR版本)**: 本仓库

---

## 📄 许可证

与主项目(RBR版本)相同的许可证。

---

## 🙏 致谢

- DSX项目 - 提供DualSense驱动
- AC社区 - 共享内存文档
- RBR版本 - 代码架构参考

---

## 📮 反馈与支持

如有问题或建议,请在项目Issues中反馈。

---

**享受真实的模拟驾驶体验!** 🏎️💨
