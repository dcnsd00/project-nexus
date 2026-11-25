# Current continuation checkpoint — 2026-11-23 (native SHA-256d block-candidate correctness)

This checkpoint supersedes the 2026-11-23 MASTER API audit checkpoint below for current source state. Earlier audit entries remain historical evidence.

## Verified repository state before this documentation update

- Repository: `dcnsd00/project-nexus`
- Active branch: `feature/edge-replay-protection-sqlite-v1`
- Source HEAD: `7a46d836c36a37b6210c3af120ac88eba18cf415`.
- Integration target: `integration/source-import-safe-0.10.25`, exact base `30210464088ff51c32cabda90ae56b6a9ce20bc8`.
- Exact GitHub comparison at source HEAD: 319 commits ahead, 0 behind, 80 changed files.
- Latest source CI run for this source HEAD: NEXUS CI run `45121800039`, queued at checkpoint time.
- Latest Windows package workflow run: `45121800031`, queued at checkpoint time.
- No application test result is claimed yet for this patch. `main` remains untouched; no PR or merge was created.

## Native SHA-256d scanner correctness fix

Files changed:
- `application/mining/native/miner.c`
- `application/mining/native_sha256d.py`
- `application/mining/bitcoin_pow_engine.py`
- `application/tests/test_native_sha256d_021.py`

Verified issue in prior implementation:
- Native C scanner accepted the pool share target only, not the independent block target.
- Scanner loops overwrote the previously found nonce when later share candidates appeared.
- Python wrapper evaluated the block target only against the single nonce returned by C.
- The Python fallback returned immediately on the first pool share, so it could also stop before a later block candidate.
- Result: a block-valid nonce could be present in a scanned interval but be lost from the reported result if a later non-block share candidate replaced it.

Patch now committed on the feature branch:
- C ABI accepts an optional block target separately.
- C scanner records the first share candidate and separately records the first block candidate; after joining worker threads, a block candidate is preferred.
- Block target ordering is validated as `block_target <= share_target`, which is the expected Bitcoin mining relation.
- Python wrapper passes the optional target buffer through ctypes.
- Python fallback continues through the interval when a block target is supplied, returns immediately if a block candidate is found, and otherwise returns the first share candidate after the interval.
- Regression tests cover native variant paths and Python fallback using a deterministic range where the first nonce meets block target and the final nonce meets only the easier share target; another test rejects invalid target ordering.

Important validation boundary:
- These are source changes, not yet validated by a completed CI run at checkpoint time.
- CI must prove the C shared-library ABI, GCC/Clang SIMD paths, MSVC scalar path, Python fallback and test suite.
- The full CPU benchmark and Windows desktop package workflows were also queued due feature-branch push triggers. They are not substitutes for the native correctness tests.
- No local compiler/test execution was performed in this environment.

## Other audit findings from this stage

- `nexus_cli.py` uses GET-only requests and is read-only by design.
- `tools/nexus_hardware_benchmark.py` is an explicit offline benchmark; it blocks when known miner processes are detected unless `--allow-active-miners` is passed. It does not connect to pools or wallets.
- `RuntimeTelemetry` uses local psutil/WMI/nvidia-smi observations and labels unavailable values rather than estimating them. Mining-process detection is process-name based and is not proof of complete process discovery.
- Desktop launcher remains loopback-only but identifies an existing instance using an unauthenticated `/api/nexus/master` product field. Harden with a verifiable local-instance handshake before treating port reuse as trusted.
- Global MASTER API authentication remains absent in the reviewed entry-point files. Do not expose beyond loopback until global authentication/authorization and Origin/CSRF boundaries are designed and tested.

## Next exact actions

1. Check CI run `45121800039` and Windows package run `45121800031`; inspect job logs if either fails. Do not mark this fix tested until both native-specific tests and full application CI complete.
2. If tests fail, isolate whether failure is ABI mismatch, compiler-specific code, target ordering, or a regression. Do not weaken tests.
3. Review the remaining changed source files and tests, then implement the launcher instance handshake and mining process arbiter as separate changes.
4. Correct the Windows version/installer metadata and stale CI provenance only after a successful run on a precisely identified source commit.
5. Recheck exact integration base, branch head, PR list and CI before any PR. Do not target or merge into `main` without explicit approval.

