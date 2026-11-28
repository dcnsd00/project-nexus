[CmdletBinding()]
param(
    [uri]$BaseUri = "http://127.0.0.1:8765",
    [switch]$RunLiveAiSelfTest
)

$ErrorActionPreference = "Stop"

function Assert-LoopbackBaseUri {
    param([uri]$Uri)

    if ($Uri.Scheme -ne "http" -or -not $Uri.IsDefaultPort -and $Uri.Port -lt 1) {
        throw "base_uri_must_be_http_loopback"
    }
    $hostName = $Uri.Host.TrimEnd(".").ToLowerInvariant()
    $isLoopback = $hostName -eq "localhost"
    $parsedIp = $null
    if ([System.Net.IPAddress]::TryParse($hostName, [ref]$parsedIp)) {
        $isLoopback = [System.Net.IPAddress]::IsLoopback($parsedIp)
    }
    if (-not $isLoopback -or $Uri.UserInfo -or $Uri.Query -or $Uri.Fragment) {
        throw "base_uri_must_be_http_loopback"
    }
}

function Invoke-NexusRead {
    param([string]$Path)
    $uri = [uri]::new($BaseUri, $Path.TrimStart("/"))
    Invoke-RestMethod -Method Get -Uri $uri -TimeoutSec 10
}

function Get-Field {
    param($Object, [string]$Name, $Default = $null)
    if ($null -eq $Object) { return $Default }
    $property = $Object.PSObject.Properties[$Name]
    if ($null -eq $property) { return $Default }
    return $property.Value
}

Assert-LoopbackBaseUri -Uri $BaseUri

$checks = [System.Collections.Generic.List[object]]::new()
$failed = $false

try {
    $catalog = Invoke-NexusRead "/api/nexus/workers"
    $workerCount = [int](Get-Field $catalog "worker_count" 0)
    $ok = $workerCount -eq 11
    $checks.Add([pscustomobject]@{
        name = "worker_catalog"
        status = if ($ok) { "passed" } else { "failed" }
        worker_count = $workerCount
        expected = 11
    })
    if (-not $ok) { $failed = $true }
}
catch {
    $checks.Add([pscustomobject]@{ name = "worker_catalog"; status = "error"; code = "worker_catalog_unavailable" })
    $failed = $true
}

try {
    $provider = Invoke-NexusRead "/api/nexus/workers/provider-status"
    $providerStatus = [string](Get-Field $provider "provider_status" "unknown")
    $checks.Add([pscustomobject]@{
        name = "ai_provider_configuration"
        status = if ($providerStatus -eq "live_verified") { "live_verified" } elseif ($providerStatus -eq "configured_not_live_verified") { "configured_pending_live_test" } else { "not_configured_or_misconfigured" }
        provider_status = $providerStatus
        provider = Get-Field $provider "provider" "unknown"
        model = Get-Field $provider "model"
        model_invocation_enabled = [bool](Get-Field $provider "model_invocation_enabled" $false)
        api_key_configured = [bool](Get-Field $provider "api_key_configured" $false)
    })
}
catch {
    $checks.Add([pscustomobject]@{ name = "ai_provider_configuration"; status = "error"; code = "provider_status_unavailable" })
    $failed = $true
}

try {
    $runtime = Invoke-NexusRead "/api/nexus/workers/local-runtime-status"
    $checks.Add([pscustomobject]@{
        name = "local_model_runtimes"
        status = "inspected"
        ollama_status = Get-Field (Get-Field $runtime "ollama") "status" "unknown"
        llamacpp_status = Get-Field (Get-Field $runtime "llamacpp") "status" "unknown"
        model_downloads_started = $false
        runtimes_started = $false
    })
}
catch {
    $checks.Add([pscustomobject]@{ name = "local_model_runtimes"; status = "error"; code = "local_runtime_status_unavailable" })
    $failed = $true
}

try {
    $integrations = Invoke-NexusRead "/api/integrations/status"
    $checks.Add([pscustomobject]@{
        name = "external_connectors"
        status = "inspected"
        total = Get-Field $integrations "total" 0
        live_verified = Get-Field $integrations "live_verified" 0
        operational_verified = Get-Field $integrations "operational_verified" 0
        writes_enabled = $false
    })
}
catch {
    $checks.Add([pscustomobject]@{ name = "external_connectors"; status = "error"; code = "integration_status_unavailable" })
    $failed = $true
}

if ($RunLiveAiSelfTest) {
    try {
        # Explicit opt-in: performs a real bounded provider probe and one inference
        # through each of the 11 stateless profiles. No tools or side effects.
        $selfTestUri = [uri]::new($BaseUri, "api/nexus/workers/self-test")
        $selfTest = Invoke-RestMethod -Method Post -Uri $selfTestUri -TimeoutSec 180
        $tested = [int](Get-Field $selfTest "workers_tested" 0)
        $passed = [int](Get-Field $selfTest "workers_passed" 0)
        $ok = (Get-Field $selfTest "operational_verified" $false) -eq $true -and $tested -eq 11 -and $passed -eq 11
        $checks.Add([pscustomobject]@{
            name = "live_ai_worker_self_test"
            status = if ($ok) { "live_verified" } else { "failed" }
            workers_tested = $tested
            workers_passed = $passed
            operational_verified = [bool](Get-Field $selfTest "operational_verified" $false)
            side_effects_performed = [bool](Get-Field $selfTest "side_effects_performed" $false)
        })
        if (-not $ok) { $failed = $true }
    }
    catch {
        $checks.Add([pscustomobject]@{ name = "live_ai_worker_self_test"; status = "error"; code = "live_ai_self_test_failed" })
        $failed = $true
    }
}
else {
    $checks.Add([pscustomobject]@{
        name = "live_ai_worker_self_test"
        status = "not_run"
        reason = "Pass -RunLiveAiSelfTest after configuring a provider to run 11 real model calls."
    })
}

$result = [pscustomobject]@{
    product = "NEXUS MASTER"
    check_type = "read_only_local_acceptance"
    base_uri = $BaseUri.GetLeftPart([System.UriPartial]::Authority)
    checked_at_utc = [DateTime]::UtcNow.ToString("o")
    checks = @($checks)
    passed = -not $failed
    model_downloads_started = $false
    runtimes_started = $false
    wallet_operations = 0
    miners_started = 0
    repository_changes = 0
}

$result | ConvertTo-Json -Depth 8
if ($failed) { exit 1 }
