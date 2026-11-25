# NEXUS 0.5.0 — Real local-node integration benchmark

This milestone moves from the v0.4 in-process ledger simulator to actual local
node software:

- Bitcoin Core **regtest** on RPC `127.0.0.1:18443`.
- Five isolated Foundry **Anvil** nodes for EVM transaction execution:
  - ETH chain ID 31337 (local development chain, not Ethereum mainnet)
  - Base chain ID 8453 (local Anvil instance, not Base mainnet)
  - BNB chain ID 56 (local Anvil instance, not BNB Smart Chain)
  - Polygon chain ID 137 (local Anvil instance, not Polygon PoS)
  - Arbitrum chain ID 42161 (local Anvil instance, not Arbitrum One)

No forks, public RPC endpoints, external peers, mainnet keys, user-provided seed
phrases, or imported private keys are supported by this harness. The EVM nodes
are isolated Anvil executions with the corresponding chain IDs; they do not
reproduce the different sequencer/bridge/fee mechanics of each production L2.

## Requirements

- Docker Desktop / Docker Engine with Compose v2
- Python 3.10+
- Internet access only to pull the pinned development images the first time

## Run on Windows

Open PowerShell in this folder and run:

```powershell
.\Run-LocalBenchmark.ps1
```

## Run on Linux/macOS

```bash
./run-linux-macos.sh
```

The script recreates the disposable containers and then executes
`nexus_v05_integration.py`. The report is written to `../results/`.

## Local lifecycle covered

### Bitcoin Regtest

- Creates 13 temporary Bitcoin Core descriptor wallets (one miner plus source,
  receiver and external-test wallet for each of four address types).
- Mines 101 blocks to mature regtest coinbase funds.
- Tests Legacy P2PKH, Nested SegWit P2SH-P2WPKH, Native SegWit P2WPKH and Taproot
  Bech32m addresses.
- Funds each source wallet from the regtest miner, sweeps source to receiver,
  then receiver to a third local test wallet.
- Confirms each transaction by mining a block and checks the final source and
  receiver balances and UTXO sets.
- Unloads source and receiver wallets after verification.

### EVM / Anvil

- Starts five independent Anvil nodes, without `--fork-url`.
- Uses the published Anvil development mnemonic only; it is public and unsafe
  for any real funds.
- Sets test balances, sends from source to receiver, then receiver to an
  external-test account, and verifies receipts, node-produced signature fields,
  chain ID, block hashes and final balances.

## Safety / deletion semantics

- All RPC endpoints are restricted by the harness to `127.0.0.1` / `localhost`.
- Docker ports are published on host loopback only.
- The Docker network is marked `internal: true`.
- The BTC node must report `chain=regtest`; EVM clients must identify as Anvil
  and return the expected local chain ID.
- No real coins or public-network transactions are used.
- Source and receiver balances are swept to zero, but their local chain history
  remains while the nodes are running.
- A wallet is key material/software, not an on-chain object. Its address and
  confirmed transaction history cannot be erased from a blockchain.
- Anvil is in-memory. Bitcoin Core data lives in the disposable container layer.
  To remove the lab after reviewing the report, run `Cleanup.ps1` or
  `./cleanup-linux-macos.sh`. Container removal discards this lab's local chain
  state; it does not erase public blockchain records.
- Unloading a Bitcoin wallet is not secure cryptographic erasure. The wallet
  files persist inside the temporary container until that container is removed.
  No secure-erasure claim is made for SSDs, Docker layers, or host memory.

## Expected artifacts

- `../results/node_integration_v0.5.json`
- `../results/NODE_INTEGRATION_REPORT_v0.5.md`

A report with `status=PASS` is created only after live RPC checks and confirmed
local-node transactions succeed. Unit tests of the RPC safety guards are
separate from the full node integration test.