---

# Current continuation checkpoint — 2026-11-23 (MASTER API surface and release metadata audit)

This checkpoint supersedes the 2026-11-22 checkpoint above for current state. Older entries remain historical evidence.

## Verified repository state

- Repository: `dcnsd00/project-nexus`
- Active branch: `feature/edge-replay-protection-sqlite-v1`
- Source HEAD before this documentation checkpoint: `036908adca62f303d83e5f3670fe83224d3f61c8`.
- Integration target: `integration/source-import-safe-0.10.25`, exact base `30210464088ff51c32cabda90ae56b6a9ce20bc8`.
- Exact GitHub comparison: 311 commits ahead, 0 behind, 78 changed files.
- No open pull requests were returned at this check.
- `main` was not modified. No application source code or tests were changed/run in this stage.
- Existing CI evidence remains tied to the earlier source HEAD `d5d84ef6ad1d934ccfb9467f811fe3e640f0cf2b`; this stage did not produce new application CI.

## MASTER API surface and local security boundary

Files reviewed: `application/nexus_master.py` (1,944 lines), `application/core/PROJECT-NEXUS-LOCAL/app/main.py` (198 lines), and `application/START_NEXUS_DESKTOP.pyw`.

- MASTER extends the existing FastAPI application and adds the wallet, wallet-recovery, earnings-intelligence, integration-registry and pool-failover routers.
- The reviewed `app.main` and `nexus_master.py` contain no global authentication middleware, authenticated operator dependency, CSRF/origin validation or request-token gate. This statement is limited to those two files; individual included routers may implement their own controls.
- The desktop launcher binds Uvicorn to `127.0.0.1` only, which materially limits network exposure. This is a deployment boundary, not API authentication.
- Sensitive local POST operations include direct miner start/stop, HybridSupervisor start/stop/switch, miner installation, local Bitcoin regtest mining, wallet recovery operations through an included router, and research jobs that persist results. In the reviewed MASTER routes, these operations are not protected by a common operator-authentication layer.
- Risk classification: local-process trust-boundary gap; not evidence of an internet-reachable exploit while the supported desktop launcher remains loopback-only. Any LAN/public binding or reverse-proxy exposure is blocked pending an authentication, origin/CSRF and authorization design.
- The launcher treats a service on port 8765 as an existing NEXUS instance when `GET /api/nexus/master` returns only `{"product":"NEXUS"}`. There is no cryptographic instance identity in that handshake. A local process able to occupy the port and spoof that response could cause the desktop shell to attach to the wrong local service. This is a local port-squatting/spoofing hardening item, not a demonstrated remote attack.
- Positive boundaries remain: the dashboard/operator snapshot is explicitly read-only; wallet/research/EDGE surfaces carry separate safeguards described in earlier checkpoints; EDGE gateway operator endpoints use their own Bearer authentication. These do not create global MASTER API authentication.

## Included-router follow-up (same audit stage)

Additional files reviewed: `modules/earnings_intelligence.py`, `modules/integration_registry.py`, `modules/pool_failover_api.py`, `modules/wallet_benchmark/nexus_wallet_manager.py` and `modules/wallet_benchmark/nexus_wallet_recovery_api.py`.

- Earnings Intelligence exposes local CRUD-style POST routes for opportunities, devices, jobs, telemetry, rewards, costs, payouts, wallet-watch and sources. No router-level authentication dependency was found in the inspected module.
- Integration Registry exposes catalog/status reads; its own policy says providers are not marked live until dedicated adapter contract, auth, freshness and response validation pass. No router-level auth dependency was found; these are configuration/status surfaces.
- Pool failover API exposes scenario and simulation routes; no router-level auth dependency was found in the inspected file.
- Wallet manager has password-gated vault unlock/decryption paths and encrypts keys at rest. Its routes do not establish a common authenticated operator identity; several metadata/watch routes are not password-gated.
- Wallet recovery checks the request peer against loopback in `_local_only()`. Its `_authorized(value: bool)` check accepts a client-supplied boolean `owner_authorized=true`; this is an explicit owner-attestation flag, not identity authentication or proof of ownership. Keep it as a user-consent safeguard, not an access-control boundary.
- The loopback check relies on `request.client.host`; behind a same-host reverse proxy, the API may see the proxy's loopback address rather than the original remote client unless the deployment is designed to preserve and validate client identity. This reinforces the no-proxy/no-LAN deployment guard until a trusted proxy/auth model is implemented.
- No secrets or credentials were read from the user's environment; this was a source-only review. No tests were run.

