# NEXUS MASTER — verified integration and functional status

**Status date:** 2026-11-26  
**Canonical repository:** `dcnsd00/project-nexus`  
**Canonical branch:** `main`  
**Current main HEAD:** `74eae1d5950f4b532b45eb68e67446760effdaaf`  
**Application version:** `0.10.27` from `application/VERSION.json`  
**Version source:** `application/nexus_master.py::_package_version()` reads the manifest; do not duplicate the version in another runtime constant.  
**Latest audit:** [docs/REPOSITORY_AUDIT_2026-11-26.md](docs/REPOSITORY_AUDIT_2026-11-26.md)

## 1. Current repository and CI position

The current main commit is `74eae1d5950f4b532b45eb68e67446760effdaaf`, signed/verified by GitHub. Its subject is `NEXUS 0.10.27: AI worker routing and mining safety`.

GitHub returned 30 check-run records for this exact HEAD:
- 21 completed successfully.
- 9 completed as cancelled in a later duplicate/restarted run.
- No failed conclusion appeared in the returned set.

Successful checks include Python tests, Windows dependencies/runtime, Windows compatibility, Windows application shards, source detection, Coraza WAF build validation, Dependabot and frozen desktop packaging. The accurate aggregate is **21 success / 9 cancelled**, not 30/30 green.

Relevant GitHub Actions evidence:
- Main CI successful run: https://github.com/dcnsd00/project-nexus/actions/runs/45792231445
- Frozen desktop workflow: https://github.com/dcnsd00/project-nexus/actions/runs/45792231327
- Duplicate/restarted run with cancelled checks: https://github.com/dcnsd00/project-nexus/actions/runs/45792818282

CI success is evidence for the checked-in commit and GitHub-hosted runners. It is not proof of installation or hardware operation on the owner's laptop.

## 2. Integrated changes through 0.10.27

The current main tree includes the cumulative NEXUS application, lifecycle/runtime composition, module registry, wallet/recovery boundaries, mining and Stratum code, EDGE host runtime, provider registry, Gate paper trading, RCSC/SHA-2 research, desktop packaging and Windows CI.

The 0.10.27 increment adds:
- 11 specialist AI-worker slots and deterministic route-preview logic;
- shared mining supervisor integration;
- fail-closed CPU/GPU thermal preflight and telemetry-driven safety monitor;
- benchmark provenance and Windows 0.10.27 package validation.

The AI-worker coordinator remains **preview-only**: zero model providers configured, zero active AI agents, model invocation disabled, and no autonomous repository/tool execution. Mutating task types require human review; write, shell, miner-start, wallet-signing and provider-write permissions remain disabled.

## 3. Architecture and evidence rules

NEXUS remains one **modular monolith**. Preserve package ownership and current paths; do not create parallel CORE, EDGE, mining, wallet or provider implementations.

The module registry distinguishes source presence, route registration and runtime-service registration. It leaves operational verification false until separate evidence exists.

Use these terms precisely:
- **PRESENT** — source or configuration exists.
- **IMPLEMENTED** — behavior exists in code.
- **TESTED** — named tests passed on a stated commit/CI run.
- **INTEGRATED** — integration tests prove components connect at the software boundary.
- **VALIDATED** — verified on the target Windows installation, physical hardware or live external service.

The historical Step 02 lifecycle finding has been addressed: optional service failures are recorded without stopping independent services; dependent services are blocked; critical service failures still roll back startup. Current lifecycle tests cover these cases. The historical duplicate `earnings_intelligence` registry ID is also resolved; the current registry rejects duplicate IDs.

## 4. Functional status and remaining boundaries

