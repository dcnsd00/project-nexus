> **Current verified state — 2026-11-19.** The historical entries below are snapshots from earlier dates; this block is the authoritative current status.
>
> - Canonical repository: `dcnsd00/project-nexus`.
> - Active implementation branch: `feature/edge-replay-protection-sqlite-v1`.
> - Current HEAD: `5bd6133e4eeeb2629a7641a45fa528d29f2af07b`.
> - Integration target: `integration/source-import-safe-0.10.25`, HEAD `30210464088ff51c32cabda90ae56b6a9ce20bc8`. The active branch is a clean fast-forward descendant, 291 commits ahead and 0 behind at this check. The branch has not yet been merged into the integration target.
> - `main` remains unchanged at `529072b777d010ac47711dd6c821b30fef7ecdf9`; it is not the target of this feature integration.
> - EDGE host-side implementation on this branch includes durable SQLite schema v4, encrypted per-node HMAC secrets, persisted anti-replay, lease/task/result recovery, node provisioning/rotation/revocation, HMAC-SHA256 protocol v1, opt-in HTTPS and MQTTS adapters, atomic/idempotent telemetry ingestion, shared-manager runtime integration and operator inventory.
> - CI for HEAD: run [44492144115](https://github.com/dcnsd00/project-nexus/actions/runs/44492144115) — Linux full test job **624 passed, 1 warning, 10 subtests passed**; Windows compatibility **623 passed, 1 skipped, 1 warning, 10 subtests passed**. Run [44492144055](https://github.com/dcnsd00/project-nexus/actions/runs/44492144055) — frozen desktop build, executable self-test, installer smoke/installation validation and artifact upload **SUCCESS**.
> - Windows CI validates a hosted runner, not the user's laptop. The installer test ran with desktop UI launch skipped. No physical ESP32-C5, real MQTT broker, provider-specific LoRaWAN/IoT, public TLS ingress or payout validation is claimed.
> - SQLite deployment is a single-host pilot. Multi-server primary/standby and active-active are intentionally unsupported. A multi-worker / multiple independent manager process using the same SQLite file has not been validated and must not be enabled.
> - No PR from this branch to the integration target was open at this status capture. Do not restart completed EDGE work; resume from the next open hardening/integration gate recorded in `docs/PROJECT_CONTINUITY.md`.

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