## Package, version and CI provenance findings

Files reviewed: `application/VERSION.json`, `application/README_RO.md`, `application/INSTALL_NEXUS.bat`, `application/INSTALL_NEXUS_ONECLICK.ps1`, `application/INSTALL_NEXUS_WINDOWS.ps1`, `application/START_NEXUS_DESKTOP.pyw`, `application/packaging/NEXUS_DESKTOP.spec`, `.github/workflows/nexus-ci.yml` and `.github/workflows/nexus-desktop-package.yml`.

- Supported package entry point is `application/INSTALL_NEXUS.bat` → `INSTALL_NEXUS_ONECLICK.ps1`; the current PyInstaller spec is `application/packaging/NEXUS_DESKTOP.spec`.
- `VERSION.json` identifies version `0.10.26`, but `desktop_shell.installer` still names legacy `INSTALL_NEXUS_WINDOWS.ps1`, which hardcodes `0.10.25`. This metadata is inconsistent with the supported package route.
- `VERSION.json` and `README_RO.md` still show Linux 636 / Windows 635 test counts and CI provenance for commit `3f9d9c3...`. Those counts are historical, not current evidence for HEAD `036908ad...`.
- The metadata's `desktop_shell.validation` text still says Windows installation/WebView2 were not executed in the build environment, while the separate `desktop_validation` section records a GitHub Actions Windows package/self-test. The distinction between hosted-runner validation and the user's laptop validation needs to be stated consistently.
- The package workflow is configured for the feature branch and workflow dispatch; it builds the frozen onedir package, runs the packaged API/dashboard self-test, runs the installer with `-NoLaunch`, and uploads the ZIP. A no-launch success does not prove interactive WebView2 behavior on the user's laptop.
- The one-click manifest verifies SHA-256 file integrity but is not a publisher signature for the NEXUS package.
- No local Windows build or interactive launch was performed in this stage.

## Findings to carry into implementation

1. **P1 deployment guard:** keep the MASTER API loopback-only. Do not expose it on LAN/public interfaces until a global operator-authentication and authorization model, Origin/CSRF protections, and tests exist. Review included routers for their own auth boundaries.
2. **P2 launcher hardening:** replace the unauthenticated port-8765 product-string check with a verifiable local-instance handshake or remove automatic attachment to an unverified process.
3. **P2 release metadata:** align `VERSION.json` installer metadata with `INSTALL_NEXUS.bat` / `INSTALL_NEXUS_ONECLICK.ps1`; refresh README and CI provenance only from a named completed run on the exact source commit; clarify hosted Windows versus user's laptop validation.
4. Preserve the separate mining process-arbitration finding between `mining.controller` and `HybridSupervisor`; add cross-path exclusion tests before automatic switching.
5. Preserve the EVM DNS-resolution/address-validation hardening item before less-trusted endpoint use.

## Exact next actions

1. Review the remaining changed files and included routers for authentication, authorization, file/path handling and startup side effects.
2. Implement only the narrow metadata/provenance correction after checking the exact current CI run IDs and commit SHA; run the affected tests and workflows.
3. Design and test a shared mining process arbiter; do not enable automatic switching.
4. Add launcher instance verification and tests before changing port reuse behavior.
5. Recheck branch head, exact integration base, open PRs and CI before PR preparation. Target `integration/source-import-safe-0.10.25` only; no `main` PR/merge without explicit approval.
6. External validation still required: interactive Windows 11/WebView2 launch, physical ESP32-C5/HIL, live MQTT/TLS/provider adapters, and backup/restore.

---

# Current continuation checkpoint — 2026-11-22 (EDGE transport and Windows package audit)

