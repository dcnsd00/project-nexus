# PyInstaller onedir build; run on Windows x64 with Python 3.11+.
from PyInstaller.utils.hooks import collect_submodules
from pathlib import Path
ROOT = Path(SPECPATH).parent.parent
hidden = (collect_submodules('webview') + collect_submodules('uvicorn') + collect_submodules('uvicorn.logging') + collect_submodules('app') + collect_submodules('modules') + collect_submodules('mining'))
datas = [
    (str(ROOT/'dashboard.html'), '.'), (str(ROOT/'wallet.html'), '.'),
    (str(ROOT/'mining'), 'mining'), (str(ROOT/'modules'), 'modules'),
    (str(ROOT/'core'), 'core'), (str(ROOT/'adapters'), 'adapters'),
    (str(ROOT/'research'), 'research'),
    (str(ROOT/'docs'), 'docs'), (str(ROOT/'VERSION.json'), '.'), (str(ROOT/'README_RO.md'), '.'),
]
a = Analysis([str(ROOT/'START_NEXUS_DESKTOP.pyw')], pathex=[str(ROOT), str(ROOT/'core/PROJECT-NEXUS-LOCAL')],
             binaries=[], datas=datas, hiddenimports=hidden, hookspath=[], hooksconfig={}, runtime_hooks=[], excludes=['tkinter'], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='NEXUS', debug=False,
          bootloader_ignore_signals=False, strip=False, upx=False, console=False)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='NEXUS')
