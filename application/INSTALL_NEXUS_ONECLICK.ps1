[CmdletBinding()]
param([switch]$NoLaunch)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$PackageRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$LogRoot = Join-Path $env:LOCALAPPDATA 'NEXUS\logs'
New-Item -ItemType Directory -Force -Path $LogRoot | Out-Null
$LogPath = Join-Path $LogRoot 'one-click-install.log'
Start-Transcript -Path $LogPath -Append | Out-Null

function Test-WebView2Runtime {
    $clientRoots = @(
        'HKLM:\SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients',
        'HKLM:\SOFTWARE\Microsoft\EdgeUpdate\Clients',
        'HKCU:\SOFTWARE\Microsoft\EdgeUpdate\Clients'
    )
    foreach ($root in $clientRoots) {
        if (Test-Path $root) {
            foreach ($key in Get-ChildItem $root -ErrorAction SilentlyContinue) {
                $p = Get-ItemProperty $key.PSPath -ErrorAction SilentlyContinue
                if ($p.name -eq 'Microsoft Edge WebView2 Runtime' -and $p.pv) { return $true }
            }
        }
    }
    return $false
}

function Ensure-WebView2Runtime {
    if (Test-WebView2Runtime) {
        Write-Host 'WebView2 Runtime: detected.' -ForegroundColor Green
        return
    }
    Write-Host 'WebView2 Runtime is missing. Downloading the official Microsoft Evergreen Bootstrapper...' -ForegroundColor Yellow
    $bootstrapper = Join-Path $env:TEMP 'NEXUS-WebView2-EvergreenBootstrapper.exe'
    Invoke-WebRequest -Uri 'https://go.microsoft.com/fwlink/p/?LinkId=2124703' -OutFile $bootstrapper -UseBasicParsing
    $signature = Get-AuthenticodeSignature -FilePath $bootstrapper
    if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch 'Microsoft') {
        throw 'WebView2 bootstrapper signature could not be verified as Microsoft. Installation stopped.'
    }
    $p = Start-Process -FilePath $bootstrapper -ArgumentList '/silent','/install' -Wait -PassThru
    if ($p.ExitCode -notin @(0, 3010)) { throw "WebView2 installation failed with exit code $($p.ExitCode)." }
    if (-not (Test-WebView2Runtime)) { throw 'WebView2 Runtime was not detected after installation.' }
    Write-Host 'WebView2 Runtime installed.' -ForegroundColor Green
}

try {
    Write-Host ''
    Write-Host 'NEXUS MASTER 0.10.26 — one-click desktop installation' -ForegroundColor Cyan
    $source = Join-Path $PackageRoot 'dist\NEXUS'
    $sourceExe = Join-Path $source 'NEXUS.exe'
    $sourceInternal = Join-Path $source '_internal'
    $manifestPath = Join-Path $PackageRoot 'NEXUS_PACKAGE_MANIFEST.json'
    if (-not (Test-Path $sourceExe) -or -not (Test-Path $sourceInternal)) {
        throw 'The frozen desktop build is missing. This ZIP is incomplete and cannot be installed.'
    }
    if (-not (Test-Path $manifestPath)) { throw 'Package integrity manifest is missing.' }

    $manifest = Get-Content $manifestPath -Raw | ConvertFrom-Json
    if ($manifest.version -ne '0.10.26') { throw "Package version mismatch: $($manifest.version)." }
    foreach ($entry in $manifest.files) {
        $filePath = Join-Path $source $entry.path
        if (-not (Test-Path $filePath -PathType Leaf)) { throw "Package file missing: $($entry.path)" }
        $actual = (Get-FileHash -Algorithm SHA256 -Path $filePath).Hash.ToLowerInvariant()
        if ($actual -ne $entry.sha256.ToLowerInvariant()) { throw "Package integrity check failed: $($entry.path)" }
    }
    Write-Host "Package integrity: $($manifest.files.Count) files verified." -ForegroundColor Green

    Ensure-WebView2Runtime

    $target = Join-Path $env:LOCALAPPDATA 'Programs\NEXUS'
    $startMenu = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\NEXUS'
    New-Item -ItemType Directory -Force -Path $target,$startMenu | Out-Null

    # Close the old desktop shell gracefully before replacing binaries.
    # Never delete data, databases, wallet vaults, configuration, or user files.
    $runningApps = @(Get-Process -Name 'NEXUS' -ErrorAction SilentlyContinue)
    foreach ($app in $runningApps) {
        try { [void]$app.CloseMainWindow() } catch {}
        if (-not $app.WaitForExit(10000)) {
            Write-Warning 'NEXUS did not close within 10 seconds; stopping the old desktop process to complete the update.'
            Stop-Process -Id $app.Id -Force -ErrorAction SilentlyContinue
        }
    }
    Copy-Item -Path (Join-Path $source '*') -Destination $target -Recurse -Force
    $installedExe = Join-Path $target 'NEXUS.exe'
    if (-not (Test-Path $installedExe)) { throw 'NEXUS.exe was not copied to the installation directory.' }

    $wsh = New-Object -ComObject WScript.Shell
    $desktopPath = [Environment]::GetFolderPath('Desktop')
    foreach ($shortcutPath in @(
        (Join-Path $desktopPath 'NEXUS MASTER.lnk'),
        (Join-Path $startMenu 'NEXUS MASTER.lnk')
    )) {
        $shortcut = $wsh.CreateShortcut($shortcutPath)
        $shortcut.TargetPath = $installedExe
        $shortcut.WorkingDirectory = $target
        $shortcut.Description = 'NEXUS MASTER — local desktop control center'
        $shortcut.IconLocation = "$installedExe,0"
        $shortcut.Save()
    }

    Write-Host 'Running packaged application smoke test...' -ForegroundColor Cyan
    $test = Start-Process -FilePath $installedExe -ArgumentList '--self-test' -WorkingDirectory $target -Wait -PassThru
    if ($test.ExitCode -ne 0) { throw "Packaged NEXUS self-test failed with exit code $($test.ExitCode)." }

    Write-Host 'NEXUS desktop installation completed successfully.' -ForegroundColor Green
    Write-Host "Installed at: $target"
    Write-Host 'Existing local data was preserved. No miner or wallet was started or unlocked.'
    if (-not $NoLaunch) {
        Write-Host 'Starting NEXUS MASTER desktop...'
        Start-Process -FilePath $installedExe -WorkingDirectory $target
    } else {
        Write-Host 'NoLaunch requested: packaged install and smoke test passed; desktop UI launch skipped.'
    }
}
catch {
    Write-Host ("INSTALLATION ERROR: " + $_.Exception.Message) -ForegroundColor Red
    Write-Host "Full log: $LogPath"
    Stop-Transcript | Out-Null
    exit 1
}
finally {
    try { Stop-Transcript | Out-Null } catch {}
}
