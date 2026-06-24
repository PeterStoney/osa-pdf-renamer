# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path


PROJECT_DIR = Path.cwd()


a = Analysis(
    [str(PROJECT_DIR / "packaging" / "app_launcher.py")],
    pathex=[str(PROJECT_DIR)],
    binaries=[
        (str(PROJECT_DIR / "vision_ocr"), "."),
    ],
    datas=[
        (str(PROJECT_DIR / "config.toml"), "."),
        (str(PROJECT_DIR / "helpers" / "vision_ocr.swift"), "helpers"),
    ],
    hiddenimports=[
        "PIL",
        "PIL.Image",
        "pdf2image",
        "requests",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="OSA PDF Renamer",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="OSA PDF Renamer",
)

app = BUNDLE(
    coll,
    name="OSA PDF Renamer.app",
    icon=None,
    bundle_identifier="au.com.osa.pdf-renamer",
    info_plist={
        "CFBundleDisplayName": "OSA PDF Renamer",
        "CFBundleName": "OSA PDF Renamer",
        "CFBundleShortVersionString": "0.1.0",
        "CFBundleVersion": "0.1.0",
        "LSMinimumSystemVersion": "12.0",
        "NSHighResolutionCapable": True,
    },
)

