# NEXUS 0.10.23 — Hybrid Mining Supervisor

## Added
- Exclusive Standard / Development mode supervisor.
- Separate CPU and GPU worker OS processes, isolated runtime directories, status files and logs.
- Independent engine stop, bounded shutdown, heartbeat reporting and opt-in bounded restarts (disabled by default).
- Development-only local SHA-256d experiment worker restricted to Regtest/Testnet; no public-pool submission.
- SHA-256d 80-byte header/target verification helper with explicit consensus-equivalence reporting.
- GPU resource guard for VRAM margin and thermal telemetry; missing telemetry fails closed.
- Repeated-window optimizer requiring unique window IDs, matching pool/share difficulty, at least three valid windows, accepted shares and consensus-equivalent candidates. Recommendations are manual-review only.
- FastAPI controls for mode selection, hybrid start/stop, per-engine start/stop, GPU switching, status and optimizer planning.
- Dashboard controls for mode selection, miner/pool selection, per-lane arguments and Development CPU experiment.

## Safety and compatibility
- Legacy `mining.controller` lifecycle and `/api/mining/hybrid/plan` preflight behavior are preserved.
- Standard API execution only accepts binaries present and available in the local miner inventory, with pool/algorithm compatibility validation.
- Development mode rejects external miner commands and public GPU workers until a verified Development GPU backend exists.
- No automatic tuning, no automatic restart by default, no public chain writes, and no claims of pool authorization or payout from local process state.

## Verification scope
- Unit, supervisor lifecycle, API, PoW research, safety and optimizer tests are included in the 0.10.23 test suite.
- Physical GPU load, public pool authorization, accepted live shares, payout, temperatures under sustained load and wall-power measurements must be verified on the target Windows machine.

### RandomX benchmark integration (follow-up)
- Added an offline XMRig benchmark adapter for RandomX with bounded thread sweeps (1–8 configurations), `1M`/`10M` benchmark datasets, strict argument validation, timeout handling and explicit unavailable/error states.
- Added `POST /api/mining/randomx/benchmark` and a dashboard panel to compare CPU thread counts.
- Results are recommendation-only; no active miner configuration is changed, no pool/wallet is used, and a production decision still requires accepted pool shares and power/thermal measurements.
- SHA-256d Development benchmark rates are kept separate from RandomX rates; algorithm-specific H/s values must never be compared directly.


### RandomX native engine and 20-header Development lab (2026-11-11)
- Added the official RandomX v1.2.3 source snapshot under `vendor/randomx-1.2.3/`; local uploaded ZIP SHA-256: `e38414a3b2543363b4fb62c1b7b03349f43399a11376a833eb4adbac96e14311`.
- Added native reference benchmark adapter, native build scripts and a separate 20-header synthetic benchmark harness using the official RandomX C API in fast/full-memory mode.
- Added `POST /api/mining/randomx/reference-benchmark` and `POST /api/mining/randomx/20block-benchmark` routes; added a dashboard panel to rerun the 20-header offline lab.
- API response explicitly records `pool_connected=false`, `authorized=false`, `accepted_shares=0`, `automatic_application=false`.
- 20-header blobs and 8–14 leading-zero-bit targets are laboratory-only test data, not valid Monero block templates or network submissions.
