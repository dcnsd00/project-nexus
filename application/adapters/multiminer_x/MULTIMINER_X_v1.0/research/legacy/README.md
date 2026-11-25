# MULTIMINER X v0.2.0

Native C++17 SHA-256d proof-of-work benchmark with a Bitcoin 80-byte header path, midstate reuse, fixed-format padding, predecoded compact target, multi-threaded disjoint nonce ranges, early-exit target comparison, and independent candidate verification.

**Important limitation:** The included simulator intentionally creates a synthetic header with a regtest-style easy target (`0x207fffff`). A reported hit is valid against that synthetic target only. The `--verify-genesis` mode separately verifies the historical Bitcoin genesis header against its real mainnet target; it does not discover a new block. It is not a real mainnet block, a pool share, or evidence that the system can mine BTC profitably.

## Quick start

See [`docs/BUILD.md`](docs/BUILD.md). Then run:

```bash
./mmx_btc --self-test
./mmx_btc --simulate --threads 4 --max-nonces 1000000
./mmx_btc --verify-genesis
./mmx_btc --bench --threads 4 --iterations 1000000
python3 tests/test_reference.py
python3 src/sha2_family_benchmark.py --seconds 2
```

## Implemented optimizations

- Per-template 80-byte header buffer; nonce changes in place.
- One-time SHA-256 midstate after bytes 0..63.
- Specialized first-hash second block and second SHA-256 block.
- One-time compact-target decoding and most-significant-byte-first early-exit comparison.
- Unique, non-overlapping nonce scheduling across CPU workers.
- Independent rehash of any discovered candidate.

See [`docs/OPTIMIZATIONS.md`](docs/OPTIMIZATIONS.md), [`docs/ERROR_CHECKING.md`](docs/ERROR_CHECKING.md), and [`docs/ENERGY_AND_BENCHMARK.md`](docs/ENERGY_AND_BENCHMARK.md).

For a local Windows scaling matrix, use `scripts/benchmark_matrix.ps1`. The generic SHA-2 family comparison is `src/sha2_family_benchmark.py`; it is deliberately separate from Bitcoin SHA-256d.
