$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root
if (-not (Get-Command py -ErrorAction SilentlyContinue)) { throw 'Python 3.11+ x64 is required. Install from https://www.python.org/downloads/windows/.' }
$ver = & py -3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
if ([version]$ver -lt [version]'3.11') { throw "Python 3.11+ required; found $ver" }
if (-not (Test-Path '.venv-build')) { & py -3 -m venv .venv-build }
$Py = Join-Path $Root '.venv-build\Scripts\python.exe'
& $Py -m pip install --upgrade pip
& $Py -m pip install -r requirements.txt -r requirements-desktop.txt pyinstaller
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
& $Py -m PyInstaller --noconfirm --clean packaging\NEXUS_DESKTOP.spec
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller build failed.' }
Write-Host 'Build created at dist\NEXUS\NEXUS.exe. This is an onedir distribution; keep the _internal folder beside the EXE.' -ForegroundColor Green
