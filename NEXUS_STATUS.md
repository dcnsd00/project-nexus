> **Current verified state — 2026-11-24.** This snapshot supersedes the dated status block below. GitHub remains the source of truth for branch heads, PRs and CI.
>
> - Repository: `dcnsd00/project-nexus`.
> - `main` remains untouched at `529072b777d010ac47711dd6c821b30fef7ecdf9`.
> - EDGE foundation branch: `feature/edge-replay-protection-sqlite-v1`, HEAD `9cdecd6ba24c7e44e26fb77d78580150d2018167`. Its latest change enables NEXUS CI for pull requests targeting this feature branch; no EDGE runtime code was changed by that workflow commit.
> - PR #4 — Windows lifecycle, branch `feature/windows-testclient-lifecycle-01026`, latest head `988caf75264c4352fa68b05a28f6bb28dda55f14`. Added Windows process-handle liveness detection and a regression test for invalid/current PIDs. CI run [45463040219](https://github.com/dcnsd00/project-nexus/actions/runs/45463040219): source detection and Linux Python tests SUCCESS; dedicated Windows lifecycle regression modules and isolated API test module SUCCESS, including the stale orphan-PID test; Windows compatibility batch 7/12 remains in progress. Do not mark PR #4 fully tested yet.
> - PR #5 — Gate Info / Paper Trading, branch `feature/gate-info-paper-trading-100ron`, latest head `549c9da5c70784bf5547a45c12740e74b14d6489`. The native SHA-256d Genesis test checks the known nonce over a 35-item tail range instead of scanning 1,000,032 unrelated nonce values in CI; independent non-multiple range and block-candidate tests remain. Focused Gate run [45463099607](https://github.com/dcnsd00/project-nexus/actions/runs/45463099607) SUCCESS. Full NEXUS run [45463099635](https://github.com/dcnsd00/project-nexus/actions/runs/45463099635): source detection and Linux Python tests SUCCESS; Windows compatibility batch 7/12 is in progress. This is the former timeout batch; no failure is reported at this snapshot. Do not mark PR #5 fully tested yet.
> - PR #6 — Provider integration contract tests, branch `feature/nexus-integrations-contract-tests-v1`, head `15e06246e75fa167a8c3649ff30242e6f543b2a3`. Tests unique provider IDs, unconfigured/partial/complete credentials, no credential echo, read-only status and catalog/status response semantics. CI run [45463294846](https://github.com/dcnsd00/project-nexus/actions/runs/45463294846): source detection and Linux Python tests SUCCESS; Windows remaining application suite in progress. No live provider adapter is claimed.
> - PR #7 — Math Intelligence hardening, branch `feature/nexus-math-intelligence-hardening-v1`, head `e07307db9d4ab0c2b662cf50c82a072dc7f6a2dd`. Adds finite-number and non-negative integer validation for measured candidate evidence, strict boolean equivalence evidence, overflow handling and regression tests. Automatic application remains disabled. CI run [45463308801](https://github.com/dcnsd00/project-nexus/actions/runs/45463308801): source detection and Linux Python tests SUCCESS; Windows remaining application suite in progress.
> - PR #8 — Fieldstation runtime boundary, branch `feature/nexus-fieldstation-runtime-validation-v1`, head `f9fd1df7b793eb63fc061e59298c1264bbda7f61`. Removes import-time creation of the optional `miners` directory and adds tests for import behavior, loopback binding and explicit port configuration. CI run [45463306245](https://github.com/dcnsd00/project-nexus/actions/runs/45463306245): source detection and Linux Python tests SUCCESS; Windows remaining application suite in progress.
> - No PR was merged in this increment. No code or configuration was committed to `main`.
> - Legacy branch disposition: `feature/edge-persistence-protocol-v1`, `feature/nexus-edge-foundation` and `integration/nexus-master-0.10.25` are divergent and materially behind the current EDGE base; use them only for selective recovery after diff review. `feature/core-lifecycle-isolation-registry-uniqueness` has no unique delta against the current integration line and its work is already represented in the active source. Do not revive these as competing bases.
> - Validation boundary: GitHub Actions is the only current CI evidence. The local container could not reach GitHub, so no local execution is claimed. Hardware, public providers, live mining, live payouts and field ESP32/LoRaWAN operation remain unvalidated.
>
# NEXUS — repository status

Updated: 2026-11-17

