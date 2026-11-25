# NEXUS MASTER 0.10.17 — wallet search and recovery integration

## Recovered prior design
The user's previous NEXUS recovery implementation (0.6.3) was found in the Library. Its architecture was restored: identify format -> invoke format-specific processor -> decrypt/validate -> verify address or checksum -> return a status without exporting key material. The earlier design specified hidden local CLI prompts and explicit owner authorization.

## Implemented and integrated
- Local wallet-file search under a user-selected directory; bounded recursion/file count, symlink exclusion, metadata-only results.
- Format catalog and local detection API.
- Ethereum Web3 Secret Storage V3 decrypt for scrypt and PBKDF2-HMAC-SHA256, AES-128-CTR, Keccak MAC and address validation. Successful keys are re-encrypted directly into the NEXUS AES-GCM vault; raw key is not returned.
- Bitcoin BIP38 non-EC 0x0142 decrypt, NFC passphrase normalization and address-hash validation. Raw key/WIF is not returned or persisted.
- BIP39 checksum and one-missing-word recovery against one owner-supplied public address and explicit derivation path.
- Bitcoin Core local loopback RPC passphrase verification with one-second unlock and immediate walletlock.
- Solana 64-byte Ed25519 keypair consistency validation.
- Wallet UI, recovery API and hidden-prompt CLI.

## Security and boundaries
- Recovery API rejects non-loopback clients and requires explicit owner authorization.
- Passwords are runtime inputs only; not stored, logged or included in output.
- No password dictionary, brute-force, arbitrary public-address scan, key export or public-chain broadcast.
- Local file search inspects metadata and limited JSON structure only; it does not attempt decryption.

## Known inactive/limited formats
- BIP38 EC-multiplied 0x0143: inactive.
- EIP-2335 BLS keystore: inactive.
- Electrum, MetaMask raw browser vault and Monero: format hints/catalogued; vendor-native recovery remains required.
- Bitcoin Core passphrase adapter is integrated but requires a running local Bitcoin Core daemon and encrypted wallet to validate live.
- BIP39 requires `python-mnemonic`; dependency declared but unavailable in this build runtime, so BIP39 runtime tests were not run here.
- No real wallet from the user's vault was decrypted because no password was entered in this build environment.
- No transaction was signed or broadcast.

## Validation
See the final full audit output for exact test totals. New recovery integration tests cover format catalog, Web3 V3 fixture decryption/import, wrong-password rejection, owner authorization, local wallet file discovery and endpoint behavior.

## Final offline test results

| Suite | PASS | FAIL |
|---|---:|---:|
| NEXUS root (includes new wallet recovery integration tests) | 240 | 0 |
| MultiMiner X | 17 | 0 |
| Crypto Fieldstation | 12 | 0 |
| Wallet Benchmark | 15 | 0 |
| Wallet v0.5 | 7 | 0 |
| **Total** | **291** | **0** |

Additional checks: Python compileall passed; both inline JavaScript blocks passed Node syntax validation; packaged vault SQLite integrity is `ok`, with 32/32 valid encrypted envelopes and 16 watch-only addresses. The vault audit did not decrypt or modify original vault data.

## Runtime checks not performed

- BIP39 official wordlist runtime flow: `mnemonic` is declared in root and wallet requirements, but was not installed in this build environment.
- Bitcoin Core RPC: adapter is loopback-restricted; no local `bitcoind` daemon/wallet was running for live passphrase verification.
- GPU, public mining pool, public blockchain transactions and provider API writes: not executed.
- SAT external backend and Z3 remain optional dependencies and were not installed for this run.
