# Changelog

## 0.3.0
- Added local BIP39 wordlist loader (requires 2048 unique words).
- Added BIP39 word-count, word-membership, entropy and checksum validation.
- Added entropy-to-mnemonic helper for unit tests.
- Added hidden terminal prompts for authorized local mnemonic entry.
- Added public-address inventory for five supported formats.
- Added local ECDSA challenge proof; private key, seed and mnemonic are not exported.
- Added three recovery-lab unit tests.
- Explicitly excludes missing-word guessing, brute force, third-party wallet access and transaction broadcast.

## 0.4.0 — Local Chain Lifecycle Benchmark
- Added BTC-style UTXO and five EVM-style account-ledger simulations.
- Added secp256k1 signed transfer envelopes, signature verification, nonce/fee checks, hash-linked blocks, and chain-integrity checks.
- Simulated 31 source-to-receiver and 9 receiver-to-external transfers (40 total).
- Added test-key buffer overwrite/retirement and explicit immutable-history semantics.
- No public RPC, network I/O, canonical wire transaction, or real funds movement.

## 0.5.0 — Real local-node integration harness
- Added a disposable Docker Compose environment with Bitcoin Core Regtest and five isolated Anvil nodes.
- Added Bitcoin transaction scenarios for Legacy P2PKH, Nested SegWit, Native SegWit and Taproot (Bech32m): regtest mining, funding, source-to-receiver spend, receiver-to-external-test spend, confirmations, final balances and UTXO checks.
- Added EVM transaction scenarios on five local Anvil nodes using chain IDs 31337, 8453, 56, 137 and 42161; no forks or public RPC endpoints.
- Added loopback-only RPC client, Bitcoin regtest-chain check, Anvil client identity and chain-ID checks, receipt/signature-field checks, Windows and Unix run/cleanup scripts.
- Added v0.5 offline safety/configuration tests. Full local-node transactions require Docker Compose and must be executed on the user's machine; they were not run in this workspace because the node/container binaries are unavailable.
- Public-chain history is immutable; balances can be swept to zero and local test-node state can be discarded by removing the disposable containers.
