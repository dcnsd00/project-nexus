# NEXUS MASTER — full repository audit

**Audit date:** 2026-11-26  
**Repository:** `dcnsd00/project-nexus`  
**Audited ref:** `main`  
**Exact HEAD:** `74eae1d5950f4b532b45eb68e67446760effdaaf`  
**Application version:** `0.10.27` (`application/VERSION.json`)  
**Audit branch:** `audit/full-repository-2026-11-26`  
**Method:** GitHub read-only inspection of repository metadata, refs, commit/check runs, open PRs, source files, tests and project documentation. No local execution or hardware test was performed.

## 1. Executive result

The repository has advanced materially from the 2026-11-17 recovery audits. The canonical source is now on `main`, the package manifest reports 0.10.27, and the codebase is a modular monolith with distinct module and runtime-service boundaries.

This audit does **not** certify the complete product as operational. The repository and tests establish source-level behavior and software-boundary integration. They do not establish the owner's Windows laptop acceptance, physical EDGE device operation, live model-provider invocation, public-pool mining/payout, live wallet signing, or production deployment.

No merge, destructive action, branch deletion, force-push, or change to `main` was performed.

## 2. Repository and commit evidence

- Default branch: `main`.
- Audited HEAD: `74eae1d5950f4b532b45eb68e67446760effdaaf`.
- Commit message: `NEXUS 0.10.27: AI worker routing and mining safety`.
- Commit timestamp: `2026-11-26T09:28:01Z`.
- GitHub commit verification: `verified=true`.
- Repository tree returned 656 tracked blob entries at audit time.
- `application/VERSION.json` reports `0.10.27`; the version remains sourced through `application/nexus_master.py::_package_version()`.

The commit adds specialist-worker route preview, shared mining supervisor integration, fail-closed CPU/GPU thermal checks, a telemetry-driven safety monitor, benchmark provenance, and Windows package validation changes.

## 3. CI evidence

GitHub's check-runs endpoint for the exact `main` HEAD returned 30 check-run records:
- 21 completed successfully.
- 9 completed as cancelled.
- No failed conclusion appeared in the returned set.

The successful checks include Python tests, Windows dependencies/runtime, Windows compatibility, Windows application shards, source detection, Coraza WAF build validation, Dependabot and frozen desktop packaging. The cancelled checks belong to a later duplicate/restarted run and include Windows application shards and Windows compatibility. Therefore the accurate status is **successful checks exist, but the aggregate listing is not 30/30 green**.

Relevant successful run links:
- Main CI run: https://github.com/dcnsd00/project-nexus/actions/runs/45792231445
- Frozen desktop workflow: https://github.com/dcnsd00/project-nexus/actions/runs/45792231327
- Duplicate/restarted run with cancelled jobs: https://github.com/dcnsd00/project-nexus/actions/runs/45792818282

These are GitHub-hosted runner results. No test command was executed locally during this audit.

## 4. Architecture and domain review

NEXUS remains a single modular monolith. The current layout keeps the application entry point, modules, mining package, EDGE package, tests, docs and deployment/workflow definitions in one repository. The unified architecture document explicitly warns against moving or duplicating packages merely to match a target diagram.

### CORE, lifecycle and module registry

**Evidence inspected**
- `application/modules/lifecycle_manager.py`
- `application/modules/nexus_runtime.py`
- `application/modules/module_registry.py`
- `application/tests/test_lifecycle_manager.py`
- `application/tests/test_module_registry.py`

The historical Step 02 finding that an optional-service failure could abort the whole runtime has been addressed in current source. `LifecycleManager.start_all()` records failed optional services, continues independent services, blocks dependents, and still aborts/rolls back if a critical service fails or a critical dependent is blocked. Tests cover optional service failure, optional factory failure, dependency blocking and rollback.

The historical duplicate `earnings_intelligence` module ID is not present in the current `MODULES` tuple. The registry now rejects duplicate IDs and has uniqueness tests.

The module registry correctly distinguishes source presence, route registration and runtime-service registration. It does not treat those facts as proof of operational health.

### AI worker coordinator

**Evidence inspected**
- `application/modules/ai_worker_coordinator.py`
- `application/tests/test_ai_worker_coordinator.py`
- `application/docs/NEXUS_AI_WORKER_MINING_SAFETY_V1.md`

