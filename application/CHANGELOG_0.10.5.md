# NEXUS MASTER 0.10.5

## Hybrid math and bounded research
- Integrated exact native modular solving, SymPy exact rational linear systems, optional Z3 bitvector XOR and the existing optional PySAT reduced-round SHA-256 CNF backend under the hybrid solver router.
- Added regression tests for verified solutions, invalid inputs, and explicit optional-backend availability.
- Preserved holdout validation and the policy that reduced-round SHA-256 results cannot be applied to miners.

## Mining catalog and SOLO
- Maintained 24 coin records and 64 operator-documented pool endpoint records, including Bitcoin SHA-256d ASIC and NerdMiner profiles, RandomX CPU, Scrypt ASIC, GPU PoW and smaller PoW coins.
- Expanded all 7 SOLO profiles with endpoint, TLS, backups, login format, auth mode, password hint, fee, reward, share difficulty, hardware class, payout and source metadata.
- Added ViaBTC account-mode activation note for SOLO.
- Fixed TLS Stratum diagnostics to use provider-specific `ssl_host` + `ssl_port` when documented.
- Kept external solo pool, local Bitcoin Core Regtest and self-hosted node/CKPool configuration as separate modes.

## Test and benchmark
- Full audit: 225 passed, 0 failed across NEXUS Master, MultiMiner X, Crypto Fieldstation, Wallet Benchmark and Wallet v0.5.
- Dashboard JavaScript syntax and Python compile checks passed.
- Functional benchmark report: five complete hash functions; exact modular and SymPy solving; SHA-256 CNF self-check for 1/4/12/20 rounds; bounded differential search with independent holdout.
- Negative differential-search candidate not promoted because it failed to beat baseline.

## Limitations
- No physical GPU mining, live accepted pool shares, live payouts, Bitcoin Core daemon or CKPool process tested.
- Z3 and PySAT were not installed; their optional solver searches were not executed.
- F2Pool and ViaBTC account API connectors remain pending. Four read-only connectors are implemented in source, but no external user credentials were tested.
- Miner launch support remains limited to XMRig, T-Rex and SRBMiner-MULTI. Other miners remain detected/inventory-only until dedicated launch and parser tests are added.
- This ZIP is not a precompiled standalone `.exe`; Windows PyInstaller build runs on Windows.
