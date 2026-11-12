# RCSC holdout threshold consistency — 2026-11-12

## Implemented in the local NEXUS 0.10.25 source tree

- Added the single authoritative `HOLDOUT_MINIMUM_RECORDS = 200` constant in `modules/rcsc_service.py`.
- The RCSC status capability and chronological holdout evaluation now use the same threshold.
- Holdout output exposes both `minimum_holdout_records` and `actual_holdout_records`.
- Added boundary tests: exactly 200 holdout records is evaluated; 199 remains `insufficient_data`.

## Validation

- `python -m compileall -q modules/rcsc_service.py tests/rcsc/test_rcsc_integration.py`: PASS.
- `python -m pytest -q tests/rcsc --disable-warnings --maxfail=1`: **21 passed in 1.13s**.

## Scope and limitations

This change is implemented and tested in the local extracted source tree. The application source patch has **not** been imported into the GitHub repository; the repository still does not contain the full NEXUS application source. No live Bitcoin collection or independent data-source replication was performed. This test result does not establish a predictive mining advantage.