This section supersedes prior 2026-11-22 checkpoints and the 2026-11-19 historical checkpoint below. Preserve older entries as historical evidence.

## Verified repository state

- Repository: `dcnsd00/project-nexus`
- Active branch: `feature/edge-replay-protection-sqlite-v1`
- Verified pre-checkpoint HEAD: `f251d5d7d99ee89a8f7107f0e53bbcfa26371fd2`.
- Integration target: `integration/source-import-safe-0.10.25`, exact base `30210464088ff51c32cabda90ae56b6a9ce20bc8`.
- Latest comparison before this documentation commit: 310 commits ahead, 0 behind, 78 changed files.
- No application source-code modifications were made during this stage. Only continuity documentation is updated.
- CI evidence for application source HEAD `d5d84ef...`: NEXUS CI run `44607394324` and Windows package run `44607394143` succeeded. Later commits in this branch are documentation-only; no new CI run was returned for the documentation commits.

## EDGE transport/gateway review

Files reviewed: `application/nexus_edge/transports.py`, `gateway.py`, `gateway_runtime.py`, `config.py`, `NEXUS_EDGE_HTTPS_GATEWAY.md`, `NEXUS_EDGE_MULTI_NETWORK.md`, and gateway/transport test suites.

- HTTPS gateway is opt-in, requires a provisioning token of at least 32 characters and encrypted persistent SQLite state. Production guidance requires a TLS terminator.
- Operator endpoints use Bearer token authentication with constant-time comparison. Node requests use HMAC authentication and monotonic sequence/replay protection.
- MQTTS requires broker authentication, TLS certificate verification (`tls_insecure_set(False)`), bounded message sizes, and manual QoS acknowledgements. Retryable persistence errors are left unacknowledged for broker redelivery; duplicate telemetry is idempotent.
- Public health and transport endpoints expose aggregate status only; inspected `EdgeManager.snapshot()` does not expose node secrets or telemetry payloads.
- LoRaWAN is correctly described as a network-server/webhook bridge, not a transparent IP socket. Provider-specific LoRaWAN/IOT adapters and physical-node validation remain unimplemented.
- No evidence-backed transport defect was identified in this static review. No live broker, TLS terminator, webhook provider or physical ESP32 was exercised.

## Windows package/release audit

Files reviewed: `VERSION.json`, `START_NEXUS_DESKTOP.pyw`, `INSTALL_NEXUS_ONECLICK.ps1`, `INSTALL_NEXUS.bat`, legacy `INSTALL_NEXUS_WINDOWS.ps1`, PyInstaller spec, Windows package workflow, packaging tests and Romanian README.

- Supported path is `INSTALL_NEXUS.bat` → `INSTALL_NEXUS_ONECLICK.ps1`; package is PyInstaller onedir with bundled Python and WebView2, desktop server bound to `127.0.0.1`.
- One-click installer verifies package file SHA-256 values against the included manifest, checks the Microsoft WebView2 bootstrapper's Authenticode signature, runs the frozen executable self-test, and preserves the user's existing data directory.
- SHA-256 manifest is an integrity check against accidental corruption; it is not a publisher signature over the NEXUS package itself.
- The legacy `INSTALL_NEXUS_WINDOWS.ps1` still exists and hardcodes version `0.10.25`; it is not the supported route documented in `README_RO.md` and `packaging/README_WINDOWS_BUILD_RO.md`.
- `VERSION.json` still points its `desktop_shell.installer` field at that legacy script, while the supported package uses `INSTALL_NEXUS.bat` / `INSTALL_NEXUS_ONECLICK.ps1`. This is a verified metadata inconsistency to correct.
- `VERSION.json` and `README_RO.md` report Linux 636 / Windows 635 test counts tied to older CI commit `3f9d9c3...`; the later verified source-head CI `44607394324` reports Linux 624 / Windows 623. Treat the old counts as historical provenance, not current branch CI totals. Update release metadata/README with exact commit and run IDs after the next source CI.
- Package CI used `-NoLaunch`: install and frozen API/dashboard self-test passed on a GitHub Windows runner, but the interactive WebView2 desktop was not launched on the user's Windows 11 laptop.
- No source code was changed and no local Windows build was run in this stage.

