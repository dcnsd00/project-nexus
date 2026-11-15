# NEXUS MASTER 0.10.17

- Restored the original wallet recovery architecture from the user's prior NEXUS discussions and project artifacts (0.6.3 recovery implementation).
- Integrated local wallet-file search with bounded traversal, symlink exclusion, candidate format detection and metadata-only output.
- Integrated Ethereum Web3 V3 decrypt (scrypt/PBKDF2, AES-128-CTR, Keccak MAC) and immediate re-encryption into NEXUS's AES-GCM local vault.
- Integrated BIP38 non-EC 0x0142 decrypt and address checksum verification without exporting or persisting the Bitcoin private key.
- Integrated BIP39 checksum validation and one-missing-word candidate recovery using an explicitly supplied owner address and derivation path.
- Integrated Solana 64-byte Ed25519 keypair validation and Bitcoin Core loopback-only passphrase verification with immediate walletlock.
- Added recovery APIs, Wallet Manager UI and hidden-prompt CLI.
- Added `mnemonic>=0.21` as a declared optional runtime dependency for official BIP39 wordlists.
- Explicitly catalogues unsupported native formats rather than marking them active.
