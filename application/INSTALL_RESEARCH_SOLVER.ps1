$ErrorActionPreference = 'Stop'
$Root = $PSScriptRoot
$VenvPython = Join-Path $Root '.venv\Scripts\python.exe'
if (-not (Test-Path $VenvPython)) { throw 'Mediul .venv nu există. Rulează mai întâi INSTALL_NEXUS_WINDOWS.ps1.' }
& $VenvPython -m pip install -r (Join-Path $Root 'requirements-research.txt')
if ($LASTEXITCODE -ne 0) { throw 'Instalarea solverului SAT a eșuat.' }
Write-Host 'Solver SAT instalat. Repornește NEXUS pentru detectare.'
