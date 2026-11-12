# Changelog – 2026-11-12 (RCSC status correction)

## Local source changes
- modules/rcsc_service.py: corrected RCSC status capability metadata. chronological_holdout now reports supported, with holdout_minimum_records=200 (70/30 split yields 60 holdout records).
- tests/rcsc/test_rcsc_integration.py: added regression tests for the capability declaration and insufficient sample handling.

## Verification
- Targeted regression command:
  python -m pytest -q tests/rcsc tests/test_master.py tests/test_solo_mining_096.py tests/test_integration_registry_015.py --disable-warnings --maxfail=1
- Result: 32 passed in 1.79s.

## Package
- NEXUS_0.10.25_RCSC_STATUS_FIX.zip
- SHA-256: 1f5631bd5be7a5da5f0e4924feb5354b970a63a726f729c9ad2a5e090b4c0d41

## Limitations
- This source patch has been saved to Library but not committed as application code to GitHub.
- No live collection or independent-provider replication performed.
- No predictive/mining gain established.
