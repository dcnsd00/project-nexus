# NEXUS local Coraza WAF pilot

This is an **optional, local-only WAF reverse-proxy pilot** for the NEXUS CORE
FastAPI service. It is not installed or activated automatically.

## Fixed integration boundary

- NEXUS CORE remains the application and listens on `127.0.0.1:8765`.
- Caddy + Coraza listens on `127.0.0.1:8780` and proxies to CORE.
- The Caddy listener is explicitly loopback-only; it is not exposed to LAN/WAN.
- OWASP CRS is embedded through the official Coraza Caddy module.
- `SecRuleEngine DetectionOnly` is intentional for the first pilot. Requests
  are inspected and logged, not blocked by CRS rules at this stage.
- The NEXUS EDGE in-process rate limiter remains a separate defense layer.
- This does not configure VPN, Windows Firewall, DNS, certificates, or a
  public listener.

The current CORE README documents the local command as:

```powershell
uvicorn app.main:app --host 127.0.0.1 --port 8765
```

## Pinned build inputs

| Component | Version |
|---|---:|
| Go | 1.26.0 or newer |
| xcaddy | 0.4.7 |
| Caddy | 2.11.9 |
| Coraza Caddy module | 2.6.2 |

The Coraza Caddy module embeds OWASP CRS when `load_owasp_crs` is enabled.
The plugin's release metadata currently pins Coraza 3.8.1 and CRS 4.30.0.
Review upstream security advisories and release notes before updating pins.

## Build on Windows

From this directory in PowerShell:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\build.ps1
```

The script installs the pinned xcaddy version into the Go bin directory if
needed, builds a custom Caddy binary with the Coraza module, checks that the
WAF module is present, and validates the Caddyfile. It does not start Caddy.

## Start the local pilot

1. Start NEXUS CORE on `127.0.0.1:8765`.
2. In a separate PowerShell window, run:

```powershell
.\caddy.exe run --config .\Caddyfile --adapter caddyfile
```

3. Use `http://127.0.0.1:8780` for requests that should pass through the WAF.
4. Confirm that the application remains reachable only on loopback. Do not
   change either listener to `0.0.0.0` for this pilot.

Requests made directly to `127.0.0.1:8765` bypass the WAF. The loopback-only
pilot is intended for local validation, not for protecting a remotely
reachable service. A future VPN deployment must bind the proxy to the
designated private interface and firewall the backend port so that clients
cannot bypass the proxy.

## Promotion gates

Do not change `DetectionOnly` to `On` until:

- normal NEXUS API traffic has been exercised through port 8780;
- Coraza audit logs have been reviewed for false positives;
- JSON request bodies and expected large payloads have been checked;
- CRS exclusions, if needed, are narrowly scoped and documented;
- direct backend access is blocked for all remote clients;
- the VPN and firewall policy is deny-by-default and tested.

Do not expose the WAF or CORE directly to the public internet as part of this
experimental package.
