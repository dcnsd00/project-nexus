$ErrorActionPreference = 'Stop'
$Root = $PSScriptRoot
$TempRoot = Join-Path $env:TEMP ('nexus-audit-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Force -Path $TempRoot | Out-Null
$env:PYTHONPATH = "$Root;$Root\core\PROJECT-NEXUS-LOCAL"
$env:NEXUS_DB = Join-Path $TempRoot 'nexus_master.db'
$env:NEXUS_INTEL_DB = Join-Path $TempRoot 'nexus_intelligence.db'
$env:NEXUS_WALLET_DB = Join-Path $TempRoot 'nexus_wallets.db'
$env:NEXUS_SHA2_RESULTS_DIR = Join-Path $TempRoot 'sha2_results'
try {
  py -3 -m compileall -q $Root
  if ($LASTEXITCODE -ne 0) { throw 'Python compile check failed.' }
  py -3 (Join-Path $Root 'tools_check_dashboard_js.py') $Root
  if ($LASTEXITCODE -ne 0) { throw 'Dashboard JavaScript check failed.' }
  py -3 -m pytest -q (Join-Path $Root 'tests')
  if ($LASTEXITCODE -ne 0) { throw 'NEXUS master tests failed.' }
  $MM = Join-Path $Root 'adapters\multiminer_x\MULTIMINER_X_v1.0'
  Push-Location $MM
  $env:PYTHONPATH = $MM
  py -3 -m pytest -q tests
  if ($LASTEXITCODE -ne 0) { throw 'MultiMiner tests failed.' }
  Pop-Location
  $FS = Join-Path $Root 'adapters\fieldstation\crypto_fieldstation'
  Push-Location $FS
  $env:PYTHONPATH = $FS
  py -3 -m pytest -q tests
  if ($LASTEXITCODE -ne 0) { throw 'Fieldstation tests failed.' }
  Pop-Location
  $W = Join-Path $Root 'modules\wallet_benchmark'
  Push-Location $W
  py -3 -m pytest -q tests
  if ($LASTEXITCODE -ne 0) { throw 'Wallet tests failed.' }
  Push-Location (Join-Path $W 'v05')
  py -3 -m pytest -q test_v05_unit.py
  if ($LASTEXITCODE -ne 0) { throw 'Local-chain unit tests failed.' }
  Pop-Location
  Pop-Location
  $Research = Join-Path $Root 'research\sha2_independent'
  Push-Location $Research
  $env:PYTHONPATH = "$Root;$Research"
  py -3 research_main.py test
  if ($LASTEXITCODE -ne 0) { throw 'Independent SHA-2 research tests failed.' }
  py -3 research_main.py verify --out-dir (Join-Path $Research 'results')
  if ($LASTEXITCODE -ne 0) { throw 'Independent SHA-2 research verification failed.' }
  Pop-Location
  Write-Host 'NEXUS 0.10.21 offline audit suites passed. Public pool, Docker/Bitcoin Core/Anvil and Windows WebView2 runtime require separate local checks.' -ForegroundColor Green
}
finally {
  Remove-Item -Recurse -Force $TempRoot -ErrorAction SilentlyContinue
}
