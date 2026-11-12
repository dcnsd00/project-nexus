# NEXUS 0.10.25 import gate — security scan update (2026-11-12)

The source bundle hash and inventory were rechecked:
- SHA-256: f4774e21854387f38152ae969a84b07d8dc2fec2ef21d120923bf82738ca1f7f
- ZIP contains 514 entries: 513 files plus directory entry.
- Uncompressed payload: 3,000,600 bytes.

A second scan identified 6 fixed password assignments in 4 source/test files:
- tests/test_keystore_recovery_20.py (1)
- tests/test_wallet_recovery_integration_016.py (3)
- modules/blockchain_regtest/nexus_v05_integration.py (1)
- modules/wallet_benchmark/v05/nexus_v05_integration.py (1)

Values are intentionally redacted in this report. They may be test-only values, but must be inspected and replaced with explicit non-secret fixtures/environment variables before a public import. The first scan did not find PEM private-key blocks, GitHub token patterns, or AWS access-key patterns. This is a heuristic scan, not a guarantee that the bundle contains no secrets.

No source files have been imported into GitHub yet. Import remains blocked pending a safe upload route and secret review.
