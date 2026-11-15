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
