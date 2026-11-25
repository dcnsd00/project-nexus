# NEXUS MASTER 0.9.7 — Solo mining adapter benchmark

## Implemented
- Bitcoin Core JSON-RPC adapter for local **regtest**.
- `getblockchaininfo` network guard; refuses mainnet/testnet/signet.
- `getblocktemplate`, coinbase construction, SHA-256d header nonce scan and `submitblock`.
- Loopback-only HTTP RPC; cookie or RPC user/password authentication.
- Bounded nonce budget (maximum 20,000,000 per request).
- Empty-mempool-only template policy; refuses templates containing transactions rather than risk invalid transaction/merkle/witness construction.
- Public payout script hex input; no private key or seed phrase is handled.
- Dashboard controls for CPU SHA-256d benchmark and explicit one-block regtest attempt.

## CPU microbenchmark
- Algorithm: SHA-256d (double SHA-256 of 80-byte block-header-shaped input)
- Iterations: 200,000
- Elapsed: 0.192182 s
- Throughput: **1,040,679.59 hashes/s** (Python CPU loop in this build environment)
- Last digest: `4ec6e71a24e944a52f3e97f15d0f1b59bc2ffe7622e15386ee1bfc937b5d7f82`

This is a Python CPU microbenchmark, not a GPU benchmark, not a production miner hashrate and not a claim of improved SHA-256. Actual mining performance must be measured with the native miner on the target hardware.

## Offline tests
- NEXUS Master: 108 passed
- MultiMiner X: 17 passed
- Crypto Fieldstation: 12 passed
- Wallet benchmark: 15 passed
- Wallet v0.5: 7 passed
- **Total: 159 passed, 0 failed**

New tests cover hash benchmark execution, regtest template handling, nonce search and block submission through a deterministic mocked Bitcoin Core RPC, network rejection, non-empty mempool rejection, and loopback/auth policy.

## Not performed / remaining prerequisites
- `bitcoind` and `bitcoin-cli` are not installed in this build environment. Therefore no live Bitcoin Core daemon was started and no block was submitted to a real local node in this run. The block assembly/search/submit flow was exercised with a deterministic RPC test double.
- No mainnet or public pool mining was attempted.
- This is a CPU solo adapter, not a Stratum proxy and not a GPU backend.
- Windows PE executable generation and execution require a Windows build host; this Linux build does not claim a tested `.exe`.
