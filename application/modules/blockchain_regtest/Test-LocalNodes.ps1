param([ValidateRange(1,300)][int]$WaitSeconds = 60)
$ErrorActionPreference = 'Stop'
$Checks = @(
  @{ Name='Bitcoin Core Regtest'; Host='127.0.0.1'; Port=18443 },
  @{ Name='Anvil ETH'; Host='127.0.0.1'; Port=18545 },
  @{ Name='Anvil Base'; Host='127.0.0.1'; Port=18546 },
  @{ Name='Anvil BNB'; Host='127.0.0.1'; Port=18547 },
  @{ Name='Anvil Polygon'; Host='127.0.0.1'; Port=18548 },
  @{ Name='Anvil Arbitrum'; Host='127.0.0.1'; Port=18549 }
)
$Deadline = (Get-Date).AddSeconds($WaitSeconds)
$Open = @{}
do {
  $AllReady = $true
  foreach ($Check in $Checks) {
    $Ready = Test-NetConnection -ComputerName $Check.Host -Port $Check.Port -InformationLevel Quiet -WarningAction SilentlyContinue
    $Open[$Check.Name] = [bool]$Ready
    if (-not $Ready) { $AllReady = $false }
  }
  if ($AllReady) { break }
  Start-Sleep -Seconds 2
} while ((Get-Date) -lt $Deadline)
foreach ($Check in $Checks) {
  if ($Open[$Check.Name]) { Write-Host "[OK] $($Check.Name) $($Check.Port)" -ForegroundColor Green }
  else { Write-Host "[MISSING] $($Check.Name) $($Check.Port)" -ForegroundColor Yellow }
}
if (-not $AllReady) { throw "Local node TCP endpoints not ready after $WaitSeconds seconds. Check Docker Desktop and container logs." }
Write-Host 'All local-node TCP endpoints are reachable. RPC/transaction checks follow in nexus_v05_integration.py.' -ForegroundColor Green
