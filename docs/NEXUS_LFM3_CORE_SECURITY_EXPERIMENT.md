# NEXUS LFM3 + CORE SECURITY — Experimental Audit

**Status:** experimental branch; integration is isolated from `main`  
**Branch:** `experiment/lfm3-core-security-lab-v1`  
**Parent baseline:** `feature/edge-replay-protection-sqlite-v1` at `d5e8901a72c8a55e9dc92e69b5cdaa026f25e6c6`  
**Scope:** local LFM3 provider adapter, source-code reuse assessment, and security architecture proposal.

## 1. Guardrails

- No changes are made to `main`.
- LFM3 is an optional provider. Existing OpenAI Responses API behavior remains the default.
- Selecting LFM3 is explicit through `NEXUS_AI_PROVIDER=lfm3-local`; provider failures do not silently fall back to a cloud provider.
- The model cannot execute tools, shell commands, mining actions, wallet actions, or network changes.
- Model output is advisory. NEXUS policies, deterministic checks, and explicit owner approvals remain authoritative.
- Model weights and third-party security services are not vendored into this repository.

## 2. LFM3: what is being integrated

LFM3 is an **open-weight model family**, not a source-code repository. The initial text model, `LiquidAI/LFM3-1.7B`, has 1.73B parameters and a 256K context window. Liquid AI documents 4-bit deployment at approximately 1 GB of model memory and native support through llama.cpp, among other runtimes.

The integration boundary is a separately managed llama.cpp-compatible OpenAI-style HTTP endpoint. NEXUS sends bounded `/v1/chat/completions` requests to that endpoint. The NEXUS repository contains only the adapter and tests, not model weights or the inference runtime.

Official sources:
- Model card: https://huggingface.co/LiquidAI/LFM3-1.7B
- Model family announcement and supported runtimes: https://www.liquid.ai/blog/lfm3
- Runtime source: https://github.com/ggml-org/llama.cpp
- License: LFM Open License v1.0, linked from the official model card. This is not the same as assuming Apache-2.0 or MIT rights; review the license conditions before commercial distribution.

### Initial NEXUS use cases

- local chat and request triage;
- summarizing EDGE telemetry after deterministic filtering;
- classifying and routing research tasks;
- drafting structured task proposals for owner review.

Do not use this small model as the only source of truth for security enforcement, complex code review, wallet operations, or multi-step infrastructure changes. Model outputs are untrusted input.

### Configuration

Set these values in the local service environment; never commit secrets:

```text
NEXUS_AI_PROVIDER=lfm3-local
NEXUS_LFM3_BASE_URL=http://127.0.0.1:8080
NEXUS_LFM3_MODEL=LiquidAI/LFM3-1.7B
NEXUS_LFM3_TIMEOUT_S=60
NEXUS_LFM3_MAX_TOKENS=512
```

An optional `NEXUS_LFM3_API_KEY` is sent as a bearer token when the local inference server requires it. The default endpoint is loopback-only. A remote endpoint is rejected unless `NEXUS_LFM3_ALLOW_REMOTE=true` is explicitly set, and remote mode requires HTTPS. For remote use, route it only through the private VPN and firewall allowlists; HTTPS alone is not authorization.

## 3. NEXUS EDGE baseline: verified source-level capabilities

The audited branch already contains these implementation elements:

- HMAC-SHA256 signed node requests and signed task results;
- monotonic sequence numbers and persistent SQLite anti-replay protection;
- SQLite persistence for nodes, tasks, leases, and telemetry;
- Fernet encryption of stored node credentials, with the encryption key supplied out-of-band;
- operator bearer-token authentication for provisioning and management endpoints;
- node provisioning, credential rotation, revocation, capability checks, and task leases;
- opt-in HTTPS gateway and MQTTS adapter;
- opt-in HTTPS gateway rate limiting (enabled by default): 120 requests per 60 seconds per source-IP and authenticated identity bucket, with bounded in-memory state;
- gateway documentation requiring a TLS terminator and loopback binding for the local pilot.

These are source-level capabilities, not proof of a hardened internet deployment. The documented scheduler is single-process; standalone and MASTER-mounted gateway modes must not run simultaneously against the same database.

### Remaining gaps in the reviewed gateway surface

