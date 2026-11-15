# NEXUS project continuity ledger

Last refreshed: 2026-11-15
Canonical repository: https://github.com/dcnsd00/project-nexus
Canonical application version in recovered source bundle: 0.10.25

## Non-negotiable continuity rule

Do not recreate NEXUS modules or start a parallel implementation. Before changing code, inspect the canonical branch, current source, tests, and history. Preserve existing interfaces and working implementations. Every code change must be incremental, committed on a feature/integration branch, tested, and recorded here or in the dated changelog.

## GitHub state verified 2026-11-15

Default branch:
- main HEAD: 529072b777d010ac47711dd6c821b30fef7ecdf9

Relevant branches:
- integration/nexus-master-0.10.25 HEAD: ccc8b6bf4292b17b957357ee12c7314eabfe7aa9
- integration/source-import-safe-0.10.25 HEAD: 6e1fc18aa3b03b779cd3e763a371231d0bc594e2
- integration/import-0.10.25 HEAD: 2c1ec087c8f766ef44072d47a69608b6ef18599b
- feature/nexus-edge-foundation HEAD: 4c40d98598c220c35233679f0e540e8cf7766138

No pull requests were found at refresh time.

The latest CI run inspected:
- Run: 43457774336
- Branch/commit: integration/nexus-master-0.10.25 / ccc8b6bf4292b17b957357ee12c7314eabfe7aa9
- Overall workflow: success
- edge-tests: success
- source-detection: success (application source absent)
- python-tests: skipped
Do not describe this as a full NEXUS application CI pass.

## Source archive recovered and verified locally

Library artifact:
- NEXUS_MASTER_0.10.25_SOURCE_IMPORT_BUNDLE_WALLET_MINING.zip
- SHA-256: 642c882557993a86db21583e8efaef359dd01f8f9b28440462ba8a723c924d50
- ZIP entries: 520 (519 manifest-listed source/config/docs/tests files + manifest)
- VERSION.json: NEXUS MASTER 0.10.25

The archive is already present in the repository tree on integration/source-import-safe-0.10.25, but the extracted application/ directory is not committed. Do not ask the user to upload this same ZIP again unless a fresh inspection proves the stored artifact is missing or corrupt.

## Verified local test results (2026-11-15)

Using the recovered ZIP extracted to a clean temporary directory:
- python -m compileall -q . : PASS
- Focused regression command covering tests/rcsc, test_nexus_runtime.py, test_lifecycle_manager.py, test_module_registry.py, test_solo_mining_096.py: 49 passed in 0.99s.
- Full pytest: attempted with 240-second limit; reached about 77% progress, then timed out. INCONCLUSIVE, not PASS. Identify the slow/hanging tests before retrying.

These results were run against the locally extracted archive, not GitHub Actions.

## Existing functionality documented in VERSION.json and changelogs

- NEXUS MASTER version 0.10.25.
- Bitcoin Stratum V1 CPU worker and optional native C SHA-256d scanner with runtime CPU dispatch; exact Python fallback.
- Loopback mock-pool handshake/header/submit accepted/rejected and controller tests; no public pool payout test.
- Mining catalog and miner adapters; several miner adapters have fake-process tests only.
- Wallet recovery interfaces; wallet operations have safety boundaries and no public-chain broadcast.
- RCSC service and research modules with local unit/API tests; no live Mempool collection or independent provider replication.
- Provider integration catalog is read-only; zero providers were live-verified in this build.
- Runtime composition, Lifecycle Manager, Module Registry, read-only wallet adapter and mining supervisor adapter exist in the local source package; they do not yet establish full end-to-end runtime integration.
- NEXUS EDGE is a separate in-memory prototype with HMAC-authenticated nodes/heartbeats, capability scheduling, task leases and signed results. No network transport, persistent storage, firmware binary, wallet access, miner control or arbitrary command execution.

## Architecture decision

One NEXUS modular monolith, one Lifecycle Manager, one Module Registry, shared configuration/logging/metrics/event contracts/persistence/security. CORE owns orchestration and approvals. EDGE is an optional node service integrated through existing lifecycle and registry, not a second independent application. Runtime data belongs in a central persistence layer; source/tests/contracts/migrations belong in Git. Secrets, wallet seeds/private keys, API tokens, live DBs and runtime state must never be committed.

## Next execution sequence

1. Use a Git-capable signed-in Codespaces workspace on integration/nexus-master-0.10.25 or a clean integration branch.
2. Import the already-committed source ZIP using the pinned and verified archive hash; verify manifest and file inventory; inspect git diff and secret scan.
3. Run compileall and full pytest on clean checkout; identify slow tests and report exact failures/timeouts.
4. Reconcile root package layout and requirements without moving/duplicating modules blindly.
5. Integrate EDGE manager as optional service using existing Lifecycle Manager and Module Registry; add persistent store and authenticated transport only with contract tests.
6. Connect modules one at a time (crypto, mining, wallet read-only, RCSC, math/research, DePIN, marketplace) with dependency declarations, health states, telemetry and integration tests.
7. Require CI, Windows 11 install/runtime tests, hardware and live-provider tests as separate evidence gates.

## Reporting standard

Use only these labels:
- PLANNED: design only.
- IMPLEMENTED: source code exists.
- TESTED: named automated tests passed.
- INTEGRATED: shared runtime contract/integration tests passed.
- VALIDATED: target Windows/hardware/live provider behavior verified.

Never infer operational readiness from file presence, route registration, compile success, or a green workflow whose application tests were skipped.
