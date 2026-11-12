# NEXUS source import security scan — corrected revision (2026-11-12)

The earlier bundle contained fixed passphrase literals in wallet tests and a fixed local Bitcoin Core regtest RPC password. These were reviewed and removed from the corrected bundle.

Remediation in local source:
- `tests/test_keystore_recovery_20.py`: test passphrase generated with `secrets.token_urlsafe(32)`.
- `tests/test_wallet_recovery_integration_016.py`: test passphrases generated at runtime; the vault unlock test reuses the same generated value within its test.
- `modules/blockchain_regtest/nexus_v05_integration.py` and `modules/wallet_benchmark/v05/nexus_v05_integration.py`: RPC password is read from `NEXUS_REGTEST_RPC_PASSWORD`; execution fails explicitly if it is not configured.

Validation on corrected local source:
- `python -m compileall -q .`: PASS.
- `python -m pytest -q tests/rcsc tests/test_keystore_recovery_20.py tests/test_wallet_recovery_integration_016.py --disable-warnings --maxfail=1`: **69 passed in 9.00s**.
- The focused wallet tests alone: 36 passed in 9.77s.

Corrected archive:
- 513 source/configuration/documentation/test files plus manifest (514 ZIP file entries).
- SHA-256: `fafd5dd81fc0911cbb3e0c54aaa2dd6ef021010e60da31871eaa2f789a9ec55e`.
- Library path: `/NEXUS/NEXUS_MASTER_0.10.25_SOURCE_IMPORT_BUNDLE(1).zip`.
- Import helper and Android guide now pin this hash and filename.

Limitations:
- This is a heuristic source review, not a formal secret-scanning guarantee.
- The corrected archive is prepared but still has not been imported into GitHub.
- 69 passing targeted tests are not the full suite and do not establish live runtime, wallet custody, hardware mining, or predictive mining performance.
