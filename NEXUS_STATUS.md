# NEXUS MASTER — verified integration and functional status

**Status date:** 2026-11-25  
**Canonical repository:** `dcnsd00/project-nexus`  
**Canonical branch:** `main`  
**Current main HEAD:** `4dcde89374e48e9079a43dde19c4f70c2052a409`  
**Application version:** `0.10.26` from `application/VERSION.json`  
**Version source:** `application/nexus_master.py::_package_version()` reads the manifest; do not duplicate the version in another runtime constant.

## 1. Integration position

The cumulative NEXUS MASTER 0.10.26 baseline and the focused follow-up integrations are now on `main`.

| PR | Scope | Result | Exact-head CI evidence |
|---|---|---|---|
| #9 | Cumulative 0.10.26 baseline | Merged | Run #771 — 14/14 jobs passed |
| #15 | Fieldstation import boundary and optional dependency tests | Merged | Run #779 — success |
| #16 | Provider registry contract tests | Merged | Run #788 — success |
| #17 | Math Intelligence evidence validation | Merged | Run #802 — 14/14 jobs passed |
| #18 | Gate public market research and 100 RON paper trading | Merged | Run #797 — success; focused Gate workflow #51 — success |
| #19 | Fail-closed Windows process liveness and managed TestClient lifecycle | Merged | Run #804 — 14/14 jobs passed |
| #20 | Residual Windows/runtime regression tests | Merged | Run #813 — 14/14 jobs passed |

The latest full CI run, **#813**, passed on PR #20's exact pre-merge HEAD `fcad96e87ab0a0e488bd16375e7cda41ae1a403a`. It covered source detection, Python tests, Windows dependencies/runtime, MSVC native build, Windows compatibility, all eight Windows application shards, and Coraza/Caddy configuration validation. The merge commit now at `main` is `4dcde89374e48e9079a43dde19c4f70c2052a409`; the CI evidence above is for the exact PR head, not a separate push-triggered run on the merge commit.

Old PRs #4–#8 were closed after selective reconciliation. They were not merged wholesale:
- #4 Windows TestClient/process lifecycle → #19 and residual tests in #20.
- #5 Gate/paper trading → #18; remaining useful regression tests → #20.
- #6 provider contracts → #16.
- #7 Math Intelligence evidence validation → #17.
- #8 Fieldstation import boundary → #15.

Dependabot PRs #10 (`actions/upload-artifact`) and #11 (`actions/setup-python`) remain open and currently report non-mergeable. They are maintenance work, not blockers to the feature integrations above; rebase and validate them separately.

## 2. Architecture and evidence rules

NEXUS remains one **modular monolith**. Preserve current package ownership and paths; do not create parallel CORE, EDGE, mining, wallet, or provider implementations.

The module registry distinguishes source presence, route registration, and runtime-service registration. It explicitly leaves `operational_verified` and `system_operational_verified` false. A source file or registered route is not proof of operational behavior.

Use these terms precisely:
- **PRESENT** — source or configuration exists.
- **IMPLEMENTED** — behavior exists in code.
- **TESTED** — named tests passed on a stated commit/CI run.
- **INTEGRATED** — integration tests prove components connect at the software boundary.
- **VALIDATED** — verified on the target Windows installation, physical hardware, or live external service.

## 3. Functional status and remaining boundaries

