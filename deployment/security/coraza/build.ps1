$ErrorActionPreference = "Stop"

$CaddyVersion = "v2.11.9"
$CorazaCaddyVersion = "v2.6.2"
$XcaddyVersion = "v0.4.7"
$Output = Join-Path $PSScriptRoot "caddy.exe"

$go = Get-Command go -ErrorAction SilentlyContinue
if (-not $go) {
    throw "Go 1.26.0 or newer is required. Install Go and reopen PowerShell."
}

$goVersionText = (& go version) -join " "
if ($goVersionText -notmatch 'go version go([0-9]+\.[0-9]+\.[0-9]+)') {
    throw "Could not parse Go version: $goVersionText"
}
if ([version]$Matches[1] -lt [version]"1.26.0") {
    throw "Go 1.26.0 or newer is required. Found $($Matches[1])."
}

$goBin = (& go env GOBIN).Trim()
if (-not $goBin) {
    $goPath = (& go env GOPATH).Trim()
    $goBin = Join-Path $goPath "bin"
}
New-Item -ItemType Directory -Force -Path $goBin | Out-Null

Write-Host "Installing pinned xcaddy $XcaddyVersion..."
& go install "github.com/caddyserver/xcaddy/cmd/xcaddy@$XcaddyVersion"
if ($LASTEXITCODE -ne 0) {
    throw "Could not install xcaddy $XcaddyVersion."
}

$xcaddyPath = Join-Path $goBin "xcaddy.exe"
if (-not (Test-Path $xcaddyPath)) {
    $xcaddyPath = Join-Path $goBin "xcaddy"
}
if (-not (Test-Path $xcaddyPath)) {
    throw "Pinned xcaddy executable was not created in $goBin."
}
$xcaddyVersionText = (& $xcaddyPath version) -join " "
if ($LASTEXITCODE -ne 0 -or $xcaddyVersionText -notmatch [regex]::Escape($XcaddyVersion)) {
    throw "Expected xcaddy $XcaddyVersion, found: $xcaddyVersionText"
}

Push-Location $PSScriptRoot
try {
    New-Item -ItemType Directory -Force -Path (Join-Path $PSScriptRoot "logs") | Out-Null
    Write-Host "Building Caddy $CaddyVersion with Coraza Caddy $CorazaCaddyVersion..."
    & $xcaddyPath build $CaddyVersion --with "github.com/corazawaf/coraza-caddy/v2@$CorazaCaddyVersion" --output $Output
    if ($LASTEXITCODE -ne 0) {
        throw "xcaddy build failed."
    }

    $modules = (& $Output list-modules) -join "`n"
    if ($LASTEXITCODE -ne 0 -or $modules -notmatch 'http\.handlers\.waf') {
        throw "The custom Caddy binary does not expose the Coraza WAF handler."
    }

    & $Output validate --config (Join-Path $PSScriptRoot "Caddyfile") --adapter caddyfile
    if ($LASTEXITCODE -ne 0) {
        throw "Caddyfile validation failed."
    }

    Write-Host "Build and Caddyfile validation succeeded: $Output"
    Write-Host "WAF remains in DetectionOnly mode and binds only to 127.0.0.1:8780."
}
finally {
    Pop-Location
}
