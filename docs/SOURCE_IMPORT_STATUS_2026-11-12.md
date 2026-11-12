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
