$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root
$LogDir = Join-Path $env:LOCALAPPDATA 'NEXUS\logs'
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$Log = Join-Path $LogDir 'install.log'
Start-Transcript -Path $Log -Append | Out-Null
try {
    Write-Host 'NEXUS MASTER - instalare laptop Windows 11' -ForegroundColor Cyan
    $PyLauncher = Get-Command py -ErrorAction SilentlyContinue
    if (-not $PyLauncher) { throw 'Python Launcher (py.exe) nu este instalat. Instaleaza Python 3.11+ x64 si bifeaza Add Python to PATH.' }
    $VersionText = (& py -3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')").Trim()
    if ([version]$VersionText -lt [version]'3.11') { throw "Este necesar Python 3.11+ x64. Detectat: $VersionText" }
    $Venv = Join-Path $Root '.venv'
    if (-not (Test-Path (Join-Path $Venv 'Scripts\python.exe'))) { & py -3 -m venv $Venv }
    $Python = Join-Path $Venv 'Scripts\python.exe'
    & $Python -m pip install --upgrade pip
    if ($LASTEXITCODE -ne 0) { throw 'Actualizarea pip a esuat.' }
    & $Python -m pip install -r (Join-Path $Root 'requirements.txt') -r (Join-Path $Root 'requirements-desktop.txt')
    if ($LASTEXITCODE -ne 0) { throw 'Instalarea dependentelor NEXUS a esuat.' }
    # Smoke test: import the real API and exercise the manifest/dashboard endpoints locally.
    $Smoke = @'
from fastapi.testclient import TestClient
from nexus_master import app
with TestClient(app) as c:
    m = c.get('/api/nexus/master')
    assert m.status_code == 200 and m.json().get('product') == 'NEXUS', (m.status_code, m.text[:300])
    d = c.get('/api/nexus/dashboard')
    assert d.status_code == 200 and len(d.text) > 100, (d.status_code, d.text[:300])
    r = c.get('/api/research/rcsc/status')
    assert r.status_code == 200 and r.json().get('integrated') is True, (r.status_code, r.text[:300])
print('NEXUS_SMOKE_TEST_OK')
'@
    $SmokeFile = Join-Path $env:TEMP 'nexus_install_smoke.py'
    Set-Content -Path $SmokeFile -Value $Smoke -Encoding UTF8
    & $Python $SmokeFile
    if ($LASTEXITCODE -ne 0) { throw 'Testul local de pornire/API a esuat. Vezi logul de instalare.' }
    $Desktop = [Environment]::GetFolderPath('Desktop')
    $Wsh = New-Object -ComObject WScript.Shell
    $Shortcut = $Wsh.CreateShortcut((Join-Path $Desktop 'NEXUS.lnk'))
    $Shortcut.TargetPath = Join-Path $Venv 'Scripts\pythonw.exe'
    $Shortcut.Arguments = '"' + (Join-Path $Root 'START_NEXUS_DESKTOP.pyw') + '"'
    $Shortcut.WorkingDirectory = $Root
    $Shortcut.Description = 'NEXUS MASTER - motor local si panou de control'
    $Shortcut.Save()
    Write-Host 'INSTALARE REUSITA. Porneste NEXUS din shortcut-ul de pe Desktop.' -ForegroundColor Green
    Write-Host 'Log instalare: ' $Log
}
catch {
    Write-Host ('EROARE: ' + $_.Exception.Message) -ForegroundColor Red
    Write-Host ('Log: ' + $Log)
    throw
}
finally { Stop-Transcript | Out-Null }
