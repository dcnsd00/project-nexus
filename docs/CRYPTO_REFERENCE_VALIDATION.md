# NEXUS cryptography reference validation

## SHA-256

The application cryptographic engine delegates SHA-256 to Python's `hashlib`; it does not implement a custom SHA-256 compression function. The test suite includes known-answer vectors from NIST FIPS 180-4:

- `abc` → `ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad`
- The standard multi-block test message beginning `abcdbcdec...` → `248d6a61d20638e5b8c026930c3e6039a33ce45964ff2167f6ecedd419db06c1`

`sha256d` is a protocol composition (SHA-256 applied twice), not a separate hash function defined by FIPS 180-4. The Bitcoin header path has separate tests against the Bitcoin genesis-header calculation and the Python `hashlib` fallback. Do not conflate a primitive test with proof that a complete mining or pool-submission path is operational.

Reference: https://csrc.nist.gov/pubs/fips/180-4/upd1/final

## RandomX

The repository vendors the RandomX reference source under `application/vendor/randomx-1.2.3`. The upstream CMake project exposes the `randomx-tests` target; its `src/tests/tests.cpp` contains reference hash vectors, interpreter/compiler paths, cache/dataset checks and commitment tests.

A dedicated NEXUS GitHub Actions workflow is configured to run the upstream CMake configure/build/test sequence on Ubuntu. Its execution result will be recorded after the integration branch's CI run completes. This validates the vendored reference implementation against its included upstream test vectors. It does not, by itself, validate NEXUS's benchmark adapter, a user's CPU feature detection, a sustained mining session, pool shares or profitability.

Upstream project and design reference:
- https://github.com/tevador/RandomX
- https://github.com/tevador/RandomX/blob/master/doc/design.md

RandomX's documented memory profiles are materially different: light verification uses a 256 MiB cache; the full mining dataset is approximately 2,080 MiB. Hardware suitability and hashrate must be measured on the actual host.

## RCSC

RCSC remains experimental research. It is not a replacement for SHA-256, RandomX, a standardized hash, or a proven consensus primitive. Keep `auto_apply=false`; require reproducible inputs, baseline comparisons, effect sizes and confidence intervals, multiple-testing correction, and independent replication before making any performance or security claim.

## Upstream source provenance verification (2026-11-26)

The upstream release reference for this vendored directory is `tevador/RandomX` tag `v1.2.3`, whose release points to commit `12f2c2ffe2108d6cf54c391fee33c8bc3646cdab` (the short commit shown on the official release page is `12f2c2f`).

A complete recursive Git tree comparison was recorded between the upstream tag commit `12f2c2ffe2108d6cf54c391fee33c8bc3646cdab` and `application/vendor/randomx-1.2.3/` in NEXUS main. Both tree responses were complete (`truncated=false`).

| Comparison | Result |
|---|---:|
| Upstream blob files at `v1.2.3` | 151 |
| Vendored blob files in NEXUS | 145 |
| Vendored files with identical upstream Git blob SHA | 145 / 145 |
| Vendored files with changed content | 0 |
| Extra files in NEXUS vendor directory | 0 |
| Upstream files not copied into NEXUS vendor directory | 6 |

The six omitted upstream files are repository metadata and audit PDFs: `.gitattributes`, `.gitignore`, `audits/Report-Kudelski.pdf`, `audits/Report-Quarkslab.pdf`, `audits/Report-TrailOfBits.pdf`, and `audits/Report-X41.pdf`. No source file in the NEXUS vendor directory differs from the matching upstream file by Git blob SHA. Thus, **all 145 vendored files are content-identical to their corresponding files at the official upstream v1.2.3 commit**.

Representative blob SHA spot checks recorded during the comparison:

| File | Git blob SHA (same upstream and vendored) |
|---|---|
| `CMakeLists.txt` | `000eaef390e6bbfd46286868596cb195688bba79` |
| `src/tests/tests.cpp` | `1dd5c06e031390ea85974fd0a004f132b3c05a61` |
| `src/randomx.cpp` | `a08968e6aaf7179547f4fab9f7ee764d2f634906` |
| `src/randomx.h` | `313bcd2e0b60f7d7cfb5d937970c3b1834d04265` |
| `LICENSE` | `b1572ae82433af4b6985acc80f8fdc7c8d1768b4` |

The provenance gap identified earlier in the review is therefore resolved by this recorded tree/blob comparison; it should not be described as still open unless a later re-check contradicts these results.

References:
- Official release: https://github.com/tevador/RandomX/releases/tag/v1.2.3
- Upstream repository: https://github.com/tevador/RandomX/tree/v1.2.3
- Verified commit: https://github.com/tevador/RandomX/commit/12f2c2ffe2108d6cf54c391fee33c8bc3646cdab
