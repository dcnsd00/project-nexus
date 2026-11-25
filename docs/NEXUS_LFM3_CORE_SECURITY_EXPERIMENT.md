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

### Gaps found in the reviewed gateway surface

- a native in-process EDGE gateway rate limiter has now been added on this experimental branch; it applies bounded fixed-window limits by source IP and, when present, node ID or hashed operator bearer identity. It is defense in depth, not a distributed limiter;
- no integrated WAF or bot-behavior detection service was found;
- no VPN/control-plane integration was found;
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

Forwarded client addresses are ignored unless the immediate TCP peer belongs to an explicitly configured trusted proxy CIDR. When trusted, the limiter walks the forwarded chain from right to left, skips trusted proxy addresses, and selects the first untrusted address; it does not blindly trust the left-most header value. Configure only the exact proxy ranges you control. The limiter is process-local and fixed-window; it does not coordinate counters across multiple workers or hosts. A multi-worker or distributed deployment must also enforce shared limits at the reverse-proxy/WAF layer (or use a shared backend). This feature is not proof of protection against every automated client.

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
- OWASP CRS: https://github.com/coreruleset/coreruleset
- CrowdSec: https://github.com/crowdsecurity/crowdsec
- Headscale: https://github.com/juanfont/headscale
- WireGuard tools: https://github.com/WireGuard/wireguard-tools