There are 11 specialist slots including the central coordinator. Routing is deterministic and based on explicit domain, repository path or branch pattern. Mutating task types request human review and a QA/security reviewer. Permissions remain read-only; repository writes, shell execution, miner start, wallet unlock, signing, broadcast and provider writes are disabled.

**Important boundary:** this is a routing-preview registry, not a running multi-agent system. The 0.10.27 manifest reports zero configured model providers, zero active agents and model invocation disabled. No agent has autonomously modified the repository or dispatched tools.

### Mining and safety

**Evidence inspected**
- `application/mining/hybrid_safety.py`
- `application/mining/safety_monitor.py`
- `application/mining/hybrid_supervisor.py`
- `application/tests/test_hybrid_safety.py`
- `application/tests/test_mining_safety_monitor.py`

CPU/GPU preflight uses measured telemetry and rejects missing or malformed readings. The monitor samples only while NEXUS-managed workers are active and stops the affected lane on a thermal-limit breach or loss of required telemetry. Default ceiling is 85°C; automatic overclock, undervolt and fan-curve changes are not enabled.

**Boundary:** tests use simulated telemetry and fake workers. The owner's laptop sensors, GTX 1650, sustained mining load, actual miner processes and real power/temperature behavior have not been validated here. Stratum V1 and SHA-256d remain tested against local/mock paths; no public-pool session, accepted public share, BTC block or payout is established by this audit.

### EDGE and DePIN

**Evidence inspected**
- `application/nexus_edge/` source tree
- EDGE persistence, replay-guard, runtime and master-integration tests
- `docs/NEXUS_EDGE_FOUNDATION.md`

Current host-side source includes node/task/lease lifecycle, HMAC-authenticated protocol messages, protocol versioning, monotonic per-node sequence/replay protection, SQLite persistence, encrypted node authentication secrets, rate limits, optional HTTPS/MQTTS transports and shared-manager lifecycle integration. Runtime locking and a single-host SQLite topology constraint are explicit.

**Boundaries:** no ESP32/ESP32-C5 firmware, physical node pairing, hardware-in-the-loop test, multi-site deployment, production broker acceptance or operational failover is evidenced. The EDGE key is operator-provisioned; stable key provisioning through an OS keyring is not yet integrated. Task/result/telemetry payloads are not encrypted by the current SQLite store; filesystem ACLs, disk encryption and controlled backups remain important.

### Crypto, research and RCSC

The crypto engine delegates SHA-256 to `hashlib`; PR #24 adds NIST known-answer tests and upstream RandomX reference test execution. The crypto PR's documentation explicitly notes a provenance gap: the vendored RandomX source directory does not record an exact upstream commit/tag hash and file-hash manifest. RCSC remains experimental, read-only research with `auto_apply=false`; independent replication is not established.

### Market data and integrations

PR #23 proposes shared public read-only Binance/Gate adapters for tickers, 24h statistics, klines, order book and recent trades. The branch includes mock contract tests and an opt-in live smoke test that is skipped unless `NEXUS_RUN_LIVE_MARKET_SMOKE=1`. The PR is currently dirty/non-mergeable and must not be merged as-is. The live smoke test has not been shown as executed.

The existing integration registry has 12 provider definitions; current status evidence does not establish any provider as live-connected or credential-validated. No write-capable exchange integration is approved by this audit.

### Wallet and financial boundaries

The manifest and status documentation keep wallet recovery local and read-only. Private-key export, live signing, public-chain broadcast, real orders, transfers and verified payouts are not enabled or proven. Gate paper trading is a local simulation and must not be described as real trading.

### Desktop, packaging and Windows

GitHub Actions has built and validated Windows artifacts and test environments. This is not equivalent to installing the package on the owner's laptop, launching WebView2 interactively, validating antivirus/driver behavior or testing the physical GPU.

## 5. Historical recovery findings — disposition

The uploaded recovery audits dated 2026-11-17 described:
1. EDGE as in-memory only with no network transport or persistence.
2. Missing monotonic anti-replay and key rotation.
3. Optional-service startup failures potentially taking down the whole runtime.
4. A duplicate module-registry ID.

Current source has addressed the host-side persistence, anti-replay, key rotation hooks, opt-in transports, optional-service isolation and registry uniqueness findings. The original reports remain valid historical snapshots, not current status descriptions. Physical firmware/device validation and production deployment remain open.

