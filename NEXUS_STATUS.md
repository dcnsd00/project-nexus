# NEXUS MASTER — verified integration and functional status

**Status date:** 2026-11-25  
**Canonical repository:** `dcnsd00/project-nexus`  
**Canonical branch:** `main`  
**Current main HEAD:** `516bb3ca7859159c962b455e55cded01e51d9224`  
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
| #21 | Enable Windows desktop package builds on main | Merged | PR-head run #822 — 14/14; post-merge main CI #84495 — 14/14; desktop package run #75 — success |

PR #21 is merged at main HEAD `516bb3ca7859159c962b455e55cded01e51d9224`. Its PR-head CI run #822 passed 14/14 jobs. The merge triggered a separate main push CI run #84495, also 14/14, and Windows desktop packaging run #75 completed successfully. The package was assembled and uploaded as `NEXUS_MASTER_0.10.26_WINDOWS_INSTALLER`; the extracted inner installer ZIP contains 635 manifest-listed files, with zero missing files and zero SHA-256 mismatches. The inner package SHA-256 is `de57c91925a99759e72e65dca80df09f3a452bc07ffbba0e01098a77301a2459`. This proves CI packaging and runner-side installation validation, not installation on the owner's laptop.

Old PRs #4–#8 were closed after selective reconciliation. They were not merged wholesale:
- #4 Windows TestClient/process lifecycle → #19 and residual tests in #20.
- #5 Gate/paper trading → #18; remaining useful regression tests → #20.
- #6 provider contracts → #16.
- #7 Math Intelligence evidence validation → #17.
- #8 Fieldstation import boundary → #15.

Dependabot PRs #10–#14 (upload-artifact, setup-python, download-artifact, checkout, setup-node) remain open. Their recorded CI runs passed; some were tested against an older base SHA. Review and rebase them separately. Current Dependabot configuration covers GitHub Actions only, not pip dependencies.

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
| EDGE host runtime | Node/task/lease manager, HMAC-authenticated messages, SQLite schema-v4 persistence, monotonic sequence/replay protection, Fernet-encrypted node secrets, rate limits and opt-in HTTPS/MQTTS paths are present with tests. Runtime composition is already in `modules/nexus_runtime.py`. | The runtime requires a stable `NEXUS_EDGE_STORAGE_KEY`; OS-keyring provisioning is not yet integrated. No physical ESP32/ESP32-C5, hardware-in-the-loop, multi-site field test, or production broker validation is claimed. Preserve `feature/edge-persistence-protocol-v1` (7 ahead / 482 behind) for its older keyring abstraction; do not merge its duplicate SQLite store wholesale. |
| Mining / Stratum | Native SHA-256d scanner and exact Python fallback; Stratum V1 job/header/coinbase/Merkle/nonce/submit paths; hybrid worker and process arbitration. Loopback mock-pool and Windows tests are included. | No public-pool payout, BTC reward, sustained real pool session, or profitability claim. CI does not validate the owner's GPU/CPU hardware. |
| Wallet / recovery | Local wallet/recovery and vault modules with read-only boundaries and tests. | No private-key export, live signing, public-chain broadcast, real transaction, or payout validation. |
| Gate research / paper trading | Public-only Gate spot client for BTC, ETH, SOL, BNB, XRP, AIOZ, GRASS, TAO, NEAR and FIL. Descriptive indicators and local SQLite paper ledger seeded with 100 RON. | Paper BUY/SELL only. No account credentials, real orders, transfers, wallet signing, or financial outcome is claimed. Market availability/liquidity must be rechecked when used. |
| Public market data adapters | PR #23 adds a shared read-only Binance/Gate adapter for ticker, 24h stats, klines, order book and trades, with source attribution, freshness, retry and rate-limit handling; targeted AIScan A/100; NEXUS CI 14/14 and Gate workflow success. | PR #23 is open and unmerged; manual live app-side smoke test has not run. Existing Binance/Gate connectors provide public read-only data; no API credentials or trading actions. |
| Provider integrations | Registry contains 12 provider definitions. Contract tests enforce readiness semantics, secret non-disclosure, `live_connection_verified=false`, and `writes_enabled=false`. | No provider is live-connected or credential-validated. A configured endpoint alone is not a validated adapter. |
| Math Intelligence | Candidate evidence rejects booleans/non-finite/overflowing hashrates, invalid counters and non-boolean equivalence claims. Tests preserve `auto_apply=false`. | Findings remain research/manual-review evidence; no automatic mining optimization is activated. |
| Earnings Intelligence | Local opportunity/device/telemetry/reward ledger; SQL parameterization regression test is included. | Reward estimates are not verified payouts. No wallet signing, claims, or automatic mining start. |
| Fieldstation | Import-time optional miner-directory side effect removed; import/runtime boundary tests and loopback default are present. | Local-only research tool; no wallet signing, seed/private-key storage, or transaction broadcast. No live hardware/chain workflow is claimed. |
| Desktop / Windows | Installer/launcher and MSVC native build path are present. Main CI #84495 passed 14/14; desktop package workflow #75 succeeded; the 0.10.26 installer ZIP and SHA-256 manifest were verified (635/635 files). | Not installed or acceptance-tested on the owner's actual Windows laptop. WebView2, driver, antivirus, local device and hardware checks remain separate. |
| LFM3 | Optional local OpenAI-compatible adapter and tests are present; OpenAI Responses API remains the default. | Model weights and inference server are external and have not been installed or benchmarked. No live local inference is claimed. The LFM3 security experiment's VPN pilot and Windows/Linux reachability/revocation gate remain unvalidated. |
| RCSC / SHA-2 research | Research engines and read-only collection boundaries are present with unit/API tests. PR #24 adds NIST SHA-256 known-answer vectors and upstream RandomX reference CI; on its branch, RandomX reference tests passed 95/95 and full CI passed 14/14. | PR #24 remains open and unmerged. No independent external replication of RCSC results is claimed; keep `auto_apply=false`. Vendored RandomX upstream commit provenance still needs recording. |
| Security deployment | Coraza-enabled Caddy build/config validation passes in CI; CrowdSec acquisition example and Headscale deny-all policy are present. Current-main AIScan is B/78 (0 critical, 0 high, 11 medium, 17 low, 9 info). | Gitleaks, Trivy and CodeQL jobs are not yet present. The WAF is not deployed/enforcing on the user's host; CrowdSec engine/bouncer and Headscale/VPN are not installed or active. No firewall remediation is claimed. |

