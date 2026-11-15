$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$Source = Join-Path $PSScriptRoot 'miner.c'
$Build = Join-Path $PSScriptRoot 'build'
$Output = Join-Path $Build 'nexus_miner.dll'
New-Item -ItemType Directory -Force -Path $Build | Out-Null
$Gcc = Get-Command gcc -ErrorAction SilentlyContinue
if (-not $Gcc) { throw 'GCC nu este în PATH. Instalează toolchain-ul MSYS2 UCRT64 cu winpthreads.' }
& $Gcc.Source -O3 -pthread -shared -DNEXUS_LIBRARY -o $Output $Source
if ($LASTEXITCODE -ne 0) { throw "Compilarea minerului C a eșuat (exit $LASTEXITCODE)." }
Write-Host "Native NEXUS miner construit: $Output"