## 6. Open pull requests and integration posture

The four feature/security/documentation PRs are all based on an earlier `main` SHA (`516bb3ca7859159c962b455e55cded01e51d9224`) and compare as one commit behind current `main`. Reconciliation against the audited HEAD is required before integration.

| PR | Scope | Current audit result |
|---|---|---|
| #23 | Shared read-only Binance/Gate market data | 16 commits ahead, 1 behind; GitHub reports `mergeable=false`, `dirty`. Do not merge; inspect/reconcile conflicts and rerun checks. |
| #24 | SHA-256 and RandomX reference validation | 3 commits ahead, 1 behind; GitHub reports clean/mergeable. Reconcile base and close RandomX provenance gap before treating provenance as complete. |
| #25 | Continuity/security/integration documentation | 8 commits ahead, 1 behind; GitHub reports clean/mergeable, but its `NEXUS_STATUS.md` still reports 0.10.26 and the old base SHA. Refresh documentation against current HEAD before integration. |
| #26 | Gitleaks, Trivy, CodeQL and Python Dependabot | 2 commits ahead, 1 behind; GitHub reports clean/mergeable. Gitleaks and Trivy are report-only baseline scans (`exit-code: 0`); CodeQL analyzes Python only. These are not yet blocking security gates. |

Dependabot PRs #10–#14 also remain open. Their update branches require individual current-base and compatibility review; do not batch-merge them.

Other historical feature branches include older EDGE persistence/replay, AI worker/mining safety, fieldstation, math, integration and desktop branches. They are not automatically authoritative over current `main`. In particular, do not merge older EDGE persistence implementations wholesale where current main already contains the capability.

## 7. Security and governance findings

1. The historical VisionEdge AIScan report in `docs/SECURITY_TRIAGE_2026-11-25.md` scanned `experiment/lfm3-core-security-lab-v1` at `7400d02c3f8a414db7feba1ce9283c300f22ae5b`, not current main. It reported 0 critical, 0 high, 11 medium, 24 low and 8 informational findings; 31 findings were not individually disclosed/triaged. Do not present it as a current-main scan.
2. PR #26 introduces a useful scan baseline, but Gitleaks/Trivy are report-only and CodeQL is Python-only. C/C++ analysis remains deferred pending a validated build mode.
3. The current `main` branch listing reports `protected=false`. The separate branch-protection endpoint returned HTTP 403 `Resource not accessible by integration`, so this connector could not independently inspect protection rules. Verify branch protection in GitHub's repository settings before claiming required checks or review enforcement.
4. Existing CI workflow files still contain version-tag action references (for example `actions/checkout@v4`, `actions/setup-python@v5`, `actions/upload-artifact@v4`). PR #26 pins actions in its own security workflow, but a complete workflow-wide immutable-SHA audit is still required.
5. `NEXUS_STATUS.md` on main is stale: it reports date 2026-11-25, HEAD `4dcde893...` and version 0.10.26. This audit branch refreshes that status separately.

## 8. Recommended implementation order

1. Keep `main` unchanged and refresh the canonical status/audit documents on a dedicated branch.
2. Reconcile PR #26 security workflow and PR #24 crypto reference validation against current main; preserve report-only/validation caveats.
3. Resolve PR #23 conflicts and run its contract tests; execute its opt-in live public GET smoke test only in a controlled network environment.
4. Review and pin remaining mutable GitHub Actions references after verifying upstream immutable SHAs and compatibility.
5. Add exact RandomX upstream revision and vendor-file hash provenance.
6. Plan an operator-controlled EDGE storage-key provisioning workflow and verify recovery/rotation procedure with backups.
7. Complete Windows laptop acceptance and physical EDGE hardware tests only with the actual target hardware available and explicit authorization.

## 9. Evidence classification

- **PRESENT / IMPLEMENTED:** source is present and behavior is implemented in the inspected revision.
- **TESTED:** a named test or GitHub Actions check passed for a specific commit/run.
- **INTEGRATED:** software components are connected by integration tests.
- **VALIDATED:** target hardware, actual Windows installation or live external service has been checked.

This audit establishes repository/source and GitHub CI evidence only. It does not claim that the full NEXUS system is operational or production-ready.
