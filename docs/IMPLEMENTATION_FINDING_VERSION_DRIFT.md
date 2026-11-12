# Implemented fix – package version drift

Date: 2026-11-12

## Source change prepared in working archive
- `nexus_master.py` now reads the authoritative version from `VERSION.json` through `_package_version()`.
- `/api/nexus/master` and `/api/nexus/dashboard-data` use that value instead of hard-coded 0.10.23.
- Regression assertions in `tests/test_master.py` and `tests/test_solo_mining_096.py` now expect 0.10.25.

## Verification
- Python compileall for changed files: PASS.
- Targeted tests: 10 passed in 1.58 seconds.

## Important
This source patch is currently in the working archive only. It has not been committed as application code to GitHub because the connector's available write methods accept text files but no binary/source-archive handoff is available in this session.
