# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec file for Yanhu Sessions desktop app."""

import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

block_cipher = None

# Determine platform-specific settings
is_macos = sys.platform == 'darwin'
is_windows = sys.platform == 'win32'

# Collect all submodules for packages with dynamic imports
hiddenimports_base = [
    'yanhu.app',
    'yanhu.cli',
    'yanhu.session',
    'yanhu.manifest',
    'yanhu.segmenter',
    'yanhu.extractor',
    'yanhu.analyzer',
    'yanhu.transcriber',
    'yanhu.aligner',
    'yanhu.composer',
    'yanhu.watcher',
    'yanhu.progress',
    'yanhu.verify',
    'yanhu.metrics',
    'yanhu.asr_registry',
    'flask',
    'markdown',
    'jinja2',
    'werkzeug',
]

# ASR dependencies with comprehensive submodule collection
hiddenimports_asr = [
    'faster_whisper',
    'av',
    'ctranslate2',
    'tokenizers',
    'huggingface_hub',
    'onnxruntime',
    'tqdm',
    'tiktoken',
    'regex',
    'safetensors',
]

# Collect submodules for packages that use dynamic imports
hiddenimports_collected = []
for pkg in ['faster_whisper', 'tokenizers', 'huggingface_hub', 'tiktoken', 'safetensors']:
    try:
        hiddenimports_collected += collect_submodules(pkg)
    except Exception:
        # If collection fails, package may not be installed (skip gracefully)
        pass

# Collect data files for huggingface packages
datas_collected = []
for pkg in ['tokenizers', 'huggingface_hub']:
    try:
        datas_collected += collect_data_files(pkg, include_py_files=True)
    except Exception:
        pass

a = Analysis(
    ['src/yanhu/launcher.py'],
    pathex=[],
    binaries=[],
    datas=datas_collected,
    hiddenimports=hiddenimports_base + hiddenimports_asr + hiddenimports_collected,
    hookspath=[],
    hooksconfig={},
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
    name='yanhu',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,  # Show console for now (can be False for Windows GUI)
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
    upx=True,
    upx_exclude=[],
    name='yanhu',
)

# macOS: Create .app bundle
if is_macos:
    app = BUNDLE(
        coll,
        name='Yanhu Sessions.app',
        icon=None,  # Add icon path here if available
        bundle_identifier='com.yanhu.sessions',
        info_plist={
            'NSPrincipalClass': 'NSApplication',
            'NSHighResolutionCapable': 'True',
            'CFBundleShortVersionString': '0.1.0',
        },
    )
