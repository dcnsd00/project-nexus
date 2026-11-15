$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw 'Docker is required. Install Docker Desktop with Compose v2.'
}
docker compose version | Out-Null
docker compose down --remove-orphans | Out-Null
docker compose up -d
if ($LASTEXITCODE -ne 0) { throw 'Could not start the local test nodes.' }
try {
    .\Test-LocalNodes.ps1 -WaitSeconds 90
    if ($LASTEXITCODE -ne 0) { throw 'Local test nodes did not become reachable.' }
    python .\nexus_v05_integration.py
    if ($LASTEXITCODE -ne 0) { throw 'NEXUS integration benchmark failed. See results/node_integration_v0.5.json.' }
} catch {
    Write-Warning 'Containers are left running for diagnostics. Review docker compose logs, then run Stop-LocalBenchmark.ps1.'
    throw
}