## Existing audit conclusions carried forward

- CORE adapters are intentionally local/read-only; presence and runtime registration do not prove operational validation.
- Wallet keys remain encrypted locally; wallet manager does not return private keys/WIF and is not approved for material funds without independent audit.
- Mining has two separate process managers: direct `mining.controller` and `HybridSupervisor`. No shared arbitration check was found. Add a regression test and common arbiter before automatic switching.
- EVM telemetry does not resolve DNS names to reject private/link-local/reserved destinations; add this hardening before non-local deployment.
- QuantumOrb/QuantOrb is all-rights-reserved and must not be copied/merged into NEXUS without written permission. MIT candidate references and a read-only Solana intelligence integration plan are recorded in the preceding checkpoint.

## Exact next actions

1. Finish review of the 78-file delta, focusing on remaining package/version/workflow changes and the complete `nexus_master.py` API surface.
2. Correct the stale legacy installer/version metadata and stale CI provenance in a separate, narrowly scoped change; rerun CI and package workflow afterward.
3. Add a focused test and shared arbitration design for the direct mining controller versus HybridSupervisor; do not enable unattended switching before it passes.
4. Add EVM DNS/address validation before enabling EVM telemetry in less-trusted deployments.
5. Recheck branch tip, integration base, PR list and CI immediately before PR preparation. Target `integration/source-import-safe-0.10.25` only; do not target or merge into `main` without explicit approval.
6. External validation remains required: Windows 11 interactive launch, ESP32-C5 firmware/board/HIL, live MQTT/TLS and provider adapters, backup/restore.
7. The shared conversation added to the NEXUS folder still was not identifiable by Library listing or searches for the share ID / “QuantumOrb”. Ask for the exact filename if it remains unavailable; do not infer its contents.

---

---

---

---

# NEXUS project continuity ledger

Last refreshed: 2026-11-15
Canonical repository: https://github.com/dcnsd00/project-nexus
Canonical application version: NEXUS MASTER 0.10.25

## Continuity rule

Do not recreate NEXUS modules, rewrite existing integrations, or start a parallel implementation. Before every code change, inspect the current branch, source, tests, commit history and CI. Preserve existing interfaces and passing behavior. Implement incremental patches only, keep changes on integration/feature branches, and record exact tests and outcomes.

## Verified GitHub state

Repository access confirmed: admin, maintain, push, pull.
Default branch main HEAD at refresh: 529072b777d010ac47711dd6c821b30fef7ecdf9.
Relevant branches:
- integration/nexus-master-0.10.25: ccc8b6bf4292b17b957357ee12c7314eabfe7aa9 (continuity ledger commit added separately)
- integration/source-import-safe-0.10.25: 40a4ebccc4eb8bbbecc384a95bfa17fb04ee801d (latest source-import workflow setup)
- integration/import-0.10.25: 2c1ec087c8f766ef44072d47a69608b6ef18599b
- feature/nexus-edge-foundation: 4c40d98598c220c35233679f0e540e8cf7766138
No pull requests existed at refresh.

## Source archive

Already committed on integration/source-import-safe-0.10.25:
- NEXUS_MASTER_0.10.25_SOURCE_IMPORT_BUNDLE_WALLET_MINING.zip
- SHA-256: 642c882557993a86db21583e8efaef359dd01f8f9b28440462ba8a723c924d50
- 520 ZIP entries: 519 manifest-listed files plus manifest
- VERSION.json confirms 0.10.25
- Local integrity check: no forbidden cache, bytecode, runtime database/log or native build artefacts found.
Do not ask the user to upload this same archive again.

## Existing implementation facts from VERSION.json and source

- Bitcoin Stratum V1 CPU worker; optional native C SHA-256d nonce scanner with runtime CPU dispatch and exact Python fallback.
- Loopback mock pool validates handshake, header construction, submit accept/reject and controller lifecycle. No public pool payout test.
- Miner adapters include some fake-process-only tests; no assumption of live binaries.
- Wallet recovery interfaces exist, with no private-key export or public-chain broadcast. Wallet adapter in shared runtime is read-only.
- RCSC service and SHA-2 research package exist. No live Mempool collection or independent provider replication verified.
- Provider catalog is read-only; VERSION.json reports zero live-verified providers.
- Runtime composition, Lifecycle Manager, Module Registry, wallet read-only adapter and mining status adapter exist locally; this is not complete end-to-end application integration.
- EDGE is an in-memory prototype: HMAC-authenticated node registration/heartbeats, capability task assignment, leases, signed results. No network transport, durable storage, firmware, wallet access or miner control.

