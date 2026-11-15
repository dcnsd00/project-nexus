$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Miners = Join-Path $Root 'miners'
$Temp = Join-Path $env:TEMP 'MULTIMINER_X_backend_install'
New-Item -ItemType Directory -Force -Path $Miners, $Temp | Out-Null

function Download-Verified($Url, $Destination, $Algorithm, $ExpectedHash) {
    Write-Host "Downloading $([IO.Path]::GetFileName($Destination)) from official release..." -ForegroundColor Cyan
    Invoke-WebRequest -Uri $Url -OutFile $Destination -UseBasicParsing
    $Actual = (Get-FileHash -Path $Destination -Algorithm $Algorithm).Hash.ToLowerInvariant()
    if ($Actual -ne $ExpectedHash.ToLowerInvariant()) {
        Remove-Item -Force $Destination
        throw "$Algorithm mismatch. Expected $ExpectedHash; got $Actual. Download removed."
    }
    Write-Host "$Algorithm verified: $Actual" -ForegroundColor Green
}

# XMRig official Windows x64 release; SHA-256 from xmrig.com/download.
$XmrigZip = Join-Path $Temp 'xmrig-6.26.0-windows-x64.zip'
Download-Verified `
  'https://github.com/xmrig/xmrig/releases/download/v6.26.0/xmrig-6.26.0-windows-x64.zip' `
  $XmrigZip 'SHA256' 'bba8097cb37d9b458a1cb1137876b27cde6740d17fe4ccbc086ba07d87d9e147'
$XmrigDir = Join-Path $Miners 'xmrig'
if (Test-Path $XmrigDir) { Remove-Item -Recurse -Force $XmrigDir }
New-Item -ItemType Directory -Force -Path $XmrigDir | Out-Null
Expand-Archive -Path $XmrigZip -DestinationPath $XmrigDir -Force

# SRBMiner-MULTI official GitHub release. MD5 is the archive checksum published by its release page.
$SrbZip = Join-Path $Temp 'SRBMiner-Multi-3-8-5-win64.zip'
Download-Verified `
  'https://github.com/doktor83/SRBMiner-Multi/releases/download/3.8.5/SRBMiner-Multi-3-8-5-win64.zip' `
  $SrbZip 'MD5' '1f1509095ad8500d81ce05994b629123'
$SrbDir = Join-Path $Miners 'srbminer'
if (Test-Path $SrbDir) { Remove-Item -Recurse -Force $SrbDir }
New-Item -ItemType Directory -Force -Path $SrbDir | Out-Null
Expand-Archive -Path $SrbZip -DestinationPath $SrbDir -Force

$X = Get-ChildItem -Path $XmrigDir -Filter 'xmrig.exe' -Recurse | Select-Object -First 1
$S = Get-ChildItem -Path $SrbDir -Filter 'SRBMiner-MULTI.exe' -Recurse | Select-Object -First 1
if (-not $X -or -not $S) { throw 'Miner executable not found after extraction.' }
Write-Host "XMRig: $($X.FullName)" -ForegroundColor Green
Write-Host "SRBMiner: $($S.FullName)" -ForegroundColor Green
Write-Host 'Install complete. No antivirus exclusions or administrator changes were made.' -ForegroundColor Green