| Area | Current evidence on main | Remaining validation boundary |
|---|---|---|
| NEXUS CORE / lifecycle | FastAPI application, lifecycle composition, service registry and loopback-oriented runtime are present. Optional-service failure isolation is implemented and tested. | Actual target-laptop installation, interactive start/stop and local authentication/authorization acceptance remain separate. |
| EDGE host runtime | Node/task/lease manager, HMAC protocol, protocol versioning, monotonic sequence/replay protection, SQLite persistence, encrypted node auth secrets, rate limits, runtime lock and opt-in HTTPS/MQTTS paths are present with software integration tests. | No ESP32/ESP32-C5 firmware, physical pairing, hardware-in-the-loop, production broker or multi-site failover validation. Stable storage-key provisioning is operator-managed; task/result/telemetry payloads are not encrypted by the current SQLite store. |
| Mining / Stratum | Native SHA-256d scanner and exact Python fallback; Stratum V1 assembly/submit paths; hybrid supervisor and CPU/GPU thermal monitor. Local mock-pool and simulated telemetry tests exist. | No public-pool session, accepted public share, BTC block/payout or profitability evidence. The user's actual GPU/CPU temperatures and sustained hashrate are not validated. |
| Wallet / recovery | Local wallet/recovery and vault modules with read-only boundaries and tests. | No private-key export, live signing, public-chain broadcast, real transaction or payout validation. |
| Gate paper trading | Public-only Gate market research and local SQLite paper ledger seeded with 100 RON. | Simulated BUY/SELL only; no real orders, transfers, wallet signing or financial outcome. |
| Public market data | Existing Gate public market research is present. PR #23 proposes shared read-only Binance/Gate ticker, 24h, kline, order-book and trade adapters. | PR #23 is open and dirty/non-mergeable; its opt-in live smoke test has not been evidenced as run. |
| Provider integrations | Registry contains 12 provider definitions with contract/readiness semantics. | No provider is currently established as live-connected or credential-validated. |
| Math Intelligence | Evidence validation and manual-review research paths are present; `auto_apply=false`. | No automatic mining optimization is activated. |
| Earnings Intelligence | Local opportunity/device/telemetry/reward ledger and SQL regression coverage are present. | Reward estimates are not verified payouts; no claims or automatic mining start. |
| Fieldstation | Import/runtime boundary and local-only research paths are present with tests. | No live hardware/chain workflow, wallet signing or transaction broadcast. |
| Desktop / Windows | Installer/launcher, MSVC native build and GitHub-hosted Windows package/test workflows are present. | Not installed or acceptance-tested on the owner's actual Windows laptop; WebView2, driver, antivirus and local hardware checks remain pending. |
| LFM3 | Optional adapter and tests are present. | Model weights/inference server are external and not installed or benchmarked; no live local inference is claimed. |
| RCSC / SHA-2 / RandomX | Research engines and read-only boundaries have tests. PR #24 adds NIST SHA-256 known-answer tests and upstream RandomX reference tests. | RCSC results are not independently replicated. Vendored RandomX exact upstream commit/tag and file-hash provenance remain to be recorded. |
| Security deployment | Coraza/Caddy build/config validation exists in CI; historical security triage is documented. | WAF is not deployed/enforcing on the user's host; CrowdSec and Headscale are not installed/active. Historical AIScan is not a current-main scan. |

## 5. Open pull requests

All four feature/security/documentation PRs below were created against an earlier main SHA (`516bb3ca7859159c962b455e55cded01e51d9224`) and compare as one commit behind current main. Reconcile against the current HEAD and rerun validation before integration.

| PR | Scope | Current state |
|---|---|---|
| #23 | Shared read-only Binance/Gate market data | 16 ahead / 1 behind; `mergeable=false`, `dirty`. Resolve conflicts and rerun contract tests before reconsideration. |
| #24 | SHA-256 and RandomX reference validation | 3 ahead / 1 behind; GitHub reports clean/mergeable. Record RandomX upstream provenance separately. |
| #25 | Continuity, security and integration docs | 8 ahead / 1 behind; GitHub reports clean/mergeable, but its status document is itself based on the 0.10.26 snapshot. Refresh against current main. |
| #26 | Gitleaks, Trivy, CodeQL and Python Dependabot | 2 ahead / 1 behind; GitHub reports clean/mergeable. Gitleaks and Trivy are report-only baseline scans; CodeQL is Python-only. Not yet blocking security gates. |

Dependabot PRs #10–#14 remain open and require individual current-base and compatibility review. Do not batch-merge them.

Older EDGE persistence/replay, AI-worker/mining-safety, fieldstation, math, integration and desktop branches are historical work streams, not automatically authoritative over current main. Do not merge older implementations wholesale where main already contains the capability.

## 6. Security and governance

- Historical VisionEdge AIScan in `docs/SECURITY_TRIAGE_2026-11-25.md` scanned `experiment/lfm3-core-security-lab-v1` at `7400d02c3f8a414db7feba1ce9283c300f22ae5b`, not current main. It reported 0 critical, 0 high, 11 medium, 24 low and 8 informational findings; 31 additional findings were not individually disclosed/triaged.
- PR #26 adds a useful scan baseline, but Gitleaks/Trivy remain report-only and CodeQL covers Python only. C/C++ analysis is deferred.
- The current branch listing reports `main.protected=false`. The branch-protection endpoint returned HTTP 403 (`Resource not accessible by integration`), so required protection rules could not be independently inspected through this connection. Verify in GitHub repository settings before claiming branch protection.
- Existing CI workflows still include version-tag action references such as `actions/checkout@v4`, `actions/setup-python@v5` and `actions/upload-artifact@v4`. PR #26 pins actions in its own security workflow, but a workflow-wide immutable-SHA review remains open.
- This status is a snapshot; use GitHub branches, commits, PRs and CI as the source of truth.

## 7. Next acceptance work

1. Reconcile PR #26 and #24 against current main and validate exact-head CI/provenance.
2. Resolve PR #23 conflicts; rerun market-data contract tests and only then run its opt-in public GET smoke test in a controlled environment.
3. Audit and pin remaining mutable GitHub Actions references after verifying upstream immutable SHAs and compatibility.
4. Record exact RandomX upstream revision and vendor file hashes.
5. Define an operator-controlled EDGE storage-key provisioning and backup/rotation acceptance procedure.
6. Perform target Windows laptop acceptance and physical EDGE hardware tests only with actual devices and explicit authorization.
7. Keep public-pool mining, wallet signing/broadcast, exchange writes, WAF enforcement, VPN and CrowdSec disabled until their separate acceptance gates pass.

The full evidence and audit findings are recorded in [docs/REPOSITORY_AUDIT_2026-11-26.md](docs/REPOSITORY_AUDIT_2026-11-26.md). This document does not claim that the complete NEXUS system is operational or production-ready.