## Test and defect evidence refreshed 2026-11-15

Against the local extraction of the exact archive:
- compileall: PASS.
- Focused CORE/RCSC/runtime/lifecycle/registry/solo mining suites: 49 passed in 0.99s before the new regression correction.
- Full pytest before correction: 306 passed, 1 failed at 82%. Failure: test_independent_stored_result_verification_passes because sanitized archive intentionally excludes generated sat_scaling.json and differential.json.
- Root cause: modules/sha2_research_service.py hard-coded PACKAGE_ROOT/results instead of an injectable verification-results directory; test expected isolated temporary result storage but did not seed required result fixtures.
- Local fix staged as a patch: add VERIFICATION_RESULTS_ROOT (NEXUS_SHA2_VERIFICATION_RESULTS_DIR override), route run_verification through it, and seed empty schema-valid SAT/differential fixtures in test fixture.
- After patch: test_sha2_research_service_020.py: 10 passed in 7.45s.
- After patch: combined focused suites including SHA2: 59 passed in 7.73s.
- Full pytest after patch: progressed through 89% before local execution timed out; the previously failing SHA2 verification test now passes. Full-suite outcome remains INCONCLUSIVE. The Stratum API test that was at the timeout point passed in isolation and all 7 tests in test_stratum_miner_014.py passed in 0.95s.

## Latest CI history

Latest prior canonical NEXUS CI run 43457774336 on integration/nexus-master-0.10.25:
- edge-tests PASS
- source-detection PASS
- python-tests SKIPPED because application/ source was absent
Overall success must not be described as full application CI.

## Work committed during this refresh

On integration/source-import-safe-0.10.25:
- importer script strengthened to verify archive SHA-256, exact manifest inventory, every file size/hash, path safety and excluded runtime/cache artefacts.
- regression patch added at patches/0.10.25/sha2-verification-results-root.patch.
- guarded source import workflow added at .github/workflows/nexus-source-import.yml. It imports the already-committed archive into application/, applies the reviewed patch, compiles, runs focused and full pytest, then commits application/ only if all gates pass. It then dispatches canonical NEXUS CI.
- workflow run started: 43701436536; initial state queued. Check this run before making further changes.

## Architecture

One NEXUS modular monolith. CORE owns orchestration, approvals and shared services. Preserve one Lifecycle Manager and one Module Registry. All modules use shared versioned contracts for configuration, logging, audit, metrics, event bus, persistence, identity and secret access. EDGE is an optional node service integrated through existing lifecycle/registry, not a parallel app. Runtime data is central persistence, not Git. Never commit wallet seeds, private keys, API tokens, live DBs, logs or machine state.

## Next steps

1. Check workflow run 43701436536 and its jobs/logs. Do not claim source import or tests passed until it completes.
2. If import fails, fix the actual error only; do not regenerate the source archive.
3. If tests fail, preserve logs and isolate exact failures; do not weaken tests or treat missing generated evidence as successful research.
4. Once source is committed, inspect actual application tree and reconcile module boundaries.
5. Integrate EDGE through existing runtime and registry with contract tests; then add persistent store and authenticated transport.
6. Integrate crypto/mining/wallet/RCSC/math/research/DePIN/marketplace one at a time through adapters and shared event/persistence contracts.
7. Keep main unchanged until a reviewed PR and passing CI; validate Windows 11 and real hardware/live provider separately.

## Status vocabulary

PLANNED = design only.
IMPLEMENTED = source exists.
TESTED = named automated tests passed.
INTEGRATED = shared runtime connection proven by integration tests.
VALIDATED = target Windows/hardware/live-provider behavior proven.

Never infer operational readiness from file presence, route registration, compile success, or a green workflow with skipped application tests.

## NEXUS integration progress — 2026-11-15 (continued)

