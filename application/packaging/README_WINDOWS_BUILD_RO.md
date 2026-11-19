# NEXUS MASTER 0.10.26 — Windows desktop package

## End-user installation

The supported delivery is the generated `NEXUS_MASTER_0.10.26_WINDOWS_INSTALLER.zip` artifact from the **NEXUS Windows Desktop Package** workflow.

1. Extract the ZIP.
2. Double-click `INSTALL_NEXUS.bat`.
3. The installer validates the SHA-256 manifest, checks Microsoft Edge WebView2 Runtime and installs the signed Microsoft bootstrapper only if missing.
4. It copies the frozen desktop application to `%LOCALAPPDATA%\Programs\NEXUS`, creates Desktop and Start Menu shortcuts, and runs `NEXUS.exe --self-test`.
5. If the smoke test passes, NEXUS MASTER starts automatically.

No separately installed Python, Visual Studio, PowerShell commands, or source-tree setup is required for end users. Internet is needed only if WebView2 Runtime is missing.

The installer does not delete user data directories, does not start miners, does not connect pools, and does not unlock wallets.

## Build and package validation

The Windows package workflow:
- builds on a clean Windows x64 runner with Python 3.12 and MSVC;
- compiles Python sources and validates dashboard JavaScript;
- runs desktop package source tests;
- creates the PyInstaller onedir application, including the bundled Python runtime and application resources;
- launches the actual frozen executable in self-test mode, exercising the FastAPI lifespan, master manifest and desktop dashboard route;
- generates SHA-256 checksums for all frozen runtime files;
- assembles and uploads the one-click installer ZIP as a GitHub Actions artifact.

The custom desktop UI is the NEXUS Control Center, served locally inside Microsoft Edge WebView2. It has navigation, dedicated operational sections, live status and interactive controls; it is not an Excel workbook or a spreadsheet-style interface.

## Validation boundary

A successful Windows CI package build and frozen executable self-test validate the packaged application code and API/dashboard startup. They do not replace a physical first-run check on the user's laptop. WebView2 is checked by the installer, while actual GPU telemetry, device thermals, external miner binaries, pool authorization and live payouts remain hardware/provider-specific checks.
