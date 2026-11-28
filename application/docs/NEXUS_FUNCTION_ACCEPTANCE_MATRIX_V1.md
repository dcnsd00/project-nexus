# NEXUS MASTER — Function-level Acceptance Matrix v1

**Repository:** `dcnsd00/project-nexus`  
**Baseline:** `main` at `c6ac7e0264d8ed01b94e386d6a8c669ce7c98905`  
**Working branch:** `feature/ai-providers-connectors-operational-v1`  
**Current PR:** #59 — draft; no merge authorised  
**Purpose:** replace subjective module percentages with explicit, evidence-backed acceptance criteria. This document is an audit baseline, not a declaration of operational readiness.

## 1. Acceptance vocabulary

| State | Meaning | Counts as 100%? |
|---|---|---|
| Present | Required source files exist | No |
| Implemented | Function and declared contract exist | No |
| Unit-tested | Deterministic normal, boundary and failure tests pass | No |
| Integrated | Correctly mounted in the NEXUS runtime and cross-module tests pass | No |
| Live-verified | Real bounded provider/model/service round-trip passes | Only for live dependencies |
| Target-validated | Tested on the intended Windows runtime and applicable physical hardware | Only for target-dependent functions |
| Accepted | All applicable gates pass with traceable evidence | Yes |

A mock, synthetic provider, import test, CI package build or route registration cannot be substituted for live/target validation. A function can be accepted without a live third-party dependency only where its contract is explicitly local-only or deterministic and all applicable runtime checks pass.

## 2. Current repository inventory

- Module registry declares **19 modules**.
- `application/nexus_master.py` contains **125 direct route decorators**.
- The **11 mounted routers** in the runtime declare **76 additional route decorators** across the files enumerated below.
- Source-declared route total: **201**. This is a source inventory; it must still be cross-checked against FastAPI's runtime OpenAPI route table before claiming that every route is actually registered.
- Latest branch comparison at this revision: 89 commits ahead of `main`, zero behind. This includes the cumulative branch history and is not equivalent to 89 newly completed functions.

## 3. Module acceptance matrix