- no WAF is active in the NEXUS runtime; a separate loopback-only Coraza/Caddy pilot scaffold has been added under `deployment/security/coraza/`; its Caddyfile and custom binary build have passed CI validation, but the proxy has not been installed or started on the user's machine;
- no CrowdSec engine or remediation bouncer is installed or active; a Windows acquisition template for Caddy JSON logs is prepared under `deployment/security/crowdsec/`;
- no VPN/control-plane is deployed or connected; a deny-all Headscale policy scaffold has been added under `deployment/security/headscale/`, but no Headscale service, client, peer keys, routes, or ACL allow rules are provisioned;
- no endpoint detection/response agent was found;
- the operator bearer token is a static configured secret; production use needs secret rotation, least-privilege handling, and protected delivery;
- reverse proxy, TLS, firewall, and public exposure controls are deployment responsibilities and are not automatically provisioned by the current gateway.

## 4. Candidate open-source security components

The components below should remain separate services or adapters. Do not copy a whole WAF, VPN, or endpoint security product into the Python core.

| Layer | Candidate source | License / role | NEXUS fit and constraints |
|---|---|---|---|
| WAF | https://github.com/corazawaf/coraza | Apache-2.0; Go WAF engine | Run in front of FastAPI through a supported proxy integration. Coraza documents OWASP CRS v4 compatibility. Prefer an external proxy/WAF deployment over embedding Go in the Python process. Validate rules in detection-only mode first. |
| Web rules | https://github.com/coreruleset/coreruleset | Apache-2.0; OWASP Core Rule Set | Pair with Coraza for common web attack patterns. Tune false positives against NEXUS API payloads before blocking. |
| Behavioral bot / IP reputation | https://github.com/crowdsecurity/crowdsec | MIT; log and HTTP behavior detection plus decisions API | Feed proxy and gateway logs to the engine; enforce decisions through a suitable firewall or reverse-proxy bouncer. It detects observable behavior and rule matches, not the identity or intent of every arbitrary AI agent. Windows event-log acquisition exists; do not assume full feature parity with Linux. |
| Private mesh VPN | https://github.com/juanfont/headscale | BSD-3-Clause; self-hosted Tailscale control server | Use with supported Tailscale clients on Windows/Linux. Headscale coordinates the mesh; clients provide the device-side networking. It is not itself a generic WireGuard client for ESP32. ESP32-C5 compatibility remains unverified. |
| VPN data plane | https://github.com/WireGuard/wireguard-tools | GPL-2.0; WireGuard configuration tools | Native WireGuard is an alternative for a manually managed site-to-site or hub-and-spoke VPN. Keep private keys outside NEXUS source and use OS/network tooling for lifecycle. |

### EDGE gateway rate-limit configuration

The experimental gateway now applies an in-process fixed-window limiter by default. Defaults are 120 requests per 60 seconds, with a bounded 10,000-key cache. It counts both the source IP and an additional identity bucket when the request contains a node ID path or bearer token. Bearer tokens are hashed before being used as bucket keys; raw token values are not retained by the limiter.

Optional environment settings:

```text
NEXUS_EDGE_RATE_LIMIT_ENABLED=true
NEXUS_EDGE_RATE_LIMIT_REQUESTS=120
NEXUS_EDGE_RATE_LIMIT_WINDOW_S=60
NEXUS_EDGE_RATE_LIMIT_MAX_KEYS=10000
NEXUS_EDGE_TRUSTED_PROXY_CIDRS=
```

Forwarded client addresses are ignored unless the immediate TCP peer belongs to an explicitly configured trusted proxy CIDR. When trusted, the limiter walks the forwarded chain from right to left, skips trusted proxy addresses, and selects the first untrusted address; it does not blindly trust the left-most header value. Configure only the exact proxy ranges you control. The limiter is process-local and fixed-window; it does not coordinate counters across multiple workers or hosts. Its key cache is bounded and fails closed for new identities when full instead of evicting active buckets, preventing identity churn from resetting another client's live limit. A multi-worker or distributed deployment must also enforce shared limits at the reverse-proxy/WAF layer (or use a shared backend). This feature is not proof of protection against every automated client.

### NEXUS CORE loopback request guard

The local CORE FastAPI application now installs
`LoopbackOnlyMiddleware`. It checks the actual ASGI socket peer and requires
the Host authority to be `localhost` or a loopback IP address. It ignores
`X-Forwarded-For` for identity and fails closed for missing, duplicate or
malformed Host values. Remote HTTP requests receive 403; remote WebSocket
requests are closed with policy code 1008.

