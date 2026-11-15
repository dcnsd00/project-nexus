# NEXUS MASTER 0.9.5

## Math Intelligence extension (additive; preserves NEXUS 0.9.4 modules)
- Added exact local throughput benchmarks for SHA-256, SHA-512, SHA-3, BLAKE2 and SHA-256d using the existing CryptoEngine.
- Added a bounded linear modular-congruence solver with exact solution verification.
- Added candidate triage for measured mining optimizations. A candidate requires exact-equivalence evidence, at least 3 independent runs, >=180 seconds, accepted shares and <=1% rejected shares before manual review. No auto-application.
- Added Research Hub dashboard controls and plain-language outputs.
- Added local/private research catalog endpoint.
- Added regression tests for benchmarks, modular solver and candidate triage.

## Boundaries
- Hash throughput benchmarks are not PoW hashrate.
- SHA reduced-round experiments remain research-only and are not fed into live mining.
- No private-key, wallet, password or third-party account brute-force.
- Pool account data remains read-only; blockchain writes remain disabled by default.
- GPU mining and external daemon behavior still require validation on the user's Windows machine.
