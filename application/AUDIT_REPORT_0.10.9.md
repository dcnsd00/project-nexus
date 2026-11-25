# NEXUS MASTER 0.10.9 – audit incremental

Data auditului: 2026-11-09. Build derivat din 0.10.8.

## Modificări verificate
- Adăugate ramuri de generare a comenzilor pentru lolMiner, GMiner, Rigel și TeamRedMiner.
- Adaptoarele folosesc argumente de proces (fără shell=True).
- Restricții explicite pe dispozitiv și mapări algoritmice conservative.
- Adăugată sursa `research/sha256d_cpu/miner_genesis_bench.c` și documentația de domeniu.
- Actualizate versiunea UI/API la 0.10.9.

## Teste
- NEXUS root suite: 194 passed.
- Crypto Fieldstation: 12 passed.
- MultiMiner X: 17 passed.
- Wallet benchmark suites: 22 passed.
- Total: 245 passed.
- `python -m compileall -q .`: passed.
- Dashboard JavaScript `node --check`: passed.
- C source compiled with GCC `-O3 -march=native -pthread -Wall -Wextra -Wpedantic`: passed.
- Genesis benchmark, 2,000,000 nonce window: all five variants found nonce 2083236893.

## Benchmark C observed in this environment
Intel Xeon Platinum 8573C, one thread, 2,000,000 nonce window:
- scalar naive: 1.33 MH/s
- midstate: 1.63 MH/s
- midstate + early exit: 1.98 MH/s
- AVX2 x8: 10.20 MH/s
- AVX-512 x16: 25.32 MH/s

These are measurements of this environment, not the user's ASUS TUF laptop. The code tests a fixed Genesis header and is not a Stratum miner.

## Important limitations / not tested
- The four new adapters were tested with fake process objects; no vendor binaries were launched.
- No accepted/rejected shares were submitted to real pools.
- Live pool connectivity could not be checked: DNS resolution is unavailable in this build environment (`Temporary failure in name resolution`).
- No GPU benchmark was run on the user's GTX 1650 Ti.
- TeamRedMiner is intended for AMD GPU families; do not select it for the user's NVIDIA GPU.
- No wallet files, keystore, seed phrases, or user runtime data were modified.
- The Stratum probe remains a subscribe/authorize diagnostic, not a complete job/submit implementation.

## Test invocation
Run root, adapters and wallet suites separately to avoid Python package-name collisions between nested projects:
```bash
PYTHONPATH=. pytest -q tests
(cd adapters/fieldstation/crypto_fieldstation && PYTHONPATH=. pytest -q tests)
(cd adapters/multiminer_x/MULTIMINER_X_v1.0 && PYTHONPATH=. pytest -q tests)
PYTHONPATH=. pytest -q modules/wallet_benchmark/tests modules/wallet_benchmark/v05/test_v05_unit.py
```
