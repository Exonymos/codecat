# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['src/codecat/__main__.py'],
    pathex=['src'],
    binaries=[],
    datas=[('assets/favicon.ico', '.')],
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='codecat',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    icon='assets/favicon.ico',
    include_binaries=True,
    version='file_version_info.txt',
)