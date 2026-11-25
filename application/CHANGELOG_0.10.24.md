# NEXUS MASTER 0.10.24 — cumulative RCSC integration

- Integrated the RCSC package into the canonical NEXUS repository and API control plane.
- Added read-only Mempool.space block collection with bounded requests (1–200 blocks per run).
- Added independent 80-byte header parsing, SHA256d, compact-target decoding and Proof-of-Work validation.
- Added complete ordered TXID retrieval and independent Merkle-root reconstruction.
- Added fee extraction from transaction pages, kept separate from scheduled subsidy and coinbase underclaim.
- Added SQLite persistence for collected block records and research runs.
- Added chronological 70/30 train/holdout association screens. They are exploratory and do not establish prediction or SHA-256 weakness.
- Added API: `/api/research/rcsc/status`, `/collect`, `/analyze`, `/verify-header`, `/runs/{run_id}`.
- Added Genesis block regression tests and API smoke tests.

## Validation boundary

Local RCSC and selected NEXUS regression tests pass in the Linux build container. Live public block collection, Windows laptop execution, live pool shares, and payout remain unverified. No external wallet writes or private-key handling were added.