The normal launch remains `127.0.0.1:8765`. The Caddy pilot explicitly rewrites
the upstream Host authority to `127.0.0.1:8765`, so future access through a
private proxy interface can remain possible without exposing CORE directly.
The standard Starlette TestClient scope pair is permitted only for tests.

This is an exposure guard, not user authentication and not a defence against
malicious software already running on the same host. Keep CORE loopback-bound;
any LAN/WAN or VPN exposure must go through a tested reverse proxy and separate
authentication/authorization controls.

### Coraza WAF pilot scaffold

The experimental branch now contains `deployment/security/coraza/`:

- `Caddyfile`: Coraza WAF + embedded OWASP CRS in front of the documented local CORE endpoint `127.0.0.1:8765`; listener is restricted to `127.0.0.1:8780`;
- `build.ps1` and `build.sh`: reproducible custom Caddy build with pinned Caddy `v2.11.9`, Coraza Caddy module `v2.6.2`, and xcaddy `v0.4.7`;
- `README.md`: local pilot steps and promotion gates.

The Caddy configuration uses `SecRuleEngine DetectionOnly`; this inspects traffic without blocking on CRS matches during initial validation. The scripts validate the custom binary's WAF module and Caddyfile but do not start the proxy. No WAF binary has been built or installed on the user's machine in this work. Requests made directly to CORE's port 8765 bypass the proxy; the current loopback pilot is not remote protection. For any future VPN exposure, the proxy must bind only to the private interface and firewall the backend port against direct remote access.

Caddy access logs are JSON at `logs/access.log`, rotated at 50 MiB with up to 10 rolled files and a 30-day age limit. Rolled files are deliberately uncompressed for the CrowdSec file acquisition. The Caddy log encoder redacts standard sensitive headers by default and replaces values for a documented list of credential-like query keys. This is a finite list, not generic secret detection; credentials must not be placed in URL paths or unlisted query parameters.

The Coraza audit configuration uses `SecAuditLogParts AHZ`: A (transaction header), H (audit trailer) and Z (final boundary). It deliberately omits B/C request headers and bodies and K (the full matched-rules list), so the current audit log does not contain complete rule IDs/messages for rule-by-rule triage. For synthetic-only diagnostics, K can be enabled temporarily in an isolated test config; treat those logs as sensitive. The serial Coraza audit log is separate from Caddy's access log and has no rotation procedure in this scaffold. External rotation/retention and restrictive file permissions must be tested before sustained use.

### CrowdSec Windows detection scaffold

`deployment/security/crowdsec/acquis-windows.yaml.example` provides a file-acquisition template for Caddy JSON logs. The official `crowdsecurity/caddy` collection supplies a Caddy parser and generic HTTP scenarios. The CrowdSec Security Engine detects suspicious request patterns; a remediation component is required to block them.

The Windows Firewall remediation component requires .NET 10 according to current CrowdSec documentation and modifies host firewall rules. It is **not installed or activated** in this experiment. Do not activate it while Caddy is loopback-only: a false positive could block local access. Before enforcement, move the proxy to a tested private VPN interface, explicitly allowlist host/management addresses, review detections, and obtain operator approval for firewall changes. Review CrowdSec Central API enrollment/data-sharing settings during Windows engine installation.

The upstream Coraza Caddy module embeds CRS when `load_owasp_crs` is enabled. Its release metadata at the selected version identifies Coraza `3.8.1` and CRS `4.30.0`. Version pins must be reviewed against upstream advisories before updates.

### Headscale policy scaffold

The experimental branch includes:
- `deployment/security/headscale/policy.example.hujson`: valid JSON/huJSON with an explicit empty `grants` array (deny all);
- `deployment/security/headscale/README.md`: Windows/Linux mesh boundary, ESP32 transport assumptions, and rollout gates;
- `application/tests/test_headscale_security_policy.py`: verifies the policy parses and remains deny-all.

This is a configuration guardrail, not an active VPN. It intentionally allows no peer traffic until reviewed least-privilege rules are added. No Headscale daemon, Tailscale client, WireGuard interface, peer key, DNS record, firewall route, or tunnel has been provisioned.

### Headscale deployment warning

