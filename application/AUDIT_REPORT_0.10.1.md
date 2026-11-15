# NEXUS MASTER 0.10.1 — audit SHA-256 Advanced Research

**Base:** NEXUS MASTER 0.10.0 from the other conversation thread  
**Build:** incremental; original 0.10.0 preserved  
**Date:** 2026-11-09

## 1. Added and integrated

- `modules/sha256_research/advanced.py`: bounded multi-bit differential search, round-by-round state-difference tracking, Tseitin CNF encoder, SAT self-check, optional SAT solve and DIMACS export.
- Uploaded `sha256_1_09.11.2026.py` and `sha256_2_09.11.2026.py` were used as method references and integrated against NEXUS's existing `sha256_core.py`; no parallel SHA-256 reference implementation was introduced.
- Dashboard controls connect the search → track → SAT workflow. A candidate found by search is placed into the delta field for subsequent tracking/solver/DIMACS operations.
- Dashboard sections now use internal scrolling; the top section header and navigation remain fixed while section content scrolls independently.
- Optional SAT dependency installation scripts added for Windows and Linux: `INSTALL_RESEARCH_SOLVER.ps1` and `INSTALL_RESEARCH_SOLVER.sh`.

## 2. Corrections applied to supplied scripts

### Differential search

- Candidates are evaluated on the same training blocks (`common random numbers`), reducing comparison noise from changing samples.
- The best candidate is measured on a separate holdout set with a derived independent seed.
- Default search is constrained to W14/W15, and the objective excludes rounds before the earliest active input word is consumed. This prevents a candidate from appearing better only because its input difference is introduced later and therefore has fewer rounds in which to diffuse.
- The empirical frequency of the most common full-state difference is labelled as a sample frequency, not as a differential-path probability. Per-round frequencies are not multiplied.
- Search is bounded by explicit steps, sample count, restart count and a maximum work-unit budget.

### SAT/CNF

- The supplied source stored bit vectors LSB-first but constrained the first `bits` literals as the digest prefix, while its independent verification checked the big-endian prefix. This was inconsistent for partial prefixes.
- NEXUS now builds the constrained output prefix MSB-first, matching SHA-256 digest serialization and independent verification.
- CNF self-check assigns a complete input block, propagates the Tseitin circuit and compares all eight output words against the NEXUS reference compressor.
- SAT solver calls have a 1–30 second timeout and formula-size limits. DIMACS export is available without installing a solver.

## 3. Tests and execution actually completed

| Suite | Passed | Failed |
|---|---:|---:|
| NEXUS Master, including advanced SHA tests | 137 | 0 |
| MultiMiner X | 17 | 0 |
| Crypto Fieldstation | 12 | 0 |
| Wallet Benchmark | 15 | 0 |
| Wallet v0.5 | 7 | 0 |
| **Total** | **188** | **0** |

Additional checks:

- Python `compileall`: PASS.
- Dashboard JavaScript `node --check`: PASS.
- SAT self-check at 1, 4, 12 and 20 reduced rounds: PASS; output words matched the reference compressor exactly.
- SAT self-check at 20 rounds: 20,065 variables and 89,409 clauses.
- DIMACS export at 12 rounds / 256 output-prefix bits: 23,625 variables, 103,858 clauses, 2,022,947 bytes; DIMACS header and file contents were checked.
- Differential search run: 20 rounds, 60 steps/restart, 16 training samples, 2 restarts, 256 independent validation samples, 76,800 work units, about 0.50 seconds in the build environment.
- The best search candidate did **not** improve the independent holdout versus a single-bit baseline at the same earliest input word. The candidate was not promoted as a useful differential improvement.
- W15 / `0x80000000` tracking: 1,024 paired blocks. State difference remained zero through the state after round 15; mean internal-state Hamming difference at round 20 was 110.36 bits. The most common full-state difference occurred once (1/1,024); this is descriptive only.

## 4. Dependencies and checks not run

- `python-sat` is not installed in the development environment and the environment had no network access; consequently, the SAT **solve** operation was not executed. The CNF encoding, self-check, API behaviour, and DIMACS export were tested. Install the optional dependency with `INSTALL_RESEARCH_SOLVER.ps1` (Windows) or `INSTALL_RESEARCH_SOLVER.sh` (Linux) to enable solving.
- The legacy native C++ SHA-256d benchmark is now optional because the default full-audit run exceeded the available execution window at that stage. Set `NEXUS_RUN_NATIVE_BENCHMARK=1` before `bash run_full_audit.sh` to run it separately.
- No live GPU mining, pool connection, accepted share, payout, NerdMiner session, Bitcoin Core daemon, Anvil instance or public-chain transaction was run by this audit.
- No Windows `.exe` was compiled or tested in this Linux build environment.
- The release ZIP excludes local SQLite databases (`data/nexus_wallets.db` and `data/nexus_intelligence.db`) so personal wallet-vault and runtime records are not distributed. Keep/backup the databases from an existing installation separately.

## 5. Cryptographic scope

The differential search and SAT encoding operate on **reduced-round SHA-256 compression** with a fixed SHA-256 IV. They do not establish a collision in standard 64-round SHA-256, do not reveal a full-SHA preimage, do not reduce Bitcoin mining difficulty, and do not produce pool-compatible shares. Findings remain local research records and are not connected to the mining controller. Any proposed mining optimization must preserve exact 64-round consensus output and be validated by independent tests and accepted pool shares.
