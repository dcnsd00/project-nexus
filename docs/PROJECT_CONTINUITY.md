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