Current working branch: `integration/source-import-safe-0.10.25`. Changes remain isolated from `main`.

### Shared persistence and runtime
- Central data path service is implemented and registered in the runtime; import/health checks are designed not to create the filesystem.
- Wallet DB, SHA-2 research, Mining Supervisor runtime files, Research Hub history, RCSC DB, Earnings Intelligence DB, mining optimization history and CoinPaprika cache now use the central data location (environment overrides retained where present).
- Research Hub and RCSC are registered as read-only runtime services. RCSC health inspection does not initialize tables or contact providers.
- SHA-2 research output directories are created only on explicit write/verification operations.
- Earnings Intelligence schema creation is deferred until an explicit API operation.

### Conditional mining switch
- Added `modules/mining_switch_controller.py`: evidence gate for candidate coin/configuration changes, minimum three measured windows of at least 300 seconds, minimum 15% net improvement, source freshness limit, thermal/reject limits, dwell time, cooldown and daily switch cap.
- Safety floors cannot be weakened by request-supplied policy. Non-finite values and future source timestamps are rejected.
- Added persistent per-engine active configuration and switch history under the central NEXUS data directory. The API uses persisted state rather than caller-supplied cooldown state.
- Added transactional `HybridSupervisor.switch_engine()` for CPU/GPU workers, with rollback attempt if the new worker fails startup.
- Added evaluation and apply API routes and a dashboard preview panel. Evaluation never changes a worker.
- **Live switch application remains intentionally blocked:** `source_adapter_status()` reports zero validated live mining source adapters. The caller cannot assert this flag to bypass the server-side gate. Provider registry currently reports zero live-verified providers.
- `NEXUS_AUTO_SWITCH_ENABLED` defaults off. Even with explicit opt-in, apply remains blocked until a real source adapter passes validation and is connected to discovery/evidence ingestion.

### Test evidence
- CI PASS: runtime RCSC/Research Hub registration and read-only probes; mining worker read-only status; switch controller policy; transactional worker switch; dashboard panel; CoinPaprika cache path and fallback tests (runs include 43732114579, 43732128435, 43732142541, 43732153419, 43732167534, 43732191475, 43732473608, 43732488617, 43732569997, 43732603636).
- Two intermediate CI failures were traced to a stale API test expecting `automatic_switch_disabled` even though the newer persistent-baseline guard correctly blocked earlier. The test was corrected to assert `current_configuration_not_tracked` and `minimum_dwell_not_reached`.
- Latest test run for commit `5e06140e43edb828af99453df2029e5b0ec6ebce` is in progress at this refresh; do not call it PASS until completed.
- CI is Python 3.12 on GitHub-hosted Ubuntu. No Windows 11 compilation/runtime validation or physical miner/pool switch test has been performed in this session.

### Next integration sequence
1. Confirm the latest full CI run and repair only evidence-backed failures.
2. Implement and validate at least one official live mining-source adapter (coin profitability, pool endpoint/authorization, miner version/support and data freshness); until then automatic switching stays blocked.
3. Connect source discovery to Earnings Intelligence and the switch controller using server-generated provenance, not caller-supplied verification booleans.
4. Add end-to-end tests with fake local Stratum endpoints and worker processes, including stale data, pool rejection, low profitability, thermal trips, cooldown, switch rollback and restart persistence.
5. Audit and integrate remaining wallet, blockchain Regtest/Anvil, Math, DePIN/EDGE and dashboard functions through the existing runtime; preserve no-autostart/no-sign/no-broadcast rules.
6. Build and validate the Windows package, then run target-machine checks on the user's Windows 11 laptop and actual installed miner binaries. Keep `main` unchanged until reviewed PR and full CI.

