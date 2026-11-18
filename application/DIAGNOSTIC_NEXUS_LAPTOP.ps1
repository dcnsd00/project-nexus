[CmdletBinding()]
param(
  [string]$OutputDirectory = (Join-Path $env:LOCALAPPDATA 'NEXUS\diagnostics')
)

$ErrorActionPreference = 'Continue'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = Join-Path $Root '.venv\Scripts\python.exe'
$Timestamp = (Get-Date).ToUniversalTime().ToString('yyyyMMdd-HHmmss')
New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null

function Get-CimRows {
  param([string]$ClassName, [string]$Namespace = 'root\cimv2', [string[]]$Properties = @('*'))
  try {
    return @(Get-CimInstance -Namespace $Namespace -ClassName $ClassName -ErrorAction Stop |
      Select-Object -Property $Properties)
  } catch {
    return @{ available = $false; reason = $_.Exception.GetType().Name }
  }
}

Write-Host '=== NEXUS MASTER — WINDOWS HARDWARE AUDIT ===' -ForegroundColor Cyan
Write-Host 'Read-only inventory and live sensor capture. No miner or stress workload is started.'

$os = Get-CimRows -ClassName 'Win32_OperatingSystem' -Properties @('Caption','Version','BuildNumber','OSArchitecture','LastBootUpTime','TotalVisibleMemorySize','FreePhysicalMemory')
$cpu = Get-CimRows -ClassName 'Win32_Processor' -Properties @('Name','Manufacturer','ProcessorId','NumberOfCores','NumberOfLogicalProcessors','MaxClockSpeed','CurrentClockSpeed','L2CacheSize','L3CacheSize','VirtualizationFirmwareEnabled','SecondLevelAddressTranslationExtensions')
$memory = Get-CimRows -ClassName 'Win32_PhysicalMemory' -Properties @('BankLabel','Capacity','Speed','ConfiguredClockSpeed','Manufacturer','PartNumber')
$system = Get-CimRows -ClassName 'Win32_ComputerSystem' -Properties @('Manufacturer','Model','SystemType','TotalPhysicalMemory','NumberOfLogicalProcessors')
$bios = Get-CimRows -ClassName 'Win32_BIOS' -Properties @('Manufacturer','SMBIOSBIOSVersion','ReleaseDate')
$board = Get-CimRows -ClassName 'Win32_BaseBoard' -Properties @('Manufacturer','Product','Version')
$video = Get-CimRows -ClassName 'Win32_VideoController' -Properties @('Name','DriverVersion','AdapterRAM','VideoProcessor','CurrentHorizontalResolution','CurrentVerticalResolution','CurrentRefreshRate')
$disk = Get-CimRows -ClassName 'Win32_LogicalDisk' -Properties @('DeviceID','FileSystem','Size','FreeSpace','VolumeName')
$network = @(Get-NetAdapter -ErrorAction SilentlyContinue |
  Select-Object Name, InterfaceDescription, Status, LinkSpeed, MacAddress)

$temperatureSensors = @()
$temperatureStatus = @{ available = $false; source = 'LibreHardwareMonitor WMI'; reason = $null }
try {
  $temperatureSensors = @(Get-CimInstance -Namespace 'root\LibreHardwareMonitor' -ClassName Sensor -ErrorAction Stop |
    Where-Object { $_.SensorType -eq 'Temperature' -and $null -ne $_.Value } |
    Select-Object Name, SensorType, Value, Identifier, Min, Max)
  $temperatureStatus.available = ($temperatureSensors.Count -gt 0)
  if (-not $temperatureStatus.available) {
    $temperatureStatus.reason = 'WMI namespace exists but no temperature sensors were returned.'
  }
} catch {
  $temperatureStatus.reason = 'LibreHardwareMonitor WMI unavailable. Start LibreHardwareMonitor and enable its WMI interface.'
}