| Area | Current evidence on main | Remaining validation boundary |
|---|---|---|
| NEXUS MASTER / CORE | FastAPI application, lifecycle composition, service registry, local API loopback guard and safe error handling are present; full CI passed on the latest pre-merge PR head. | Loopback binding is not user authentication. Verify actual start/stop and install on the owner's Windows laptop. |
| EDGE host runtime | Node/task/lease manager, HMAC-authenticated messages, SQLite persistence, monotonic sequence/replay protection, credential encryption hooks, rate limits and opt-in HTTPS/MQTTS paths are present with tests. | No physical ESP32/ESP32-C5, hardware-in-the-loop, multi-site field test, or production broker validation is claimed. |
| Mining / Stratum | Native SHA-256d scanner and exact Python fallback; Stratum V1 job/header/coinbase/Merkle/nonce/submit paths; hybrid worker and process arbitration. Loopback mock-pool and Windows tests are included. | No public-pool payout, BTC reward, sustained real pool session, or profitability claim. CI does not validate the owner's GPU/CPU hardware. |
| Wallet / recovery | Local wallet/recovery and vault modules with read-only boundaries and tests. | No private-key export, live signing, public-chain broadcast, real transaction, or payout validation. |
| Gate research / paper trading | Public-only Gate spot client for BTC, ETH, SOL, BNB, XRP, AIOZ, GRASS, TAO, NEAR and FIL. Descriptive indicators and local SQLite paper ledger seeded with 100 RON. | Paper BUY/SELL only. No account credentials, real orders, transfers, wallet signing, or financial outcome is claimed. Market availability/liquidity must be rechecked when used. |
| Provider integrations | Registry contains 12 provider definitions. Contract tests enforce readiness semantics, secret non-disclosure, `live_connection_verified=false`, and `writes_enabled=false`. | No provider is live-connected or credential-validated. A configured endpoint alone is not a validated adapter. |
| Math Intelligence | Candidate evidence rejects booleans/non-finite/overflowing hashrates, invalid counters and non-boolean equivalence claims. Tests preserve `auto_apply=false`. | Findings remain research/manual-review evidence; no automatic mining optimization is activated. |
| Earnings Intelligence | Local opportunity/device/telemetry/reward ledger; SQL parameterization regression test is included. | Reward estimates are not verified payouts. No wallet signing, claims, or automatic mining start. |
| Fieldstation | Import-time optional miner-directory side effect removed; import/runtime boundary tests and loopback default are present. | Local-only research tool; no wallet signing, seed/private-key storage, or transaction broadcast. No live hardware/chain workflow is claimed. |
| Desktop / Windows | Installer/launcher and MSVC native build path are present. Latest full CI passed Windows dependency preparation, native build, compatibility, and eight test shards. | Not installed or acceptance-tested on the owner's actual Windows laptop. WebView2, driver, antivirus, local device and hardware checks remain separate. |
| LFM3 | Optional adapter and tests are present. | Model weights and inference server are external and have not been installed or benchmarked. No live local inference is claimed. |
| RCSC / SHA-2 research | Research engines and read-only collection boundaries are present with unit/API tests. | No independent external replication of public-data results is claimed. |
| Security deployment | Coraza-enabled Caddy build/config validation passes in CI; CrowdSec acquisition example and Headscale deny-all policy are present. | WAF is not deployed/enforcing on the user's host; CrowdSec engine/bouncer and Headscale/VPN are not installed or active. No firewall remediation is claimed. |

## 4. Security scan history

`docs/SECURITY_TRIAGE_2026-11-25.md` records a historical VisionEdge AIScan result from an earlier experiment-branch snapshot, not the current `main` HEAD:
- Grade C (73/100), verdict `GO_WITH_CONDITIONS`.
- 0 critical, 0 high, 11 medium, 24 low, 8 informational findings.
- Twelve returned findings received detailed triage; 31 additional findings were reported without individual details and remain untriaged.
- Static analysis is not proof of runtime security. The report's branch/commit and CI references are historical and must not be presented as a current-main scan.

## 5. Next acceptance work

1. Install the cumulative Windows package on the actual target laptop and record version, startup, shutdown, logs and rollback evidence.
2. Verify the local dashboard against the live local API; distinguish simulated/demo values from hardware telemetry and provider data.
3. Perform hardware-in-the-loop EDGE checks with the actual ESP32/ESP32-C5 devices before claiming node operation.
4. Validate any provider adapter individually with documented authentication, freshness, response schema and read-only behavior before marking it live.
5. Keep public pool, wallet signing/broadcast, WAF enforcement, VPN and CrowdSec disabled until their separate security and operational acceptance checks pass.

GitHub branches, commits, PRs and CI are the source of truth for implementation status. This document is a snapshot and must be refreshed after material integration changes.