### EDGE and runtime inventory update — 2026-11-15
- Imported the existing `feature/nexus-edge-foundation` package into `application/nexus_edge/` without rewriting it: transport-agnostic in-memory node registry, HMAC heartbeat/result verification, capability scheduling, leases, expiry/requeue and bounded payloads.
- Added the existing EDGE manager/service test suites under `application/tests/`.
- Registered EDGE as optional `edge_manager` in the shared NEXUS LifecycleManager runtime. Runtime tests confirm no network I/O, wallet access or miner autostart.
- EDGE remains an **in-memory pilot**, not production DePIN: no persistent node/task store, MQTT/HTTPS transport, ESP32-C5 firmware, OTA, or physical device validation.
- Added Earnings Intelligence as a read-only Runtime service; its health probe inspects existing SQLite state without creating the database. Live provider connectors remain zero.
- Extended Module Registry to distinguish route registration, LifecycleManager registration and actual operational validation. Runtime registration is not reported as proof of operational readiness.

## Branch topology audit — 2026-11-15

Repository: `dcnsd00/project-nexus`. No open pull requests were present at audit time.

- `main`: canonical baseline, HEAD `529072b777d010ac47711dd6c821b30fef7ecdf9`; latest recorded CI run for this HEAD succeeded. Kept unchanged during current integration.
- `integration/import-0.10.25`: stale bootstrap branch, 40 commits behind `main`, no recent CI run; do not use as integration target.
- `integration/nexus-master-0.10.25`: architecture/EDGE line, 13 commits ahead of `main`; latest HEAD CI succeeded. Contains the unified architecture, EDGE foundation, sanitized import bundle and canonical continuity baseline.
- `feature/nexus-edge-foundation`: EDGE feature line, 9 commits ahead of `main`, 4 commits behind `integration/nexus-master-0.10.25`; latest HEAD CI succeeded. Its EDGE source and tests were imported into the general branch; the branch itself was not merged.
- `integration/source-import-safe-0.10.25`: active general integration line, 103 commits ahead of `main` at the audit baseline. It diverges from `integration/nexus-master-0.10.25` (103 commits ahead and 13 behind), so do not perform a blind merge. It is the only branch receiving the current runtime/mining/data integration work.
- No pull requests were open at the audit time. No branch has been merged into `main` by this work.

Consolidation decision:
1. Continue all implementation on `integration/source-import-safe-0.10.25`.
2. Preserve `main` as stable baseline.
3. Import missing architecture documentation and selected verified EDGE source/tests from the architecture/feature branches; this is content consolidation, not a branch merge.
4. Review the 13 commits unique to `integration/nexus-master-0.10.25` individually before any ancestry merge or PR. Avoid force-push and avoid merging divergent histories without conflict review.
5. Retire `integration/import-0.10.25` only after confirming no external work depends on it; no deletion performed.

## Runtime integration audit — Fieldstation and Math — 2026-11-15

### DePIN Crypto Fieldstation
- Removed import-time filesystem creation and import-time JSON loading/seeding from `adapters/fieldstation/crypto_fieldstation/app.py`.
- Persistent data now resolves under the central NEXUS data root (`fieldstation/`); environment-independent default is supplied by `data_path`.
- Existing JSON state is loaded only when the standalone Fieldstation `main()` is explicitly invoked. Writes create the parent directory only on explicit save.
- Registered `depin_fieldstation` in the shared LifecycleManager and Module Registry.
- Runtime health probe is metadata-only: it does not load state, start the HTTP server, call external sources, access wallet signing or start miners.
- Test coverage added for import/runtime no-side-effects and corrupt-state recovery. Do not claim Fieldstation's external research APIs, live chain reads, reward accounting or provider connections are validated; they remain separate capabilities requiring contract tests.

### Math Intelligence
- `math_intelligence` was already registered in the shared runtime; the probe previously checked only catalog presence.
- Added deterministic runtime self-checks for the modular congruence solver and measured-candidate triage. The triage self-check explicitly asserts `auto_apply=False`.
- Added a runtime integration test that verifies both self-checks and no network calls.
- This validates local mathematical functions only. It does not validate GPU/ASIC mining gains, consensus PoW compatibility or an optimization being applied to a live miner.

### Verified CI evidence
- Commit `c08639e5b2977ac15901960f82f7a0efd18d678c`, run `43733890984`: source-detection PASS; Python 3.12 test suite **424 passed, 1 warning**.
- The subsequent Math Intelligence self-test changes are newer than that run and must be validated by their own latest CI run before being called tested.
- No Windows 11 or physical-device validation is implied by GitHub-hosted Ubuntu CI.
