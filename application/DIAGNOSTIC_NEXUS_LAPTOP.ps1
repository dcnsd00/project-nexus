$ErrorActionPreference = 'Continue'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = Join-Path $Root '.venv\Scripts\python.exe'
Write-Host '=== NEXUS LAPTOP DIAGNOSTIC ===' -ForegroundColor Cyan
Get-CimInstance Win32_OperatingSystem | Select-Object Caption, Version, OSArchitecture
Get-CimInstance Win32_Processor | Select-Object Name, NumberOfCores, NumberOfLogicalProcessors
Get-CimInstance Win32_VideoController | Select-Object Name, DriverVersion, AdapterRAM
if (Get-Command nvidia-smi -ErrorAction SilentlyContinue) { nvidia-smi }
else { Write-Host 'nvidia-smi: indisponibil; GPU NVIDIA nu poate fi interogata prin driverul CLI.' }
if (Test-Path $Python) {
  & $Python -c "import sys; print('Python:',sys.version)"
  & $Python -c "import fastapi,uvicorn,pydantic,httpx,psutil; print('NEXUS dependencies: OK')"
  & $Python -c "from nexus_master import app; print('API routes:',len(app.routes)); print('NEXUS import: OK')"
} else { Write-Host 'Mediul .venv nu exista. Ruleaza INSTALL_NEXUS_LAPTOP.ps1.' }
