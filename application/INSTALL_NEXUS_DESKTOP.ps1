$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root
$PythonW = Join-Path $Root '.venv\Scripts\pythonw.exe'
$Python = Join-Path $Root '.venv\Scripts\python.exe'
if (-not (Test-Path $Python)) { throw 'NEXUS nu este instalat. Rulează mai întâi INSTALL_NEXUS_WINDOWS.ps1.' }
& $Python -m pip install -r (Join-Path $Root 'requirements-desktop.txt')
if ($LASTEXITCODE -ne 0) { throw 'Instalarea pywebview a eșuat. Verifică rețeaua și încearcă din nou.' }
$Desktop = [Environment]::GetFolderPath('Desktop')
$ShortcutPath = Join-Path $Desktop 'NEXUS Desktop.lnk'
$Wsh = New-Object -ComObject WScript.Shell
$Sc = $Wsh.CreateShortcut($ShortcutPath)
$Sc.TargetPath = $PythonW
$Sc.Arguments = '"' + (Join-Path $Root 'START_NEXUS_DESKTOP.pyw') + '"'
$Sc.WorkingDirectory = $Root
$Sc.Description = 'NEXUS desktop app - local API and connected web modules'
$Sc.Save()
Write-Host 'NEXUS Desktop installed. Launch it from the desktop shortcut.' -ForegroundColor Green
