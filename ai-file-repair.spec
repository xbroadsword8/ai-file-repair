# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        # Core modules
        'core.interfaces',
        'core.disk_recovery',
        'core.raw_scan',
        'core.disk_sector_scanner',
        'core.ntfs_mft',
        'core.ntfs_mft_parser',
        'core.researched_disk_recovery',
        'core.core_disk_recovery',
        'core.real_disk_info',
        'core.real_disk_scanner',
        # GUI modules
        'gui.gui_main',
        'gui.finaldata_style_gui',
        'gui.comprehensive_disk_recovery',
        # Utils modules
        'utils.file_size_estimator',
        'utils.eula_display',
        'utils.ai_repair',
        'utils.ai_repair_engine',
        'utils.build_with_eula',
        'utils.disk_repair',
        'utils.reconstruction',
        'utils.generate_eula_pdf',
        'utils.bad_sector_handler',
        'utils.repair_engine',
        'tkinter',
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
    a.binaries,
    a.datas,
    [],
    name='ai-file-repair',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