Headscale documentation states that when no policy is loaded, node-to-node traffic is allowed. An explicit least-privilege ACL/Grants policy is therefore a prerequisite. The project also warns that reverse-proxy deployment is not supported or encouraged; if used, its WebSocket, TLS, and trusted-proxy requirements must be followed. Do not expose the control plane before policy and proxy validation.

## 5. Proposed NEXUS CORE SECURITY architecture

1. **Application identity:** per-node credentials, signed requests, replay protection, capability scopes, credential revocation.
2. **Agent firewall:** allowlisted agent identities; per-agent and per-route request budgets; maximum payloads; concurrency caps; expiry; audit trail; explicit tool permissions.
3. **Ingress protection:** reverse proxy with TLS, request-size limits, IP reputation, rate limits, and Coraza + OWASP CRS.
4. **Behavioral defense:** CrowdSec consumes reverse-proxy and NEXUS gateway logs; a bouncer applies bans at the proxy/firewall boundary.
5. **Private network:** WireGuard or Headscale mesh for administration and private node traffic; do not expose management APIs directly to the public internet.
6. **Host security:** Windows Firewall/Defender and Linux firewall/host monitoring remain the endpoint baseline. Wazuh can be evaluated later if centralized endpoint detection and file-integrity monitoring are needed.
7. **Secrets and updates:** OS-protected secret storage, key rotation, signed releases, dependency pinning, SBOM and vulnerability scanning.
8. **Recovery:** backup and restore tests for the EDGE database, Fernet key custody, operator credentials, and VPN identity material.

### Bot classes and controls

- **Anonymous internet scanners:** WAF rules, rate limits, reputation feeds, and request budgets.
- **Credential-stuffing/brute-force traffic:** authentication throttling, CrowdSec decisions, token rotation, and alerting.
- **Legitimate NEXUS nodes:** cryptographic identity, sequence protection, capability scopes, leases, and quotas.
- **AI agents with valid credentials:** least-privilege tools, bounded context and output, egress allowlists, per-agent quotas, and human approval for privileged actions.
- **Compromised nodes:** immediate revocation, task lease recovery, VPN ACL removal, and credential rotation.

No single CAPTCHA, WAF, VPN, or model can reliably identify every automated client. Defense must be layered and based on identity, observable behavior, and permissions.

## 6. Validation gates

- Unit tests for local-only endpoint validation, explicit remote HTTPS opt-in, payload bounds, response parsing, and no implicit tool execution.
- Core API test confirming local LFM3 selection without an OpenAI key.
- CI on Linux and Windows; investigate any existing platform-specific CI failures rather than suppressing them.
- Runtime smoke test against an actual llama.cpp server and a pinned LFM3 GGUF model.
- Benchmark first-token latency, tokens/second, RAM/VRAM use, and stability at 4K/8K context before choosing defaults.
- Security pilot in WAF detection-only mode; review false positives before enabling blocking.
- VPN pilot with explicit deny-by-default ACLs, then test Windows/Linux reachability and node revocation.
- No production activation until operator authentication, rate limits, WAF, firewall, backup/restore, and VPN policy are validated.

## 7. Source references

- LFM3 official announcement: https://www.liquid.ai/blog/lfm3
- LFM3 official model card: https://huggingface.co/LiquidAI/LFM3-1.7B
- llama.cpp: https://github.com/ggml-org/llama.cpp
- Coraza: https://github.com/corazawaf/coraza
- Coraza Caddy connector: https://github.com/corazawaf/coraza-caddy
- CrowdSec Caddy collection: https://app.crowdsec.net/hub/author/crowdsecurity/collections/caddy
- CrowdSec Windows installation and firewall bouncer: https://docs.crowdsec.net/docs/getting_started/install_windows/
- xcaddy builder: https://github.com/caddyserver/xcaddy
- Caddy: https://github.com/caddyserver/caddy
- OWASP CRS: https://github.com/coreruleset/coreruleset
- CrowdSec: https://github.com/crowdsecurity/crowdsec
- Headscale: https://github.com/juanfont/headscale
- Headscale ACL/Grants policy behavior: https://headscale.net/stable/ref/acls/
- WireGuard tools: https://github.com/WireGuard/wireguard-tools


## 8. Latest verification and scan triage

See [SECURITY_TRIAGE_2026-11-25.md](SECURITY_TRIAGE_2026-11-25.md) for the latest AIScan counts, manual triage of returned findings, and the current CI evidence. The scan's unreturned findings remain open for review.
