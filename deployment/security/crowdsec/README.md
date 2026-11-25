# NEXUS CrowdSec log detection pilot

This directory contains an acquisition template for the optional Caddy + Coraza
pilot. It does not install CrowdSec, create firewall rules, or start a bouncer.

## Data path

1. Caddy writes JSON access logs to
   `deployment/security/coraza/logs/access.log`.
2. CrowdSec reads that file using the official `crowdsecurity/caddy`
   collection and its HTTP behavior scenarios.
3. The Security Engine creates decisions; it does not block traffic by itself.
4. A remediation component (bouncer) is required to enforce decisions.

Caddy's access logger redacts sensitive request headers such as Authorization
and Cookie by default. Do not enable Caddy's `log_credentials` option for this
pilot.

## Configure the Windows acquisition

1. Install the CrowdSec Security Engine using its official Windows installer.
2. Copy `acquis-windows.yaml.example` into the CrowdSec acquisition
   configuration at `C:\\ProgramData\\CrowdSec\\config\\acquis.yaml`,
   merging it with any existing acquisition entries rather than overwriting
   unrelated sources.
3. Replace the placeholder path with the absolute path to
   `deployment/security/coraza/logs/access.log`.
4. From an elevated PowerShell prompt, install the Caddy collection:

```powershell
& "C:\\Program Files\\CrowdSec\\cscli.exe" collections install crowdsecurity/caddy
```

5. Restart the CrowdSec service and verify that the Caddy access log is being
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
