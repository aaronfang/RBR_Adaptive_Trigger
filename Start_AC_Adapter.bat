@echo off
chcp 65001 > nul
echo ================================================================
echo AC DualSense Adapter - Assetto Corsa Series
echo ================================================================
echo.
echo [1] Checking Python installation...
python --version 2>nul
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH!
    echo Please install Python 3.7+ from https://www.python.org/
    pause
    exit /b 1
)
echo [OK] Python is installed
echo.

echo [2] Starting AC DualSense Adapter...
echo.
echo ================================================================
echo Please ensure:
echo   1. DSX (DualSenseX) is running
echo   2. DualSense controller is connected
echo   3. Game (AC/ACC/ACR) is running
echo ================================================================
echo.

python Adaptive_Trigger_AC.py

if errorlevel 1 (
    echo.
    echo [ERROR] Program exited with error!
    echo.
    echo Common issues:
    echo   - Missing dependencies: pip install psutil numpy matplotlib pywin32
    echo   - DSX not running
    echo   - Game not running
    echo.
)

pause
