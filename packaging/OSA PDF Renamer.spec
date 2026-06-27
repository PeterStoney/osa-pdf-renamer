# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path


PROJECT_DIR = Path.cwd()
POPPLER_DIR = PROJECT_DIR / "build" / "vendor_poppler"
VERSION = (PROJECT_DIR / "VERSION").read_text().strip()


def include_if_exists(path: Path, target: str):
    return [(str(path), target)] if path.exists() else []


a = Analysis(
    [str(PROJECT_DIR / "packaging" / "app_launcher.py")],
    pathex=[str(PROJECT_DIR)],
    binaries=[
        (str(PROJECT_DIR / "vision_ocr"), "."),
        (str(PROJECT_DIR / "progress_runner"), "."),
        *include_if_exists(POPPLER_DIR / "bin" / "pdftotext", "bin"),
        *include_if_exists(POPPLER_DIR / "bin" / "pdftoppm", "bin"),
        *include_if_exists(POPPLER_DIR / "bin" / "pdfinfo", "bin"),
        *include_if_exists(
            POPPLER_DIR / "lib" / "libpoppler.161.dylib",
            "lib",
        ),
        *include_if_exists(
            POPPLER_DIR / "lib" / "liblcms2.2.dylib",
            "lib",
        ),
        *include_if_exists(
            PROJECT_DIR / "build" / "vendor_ollama" / "bin" / "ollama",
            "bin",
        ),
    ],
    datas=[
        (str(PROJECT_DIR / "config.toml"), "."),
        (str(PROJECT_DIR / "VERSION"), "."),
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
    argv_emulation=True,
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
        "CFBundleShortVersionString": VERSION,
        "CFBundleVersion": VERSION,
        "CFBundleDocumentTypes": [
            {
                "CFBundleTypeName": "PDF document",
                "CFBundleTypeRole": "Editor",
                "LSHandlerRank": "Alternate",
                "LSItemContentTypes": [
                    "com.adobe.pdf",
                    "com.apple.pdf",
                    "public.pdf",
                ],
            },
        ],
        "LSMinimumSystemVersion": "12.0",
        "NSHighResolutionCapable": True,
    },
)
