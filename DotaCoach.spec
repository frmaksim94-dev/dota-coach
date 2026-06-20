# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_submodules


datas = [
    ('ui/assets/dota_coach_logo.svg', 'ui/assets'),
    ('ui/assets/dota_coach_icon.ico', 'ui/assets'),
    ('ui/assets/dota_coach.ico', 'ui/assets'),
    ('ui/assets/dota_coach_icon.png', 'ui/assets'),
    ('ui/assets/guides', 'ui/assets/guides'),
    ('ui/assets/patterns', 'ui/assets/patterns'),
    ('ui/assets/catalog/heroes', 'ui/assets/catalog/heroes'),
    ('ui/assets/catalog/items', 'ui/assets/catalog/items'),
    ('config/gamestate_integration_dota_coach.cfg', 'config'),
    ('.env.example', '.'),
]

hiddenimports = collect_submodules('PySide6') + collect_submodules('PIL') + ['ollama', 'dota_catalog', 'dota_meta', 'profile_store', 'map_assets']

a = Analysis(
    ['DotaCoach.pyw'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
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
    name='Dota Coach AI',
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
    icon='ui/assets/dota_coach.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Dota Coach AI',
)
