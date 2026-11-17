# NEXUS — repository status

Updated: 2026-11-17

## Canonical development workflow
- GitHub is the canonical development, integration, and CI verification environment.
- Implement code changes on focused feature branches created from the latest integration baseline.
- Run formatting, compilation, unit/integration tests and security checks in GitHub Actions.
- Merge only by reviewed pull request after required checks pass.
- Local archives are source/backup artifacts; local container test results are supplementary and are not a substitute for GitHub CI.
- Do not modify `main` directly.

## Repository
- Repository: dcnsd00/project-nexus
- Default branch: main
- Active source baseline: integration/source-import-safe-0.10.25
- Current work branch: feature/core-lifecycle-isolation-registry-uniqueness
- Baseline commit: b6f78fc1e6e4bc122ff39230307d74b52cb0e71a
- Source archive: NEXUS MASTER 0.10.25, 519 project files plus manifest.
- Source bundle SHA-256: 642c882557993a86db21583e8efaef359dd01f8f9b28440462ba8a723c924d50

## Implemented baseline already present
- NEXUS MASTER 0.10.25 application source exists under application/ on the active integration branch.
- Lifecycle Manager, Module Registry, Runtime composition, Wallet read-only adapter, Mining Supervisor read-only adapter, RCSC and EDGE foundation are present.
- EDGE is currently an in-memory pilot with no network transport, persistence or ESP32 firmware.
- GitHub Actions run 43761167547 (2026-11-15) completed with source-detection and python-tests successful on the integration branch.
- That CI result does not validate Windows installation, physical hardware or live pool payouts.

## Current implementation increment — CI pending
- Isolate noncritical service failures so independent services continue starting.
- Mark dependents of failed services as BLOCKED.
- Preserve rollback and startup-abort behavior for critical failures.
- Remove the duplicate earnings_intelligence registry entry; retain the actual /api/intel route.
- Reject future duplicate or empty module registry IDs.
- Add regression tests for optional failure, blocked dependents and registry uniqueness.
- This increment is being committed on the feature branch named above. GitHub Actions results will be recorded after the workflow completes.

## Next implementation sequence
1. Verify this branch's GitHub Actions run and fix any CI failures.
2. Review the runtime's degraded/blocked service reporting and dependency policy.
3. Add EDGE persistence and protocol replay protection.
4. Add transport adapter and local broker integration tests.
5. Develop ESP32-C5 firmware as a separate component/branch; integrate only after host-side protocol tests pass.
6. Continue Mining, Wallet, RCSC, Math and Strategy Engine integration with tests in GitHub.
7. Open pull requests against main only after review gates pass.

## Status vocabulary
- PRESENT: source file exists on a named branch.
- IMPLEMENTED: behavior exists in source.
- TESTED: named GitHub Actions test job passed.
- INTEGRATED: runtime integration test verifies the connection.
- VALIDATED: confirmed on target Windows installation, physical hardware or live service.
