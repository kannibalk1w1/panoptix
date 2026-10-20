# Build on Linux. Native KDE capture/dialog tools are supplied by the OS.
from pathlib import Path

project_root = Path.cwd()
a = Analysis(
    ['panoptix.py'], pathex=[str(project_root)],
    binaries=[], datas=[('frontend', 'frontend'), ('panoptix_app/qt_tray.py', 'helpers')],
    hiddenimports=['pynput.keyboard._xorg', 'pynput.mouse._xorg', 'pystray._xorg'],
    hookspath=[], hooksconfig={}, runtime_hooks=[],
    excludes=['gi'], noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [], exclude_binaries=True, name='panoptix',
    debug=False, strip=False, upx=False, console=True,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='PanoptixLinux')
