# NEXUS MASTER 0.10.21 — Build remediation report

## Scope
Remediation based on the 0.10.20 module audit. Original 0.10.20 archive is preserved. Work is isolated in the 0.10.21 source tree.

## Completed in source
1. Native miner: exact thread partitioning, SIMD tail processing, runtime AVX checks, generic target handling, safer byte serialization and C ABI for Stratum job scanning.
2. Stratum: existing Python protocol lifecycle retained; controller requests native scanning and falls back to exact Python reference if native compilation/loading is unavailable.
3. CoinPaprika: atomic cache, stale-if-error behavior, bundled NEXUS mining-catalogue fallback, explicit stale/fallback metadata.
4. Wallet: startup schema migration creates EVM/watch/Bitcoin vault tables without decrypting or rewriting encrypted records.
5. Desktop: loopback-only dynamic port selection; PyInstaller spec includes the independent research package and excludes user `data/` databases.
6. Local blockchain: added endpoint readiness and cleanup scripts; compose configuration parses as valid YAML.

## Full offline test totals
- NEXUS root: 273 passed.
- MultiMiner X: 17 passed.
- Crypto Fieldstation: 12 passed.
- Wallet Benchmark: 15 passed.
- Wallet Benchmark v0.5: 7 passed.
- SHA-2 independent package: 13 executed, 12 passed, 1 skipped because `python-sat` is absent.
- Python compileall and both dashboard JavaScript blocks: passed.
- Docker Compose YAML parsed with six services and an isolated network.

## Native scanner tests
- All CPU-supported native variants found the real Bitcoin Genesis nonce 2083236893 in the 1,000,032 nonce range with four worker threads.
- Non-multiple range test (1,003 hashes, seven threads) returned exactly 1,003 checked hashes and no false share at target=1.
- Easy share target with nonzero top target byte was checked without early-exit false negatives.
- Candidate digest is independently recomputed using Python `hashlib` before the Stratum worker submits it.
- Local mock Stratum test covers subscribe, authorize, notify, native scan, submit and accept/reject handling.
- Native code compiled with generic `-O3 -pthread` flags; AVX2/AVX-512 dispatch uses function target attributes and runtime CPU detection. It does not require `-march=native`.
- Portable GCC benchmark over 20,000,000 Genesis-header nonces: scalar 1.38 MH/s, midstate 2.16 MH/s, midstate+early 2.27 MH/s, AVX2 13.88 MH/s, AVX-512 24.23 MH/s. AVX-512 measured 17.54x versus scalar in this run.
- AVX-512 thread scaling in the same build environment: 1 thread 24.50 MH/s, 2 threads 39.54 MH/s, 4 threads 68.69 MH/s, 8 threads 76.81 MH/s. These are container measurements, not the user's laptop.

## Not yet externally validated
- Windows DLL build and Edge WebView2 desktop runtime must be tested on the user's Windows laptop. The Windows build script and MSYS2 instructions are included; this Linux environment cannot validate a Windows PE DLL.
- Docker/Bitcoin Core/Anvil were unavailable in the build environment; local-chain transfers were not executed. Compose syntax was validated and Windows readiness/cleanup scripts were added.
- No public pool connection, authorization, share acceptance or payout was performed.
- External provider integrations remain unconfigured and are not made live by this release.

## Safety
No private wallet was decrypted, no public blockchain write was made, and no public mining share was submitted. Test DBs use temporary paths. The existing wallet DB is only schema-initialized at app startup; encrypted records are retained.