$nvidia = @{ available = $false; source = 'nvidia-smi'; output = $null; reason = 'nvidia-smi not found' }
$NvidiaSmi = Get-Command 'nvidia-smi.exe' -ErrorAction SilentlyContinue
if ($NvidiaSmi) {
  $NvidiaQuery = 'name,driver_version,temperature.gpu,utilization.gpu,memory.used,memory.total,power.draw,power.limit,clocks.current.graphics,clocks.current.sm,clocks.current.memory,clocks_throttle_reasons.active'
  $NvidiaOutput = & $NvidiaSmi.Source "--query-gpu=$NvidiaQuery" '--format=csv,noheader,nounits' 2>&1
  if ($LASTEXITCODE -eq 0) {
    $nvidia = @{ available = $true; source = 'nvidia-smi'; output = ($NvidiaOutput | Out-String).Trim(); reason = $null }
  } else {
    $FallbackOutput = & $NvidiaSmi.Source '--query-gpu=name,driver_version,temperature.gpu,utilization.gpu,memory.used,memory.total,power.draw' '--format=csv,noheader,nounits' 2>&1
    if ($LASTEXITCODE -eq 0) {
      $nvidia = @{ available = $true; source = 'nvidia-smi-basic-query'; output = ($FallbackOutput | Out-String).Trim(); reason = 'Some optional clock/power/throttle fields are unsupported by this GPU or driver.' }
    } else {
      $nvidia = @{ available = $false; source = 'nvidia-smi'; output = ($FallbackOutput | Out-String).Trim(); reason = 'nvidia-smi query failed.' }
    }
  }
}

$powerPlan = (& powercfg.exe /getactivescheme 2>&1 | Out-String).Trim()
$pythonInfo = @{ available = $false; executable = $Python; version = $null; imports = $null }
if (Test-Path $Python) {
  $pythonInfo.version = (& $Python -c "import sys; print(sys.version)" 2>&1 | Out-String).Trim()
  $pythonInfo.imports = (& $Python -c "import fastapi,uvicorn,pydantic,httpx,psutil; print('NEXUS dependencies: OK')" 2>&1 | Out-String).Trim()
  $pythonInfo.available = ($LASTEXITCODE -eq 0)
} else {
  $pythonInfo.reason = 'NEXUS .venv not found. Run INSTALL_NEXUS_LAPTOP.ps1 first.'
}

$report = [ordered]@{
  schema = 'nexus.hardware.audit.v1'
  generated_at_utc = (Get-Date).ToUniversalTime().ToString('o')
  collection_mode = 'read_only_no_miner_autostart_no_stress_test'
  system = $system
  operating_system = $os
  processors = $cpu
  memory_modules = $memory
  bios = $bios
  motherboard = $board
  video_controllers = $video
  nvidia_gpu = $nvidia
  temperatures = $temperatureStatus
  temperature_sensors = $temperatureSensors
  disks = $disk
  network_adapters = $network
  active_power_plan = $powerPlan
  nexus_python_environment = $pythonInfo
  notes = @(
    'CPU temperature readings require a working hardware sensor provider; on Windows this script uses LibreHardwareMonitor WMI.',
    'GPU AdapterRAM from Win32_VideoController is not treated as authoritative; prefer nvidia-smi memory.total where supported.',
    'This diagnostic does not start miners, overclock hardware, or run a stress test.',
    'Thermal throttling is reported only when the sensor/driver exposes the relevant value.'
  )
}
$OutputFile = Join-Path $OutputDirectory "nexus-hardware-audit-$Timestamp.json"
$report | ConvertTo-Json -Depth 10 | Set-Content -Path $OutputFile -Encoding UTF8

Write-Host ''
Write-Host 'CPU:'
$cpu | Format-Table Name, NumberOfCores, NumberOfLogicalProcessors, MaxClockSpeed, CurrentClockSpeed -AutoSize
Write-Host 'GPU:'
$nvidia | Format-List
Write-Host ("Temperature sensors: " + $temperatureSensors.Count)
if (-not $temperatureStatus.available) { Write-Warning $temperatureStatus.reason }
Write-Host ''
Write-Host "Raport salvat: $OutputFile" -ForegroundColor Green
Write-Host 'Trimite raportul JSON pentru verificarea compatibilitatii si compararea benchmark-urilor.'
