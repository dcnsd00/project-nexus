# NEXUS 0.4.0 — Local Chain Lifecycle Benchmark

This milestone adds an **isolated local signed-ledger lifecycle test**. It simulates a BTC-style UTXO ledger and five EVM-style account ledgers (ETH, Base, BNB, Polygon, Arbitrum), with synthetic balances only.

## Run

```bash
python -m pip install -r requirements.txt
python nexus_local_chain_benchmark.py
pytest -q tests/test_local_chain_v04.py
```

## What it does

- Creates synthetic source, receiver, and external wallets.
- Signs each local transfer envelope using secp256k1 ECDSA.
- Verifies signatures before state changes.
- Applies BTC-style UTXO spends or EVM-style nonce/balance updates.
- Commits each transaction into a hash-linked local block.
- Consolidates source balances into receivers, then sends receiver balances to external test addresses.
- Overwrites source/receiver private-key buffers and marks those wallets retired.
- Exports chain blocks, receipts, and a report.

## Critical limits

This is a **local ledger simulation**, not a full EVM client, Bitcoin Core regtest, consensus implementation, or public blockchain. Its signed envelopes are not canonical Ethereum or Bitcoin wire transactions. No RPC, internet, faucet, external wallet, or public-chain broadcast is used; no real funds move.

A wallet cannot be deleted from blockchain history. Keys/software can be retired and a balance can be moved to zero, but addresses and confirmed transactions remain in the immutable ledger. The benchmark models this accurately: key material is retired; history is retained.

All keys and balances are deterministic, disposable test fixtures. Never use them for real funds.
