$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw 'Docker is required. Install Docker Desktop with Compose v2.'
}
docker compose version | Out-Null
docker compose down --remove-orphans | Out-Null
docker compose up -d
if ($LASTEXITCODE -ne 0) { throw 'Could not start the local test nodes.' }
python .\nexus_v05_integration.py
if ($LASTEXITCODE -ne 0) { throw 'NEXUS integration benchmark failed. See results/node_integration_v0.5.json.' }