## 4. Security scan history

`docs/SECURITY_TRIAGE_2026-11-25.md` retains the historical feature-branch scan (grade C/73, 11 medium, 24 low, 8 info). A separate full scan was run against current main HEAD `516bb3ca7859159c962b455e55cded01e51d9224`:
- Grade B/78; 0 critical, 0 high, 11 medium, 17 low, 9 informational findings.
- The 9 medium randomness alerts point to fixed-seed deterministic research/benchmark sampling, not authentication or cryptographic secrets.
- Two medium SQL alerts were manually reviewed as provisional false positives: a table identifier drawn from a fixed internal tuple, and SQLite `busy_timeout` interpolation of an integer derived from local configuration. No SQL injection was confirmed.
- One low finding concerns open version ranges in local CORE requirements. Other low/informational findings still need item-level triage.
- A 24 Nov Notion snapshot used a different branch/commit and scanner target; its counts are not directly comparable.
- Static analysis is not proof of runtime security. See the security triage doc for evidence and limits.

## 5. Next acceptance work

1. Install the cumulative Windows package on the actual target laptop and record version, startup, shutdown, logs and rollback evidence.
2. Review PR #23 (read-only Binance/Gate adapters) and PR #24 (SHA-256/RandomX reference validation); do not merge without review. Run the manual public GET-only market smoke workflow after its workflow file is on main.
3. Reconcile EDGE key provisioning: current main uses Fernet with `NEXUS_EDGE_STORAGE_KEY`; review the preserved keyring branch without replacing the current SQLite schema. Then run hardware-in-the-loop checks with actual ESP32/ESP32-C5 devices.
4. Complete the LFM3 VPN pilot with deny-by-default ACLs, Windows/Linux reachability and node-revocation tests before calling the security lab validated.
5. Add Gitleaks, Trivy, CodeQL where repository permissions/plan allow, and pip dependency updates/lockfiles; manually triage remaining AIScan low/info findings.
6. Verify the local dashboard against the live local API; distinguish simulated/demo values from hardware telemetry and provider data.
7. Keep public pool, wallet signing/broadcast, WAF enforcement, VPN and CrowdSec disabled until their separate security and operational acceptance checks pass.

GitHub branches, commits, PRs and CI are the source of truth for implementation status. This document is a snapshot and must be refreshed after material integration changes.


## 6. Current open issues and review branches

- Issue #1 remains open for source-import provenance. Three artifact hashes are recorded: issue-body hash `17702ce64497599d04c65c3893ddf6c7b54ac5d41e84032a203799a6d9db90bc`; original bundle audit hash `642c882557993a86db21583e8efaef359dd01f8f9b28440462ba8a723c924d50`; sanitized import hash `9c7b70c2b292a987029071d022c24950bc0a2b9e05af2597e5392b1361f6a469`. The preserved 0.10.25 importer/audit branch is historical; do not run it against current 0.10.26 application source.
- Issue #2 is closed: runtime version metadata reads the authoritative VERSION.json manifest and current main CI/package checks pass.
- PR #23 (`feature/read-only-market-data-adapters-v1`) and PR #24 (`feature/crypto-reference-validation-v1`) are open, CI-green, and unmerged pending review.
- PRs #5/#6 were selectively superseded by PRs #18/#16; the Gate and provider-contract file blobs match main. PR #7 is superseded by PR #17. No wholesale merge of old branches is authorized.
- `feature/nexus-math-intelligence-hardening-v1` and `feature/nexus-fieldstation-runtime-validation-v1` have the same relevant file blobs as main; their useful changes are already present through PRs #17 and #15.
- The old Windows TestClient branch contains older versions of files now superseded by PRs #19/#20; current main already has Windows process-handle liveness and dedicated tests. Preserve old branch refs; do not merge the stale workflow/test snapshots.
- `feature/nexus-edge-foundation` and `integration/nexus-master-0.10.25` retain historical root-level package/import work. Preserve for provenance; do not merge duplicate package paths into the modular monolith.

NEXUS remains local-first. AppDeploy currently hosts Crypto Agent only; NEXUS Control Center is not declared deployed. No secrets, wallets or mining processes are moved to AppDeploy. InVideo, YouTube and Unseen Frontier remain on HOLD.
