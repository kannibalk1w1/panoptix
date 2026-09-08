# -*- mode: python ; coding: utf-8 -*-

import os
import re
from pathlib import Path


project_root = Path.cwd()


def build_version_resource() -> str:
    """Write the Windows version resource, stamped with PANOPTIX_VERSION when the
    build script sets it, so the exe metadata matches the installer version."""
    text = (project_root / "installer" / "version_info.txt").read_text(encoding="utf-8")
    requested = os.environ.get("PANOPTIX_VERSION", "").strip()
    if requested:
        parts = (re.split(r"[.+-]", requested) + ["0", "0", "0"])[:3]
        numbers = [int(part) if part.isdigit() else 0 for part in parts]
        tup = "({}, {}, {}, 0)".format(*numbers)
        dotted = "{}.{}.{}.0".format(*numbers)
        text = re.sub(r"filevers=\([^)]*\)", "filevers=" + tup, text)
        text = re.sub(r"prodvers=\([^)]*\)", "prodvers=" + tup, text)
        text = re.sub(r'(StringStruct\("FileVersion", ")[^"]*', r"\g<1>" + dotted, text)
        text = re.sub(r'(StringStruct\("ProductVersion", ")[^"]*', r"\g<1>" + dotted, text)
    # workpath is already created and cleaned by this point in the build.
    generated = project_root / "build" / "version_info.txt"
    generated.parent.mkdir(parents=True, exist_ok=True)
    generated.write_text(text, encoding="utf-8")
    return str(generated)


version_resource = build_version_resource()


a = Analysis(
    ["panoptix.py"],
    pathex=[str(project_root)],
    binaries=[],
    datas=[("frontend", "frontend")],
    hiddenimports=["pynput.keyboard._win32", "pynput.mouse._win32", "pystray"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="Panoptix",
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
    icon="assets/panoptix.ico",
    version=version_resource,
)
