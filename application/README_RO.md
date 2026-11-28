# NEXUS MASTER 0.10.28

## Windows desktop package

This package is a frozen Windows x64 desktop build. It includes the bundled Python runtime, the NEXUS desktop shell, CORE modules, the NEXUS EDGE package and the local diagnostic interfaces.

### Install

1. Extract the complete installer ZIP to a local folder.
2. Run `INSTALL_NEXUS.bat`.
3. The installer validates the package SHA-256 manifest, checks Microsoft Edge WebView2 Runtime, installs NEXUS under `%LOCALAPPDATA%\\Programs\\NEXUS`, and runs the packaged self-test.
4. A Desktop and Start Menu shortcut are created.

Windows 10/11 x64. Python and Visual Studio are not required on the target computer. An internet connection is used only if the Microsoft WebView2 Runtime must be installed.

## Included capabilities

- NEXUS MASTER local desktop shell and loopback-only API.
- Mining catalogue, miner controller interfaces and algorithm-specific profiles.
- Native SHA-256d CPU scanner with runtime CPU feature dispatch and exact Python fallback.
- SHA-2 research tools, mathematical utilities and offline benchmarks.
- Wallet tooling and local encrypted keystore support.
- NEXUS EDGE components: manager, SQLite persistence, replay guard, runtime, HTTPS gateway and transport adapters.
- RainbowMiner read-only local telemetry import with authenticated SQLite storage.
- Mining Profit Intelligence with RON/kWh cost modelling and recommendation-only pool scoring.
- Central AI coordination across up to three domain specialists with QA/security review; model provider is opt-in and text-only.

## Validation status

- GitHub Actions Python suites: Windows 635 passed / 1 skipped; Linux 636 passed.
- Additional suites: MultiMiner X 17 passed; Crypto FieldStation 12 passed; Wallet 15 passed; Wallet V05 7 passed; SHA-2 independent 13 tests with 1 optional skip.
- Frozen Windows executable self-test: passed on GitHub Actions.
- One-click installer validation: passed on GitHub Actions using the packaged installer in no-launch mode.
- Cross-platform SHA-256d CPU benchmark: passed on GitHub Actions Linux and Windows runners.

GitHub-hosted benchmark results are not a measurement of the user's laptop. The local laptop benchmark must be run after installation. The GitHub Windows runner exposed scalar native variants only; AVX2/AVX-512 availability must be measured on the actual host.

## Important limitations

- A module being included does not prove that an external provider is connected or that its hardware path has been exercised.
- Live public pool login, accepted shares, payouts and mainnet transactions have not been validated by this package build.
- GPU mining and RandomX performance are not represented by the SHA-256d CPU benchmark.
- Provider integrations are reported as configured/read-only where applicable; live-verified provider connectors: 0.
- Miner binaries are not automatically launched. Installation does not connect pools, start mining, or unlock wallets.
- Wallet recovery must be used only for wallets owned by the user or with explicit authorization. Never share a real seed phrase or private key.
- Keep backups of any existing NEXUS data directories before updating. The installer preserves user data and does not include personal wallet databases in the package.

## Project

Repository: https://github.com/dcnsd00/project-nexus
Release target branch: `main`
