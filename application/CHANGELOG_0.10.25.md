# NEXUS MASTER 0.10.25 — Windows desktop installer hardening

Date: 2026-11-12
Base: NEXUS_MASTER_0.10.24_CUMULATIVE_WINDOWS

## Implemented in this package
- `INSTALL_NEXUS_WINDOWS.ps1`: corrected release version to 0.10.25; validates Python 3.11+; creates an isolated `.venv`; checks pip/dependency installation exit codes; verifies imports for FastAPI, Uvicorn, pywebview and `nexus_master` before creating shortcuts.
- Installer prefers a present PyInstaller onedir build and verifies `NEXUS.exe` after copying.
- Installer creates Desktop and Start Menu shortcuts for both frozen and Python desktop modes.
- `packaging/README_WINDOWS_BUILD_RO.md`: updated install/build instructions and explicit validation boundaries.
- `VERSION.json`: updated package version and desktop installer metadata.

## Inherited components (present in 0.10.24; not newly implemented here)
- Hybrid Mining Supervisor and worker processes.
- RandomX benchmark API/adapter.
- RCSC collector/service/API and SQLite persistence.
- Desktop shell using pywebview and loopback binding.

## Not validated in this environment
- PowerShell installer execution on Windows.
- PyInstaller build and Edge WebView2 runtime.
- Live pool connection, accepted shares, payout, live RCSC collection, physical GPU mining, or profitability.
- This package update does not install external miner binaries or configure wallet credentials.
