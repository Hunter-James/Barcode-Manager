# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Barcode Manager.

Build with:
    py -3 -m PyInstaller --noconfirm BarcodeManager.spec
"""

from pathlib import Path

ROOT = Path(SPECPATH)

a = Analysis(
    [str(ROOT / "main.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        (str(ROOT / "resources" / "app_icon.ico"), "resources"),
        (str(ROOT / "resources" / "app_icon.png"), "resources"),
    ],
    hiddenimports=[
        "pyzbar",
        "pyzbar.pyzbar",
        "zxingcpp",
        "cv2",
        "PIL.Image",
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "matplotlib",
        "PySide6",
        "PyQt5",
        "scipy",
        "pandas",
        "IPython",
        "jupyter",
        "notebook",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="BarcodeManager",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ROOT / "resources" / "app_icon.ico"),
)