| Module ID | Module | Source paths | Existing test evidence | Remaining acceptance gate |
|---|---|---|---|---|
| `core` | NEXUS Core | `core/PROJECT-NEXUS-LOCAL/app/main.py` | test_core_api.py; test_master.py; test_nexus_runtime.py; test_lifecycle_manager.py | CI + frozen desktop self-test; owner Windows launch and full local-service acceptance pending |
| `wallet` | Wallet Engine | `modules/wallet_benchmark/nexus_wallet_manager.py` | test_wallet_manager.py; test_wallet_recovery_integration_016.py; test_keystore_recovery_20.py; wallet benchmark/recovery suites | Synthetic tests exist; real user vault/recovery acceptance not run; wallet operations must remain local and owner-controlled |
| `mining_supervisor` | Hybrid Mining Supervisor | `mining/hybrid_supervisor.py; mining/hybrid_orchestrator.py` | test_hybrid_supervisor.py; test_hybrid_orchestrator.py; test_hybrid_worker.py; test_miner_adapters_0109.py; test_mining_process_arbiter.py | Mock/process tests exist; no acceptance on user's actual miners, GPU/ASIC/ESP32 or public pool |
| `crypto_engine` | Cryptographic Engine | `modules/crypto_engine/engine.py` | test_crypto_engine.py; test_crypto_security.py; test_native_sha256d_021.py | Automated tests exist; algorithm-level independent vectors and target-host performance acceptance still required |
| `rcsc` | RCSC Research | `research/rcsc/nexus_rcsc/nexus_rcsc/collector.py; modules/rcsc_service.py` | application/tests/rcsc/*; test_sha2_research_bridge_0113.py; test_sha2_research_service_020.py | Historical local suite: 11 RCSC tests; SHA2 suite 12 passed/1 skipped where python-sat unavailable; independent reproducibility remains |
| `integrations` | Provider Integrations | `modules/integration_registry.py` | test_integration_connectors_runtime_v1.py; test_integration_registry_contracts.py; test_integration_registry_015.py | 12 connectors registered; 9 documented response contracts (including Nodle public supply), 3 contract-pending (Acurast, Grass, Wingbits); Nodle personal device/reward data still unsupported; no owner credential live verification |
| `market_data` | Public Market Data | `modules/market_data.py` | test_market_data.py; test_market_data_live_smoke.py | Live smoke is opt-in and was skipped by default; provider round-trip/freshness/rate-limit acceptance pending |
| `rainbowminer_telemetry` | RainbowMiner Read-only Telemetry | `modules/rainbowminer_telemetry.py` | test_rainbowminer_telemetry.py; test_mining_telemetry_evidence.py | Parser/contract tests exist; zero actual RainbowMiner reports received in prior audit; target machine feed pending |
| `mining_profit_intelligence` | Mining Profit Intelligence | `modules/mining_profit_intelligence.py` | test_mining_profit_intelligence.py; test_mining_efficiency_optimizer.py | External price fetching disabled in prior audit; live profit/yield and power-cost reconciliation pending |
| `ai_worker_coordinator` | NEXUS AI Worker Coordinator | `modules/ai_worker_coordinator.py; modules/ai_worker_provider.py; modules/local_ai_models.py` | test_ai_worker_coordinator.py; test_ai_worker_provider.py; test_ai_provider_multi_vendor_v1.py; test_ai_worker_all_specialists_v1.py; test_local_ai_models.py | Synthetic dispatch/provider tests; real model download/load/inference and all-11 worker self-test on owner's Windows host pending |
| `gate_info` | Gate Info Research & Paper Trading | `modules/gate_paper_trading.py` | test_gate_paper_trading.py | Latest Gate Info/Paper Trading workflow passed on tested branch head; only simulated capital/orders, no exchange private keys or live orders |
| `math_intelligence` | Math Intelligence | `modules/math_intelligence.py; modules/hybrid_solver.py` | test_math_intelligence_095.py; test_math_intelligence_api_095.py; test_math_intelligence_contracts.py; test_mathematical_regression_015.py | Automated deterministic tests exist; independent numerical/property validation and performance envelopes pending |
| `puzzle_solver` | Multi-Method Puzzle Solver | `modules/puzzle_solver.py; modules/phy_challenge_research.py` | test_puzzle_solver.py; test_puzzle_solver_page.py; test_phy_challenge_research.py | Automated test coverage exists; benchmark corpus, solve-rate and correctness ground-truth acceptance pending |
| `research_hub` | Research Hub | `modules/research_hub.py; modules/sha256_research/*` | test_sha256_research.py; test_sha256_advanced.py; test_sha_avalanche_0102.py; test_development_pow.py | Local research suites exist; external independent replication and result provenance acceptance pending |
| `earnings_intelligence` | Earnings Intelligence | `modules/earnings_intelligence.py` | test_earnings_intelligence.py | Ledger/device/reward endpoints implemented; no real provider/account/payout data reconciliation |
| `mining_switch_controller` | Conditional Mining Switch | `modules/mining_switch_controller.py` | test_mining_switch_controller.py; test_hybrid_safety.py; test_mining_controller_090.py | Policy/simulation tests exist; actual switch on live miner must remain disabled until explicit owner acceptance and hardware tests |
| `blockchain_regtest` | Local Blockchain Regtest | `modules/blockchain_regtest/nexus_v05_integration.py` | test_blockchain_regtest_import.py; test_local_chain_v04.py; test_solo_bitcoin_rpc_097.py | Import/contract tests exist; local Bitcoin/EVM regtest node not started and validated in current acceptance |
| `edge_manager` | NEXUS EDGE Manager | `nexus_edge/*; modules/nexus_runtime.py` | test_nexus_edge_manager.py; test_nexus_edge_gateway.py; test_nexus_edge_gateway_runtime.py; test_nexus_edge_persistence.py; test_nexus_edge_replay_guard.py; test_nexus_edge_sqlite_store.py; test_nexus_edge_transports.py; test_nexus_edge_runtime.py | SQLite/replay/transport tests exist; real broker + ESP32/ESP32-C5 transport and hardware-in-loop acceptance pending |
| `depin_fieldstation` | DePIN Fieldstation | `adapters/fieldstation/crypto_fieldstation/app.py` | test_fieldstation_import_safety.py; Fieldstation suite | Prior Fieldstation suite: 16 tests; no physical station/node acceptance |

## 4. Route-by-route inventory

Every route below requires an individual contract row in the final acceptance ledger: request schema, response schema, auth/loopback boundary, side-effect class, success test, invalid-input test, failure/recovery test, integration test and target/live evidence where applicable.

### 4.1 Direct routes — `application/nexus_master.py` (125)

| Method | Route |
|---|---|
| GET | `/api/edge/transports` |
| GET | `/api/edge/gateway` |
| GET | `/api/edge/nodes` |
| GET | `/api/edge/tasks` |
| GET | `/api/edge/telemetry` |
| GET | `/api/edge/topology` |
| GET | `/api/nexus/master` |
| GET | `/api/nexus/readiness` |
| GET | `/api/mining/profiles` |
| GET | `/api/mining/hardware` |
| GET | `/api/mining/safety/status` |
| GET | `/api/mining/reference-benchmarks` |
| GET | `/api/mining/native-engine` |
| GET | `/api/nexus/modules` |
| GET | `/api/wallet/audit` |
| GET | `/wallet` |
| GET | `/puzzles` |
| GET | `/api/crypto/algorithms` |
| POST | `/api/crypto/hash` |
| POST | `/api/crypto/benchmark` |
| GET | `/api/mining/pools` |
| POST | `/api/mining/config` |
| GET | `/api/coins/catalog` |
| GET | `/api/nexus/telemetry` |
| GET | `/api/blockchain/nodes/bitcoin` |
| GET | `/api/blockchain/nodes/evm` |
| GET | `/api/nexus/dashboard` |
| GET | `/api/mining/miners` |
| POST | `/api/mining/start` |
| POST | `/api/mining/stop` |
| GET | `/api/mining/solo-readiness` |
| GET | `/api/mining/solo-rpc/benchmark` |
| POST | `/api/mining/solo-rpc/mine-regtest` |
| GET | `/api/mining/status` |
| GET | `/api/mining/processes` |
| GET | `/api/mining/diagnostics` |
| GET | `/api/mining/installers` |
| GET | `/api/mining/installers/{miner_id}/latest` |
| POST | `/api/mining/installers/{miner_id}/install` |
| GET | `/api/research/sha256/info` |
| POST | `/api/research/sha256/differential` |
| POST | `/api/research/sha256/sweep` |
| POST | `/api/research/sha256/multi-delta` |
| GET | `/api/research/sha256/results` |
| POST | `/api/research/sha256/compression-carries` |
| GET | `/api/research/sha256/advanced/info` |
| POST | `/api/research/sha256/advanced/search` |
| POST | `/api/research/sha256/advanced/track` |
| POST | `/api/research/sha256/sat/selfcheck` |
| POST | `/api/research/sha256/sat/solve` |
| POST | `/api/research/sha256/sat/dimacs` |
| POST | `/api/mining/compatibility` |
| POST | `/api/mining/hybrid/plan` |
| POST | `/api/mining/mode/{mode}/start` |
| POST | `/api/mining/mode/{mode}/stop` |
| GET | `/api/mining/mode/status` |
| POST | `/api/mining/hybrid/start` |
| POST | `/api/mining/hybrid/stop` |
| POST | `/api/mining/hybrid/engine/{engine}/start` |
| POST | `/api/mining/hybrid/engine/{engine}/stop` |
| POST | `/api/mining/hybrid/gpu/switch` |
| POST | `/api/mining/hybrid/engine/{engine}/switch/evaluate` |
| POST | `/api/mining/hybrid/engine/{engine}/switch/apply` |
| GET | `/api/mining/hybrid/status` |
| POST | `/api/mining/randomx/20block-benchmark` |
| POST | `/api/mining/randomx/reference-benchmark` |
| POST | `/api/mining/randomx/benchmark` |
| POST | `/api/mining/hybrid/optimize/plan` |
| POST | `/api/mining/pool-test` |
| GET | `/api/nexus/dashboard-data` |
| POST | `/api/mining/optimization-trials` |
| GET | `/api/mining/optimization-trials` |
| GET | `/api/mining/pool-account` |
| GET | `/api/research/hub` |
| GET | `/api/research/hub/summary` |
| GET | `/api/research/hub/history` |
| POST | `/api/research/hub/toy-pow` |
| POST | `/api/research/hub/toy-collision` |
| POST | `/api/research/hub/run-suite` |
| GET | `/api/math-intelligence/catalog` |
| POST | `/api/math-intelligence/hash-benchmark` |
| POST | `/api/math-intelligence/modular-solve` |
| POST | `/api/math-intelligence/triage` |
| GET | `/api/math-intelligence/avalanche/catalog` |
| POST | `/api/math-intelligence/avalanche/run` |
| GET | `/api/research/sha2/status` |
| POST | `/api/research/sha2/selftest` |
| POST | `/api/research/sha2/benchmark` |
| POST | `/api/research/sha2/avalanche` |
| POST | `/api/research/sha2/statistics` |
| POST | `/api/research/sha2/differential` |
| POST | `/api/research/sha2/message-modification` |
| POST | `/api/research/sha2/message-modification/e2` |
| POST | `/api/research/sha2/sat/solve` |
| POST | `/api/research/sha2/verify` |
| GET | `/api/mining/coins` |
| GET | `/api/staking/assets` |
| GET | `/api/mining/merged-rewards` |
| GET | `/api/mining/unmineable/routes` |
| GET | `/api/mining/unmineable/assets` |
| GET | `/api/mining/pool-connectors` |
| GET | `/api/mining/catalog-audit` |
| GET | `/api/mining/solo-profiles` |
| POST | `/api/mining/solo/config` |
| POST | `/api/mining/stratum-probe` |
| POST | `/api/mining/stratum-job-probe` |
| POST | `/api/mining/rewards-check` |
| GET | `/api/math/hybrid/capabilities` |
| POST | `/api/math/hybrid/solve` |
| GET | `/api/research/rcsc/status` |
| POST | `/api/research/rcsc/collect` |
| POST | `/api/research/rcsc/analyze` |
| POST | `/api/research/rcsc/verify-header` |
| GET | `/api/research/rcsc/runs/{run_id}` |
| GET | `/api/nexus/runtime` |
| GET | `/api/nexus/module-registry` |
| GET | `/api/nexus/module-registry/health` |
| GET | `/api/mining/capabilities/algorithms` |
| GET | `/api/mining/capabilities/pool-coverage` |
| POST | `/api/mining/capabilities/evaluate` |
| GET | `/api/mining/backends` |
| GET | `/api/mining/backends/discovery` |
| POST | `/api/mining/backends/evaluate` |
| GET | `/api/mining/capabilities/compatibility-matrix` |
| GET | `/api/nexus/operator` |

### 4.2 Mounted router routes (76)

#### `application/modules/wallet_benchmark/nexus_wallet_manager.py` — 9 routes (prefix `/api/wallet`)

| Method | Route |
|---|---|
| POST | `/api/wallet/vault/create` |
| POST | `/api/wallet/vault/unlock` |
| GET | `/api/wallet/vaults` |
| GET | `/api/wallet/bitcoin/vaults` |
| POST | `/api/wallet/bitcoin/vault/unlock` |
| POST | `/api/wallet/watch` |
| GET | `/api/wallet/watch` |
| DELETE | `/api/wallet/watch/{watch_id}` |
| GET | `/api/wallet/status` |

#### `application/modules/wallet_benchmark/nexus_wallet_recovery_api.py` — 10 routes (prefix `/api/wallet/recovery`)

| Method | Route |
|---|---|
| GET | `/api/wallet/recovery/formats` |
| POST | `/api/wallet/recovery/detect` |
| POST | `/api/wallet/recovery/decrypt` |
| POST | `/api/wallet/recovery/import-bip38` |
| POST | `/api/wallet/recovery/solana/validate` |
| POST | `/api/wallet/recovery/bip39/check` |
| POST | `/api/wallet/recovery/bip39/one-missing` |
| POST | `/api/wallet/recovery/search` |
| POST | `/api/wallet/recovery/bitcoin-core/inspect` |
| POST | `/api/wallet/recovery/bitcoin-core/check` |

#### `application/modules/earnings_intelligence.py` — 19 routes (prefix `/api/intel`)

| Method | Route |
|---|---|
| GET | `/api/intel/status` |
| POST | `/api/intel/opportunities` |
| GET | `/api/intel/opportunities` |
| POST | `/api/intel/devices` |
| GET | `/api/intel/devices` |
| POST | `/api/intel/jobs` |
| GET | `/api/intel/jobs` |
| POST | `/api/intel/telemetry` |
| POST | `/api/intel/rewards` |
| POST | `/api/intel/costs` |
| POST | `/api/intel/payouts` |
| GET | `/api/intel/ledger` |
| POST | `/api/intel/wallet-watch` |
| GET | `/api/intel/wallet-watch` |
| POST | `/api/intel/sources` |
| GET | `/api/intel/sources` |
| GET | `/api/intel/evaluate/{opportunity_id}/{device_id}` |
| POST | `/api/intel/scheduler/shadow` |
| GET | `/api/intel/telemetry` |

#### `application/modules/integration_registry.py` — 5 routes (prefix `/api/integrations`)

| Method | Route |
|---|---|
| GET | `/api/integrations/catalog` |
| GET | `/api/integrations/status` |
| POST | `/api/integrations/self-test` |
| POST | `/api/integrations/{provider_id}/probe` |
| GET | `/api/integrations/{provider_id}/read/{resource}` |

#### `application/modules/ai_worker_coordinator.py` — 10 routes (prefix `/api/nexus/workers`)

| Method | Route |
|---|---|
| GET | `/api/nexus/workers/provider-status` |
| GET | `/api/nexus/workers/local-models` |
| GET | `/api/nexus/workers/local-runtime-status` |
| POST | `/api/nexus/workers/local-models/{profile_id}/pull` |
| GET | `/api/nexus/workers/local-models/pulls/{profile_id}` |
| POST | `/api/nexus/workers/provider-test` |
| POST | `/api/nexus/workers/self-test` |
| POST | `/api/nexus/workers/execute` |
| POST | `/api/nexus/workers/coordinate` |
| POST | `/api/nexus/workers/route` |

#### `application/modules/gate_paper_trading.py` — 7 routes

| Method | Route |
|---|---|
| GET | `/api/gate/config` |
| GET | `/api/gate/markets` |
| GET | `/api/gate/market/{symbol}` |
| GET | `/api/gate/research/{symbol}` |
| GET | `/api/gate/paper/portfolio` |
| POST | `/api/gate/paper/orders` |
| GET | `/gate-paper` |

#### `application/modules/market_data.py` — 6 routes

| Method | Route |
|---|---|
| GET | `/api/market-data/providers` |
| GET | `/api/market-data/{provider}/ticker/{symbol}` |
| GET | `/api/market-data/{provider}/24h/{symbol}` |
| GET | `/api/market-data/{provider}/klines/{symbol}` |
| GET | `/api/market-data/{provider}/order-book/{symbol}` |
| GET | `/api/market-data/{provider}/trades/{symbol}` |

#### `application/modules/rainbowminer_telemetry.py` — 4 routes (prefix `/api/mining/rainbowminer`)

| Method | Route |
|---|---|
| POST | `/api/mining/rainbowminer/report` |
| GET | `/api/mining/rainbowminer/pools/latest` |
| GET | `/api/mining/rainbowminer/miners/latest` |
| GET | `/api/mining/rainbowminer/status` |

#### `application/modules/mining_profit_intelligence.py` — 2 routes (prefix `/api/mining/profit-intelligence`)

| Method | Route |
|---|---|
| GET | `/api/mining/profit-intelligence/status` |
| POST | `/api/mining/profit-intelligence/rank` |

#### `application/modules/pool_failover_api.py` — 2 routes

| Method | Route |
|---|---|
| GET | `/api/mining/pool-failover/scenarios` |
| POST | `/api/mining/pool-failover/simulate` |

#### `application/modules/puzzle_solver.py` — 2 routes (prefix `/api/puzzles`)

| Method | Route |
|---|---|
| GET | `/api/puzzles/capabilities` |
| POST | `/api/puzzles/solve` |

## 5. Cross-cutting acceptance gates

| Gate | Required evidence | Current finding |
|---|---|---|
| Main runtime | Startup, shutdown, readiness, lifecycle recovery, runtime route enumeration | CI evidence exists; owner Windows interactive acceptance pending |
| Windows desktop | Install/upgrade/uninstall, launch, WebView, firewall/network policy, data-path persistence, crash recovery | CI frozen executable/package tests exist; owner laptop not yet validated |
| Wallet safety | Synthetic wallet fixtures, format detection, vault unlock, recovery, zero secret logging, backup/restore; no destructive action without explicit owner approval | Automated tests exist; no acceptance with owner's real wallet/vault |
| Mining safety | Dry-run, process ownership, stop/restart recovery, backend availability, no accidental duplicate miner; pool auth and hardware checks | Unit/mock coverage exists; no live target miner acceptance |
| AI workers | Provider configuration, real model inference, all 11 profiles, timeout/retry, malformed output, token budget, isolation and permission denial | Synthetic tests exist; provider disabled until owner configures it; live all-11 self-test pending |
| External integrations | Official endpoint, documented schema, allowlist, TLS, bounded response, auth, rate-limit/failure tests, live probe, data freshness | 12 registered; 8 documented contracts; 4 contract-pending; no owner credentials used |
| EDGE | Persistent replay guard, restart recovery, transport connection, gateway, key rotation, broker auth, device HIL | CI test coverage exists; physical broker/device HIL pending |
| DePIN Fieldstation | Device boot, sensor/telemetry path, connectivity loss/recovery, key handling, field deployment | Import/unit tests exist; physical field test pending |
| Security | CodeQL, Gitleaks, dependency scan, threat model, secret redaction, local-only boundaries, SSRF/redirect tests | Security Baseline passed on `d13ebb9`; subsequent AI-provider HMAC fingerprint and diagnostic-script changes require a fresh exact-head scan |
| Regression | Full Linux + Windows shards, RandomX references, Gate/Paper Trading, desktop package on exact candidate SHA | `d13ebb9` passed all 15 CI jobs, Python 922 passed/1 skipped/1 warning/10 subtests, Windows package, RandomX and Gate/Paper Trading; later commits require exact-head rerun |

## 6. Immediate blockers and next implementation order

1. **Close the failing connector test and security findings.** The AIOZ test was stale against the newer provider-specific response-contract state. The code now uses a keyed HMAC configuration fingerprint and static API error responses to avoid exposing exception detail. These changes require a fresh exact-head CI and CodeQL result.
2. **Finish AI provider validation.** Added `DIAGNOSTIC_AI_ACCEPTANCE.ps1`: read-only loopback status checks by default; the real provider probe plus all-11 worker inference is an explicit `-RunLiveAiSelfTest` opt-in. It does not install runtimes, download models or start services. The script still needs Windows PowerShell execution against a configured local provider.
3. **Finish the connector contract ledger.** For each of the 12 providers, record official endpoint, protocol, auth, resource schema, pagination/rate limits and live probe evidence. Acurast, Grass and Wingbits remain blocked until official HTTP/API contracts are established; do not fabricate REST adapters. Nodle public token supply is implemented, but personal rewards remain out of scope pending its private-beta IoT API contract.
4. **Validate the 19 modules in the real runtime.** The registry's `operational_verified` flag must remain false until the module-specific health evidence and required routes/dependencies pass.
5. **Run Windows and physical HIL acceptance.** EDGE, mining, DePIN Fieldstation and wallet recovery cannot be declared 100% from GitHub-hosted mocks alone.
6. **Recalculate percentages only from ledger rows.** A percentage is `accepted criteria / applicable criteria`, with blocked external/HIL criteria counted as incomplete. Do not average a module to 100% if any mandatory criterion is pending.

## 7. Current validation record

- Last observed Python CI failure before the latest fixes: `256 passed, 1 failed, 1 warning`; the failure was an AIOZ test expecting `reachable` while the implementation returned a provider-contract verification state. The test was updated to expect `live_verified` and `contract_verified=true`.
- Latest security changes: connector and AI-provider configuration fingerprints now use process-keyed HMAC-SHA256; AI worker HTTP handlers return fixed error codes rather than raw exception strings.
- The corrected baseline commit `d13ebb94466da15132e17f22191f4428be45d61c` passed all 15 NEXUS CI jobs, 922 Python tests (1 skipped, 1 warning, 10 subtests), all eight Windows shards, Windows desktop package, Security Baseline, RandomX references and Gate/Paper Trading.
- After that successful baseline, the AI-provider fingerprint was also changed to HMAC, a loopback-only Windows diagnostic script was added, and a static safety test was added. These later commits mean **the current exact head still requires a fresh full CI and CodeQL result**.
- No merge to `main`, no installer delivery and no 100% claim is authorised by this matrix.

## 8. Audit metadata

- `application/nexus_master.py`: blob `6672a637d1efb51afa71d077fec279015ae6cc9f`; 125 declared route decorators.
- `application/modules/wallet_benchmark/nexus_wallet_manager.py`: blob `5e4954ea1f9c5a17180ace97536b8c408a780269`; 9 declared route decorators.
- `application/modules/wallet_benchmark/nexus_wallet_recovery_api.py`: blob `5c0d4a1e3c14984805c31f500e98fc980b688320`; 10 declared route decorators.
- `application/modules/earnings_intelligence.py`: blob `35e0895e7c153069220c7d965db4741840aec561`; 19 declared route decorators.
- `application/modules/integration_registry.py`: blob `8decd8657072d3e465efbbb3b6547a3f63266b3c`; 5 declared route decorators.
- `application/modules/ai_worker_coordinator.py`: blob `519a2121f3ecb8ef77fadfa58895a98f644aa77b`; 10 declared route decorators.
- `application/modules/ai_worker_provider.py`: blob `dd2d9504c5c13d9bab1b069580803de69a5d7967`; provider configuration fingerprints use process-keyed HMAC-SHA256.
- `application/DIAGNOSTIC_AI_ACCEPTANCE.ps1`: blob `66413d140973e05bab7ac489d6355bdc678fcaf8`; read-only local AI/connectors diagnostic with explicit live all-worker self-test opt-in.
- `application/tests/test_local_ai_models.py`: blob `71b25816ef34f752746af3dc6b6efcf51ac742c4`; verifies the Windows diagnostic remains loopback-only and non-installing.
- `application/modules/gate_paper_trading.py`: blob `444a5b093d2819beb209187e911c46e397ed0f9f`; 7 declared route decorators.
- `application/modules/market_data.py`: blob `42112e1f2d2fd8dc93596725f18b15e9dff5f08c`; 6 declared route decorators.
- `application/modules/rainbowminer_telemetry.py`: blob `066fa592001ef842a0961da88805e66fc21ce0a2`; 4 declared route decorators.
- `application/modules/mining_profit_intelligence.py`: blob `1bff4ef0e9aa9035a3f9d9546971180eea676406`; 2 declared route decorators.
- `application/modules/pool_failover_api.py`: blob `4e339975782eb172b313093e3a65c0d30798ffce`; 2 declared route decorators.
- `application/modules/puzzle_solver.py`: blob `0a2dcb816cf7f51c2f519e4e3e7a9d374014d292`; 2 declared route decorators.
