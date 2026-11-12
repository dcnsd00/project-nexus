# NEXUS MASTER 0.10.25 – source inspection

Date: 2026-11-12
Archive: `NEXUS_MASTER_0.10.25_CUMULATIVE_WINDOWS.zip`
SHA-256: `17702ce64497599d04c65c3893ddf6c7b54ac5d41e84032a203799a6d9db90bc`

## Inventory
- ZIP entries: 1,934 (including directory entries)
- Extracted files at initial extraction: 1,832
- Python modules: 166
- Test modules: 60
- Root entrypoint: `nexus_master.py`
- Requirements: `requirements.txt`, `requirements-dev.txt`, `requirements-desktop.txt`, `requirements-research.txt`
- Main areas: `core/`, `modules/`, `mining/`, `adapters/`, `research/`, `tests/`, `packaging/`, `vendor/`

## Verification in this session
- `python -m compileall -q .`: exit code 0.
- `python -m pytest -q tests/rcsc --disable-warnings --maxfail=1`: 17 passed in 1.68s.
- Earlier combined targeted suite exceeded the 60-second runtime limit; inconclusive.
- Earlier full suite exceeded the 30-second runtime limit; inconclusive.

## Findings
1. Package metadata in `VERSION.json` declares 0.10.25, while `nexus_master.py` still returns 0.10.23 in the master manifest and hybrid status API. Existing tests encode both values; legacy catalog behavior needs separate compatibility review. Tracked in GitHub issue #2.
2. The archive contains generated research results, local state, build artifacts, vendor code and caches. A safe source import needs an explicit allow/deny inventory rather than copying every extracted file.
3. The repository does not yet contain application source. Only project documentation and CI scaffolding have been committed.

## Not validated
- Python 3.12 CI run on GitHub.
- Windows 11 installation on the user's machine.
- Live pool shares/payouts, wallet transactions, sustained CPU/GPU mining, external provider connections.

## Next
- Prepare a source-only import manifest excluding secrets, caches, local DB/state, generated results and machine-specific artifacts.
- Import source into `integration/import-0.10.25` and open a reviewable PR.
- Establish full clean-checkout test baseline before changing runtime behavior.
