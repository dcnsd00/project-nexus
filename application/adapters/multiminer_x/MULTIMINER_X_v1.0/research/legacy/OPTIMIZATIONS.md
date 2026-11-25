# Optimizations and what they do (and do not do)

## Implemented

1. **Header template prepared once.** The 80-byte layout is fixed for a given job; only the 4-byte nonce is changed in the worker-local copy. This removes repeated general-purpose serialization/allocation from the nonce loop.
2. **SHA-256 midstate.** The first 64 bytes of the header do not contain the nonce. Their compression is done once per header template and the 8-word state is reused. For Bitcoin headers, the nonce is in bytes 76..79; the second SHA-256 block contains header bytes 64..79 plus padding.
3. **Specialized fixed-length SHA-256d path.** The remaining first-hash block has 80-byte message padding (640-bit length); the second hash is a one-block 32-byte message (256-bit length). No generic padding routine is run for every nonce.
4. **Predecoded target.** Compact `nBits` is decoded once outside the nonce loop into a 256-bit little-endian target representation.
5. **Early-exit target comparison.** Compare most-significant bytes first and stop on the first difference. This saves comparison instructions on average, not SHA rounds: the complete digest must be computed before this test.
6. **Disjoint nonce scheduling.** Worker `t` tests indices `t, t+threads, t+2*threads...`, so workers do not overlap within a job. This is CPU thread parallelism, not an escape from the total work required.
7. **Independent hit recheck.** Any found candidate is recomputed through a separate generic SHA-256 implementation in the program before it is reported. The Python test harness independently checks 250 random 80-byte headers with `hashlib`.

## Not implemented / not mathematically justified

- Removing SHA-256 rounds, `Ch`, `Maj`, sigma functions, or state words while claiming standard SHA-256.
- Guessing/deducing the final digest from a partial internal state.
- Treating SHA-512 or SHA-512/256 as a substitute for SHA-256d.
- Rejecting a nonce using a partial hash before the full digest exists.
- Predicting random hardware faults and correcting them by algebraic deduction. The practical method here is known-answer tests, periodic self-tests, and independent candidate verification.

## Header-space expansion

When a real pool/job protocol permits changes, the search space can be renewed by rolling nonce, permitted version bits, `nTime` within consensus/pool policy, and extranonce/coinbase data (which changes the Merkle root). These are new valid job templates, not reuse of a previous PoW answer. The server must allocate non-overlapping work to devices. Stratum V2 explicitly calls for unique subsets of the search space and permits `nTime` rolling under its constraints.

## Quantum error correction

Quantum error correction overhead concerns fault-tolerant quantum computation. It does not apply to the current classical CPU/phone/ESP32 SHA-256 implementation. Classical reliability is handled with error detection and independent verification. No quantum error-correction subsystem is simulated by this project.

8. **Predecoded second-block template.** The three SHA-256 message words covering header bytes 64..75 (Merkle tail, time and `nBits`) are prepared once. Each nonce iteration only supplies the nonce word. This further reduces per-candidate byte parsing and header mutation.
9. **Compare final state words directly.** On unsuccessful candidates, compare the final eight 32-bit state words to the decoded target without first writing a 32-byte digest buffer. On a hit, serialize the digest and independently rehash the complete 80-byte header. All 64+64 SHA rounds remain intact.

## SHA-512/256 stays a separate benchmark

`src/sha2_family_benchmark.py` retains a serial comparison of SHA-256, SHA-512 and SHA-512/256 for generic input lengths. It validates the standard `abc` known-answer digest for each function before timing. These measurements must not be mixed with Bitcoin SHA-256d H/s: SHA-512 and SHA-512/256 outputs are not valid substitutes for the Bitcoin proof-of-work function.
