# NEXUS MASTER 0.10.25 source import status — 2026-11-12

## Transfer package prepared
- Version confirmed from `VERSION.json`: 0.10.25.
- 513 source/configuration/documentation/test files included.
- SHA-256: `f4774e21854387f38152ae969a84b07d8dc2fec2ef21d120923bf82738ca1f7f`.
- Generated databases, local data, build outputs, caches, and result directories are excluded.
- Transfer archive is stored in ChatGPT Library → NEXUS as `NEXUS_MASTER_0.10.25_SOURCE_IMPORT_BUNDLE.zip`.

## Local validation
- The RCSC common-ancestor recovery patch has now been merged into the extracted source tree (this corrects the earlier premature statement that it was already cumulative).
- `python -m compileall -q modules/rcsc_service.py tests/rcsc/test_rcsc_integration.py`: PASS.
- `python -m pytest -q tests/rcsc --disable-warnings --maxfail=1`: 33 passed in 1.40s.

## GitHub import is NOT complete
The available GitHub connector supports text-file writes and Git object operations but no bulk binary/archive upload or local filesystem handoff. The local runtime cannot resolve `github.com`, so clone/push is unavailable. Consequently, the 513 application source files have not been committed to this repository. Existing GitHub commits are documentation only.

## Security review
A preliminary scan found fixed password-like strings in test fixtures and local-regtest modules. They appear test-specific but require review before production release. No environment files, PEM/private-key files, or wallet result JSON files were included in the transfer bundle.

## Required next step
Import the archive through a Git-capable environment (for example GitHub Codespaces or a trusted local Git client), create a pull request, run CI and secret scanning, then review before merge. The archive is a transfer package, not a completed GitHub import.


## Import tooling added
- Updated `.github/workflows/nexus-ci.yml` to detect either `application/` or repository-root source layout; it still fails closed if neither is present.
- Added `scripts/import_source_bundle.sh`: verifies the pinned SHA-256, 514-file inventory, safe ZIP paths, refuses overwrite, and extracts into `application/`.
- Added `docs/ANDROID_CODESPACES_IMPORT.md` with Android/browser-based Codespaces steps.
- Latest supporting commits: CI `8766c09`, import helper `55e68a5`, Android guide `61895db`, security scan `3c40f3f`.

The archive itself is still not committed to GitHub and the 514 source files have not yet been imported. The next action requires uploading the ZIP from Library into the Codespaces workspace and running the helper.


## Corrected security-reviewed bundle (latest)
- Replaced fixed wallet test passphrases with per-test random values.
- Removed fixed local regtest RPC password; both local integration modules now require `NEXUS_REGTEST_RPC_PASSWORD`.
- Corrected bundle SHA-256: `fafd5dd81fc0911cbb3e0c54aaa2dd6ef021010e60da31871eaa2f789a9ec55e`.
- Corrected bundle path in Library: `/NEXUS/NEXUS_MASTER_0.10.25_SOURCE_IMPORT_BUNDLE(1).zip`.
- Full-source compileall: PASS.
- Targeted combined validation: **69 passed in 9.00s** (RCSC + wallet recovery tests).
- Updated importer hash and Android guide: commits `f987921` and `48697e6`.
- Security scan remediation record: commit `9bbb5df`.

The corrected source archive is still NOT imported into GitHub. The next required action remains uploading this corrected ZIP to the Codespaces workspace and running the importer.


## Latest cumulative bundle — RCSC recovery tip-window correction
- Corrected the recovery algorithm to merge backward overlap with the original newer tip window, preserving the full replacement segment.
- Added a regression test for the newer-tip preservation case.
- RCSC suite: **34 passed in 3.14s**; compileall PASS.
- Updated cumulative import bundle: `NEXUS_MASTER_0.10.25_RECOVERY_TIP_WINDOW.zip`.
- SHA-256: `f7385ccec2101cc07da36785cd7ee5ed250737a127f3cacd5e7273696a60e14e`.
- Patch ZIP: `NEXUS_0.10.25_RCSC_RECOVERY_TIP_WINDOW_FIX.zip`.
- Android guide updated in commit `7772d51`.
- The cumulative source archive is still not imported into GitHub; the repository does not yet contain the application Python source.


