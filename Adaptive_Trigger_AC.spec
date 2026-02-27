# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for AC DualSense Adapter
Build: pyinstaller Adaptive_Trigger_AC.spec
"""
import os

block_cipher = None

a = Analysis(
    ['Adaptive_Trigger_AC.py'],
    pathex=[],
    binaries=[],
    datas=([('icon.ico', '.')] if os.path.exists('icon.ico') else []),
    hiddenimports=[
        'pydirectinput', 'keyboard', 'psutil',
        'win32gui', 'win32con', 'win32api', 'win32process',
        'numpy', 'matplotlib', 'PIL', 'PIL._tkinter_finder',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='AC_DualSense_Adapter_v1.0.0',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon.ico' if os.path.exists('icon.ico') else None,
    version='version_info_ac.txt',
)
