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
