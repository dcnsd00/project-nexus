# NEXUS MASTER 0.10.5 — Audit and Functional Benchmark

**Date:** 2026-11-09  
**Build:** incremental extension of 0.10.2 / 0.10.4 work; source preserved  
**Scope:** hybrid solver, coin/pool catalog, pool account connectors, Stratum diagnostics, SOLO profiles, dashboard and existing suites.

## 1. Automated test suites

| Suite | Passed | Failed |
|---|---:|---:|
| NEXUS Master | 174 | 0 |
| MultiMiner X | 17 | 0 |
| Crypto Fieldstation | 12 | 0 |
| Wallet Benchmark | 15 | 0 |
| Wallet v0.5 | 7 | 0 |
| **Total** | **225** | **0** |

Additional checks:
- `python -m compileall -q .`: PASS.
- Dashboard JavaScript syntax (`node --check`): PASS.
- ZIP CRC / archive integrity: validated during packaging.
- The optional long native SHA-256d benchmark was skipped by `run_full_audit.sh` by default to keep the audit resource-bounded.

## 2. Functional mathematics benchmarks

### Full standard digest avalanche

Each algorithm used 256 deterministic single-bit mutation probes on 64-byte messages, seed `20261109`.

| Algorithm | Mean changed digest bits | Ideal reference | z-score | Within 3 SE |
|---|---:|---:|---:|---|
| SHA-256 | 128.1055 | 128 | 0.211 | Yes |
| SHA-512 | 255.8477 | 256 | -0.215 | Yes |
| SHA3-256 | 128.0664 | 128 | 0.133 | Yes |
| SHA3-512 | 255.3477 | 256 | -0.923 | Yes |
| BLAKE2b-256 | 127.6250 | 128 | -0.750 | Yes |

These are statistical diagnostics over complete standard digests; they are not cryptographic security proofs or PoW hashrate benchmarks.

### Hybrid solver

- Native modular congruence: `14*x ≡ 30 (mod 100)` → representative solution `x=45`, solution count `2`, exact substitution check passed.
- SymPy exact rational linear system `[[2,1],[1,-1]] * x = [5,1]` → `(2,1)`, exact substitution check passed.
- Z3 bitvector XOR and PySAT reduced-round solve: optional backends detected as unavailable in this build environment; no SAT/SMT search is claimed.

### SHA-256 reduced-round SAT encoding

Self-check compares the CNF unit-propagation output against the reference reduced-round compressor:

| Rounds | Variables | Clauses | Encoding matches reference |
|---:|---:|---:|---|
| 1 | 2,130 | 7,463 | Yes |
| 4 | 4,701 | 19,241 | Yes |
| 12 | 11,557 | 50,649 | Yes |
| 20 | 20,065 | 89,409 | Yes |

This validates encoding consistency, not a SAT solver's ability to find a collision. Reduced-round SHA-256 results are research-only and not connected to consensus mining.

### Differential search

A resource-bounded 20-round search used 20 steps, 8 training blocks, one restart, 32 independent holdout blocks and 6,400 work units. The candidate did **not** beat the independent random single-bit baseline, so it was not promoted. This negative result is retained rather than labelled as an optimization.

## 3. Mining catalog and SOLO profiles

Structural catalog audit:
- 24 coin records; 22 marked PoW-mineable and two explicitly non-PoW (ETH and SOL).
- 64 curated pool endpoint records.
- 7 SOLO profiles: Public Pool BTC, NerdMiner low-difficulty Public Pool endpoint, ViaBTC account-mode selectable SOLO, Braiins Solo BTC, CKPool BTC, 2Miners RVN SOLO, Kryptex PRL SOLO.
- No duplicate pool IDs, missing required endpoint/source fields or missing SOLO worker formats.

The SOLO response now exposes primary endpoint, TLS availability, backup hosts/ports, account/wallet format, authentication type, default password hint, device class, fee/payout notes, share-difficulty settings where published, minimum payout metadata where published, and source. ViaBTC explicitly requires SOLO to be enabled in its account/dashboard before using its Stratum endpoint.

Three execution modes remain distinct:
- `SOLO_POOL`: documented external solo pool endpoint.
- `LOCAL_REGTEST`: Bitcoin Core RPC CPU SHA-256d on local Regtest; only test network accepted.
- `LOCAL_NODE_STRATUM_PROXY`: CKPool configuration profile for a self-hosted node; config only, CKPool is not installed or started by NEXUS.

A catalog entry or a generated profile does not mean a real pool was reachable or that a share/block was accepted.

## 4. Pool connectors and Stratum tests

Implemented read-only connector paths:
- 2Miners public wallet account API.
- unMineable signed GET API using HMAC-SHA256; credentials are request-scoped and not persisted.
- Kryptex public GET balance/payout/worker endpoints.
- Braiins read-only account/profile/worker endpoints using a request-scoped token.

F2Pool is catalogued but its account connector remains pending exact read-only route/schema validation. ViaBTC account monitoring remains pending; the official account dashboard is not misrepresented as a connected API.

Stratum subscribe/authorize uses a bounded local integration test server. The probe does not request a mining job (`mining.notify`), submit a share, or prove a live pool payout. TLS probes use a catalogued provider-specific TLS host/port when published.

## 5. Mining adapters and hardware limits

The release preserves the current adapter inventory. Actual managed launch support remains limited to adapters with `launch=true` in `mining/controller.py` (XMRig, T-Rex and SRBMiner-MULTI). lolMiner, GMiner, Rigel and TeamRedMiner remain inventory/compatibility entries with launch disabled; they are not claimed as working controllers. ASIC and NerdMiner profiles generate external device configurations only.

No physical GTX 1650 Ti benchmark, accepted pool share, external account payout, Bitcoin Core daemon lifecycle or CKPool process was executed in this build environment. User-reported hardware state is not substituted for this build's benchmark.

## 6. Credentials, private data and distribution

- No wallet seed phrase, private key, wallet database, API token or password is included in the distribution archive.
- Pool account API tokens are request-scoped; connectors are GET/read-only only.
- Public-chain writes are not enabled by the master API. The separate user-managed Bitcoin Core/CKPool profile documents that a manually configured mainnet node could submit a valid block if found.
- The ZIP is a source + Python desktop installer package. It is not a precompiled standalone Windows `.exe`; PyInstaller build must be executed on Windows.

## 7. Artifacts

- `BENCHMARK_REPORT_0.10.5_FUNCTIONAL.json` contains reproducible functional benchmark details.
- `CHANGELOG_0.10.5.md` lists incremental changes.
- `VERSION.json` describes the release and optional backend status.
