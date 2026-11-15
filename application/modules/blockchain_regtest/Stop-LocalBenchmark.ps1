$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
docker compose down --remove-orphans
if ($LASTEXITCODE -ne 0) { throw 'Docker Compose cleanup failed.' }
Write-Host 'Disposable local Bitcoin Regtest and Anvil containers stopped and removed.' -ForegroundColor Green