## Canonical development workflow
- GitHub is the canonical development, integration and CI verification environment.
- Implement changes on focused feature branches from the latest integration baseline.
- Use connected plugins and auxiliary development tools for research, code generation and specialist work; all candidate code must be committed to GitHub and tested there before integration.
- Require compilation, unit/integration tests and applicable security checks in GitHub Actions.
- Integrate through pull requests. Do not modify `main` directly.
- Local archives are source/backup artifacts; local test results are supplementary and never replace GitHub CI evidence.

## Repository
- Repository: dcnsd00/project-nexus
- Default branch: main (not modified by this increment)
- Active application branch: integration/source-import-safe-0.10.25
- Source bundle: NEXUS MASTER 0.10.25, 519 project files plus manifest.
- Source bundle SHA-256: 642c882557993a86db21583e8efaef359dd01f8f9b28440462ba8a723c924d50

## Completed increment — CORE resilience and Module Registry integrity
- Feature branch: feature/core-lifecycle-isolation-registry-uniqueness
- Pull request: [#3](https://github.com/dcnsd00/project-nexus/pull/3), merged into the active integration branch.
- Merge commit: fd332d91c54df2accd4dad4b74920575e5729d1d
- Lifecycle Manager now isolates failures of noncritical services; independent services continue.
- Dependents of failed or unavailable services are marked BLOCKED.
- Failure of a critical service or a critical service's dependency still aborts startup and rolls back services already started.
- Cleanup attempts both stop and shutdown and records cleanup failures without masking the primary startup failure.
- Removed the duplicate `earnings_intelligence` registry entry; retained `/api/intel`, matching the actual router.
- Module Registry rejects empty or duplicate module IDs.
- Added regression tests for optional service isolation, blocked dependents, critical rollback and registry uniqueness.

## GitHub Actions evidence
All runs below completed with conclusion SUCCESS:
- Run 44039323668 — feature code commit: 495 passed, 1 warning.
- Run 44039699684 — status/changelog commit: 495 passed, 1 warning.
- Run 44040117420 — final feature branch head: 495 passed, 1 warning.
- Run 44040373918 — post-merge integration branch commit fd332d9: 495 passed, 1 warning.
- Each run completed source detection, Python 3.12 dependency installation, Python compileall and the full pytest suite.
- The existing workflow reports a Node.js 20 deprecation warning for `actions/checkout@v4` and `actions/setup-python@v5`; it did not fail the jobs.
- Validation scope: GitHub-hosted Linux CI. Windows installation, physical hardware, ESP32 communication, live mining and payouts remain unvalidated.

## Active increment — NEXUS EDGE protocol anti-replay and SQLite

- Feature branch: `feature/edge-replay-protection-sqlite-v1`
- Base: `integration/source-import-safe-0.10.25`; `main` remains untouched.
- Added `application/nexus_edge/replay_guard.py`: in-memory and SQLite-backed replay guard implementations.
- Heartbeats now sign and carry a monotonically increasing per-node sequence; duplicate and out-of-order sequences are rejected.
- SQLite uses an atomic write transaction and persists only sequence counters, not HMAC secret material.
- NEXUS Runtime injects the SQLite replay guard at the canonical `NEXUS_DATA_DIR/db/edge_replay.sqlite3` path.
- Updated EDGE foundation documentation to distinguish implemented replay protection from still-ephemeral node/task state.
- Initial full CI exposed one legacy test call using the old heartbeat signature; corrected in commit `057b0402a90ed97d29272e7ff8685df0dddcb011`.
- Current branch head is being re-tested. Do not treat this increment as tested or integrated until the latest full CI run completes successfully.
- Still pending: durable node/task/lease persistence, key provisioning/rotation, protocol versioning, transport, ESP32 firmware and physical validation.

## Next engineering increment
1. Create a separate feature branch for NEXUS EDGE persistence and protocol hardening.
2. Define storage interfaces and migration/version contracts before implementation; test restart recovery and crash consistency.
3. Add message protocol versioning, monotonic sequence numbers/nonces, key provisioning and rotation hooks.
4. Add MQTT/HTTPS transport with TLS and a local broker integration test only after persistence and protocol tests pass.
5. Develop ESP32-C5 firmware as a separate component/branch; connect physical nodes only after host-side protocol tests pass.
6. Continue Mining, Wallet, RCSC, Math and Strategy Engine integration as focused GitHub branches with CI evidence.
7. Promote changes to main only through a separately reviewed pull request after all integration gates pass.

## Status vocabulary
- PRESENT: source file exists on a named branch.
- IMPLEMENTED: behavior exists in source.
- TESTED: named GitHub Actions test job passed.
- INTEGRATED: runtime integration test verifies the connection.
- VALIDATED: confirmed on target Windows installation, physical hardware or live service.
