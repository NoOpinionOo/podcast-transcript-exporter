# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path


project_root = Path(SPECPATH)

a = Analysis(
    [str(project_root / "run_app.pyw")],
    pathex=[str(project_root)],
    binaries=[],
    datas=[
        (
            str(project_root / "spotify_transcript_app" / "samples" / "example_transcript.json"),
            "spotify_transcript_app/samples",
        )
    ],
    hiddenimports=[],
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
    name="Podcast-Transkript-Exporter",
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
    version=str(project_root / "windows_version_info.txt"),
)

