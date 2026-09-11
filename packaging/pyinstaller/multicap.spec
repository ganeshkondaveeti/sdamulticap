# PyInstaller one-folder spec — cross-OS single source, per-OS branches.
# Consumed by all three Phase 10 installers (§15) and the Phase 0 smoke (§5).
# Build: `pyinstaller packaging/pyinstaller/multicap.spec`
#
# PySide6 is LGPL: keep one-folder dynamic Qt libraries visible beside the app.
# Do not switch to one-file mode without a new licensing review.

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_submodules

block_cipher = None
project_root = Path.cwd()

qt_material_datas, qt_material_binaries, qt_material_hiddenimports = collect_all("qt_material")
qt_material_resource_datas = collect_data_files(
    "qt_material",
    includes=[
        "resources/*.py",
        "resources/logo/*",
        "resources/source/*.svg",
        "themes/*.xml",
    ],
)
qt_plugin_datas = collect_data_files(
    "PySide6",
    includes=[
        "Qt/plugins/iconengines/*",
        "Qt/plugins/imageformats/*",
        "Qt/plugins/platforms/*",
        "Qt/plugins/platformthemes/*",
        "Qt/plugins/styles/*",
        "Qt/plugins/tls/*",
        "Qt/translations/qtbase_*.qm",
    ],
)
hiddenimports = sorted(
    {
        "multicap",
        "PySide6.QtCore",
        "PySide6.QtGui",
        "PySide6.QtNetwork",
        "PySide6.QtPrintSupport",
        "PySide6.QtSvg",
        "PySide6.QtWidgets",
        *collect_submodules("multicap"),
        *qt_material_hiddenimports,
    }
)

a = Analysis(
    [str(project_root / "src" / "multicap" / "__main__.py")],
    pathex=[str(project_root / "src")],
    binaries=[*qt_material_binaries],
    datas=[*qt_material_datas, *qt_material_resource_datas, *qt_plugin_datas],
    hiddenimports=hiddenimports,
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
        name="MultiCap.app",
        icon=None,
        bundle_identifier="com.cisco.multicap",
        info_plist={
            "CFBundleDisplayName": "MultiCap",
            "CFBundleName": "MultiCap",
            "CFBundleShortVersionString": "0.0.0",
            "CFBundleVersion": "0.0.0",
            "LSMinimumSystemVersion": "12.0",
            "NSHighResolutionCapable": "True",
            "NSPrincipalClass": "NSApplication",
        },
    )
