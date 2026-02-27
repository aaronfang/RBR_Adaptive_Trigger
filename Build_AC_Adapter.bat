@echo off
chcp 65001 > nul
echo ================================================================
echo AC DualSense Adapter - 打包构建脚本
echo ================================================================
echo.

echo [1] 检查 PyInstaller...
pyinstaller --version 2>nul
if errorlevel 1 (
    echo [INFO] 安装 PyInstaller...
    pip install pyinstaller
)
echo.

echo [2] 安装依赖...
pip install -r requirements.txt -q
echo.

echo [3] 开始打包...
pyinstaller Adaptive_Trigger_AC.spec
if errorlevel 1 (
    echo [ERROR] 打包失败!
    pause
    exit /b 1
)
echo.

echo [4] 复制配置文件到输出目录...
if exist config_ac.ini (
    copy /Y config_ac.ini dist\config_ac.ini > nul
    echo 已复制 config_ac.ini
) else (
    echo 注意: config_ac.ini 不存在，首次运行 exe 时会自动创建
)
echo.

echo ================================================================
echo 打包完成!
echo 输出目录: dist\
echo 可执行文件: dist\AC_DualSense_Adapter_v1.0.0.exe
echo.
echo 分发给用户时，将 dist 文件夹中的 exe 和 config_ac.ini 一起提供即可。
echo 用户无需安装 Python。
echo ================================================================
pause