## RCSC SQLite lifecycle hardening — latest local build
- Added a managed SQLite context that always closes connections and commits/rolls back deterministically.
- Configured a 30-second busy timeout and FULL synchronous durability while retaining WAL.
- Added connection lifecycle/commit/rollback regression tests.
- RCSC suite: **36 passed in 1.66s**; compileall PASS.
- Latest source bundle SHA-256: `658c5b9886e100258d344dce7b96becf6d261101385dcb292af424912c49db59`.
- Latest Library path: `/NEXUS/NEXUS_MASTER_0.10.25_SOURCE_IMPORT_BUNDLE_LATEST.zip`.
- Patch: `NEXUS_0.10.25_RCSC_SQLITE_LIFECYCLE_FIX.zip`.

Architecture limitation: this change hardens the RCSC SQLite service only. The project does not yet have a verified shared database abstraction across every module, and the collection block update plus run-ledger record are still separate transactions. No multi-process stress or power-loss test was run.

The latest archive is still not imported into GitHub; GitHub source CI has not yet executed.


## NEXUS Module Registry implementation
- Added `modules/module_registry.py` and integrated two endpoints in `nexus_master.py`.
- `GET /api/nexus/module-registry` and `GET /api/nexus/module-registry/health`.
- Actual local import of `nexus_master` and direct registry invocation succeeded.
- Structural inventory: 10 modules; 8 show registered-route evidence; 2 are source-present without route registration; 0 declared source paths missing.
- 4 critical modules show source and route evidence, but every module remains explicitly `operational_verified=false`.
- Focused validation: 48 passed in 1.77s.
- Latest bundle: 515 project files + manifest; SHA-256 `88ad6e728642b3a52b3a65905ee18e228b413e98e38b443050b05c2b2f157caf`.
- Import helper and Android guide updated: commits `f082dd5`, `08c8d7b`.
- Registry audit document: commit `5d06649`.

The latest application source remains local/Library only. GitHub does not yet contain the 515 project files, and CI has not yet run the application's tests.


## Runtime composition increment — 2026-11-12
- Added `modules/nexus_runtime.py` as a local composition root over `LifecycleManager`.
- Runtime currently registers Crypto Engine (critical), Math Intelligence, Provider Registry, and optional SHA-2 Research.
- Adapters perform local import and read-only health probes. Startup does not launch miners, unlock wallets, contact providers, broadcast transactions, or collect blockchain data.
- Added `tests/test_nexus_runtime.py`; corrected a stale version assertion to match `VERSION.json` (0.10.25).
- Focused validation: **43 passed in 1.78s** (runtime + lifecycle manager + module registry + RCSC).
- Full pytest run was attempted but exceeded the execution time limit; no full-suite pass is claimed.
- Latest cumulative bundle: 519 project files + manifest (520 ZIP file entries).
- SHA-256: `4d2dcf415c5f98f8c919f559fc98a38febb04708121c33a9643b1e19d5457e33`.
- Library path: `/NEXUS/NEXUS_MASTER_0.10.25_SOURCE_IMPORT_BUNDLE_RUNTIME.zip`.
- Patch: `/NEXUS/NEXUS_0.10.25_RUNTIME_INTEGRATION_FIX.zip`.
- Changelog: `/NEXUS/CHANGELOG_RUNTIME_INTEGRATION_2026-11-12.txt`.
- Import helper updated for the new archive hash and 520 ZIP entries; commit: `00e13691`.

Integration boundary: Wallet, mining supervisor, DePIN fieldstation, and the separate PROJECT-NEXUS-LOCAL FastAPI app are not yet wired into this runtime. The source bundle is still not imported into GitHub; CI has not validated the application source.
