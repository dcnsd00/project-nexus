# NEXUS MASTER 0.7.0

- Added modular cryptographic hash engine.
- Added SHA-2, SHA-3, SHAKE, BLAKE2, SHA-256d and HMAC-SHA256 support.
- Added explicitly experimental, domain-separated SHA-256/BLAKE2b composite.
- Added API endpoints for algorithm discovery, digest calculation and microbenchmarking.
- Added known-answer, input-boundary, API and benchmark tests.
- Preserved wallet, local-chain, mining adapter and Fieldstation code from 0.6.2.
- Public-chain writes remain disabled; no external mining process is auto-started.
