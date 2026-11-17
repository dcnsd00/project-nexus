# NEXUS changelog — 2026-11-17

## CORE resilience and Module Registry integrity

Target branch: `feature/core-lifecycle-isolation-registry-uniqueness`
Base branch: `integration/source-import-safe-0.10.25`
Base commit: `b6f78fc1e6e4bc122ff39230307d74b52cb0e71a`

### Changes in this increment
- Lifecycle Manager now isolates failures of optional services.
- A failed optional service is recorded as `failed`; independent services continue.
- Services depending on a service that did not reach `running` are recorded as `blocked`.
- A blocked critical service still aborts startup and rolls back services started earlier.
- Startup cleanup attempts both `stop` and `shutdown`, recording cleanup errors without masking the primary failure.
- Removed the duplicate `earnings_intelligence` registry ID. The retained route prefix is `/api/intel`, matching `modules/earnings_intelligence.py`.
- Module Registry now rejects empty or duplicate module IDs.
- Added regression tests for optional failure isolation, dependency blocking, critical rollback, and registry uniqueness.

### Verification
- Status: GitHub Actions pending for the commit created by this change.
- No successful test result is claimed until the corresponding GitHub Actions run is inspected.
- No changes are made to `main`.


### GitHub CI result — 2026-11-17
- Commit: `78cb5c3c4e128545f73d6d03be212bda8b3db8fc`
- Workflow run: [44039323668](https://github.com/dcnsd00/project-nexus/actions/runs/44039323668)
- Conclusion: SUCCESS
- Source detection: SUCCESS
- Python 3.12 dependency installation: SUCCESS
- Python compileall: SUCCESS
- Full test suite: **495 passed, 1 warning, 30.13 seconds**
- Existing workflow action deprecation warning (Node.js 20) did not affect the test result.
- Scope: GitHub-hosted Linux CI. Windows installation, physical hardware and live mining remain unvalidated.
