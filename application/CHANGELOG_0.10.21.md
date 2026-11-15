# NEXUS MASTER 0.10.21

## Native SHA-256d and Stratum
- Added the supplied Bitcoin C scanner as `mining/native/miner.c` and exposed a C ABI for caller-provided 80-byte headers, big-endian share targets, nonce ranges, variants and thread counts.
- Fixed exact nonce partitioning across worker threads; all remainders are assigned and processed.
- Added AVX2/AVX-512 tail handling for incomplete SIMD batches.
- Added CPU feature checks before SIMD dispatch and safe fallback when thread creation fails.
- Added generic share-target comparison. Early-exit filtering is only used when the target's most-significant 32 bits are zero; easier pool targets fall back to full digest comparison to avoid missing valid shares.
- Removed unaligned word loads/stores from SHA-256 byte handling and made nonce serialization explicitly little-endian.
- Added runtime native library loading/compilation with portable CPU dispatch and exact Python fallback.
- NEXUS internal Stratum worker now requests the native backend with a 50,000 nonce chunk; protocol, TLS verification and share submission remain in the existing Python worker.
- Added read-only `/api/mining/native-engine` status endpoint and Windows MSYS2/GCC build instructions.

## Coin catalogue resilience
- CoinPaprika cache now uses atomic writes and schema metadata.
- Failed refreshes serve the last valid stale cache without overwriting it.
- If no CoinPaprika cache exists, NEXUS returns its bundled mining catalogue and labels it explicitly as a local fallback, not as fresh CoinPaprika data.
- API returns freshness, fallback, cache age and upstream error metadata.

## Wallet, blockchain and desktop readiness
- Wallet database schema is initialized during application startup, including the Bitcoin vault table; encrypted records are not decrypted or rewritten.
- Desktop launcher remains loopback-only and selects a free port if 8765 is occupied by another process.
- PyInstaller bundle now includes the independent `research/` package but does not bundle local `data/` databases or wallet material.
- Added local-node readiness and cleanup scripts for the Bitcoin Core Regtest + Anvil benchmark stack.

## Verification scope
- Added regression tests for Genesis nonce across native variants and uneven thread partitioning, exact range exhaustion, easy Stratum targets, malformed compact-target header bytes, CoinPaprika stale/bundled fallback, wallet schema migration and desktop port selection.
- Public pool authorization, real share acceptance/payout, Windows PE build, and Bitcoin Core/Anvil transaction execution remain separate runtime checks; no public share or transaction was submitted during this build.
