# NEXUS MASTER 0.9.8 — audit report

Date: 2026-11-08
Base: NEXUS MASTER 0.9.7
Build type: additive update; source and prior modules retained.

## Implemented in 0.9.8

1. **Verthash / Vertcoin support in SRBMiner-MULTI**
   - Added `Verthash` to the NEXUS SRBMiner algorithm allow-list.
   - Added Verthash dataset estimate (1,200 MiB) and a 256 MiB runtime safety margin.
   - Added VeinPool VTC EU endpoint: `veinpool.fr:3710`, TLS `13710`, PPLNS.
   - Added WoolyPooly VTC endpoint: `pool.woolypooly.com:3102`, PPLNS. No TLS port is configured because the retrieved operator page did not document one.
   - SRBMiner launch uses lower-case CLI algorithm name, `wallet.worker` login, GPU-only flag, worker ramp-up, and Verthash slow table build.

2. **Mining start safety**
   - `/api/mining/start` now enforces the same coin/pool/miner/device compatibility gate used by the UI.
   - Known dataset algorithms are blocked if detected NVIDIA VRAM is below dataset + 256 MiB.
   - Missing custom host/port is rejected before compatibility checks.

3. **Functional pool diagnostics**
   - Added `/api/mining/pool-test`: DNS/TCP connect test against the selected catalog endpoint.
   - Response explicitly says that TCP reachability does not authenticate Stratum and does not prove accepted shares.
   - Reward-account panel is separated from miner configuration. The current account endpoint remains read-only and 2Miners-only; other providers return an explicit unsupported message, never simulated balances.

4. **UI**
   - Version labels updated to 0.9.8.
   - Wallet placeholder follows the selected coin; VTC input gives address-format guidance.
   - Pool account action remains clickable and reports provider coverage instead of appearing inert.
   - Output panels use independent internal scrolling; sidebar remains sticky.

5. **Windows desktop packaging source**
   - Desktop launcher imports the FastAPI app statically so PyInstaller can collect it.
   - PyInstaller spec includes app/modules/mining submodules and VERSION/README data.
   - Windows build/install scripts updated to 0.9.8.

## Automated validation

| Suite | Passed | Failed |
|---|---:|---:|
| NEXUS master | 115 | 0 |
| MultiMiner X | 17 | 0 |
| Crypto Fieldstation | 12 | 0 |
| Wallet benchmark | 15 | 0 |
| Wallet v0.5 | 7 | 0 |
| **Total** | **166** | **0** |

Additional checks:
- Python compile checks passed.
- Dashboard JavaScript syntax check passed with Node.js.
- API tests cover VTC pool catalog entries, SRBMiner Verthash allow-list, 4 GB GPU compatibility gate, config preview, SOLO rejection, and TCP test response.

## Hardware facts from the user's Windows screenshots

- NVIDIA GeForce GTX 1650 Ti, Turing, Compute Capability 7.5.
- VRAM: 4,096 MiB.
- SRBMiner-MULTI 3.8.5 reports the device under CUDA.
- SRBMiner's OpenCL PCI topology warnings coexist with successful CUDA device detection.

The Verthash dataset estimate is approximately 1.2 GB according to the VeinPool operator page; this is compatible on paper with a 4 GB card, but actual launch and stable hashrate still require the user's Windows machine.

## Not claimed as tested

- No real GPU mining process was started in this Linux build environment.
- No live VeinPool/WoolyPooly TCP handshake or accepted Stratum share was performed from the user's laptop.
- No real payout/reward API is integrated for VeinPool or WoolyPooly.
- No Windows PE `NEXUS.exe` was compiled here. The archive includes the reproducible Windows build and install scripts; build must run on Windows 10/11 x64.
- Bitcoin Core/Anvil regtest daemons were not started by this audit.

## Security and packaging

The runtime `data/nexus_wallets.db` from the source archive contains vault/watch-address records. It is intentionally excluded from the distributable ZIP so encrypted wallet records are not copied into a software update archive. The original 0.9.7 installation and its database are not modified. Back up any local wallet data separately before replacing or migrating installations.

## Sources for VTC pool configuration

- VeinPool VTC page: https://veinpool.fr/en/coin/vtc
- WoolyPooly VTC page: https://woolypooly.com/en/coin/vtc
- SRBMiner parameters: https://github.com/doktor83/SRBMiner-Multi/blob/master/Parameters
- SRBMiner releases: https://github.com/doktor83/SRBMiner-Multi/releases
