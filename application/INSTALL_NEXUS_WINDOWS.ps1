$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root
$VersionManifest = Join-Path $Root 'VERSION.json'
if (-not (Test-Path $VersionManifest -PathType Leaf)) {
  throw "NEXUS version manifest is missing: $VersionManifest"
}
try {
  $VersionData = Get-Content -Path $VersionManifest -Raw | ConvertFrom-Json
  $Version = [string]$VersionData.version
} catch {
  throw "NEXUS version manifest is invalid: $($_.Exception.Message)"
}
$ParsedVersion = [version]::MinValue
if ([string]::IsNullOrWhiteSpace($Version) -or -not [version]::TryParse($Version, [ref]$ParsedVersion)) {
  throw "NEXUS version manifest contains an invalid version: '$Version'."
}
$Target = Join-Path $env:LOCALAPPDATA 'Programs\NEXUS'
$Desktop = [Environment]::GetFolderPath('Desktop')
$StartMenu = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\NEXUS'

Write-Host "NEXUS MASTER $Version - Windows installer" -ForegroundColor Cyan

function New-NexusShortcut([string]$Path, [string]$TargetPath, [string]$Arguments, [string]$WorkingDirectory) {
  $Wsh = New-Object -ComObject WScript.Shell
  $Sc = $Wsh.CreateShortcut($Path)
  $Sc.TargetPath = $TargetPath
  $Sc.Arguments = $Arguments
  $Sc.WorkingDirectory = $WorkingDirectory
  $Sc.Description = "NEXUS MASTER $Version"
  $Sc.Save()
}

# Prefer a verified frozen build, otherwise install an isolated Python desktop runtime.
$FrozenExe = Join-Path $Root 'dist\NEXUS\NEXUS.exe'
if (Test-Path $FrozenExe) {
  New-Item -ItemType Directory -Force -Path $Target | Out-Null
  Copy-Item (Join-Path $Root 'dist\NEXUS\*') $Target -Recurse -Force
  $InstalledExe = Join-Path $Target 'NEXUS.exe'
  if (-not (Test-Path $InstalledExe)) { throw 'Frozen build copy incomplete: NEXUS.exe is missing.' }
  New-Item -ItemType Directory -Force -Path $StartMenu | Out-Null
  New-NexusShortcut (Join-Path $Desktop 'NEXUS.lnk') $InstalledExe '' $Target
  New-NexusShortcut (Join-Path $StartMenu 'NEXUS.lnk') $InstalledExe '' $Target
  Write-Host "Frozen desktop build installed to $Target" -ForegroundColor Green
  exit 0
}

$PyLauncher = Get-Command py -ErrorAction SilentlyContinue
if (-not $PyLauncher) { throw 'Python 3.11+ x64 is required. Install it from https://www.python.org/downloads/windows/ and enable the Python Launcher.' }
$PyVersion = & py -3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
if ($LASTEXITCODE -ne 0 -or [version]$PyVersion -lt [version]'3.11') { throw "Python 3.11+ required; detected '$PyVersion'." }

$Venv = Join-Path $Root '.venv'
if (-not (Test-Path (Join-Path $Venv 'Scripts\python.exe'))) { & py -3 -m venv $Venv }
$Python = Join-Path $Venv 'Scripts\python.exe'
$PythonW = Join-Path $Venv 'Scripts\pythonw.exe'
if (-not (Test-Path $Python)) { throw 'Virtual environment creation failed.' }

& $Python -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw 'pip upgrade failed.' }
& $Python -m pip install -r requirements.txt -r requirements-desktop.txt
if ($LASTEXITCODE -ne 0) { throw 'NEXUS dependency installation failed.' }
& $Python -c "import fastapi, uvicorn, webview; import nexus_master; print('NEXUS desktop dependencies and core import: OK')"
if ($LASTEXITCODE -ne 0) { throw 'NEXUS import verification failed; no shortcuts were created.' }

New-Item -ItemType Directory -Force -Path $StartMenu | Out-Null
$Entry = Join-Path $Root 'START_NEXUS_DESKTOP.pyw'
New-NexusShortcut (Join-Path $Desktop 'NEXUS Desktop.lnk') $PythonW ('"' + $Entry + '"') $Root
New-NexusShortcut (Join-Path $StartMenu 'NEXUS Desktop.lnk') $PythonW ('"' + $Entry + '"') $Root
Write-Host "NEXUS $Version Python desktop runtime installed in $Venv" -ForegroundColor Green
Write-Host 'Shortcuts created on Desktop and Start Menu. The application binds only to 127.0.0.1.'
Write-Host 'Note: this installs the desktop runtime, not external miner binaries or wallet credentials.'
