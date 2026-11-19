# NEXUS MASTER Windows x64 desktop bundle.
# Build on Windows with: python -m PyInstaller --noconfirm --clean packaging\NEXUS_DESKTOP.spec
from PyInstaller.utils.hooks import collect_submodules
from pathlib import Path

ROOT = Path(SPECPATH).parent
hidden = []
for package in (
    'webview', 'uvicorn', 'uvicorn.logging', 'app', 'modules', 'mining',
    'nexus_edge', 'research.sha2_independent.nexus_sha',
):
    try:
        hidden += collect_submodules(package)
    except Exception:
        pass

datas = [
    (str(ROOT/'dashboard.html'), '.'),
    (str(ROOT/'wallet.html'), '.'),
    (str(ROOT/'mining'), 'mining'),
    (str(ROOT/'modules'), 'modules'),
    (str(ROOT/'core'), 'core'),
    (str(ROOT/'adapters'), 'adapters'),
    (str(ROOT/'nexus_edge'), 'nexus_edge'),
    (str(ROOT/'research'), 'research'),
    (str(ROOT/'tools'), 'tools'),
    (str(ROOT/'docs'), 'docs'),
    (str(ROOT/'VERSION.json'), '.'),
    (str(ROOT/'README_RO.md'), '.'),
    (str(ROOT/'START_NEXUS_DESKTOP.pyw'), '.'),
]
a = Analysis(
    [str(ROOT/'START_NEXUS_DESKTOP.pyw')],
    pathex=[str(ROOT), str(ROOT/'core/PROJECT-NEXUS-LOCAL')],
    binaries=[],
    datas=datas,
    hiddenimports=hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter'],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [], exclude_binaries=True, name='NEXUS',
    debug=False, bootloader_ignore_signals=False, strip=False,
    upx=False, console=False,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='NEXUS')
