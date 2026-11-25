# NEXUS 0.10.23 — RandomX benchmark integration follow-up

Date: 2026-11-11

## Implemented

- `mining/randomx_benchmark.py`: offline XMRig benchmark adapter, restricted to a detected NEXUS-managed/PATH XMRig executable, bounded thread count and dataset options, timeout handling, output parsing and explicit failure states.
- `POST /api/mining/randomx/benchmark`: accepts 1–8 unique CPU thread counts and runs offline RandomX benchmark trials.
- `dashboard.html`: RandomX CPU benchmark panel with thread sweep and dataset selection.
- README and changelog updated.

## Safety and interpretation

- Benchmark command uses XMRig benchmark mode (`--bench`) and does not provide pool URL, wallet, credentials or share submission arguments.
- RandomX results remain algorithm-specific H/s and must not be compared with SHA-256d results.
- No active miner configuration is modified. The API reports recommendation-only and automatic application false.
- A local benchmark does not establish accepted pool shares, payout or net profitability. Production tuning still requires repeated sustained trials on the target PC, pool-side accepted/rejected shares, temperature and power measurements.
- No XMRig executable is installed/detected in the build environment. Runtime API test therefore returned HTTP 200 with `state=backend_unavailable` for each requested thread count. Real RandomX H/s was not measured here.

## Verification

- Targeted tests: 19 passed.
- Full suite verbose output: 318 passed in 41.06 seconds.
- Python compileall: exit code 0.
- Dashboard JavaScript: 2 inline script blocks checked successfully.
- API smoke: POST `/api/mining/randomx/benchmark` returned HTTP 200 and explicit backend_unavailable (no false hashrate).
- ZIP integrity: `unzip -t` reported no errors.

## Remaining hardware validation

Install/detect XMRig on the user's Windows PC, run thread sweeps at 1, 2, 4, etc. (within physical/logical CPU limits), then compare stable pool-side measurements with the existing unMineable/RandomX setup. Do not change the live miner automatically.
