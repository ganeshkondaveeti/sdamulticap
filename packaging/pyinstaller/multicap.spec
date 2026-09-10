# PyInstaller one-folder spec — cross-OS single source, per-OS branches.
# Consumed by all three Phase 10 installers (§15) and the Phase 0 smoke (§5).
# Build: `pyinstaller packaging/pyinstaller/multicap.spec`

import sys
from pathlib import Path

block_cipher = None
project_root = Path.cwd()

a = Analysis(
    [str(project_root / "src" / "multicap" / "__main__.py")],
    pathex=[str(project_root / "src")],
    binaries=[],
    datas=[],
    hiddenimports=["multicap"],
    hookspath=[],
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
    [],
    exclude_binaries=True,
    name="multicap",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False if sys.platform != "linux" else True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="multicap",
)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="multicap.app",
        icon=None,
        bundle_identifier="com.cisco.multicap",
    )
