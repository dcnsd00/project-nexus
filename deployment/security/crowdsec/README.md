# NEXUS CrowdSec log detection pilot

This directory contains an acquisition template for the optional Caddy + Coraza
pilot. It does not install CrowdSec, create firewall rules, or start a bouncer.

## Data path

1. Caddy writes JSON access logs to
   `deployment/security/coraza/logs/access.log` and rotates older files in the
   same directory using names such as `access-<timestamp>-size.log`.
2. Rotated access logs are kept uncompressed so the acquisition can parse them.
3. CrowdSec reads active and rotated access logs using the official
   `crowdsecurity/caddy` collection and its HTTP behavior scenarios.
3. The Security Engine creates decisions; it does not block traffic by itself.
4. A remediation component (bouncer) is required to enforce decisions.

Caddy's access logger redacts standard sensitive request headers such as
Authorization, Proxy-Authorization, Cookie and Set-Cookie by default. Do not
enable Caddy's `log_credentials` option. The NEXUS Caddyfile also replaces
values for a fixed list of common credential-like query parameters, but this
is not generic secret detection: do not place credentials in URLs.

The acquisition file intentionally matches `access*.log`, which includes the
active `access.log` and uncompressed rolled files `access-*.log`. It does not
match the separate Coraza serial audit log.

## Configure the Windows acquisition

1. Install the CrowdSec Security Engine using its official Windows installer.
2. Review the CrowdSec Central API enrollment and data-sharing settings during installation; the Windows installer may register the engine with the Central API. Copy `acquis-windows.yaml.example` into the CrowdSec acquisition
   configuration at `C:\ProgramData\CrowdSec\config\acquis.yaml`,
   merging it with any existing acquisition entries rather than overwriting
   unrelated sources.
3. Replace the placeholder path with the absolute path to
   `deployment/security/coraza/logs/access*.log` (including rotated files).
4. From an elevated PowerShell prompt, install the Caddy collection:

```powershell
& "C:\Program Files\CrowdSec\cscli.exe" collections install crowdsecurity/caddy
```

5. Restart the CrowdSec service and verify that the Caddy access logs are being
   parsed before enabling any remediation component.

The official `crowdsecurity/caddy` collection includes the Caddy log parser and
generic HTTP scenarios for scanning and abusive request patterns. It expects
Caddy's standard JSON access-log structure.

## Enforcement warning

The Security Engine detects; it does not block. The Windows Firewall
Remediation Component can enforce decisions by adding managed Windows
Firewall rules. The current CrowdSec Windows documentation requires the
.NET 10 runtime for this component.

**Do not install or activate the Windows Firewall bouncer while the NEXUS
Caddy pilot is loopback-only.** In that mode, requests arrive from loopback;
a false positive could block local access. First move to a tested private VPN
interface, configure allowlists for the host and management peers, validate
the decision stream, and only then consider enabling the bouncer.

The bouncer modifies host firewall policy. Its installation and activation
require explicit operator approval and an administrative maintenance window.
No API key or bouncer secret belongs in Git or this repository.
