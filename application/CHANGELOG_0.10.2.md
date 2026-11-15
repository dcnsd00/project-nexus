# NEXUS MASTER 0.10.2

## Hash Avalanche Research
- Added a bounded full-standard digest avalanche diagnostic for SHA-256, SHA-512, SHA3-256, SHA3-512 and BLAKE2b-256.
- Uses one-bit input perturbations, deterministic seeds, full digest Hamming distance, ideal-random reference mean and a descriptive z-score.
- Added API endpoints `/api/math-intelligence/avalanche/catalog` and `/api/math-intelligence/avalanche/run`.
- Added controls and a result panel to Math Intelligence in the dashboard.
- Clearly separates standard full-digest statistical diagnostics from reduced-round cryptanalysis and from PoW hashrate.
- Limits: 16–4096 samples and 1–4096 input bytes. Results do not prove cryptographic security.

## Preservation
- All existing 0.10.1 modules, mining adapters, pool catalogue, earnings ledger, wallet modules and SHA-256 reduced-round research retained.
- No wallet database or private key material added to the release.
