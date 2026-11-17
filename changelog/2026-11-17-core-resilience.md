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

### GitHub CI verification — 2026-11-17
- Code commit: `78cb5c3c4e128545f73d6d03be212bda8b3db8fc`.
- CI run [44039323668](https://github.com/dcnsd00/project-nexus/actions/runs/44039323668): SUCCESS.
- Status/changelog commit: `75441343e94285afee87e629bb60e989001ac65c`.
- CI run [44039699684](https://github.com/dcnsd00/project-nexus/actions/runs/44039699684): SUCCESS.
- Both runs completed source detection, Python 3.12 dependency installation, Python `compileall`, and the full test suite: **495 passed, 1 warning** per run.
- The existing workflow uses actions currently flagged for Node.js 20 deprecation; this warning did not fail the jobs.
- Scope: GitHub-hosted Linux CI only. Windows installation, physical hardware, ESP32 communication, live mining and payouts remain unvalidated.
- This feature branch targets `integration/source-import-safe-0.10.25`; `main` is unchanged.
