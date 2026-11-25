# NEXUS MASTER 0.9.6 — audit report

## Automated tests

| Component | Passed | Failed |
|---|---:|---:|
| NEXUS Master | 103 | 0 |
| MultiMiner X | 17 | 0 |
| Crypto Fieldstation | 12 | 0 |
| Wallet Benchmark | 15 | 0 |
| Wallet v0.5 | 7 | 0 |
| **Total** | **154** | **0** |

Python compilation and dashboard JavaScript syntax validation also completed without errors.

## Offline scenario benchmark

`results/benchmark_0.9.6_scenarios.json` contains eight scenarios:

- Exact hash throughput: seven standard algorithms, 1 KiB payload, 5,000 iterations per algorithm.
- Modular congruence solver with exact verification.
- Optimization candidate evidence gate; test candidate is classified for manual review only.
- Local synthetic PoW puzzle at 16 bits; a nonce was found.
- Synthetic truncated-digest collision at 16 bits.
- POOL configuration dry-run: 2Miners RVN endpoint resolved to `stratum+tcp://rvn.2miners.com:6060`.
- SOLO_POOL configuration dry-run: WoolyPooly RVN endpoint resolved to `stratum+tcp://pool.woolypooly.com:55555`.
- Solo eligibility/readiness response, with local-node mode explicitly not ready.

These are reproducible local software/benchmark scenarios, not actual external mining. Hash throughput is not PoW hashrate and cannot be compared as expected coin rewards.

## Packaging and platform validation

- Included Windows x64 PyInstaller onedir spec and `BUILD_NEXUS_WINDOWS.ps1`.
- Included `INSTALL_NEXUS_WINDOWS.ps1`, which installs the built executable distribution if present, otherwise installs the Python/pywebview fallback.
- Included Linux install script.
- **Windows EXE has not been generated or executed in this Linux environment.** A Windows PE executable must be built on Windows using the included script. Therefore this archive contains the complete source/build recipe, not a falsely claimed prebuilt `NEXUS.exe`.

## Not tested / external prerequisites

No NVIDIA GPU miner was launched; miner binaries and physical GPU telemetry were unavailable in the benchmark environment. No real Stratum share, pool payout, solo block discovery, Bitcoin Core/Anvil daemon lifecycle, or Windows WebView2 desktop launch was tested. No public-chain transaction was sent.
