# NEXUS MASTER — Function-Level Acceptance Matrix v1

**Baseline:** `main` at `c6ac7e0264d8ed01b94e386d6a8c669ce7c98905` (version 0.10.28), inspected 2026-11-28.  
**Purpose:** Replace subjective module percentages with auditable acceptance evidence. This is an audit register, not a claim that the system is operational.  
**Release rule:** No installer or package delivery until every in-scope acceptance item is `PASS` or explicitly `N/A` with a documented reason, and all applicable runtime/HIL gates are evidenced.

## 1. Acceptance vocabulary

| State | Meaning | Evidence required |
|---|---|---|
| PRESENT | Source exists in the canonical repository | Exact source path at an identified commit |
| IMPLEMENTED | Required behavior is present | Reviewed implementation and API/contract definition |
| TESTED | Automated tests pass | Test names, exact commit, CI run and logs |
| INTEGRATED | Registered in the running NEXUS application | Route/service registration plus integration test |
| LIVE-VERIFIED | Real dependency/provider round-trip succeeded | Sanitized probe result, timestamp, endpoint/provider and contract |
| TARGET-VERIFIED | Validated on target Windows host or physical hardware | Reproducible acceptance record and environment details |
| BLOCKED | Required external access, hardware, credentials or operator action unavailable | Explicit blocker and owner/action |
| N/A | Criterion does not apply | Reason and reviewer sign-off |

A mocked transport, fake provider, fixture, source file, route registration, successful package build, or CI test does not establish LIVE-VERIFIED or TARGET-VERIFIED.

## 2. System-wide release gates

| ID | Gate | Pass condition | Current baseline |
|---|---|---|---|
| SYS-01 | Canonical source | Tested commit is reachable from reviewed PR; no unreviewed main changes | Main baseline identified |
| SYS-02 | Unit tests | All in-scope unit tests pass, including boundary, invalid input, timeout, retry and recovery cases | Main CI evidence exists; function-by-function mapping still required |
| SYS-03 | Integration tests | Cross-module contracts and lifecycle behavior pass without mocks where feasible | Partial; module-specific evidence to be recorded |
| SYS-04 | Security | CodeQL, secret scanning, dependency and security baseline checks pass; findings triaged | Main baseline CI had a successful security workflow; each new PR requires fresh evidence |
| SYS-05 | Windows runtime | Frozen application starts, serves local API, opens UI/WebView, shuts down cleanly and upgrades/recovers on target Windows | CI packaging/frozen executable evidence exists; owner-device acceptance remains outstanding |
| SYS-06 | Local AI | Selected model runtime is actually available; provider probe and all worker profiles complete real inference | BLOCKED pending local runtime/model execution on target host |
| SYS-07 | External services | Every declared connector has a documented API contract and a successful real bounded probe/read | BLOCKED; baseline records no live-verified connectors |
| SYS-08 | Mining hardware | Supported miner processes, pool protocols, telemetry, stop/restart and arbitration are tested on actual supported hardware | BLOCKED pending physical/user hardware acceptance |
| SYS-09 | Wallet safety | Encrypted backup/restore, recovery, address derivation and read-only flows validated with test vectors and owner-controlled test wallet; no signing without authorization | BLOCKED pending target-wallet acceptance |
| SYS-10 | EDGE / DePIN HIL | Real broker/transport, device identity, replay protection, key rotation, reconnect and persistence tested with physical node(s) | BLOCKED pending broker and hardware-in-loop acceptance |
| SYS-11 | Recovery | Backup, restore, interrupted update, corrupted state and rollback are exercised | NOT YET VERIFIED |
| SYS-12 | Release evidence | Each function has a completed row below and all applicable gates pass | OPEN |

## 3. Module inventory and acceptance requirements

The 19 module IDs and source paths below are taken from `application/modules/module_registry.py` on the baseline commit. Source presence in that registry is inventory evidence only. Unless a row explicitly says otherwise, per-function test mapping and target acceptance remain **NOT YET AUDITED**; do not infer a percentage.

| Module | Canonical source path(s) | Required functional acceptance | Current evidence / gap |
|---|---|---|---|
| core | `core/PROJECT-NEXUS-LOCAL/app/main.py` | Startup/shutdown; lifecycle; configuration validation; health; API routing; graceful dependency failure; restart/recovery; local-only security boundaries | PRESENT in registry; full target Windows lifecycle acceptance pending |
| wallet | `modules/wallet_benchmark/nexus_wallet_manager.py` | Address/key derivation test vectors; encrypted backup and restore; wrong password; corrupted backup; version migration; zeroization/log redaction; read-only default; signing and broadcast denied unless explicitly authorized | PRESENT in registry; real owner-host wallet acceptance pending |
| mining_supervisor | `mining/hybrid_supervisor.py`, `mining/hybrid_orchestrator.py` | Miner discovery; capability checks; process ownership; start/stop/restart; crash recovery; CPU/GPU arbitration; pool failover; telemetry; no unexpected miner launch | PRESENT in registry; actual miner/pool/hardware acceptance pending |
| crypto_engine | `modules/crypto_engine/engine.py` | Deterministic vectors; supported algorithms; malformed input; edge lengths; constant-time/security review where relevant; independent implementation cross-check | PRESENT in registry; map exact algorithm test suites and independent vectors |
| rcsc | `research/rcsc/nexus_rcsc/nexus_rcsc/collector.py`, `modules/rcsc_service.py` | Reproducible collection; permutation/statistical tests; null and malformed data; multiple-testing correction; deterministic reports; provenance | PRESENT in registry; full pipeline/reproducibility acceptance pending |
| integrations | `modules/integration_registry.py` | Per-provider documented contract; TLS/host allowlist; auth handling; bounded response; schema validation; timeout/error handling; secret redaction; read-only enforcement; real probe | PRESENT in registry; 12-provider live validation not demonstrated on baseline |
| market_data | `modules/market_data.py` | Provider selection; schema normalization; stale data; rate limits; timeout/retry; invalid symbols; source attribution; no trading/write side effects | PRESENT in registry; live market smoke is opt-in and not proof unless run with evidence |
| rainbowminer_telemetry | `modules/rainbowminer_telemetry.py` | Read-only report ingestion; schema/version compatibility; missing/corrupt reports; stale telemetry; process isolation; no control commands | PRESENT in registry; real RainbowMiner report ingestion on target host pending |
| mining_profit_intelligence | `modules/mining_profit_intelligence.py` | Live price and difficulty inputs; hashrate/power/fee calculations; currency conversion; freshness; uncertainty; pool/miner compatibility; reproducible profitability output | PRESENT in registry; live profitability and actual hardware measurements pending |
| ai_worker_coordinator | `modules/ai_worker_coordinator.py` | Provider discovery; real model inference; coordinator and each of 10 specialists; all-profile dispatch; QA/security review; timeout; malformed response; token/context limits; secret redaction; no implicit privileged tools | PRESENT in registry; real inference and target model benchmark pending |
| gate_info | `modules/gate_paper_trading.py` | Read-only market data; paper-order lifecycle; deterministic balance/PnL/fees; restart persistence; invalid order rejection; no real exchange order path | PRESENT in registry; paper tests exist; live-data freshness and persistence acceptance to be recorded |
| math_intelligence | `modules/math_intelligence.py` | Exact arithmetic; numerical tolerances; domain errors; bounds; symbolic/numeric cross-check; reproducible output; resource limits | PRESENT in registry; exact per-function coverage mapping pending |
| puzzle_solver | `modules/puzzle_solver.py` | Known-answer fixtures; multi-method agreement; false-positive rejection; bounded search; cancellation/timeouts; reproducibility; no unsafe external side effects | PRESENT in registry; exact corpus and performance acceptance pending |
| research_hub | `modules/research_hub.py` | Source provenance; deduplication; freshness; retrieval failure; citation integrity; untrusted-content isolation; reproducible summaries | PRESENT in registry; end-to-end source integration acceptance pending |
| earnings_intelligence | `modules/earnings_intelligence.py` | Input provenance; reward/earnings normalization; currency/unit correctness; duplicate handling; missing data; time-window correctness; stale source warnings | PRESENT in registry; live provider evidence pending |
| mining_switch_controller | `modules/mining_switch_controller.py` | Policy thresholds; hysteresis; cooldown; conflicting commands; process ownership; safe stop/start; restart persistence; manual override; no autonomous start without configured consent | PRESENT in registry; real miner arbitration acceptance pending |
| blockchain_regtest | `modules/blockchain_regtest/nexus_v05_integration.py` | Local node discovery/start/stop; regtest funding; block generation; RPC auth; chain reset; persistence; no mainnet transaction; recovery | PRESENT in registry; actual local node/regtest session pending |
| edge_manager | `nexus_edge/manager.py`, `nexus_edge/service.py`, `nexus_edge/replay_guard.py`, `nexus_edge/sqlite_store.py`, `nexus_edge/gateway.py`, `nexus_edge/gateway_runtime.py`, `nexus_edge/runtime.py`, `nexus_edge/transports.py`, `nexus_edge/topology.py`, `nexus_edge/config.py`, `nexus_edge/rotate_storage_key.py` | Persistent state; replay rejection; idempotency; authentication; key rotation; transport reconnect; gateway authorization; broker integration; message ordering; physical node HIL | PRESENT in registry; real broker/transport and physical HIL pending |
| depin_fieldstation | `adapters/fieldstation/crypto_fieldstation/app.py` | Device enrollment; secure identity; telemetry integrity; offline queue; reconnect; reward data provenance; power/network recovery; physical device acceptance | PRESENT in registry; physical fieldstation acceptance pending |

## 4. Function-level evidence record template

Create one record for every externally callable function, route, worker operation, connector resource and critical background task. Do not use one module-level pass to imply every function passed.

| Field | Required value |
|---|---|
| Function ID | Stable module/function or route identifier |
| Contract | Inputs, outputs, side effects, permissions and failure semantics |
| Source | Path and line range at exact commit |
| Unit tests | Test IDs covering nominal, boundary, invalid, timeout and recovery |
| Integration test | Test ID and participating modules |
| Security | Threat/permission review and secret-handling result |
| Live dependency | Provider/device/broker and sanitized evidence, or N/A reason |
| Target runtime | Windows/device model, version and acceptance result |
| CI evidence | Workflow run, job, exact commit and log |
| Status | PRESENT / IMPLEMENTED / TESTED / INTEGRATED / LIVE-VERIFIED / TARGET-VERIFIED / BLOCKED |
| Defect link | Issue/PR and remediation commit |
| Reviewer | Human sign-off for release-critical behavior |

## 5. Scoring rules

- Do not publish a single aggregate percentage until every function has an enumerated denominator.
- For each function, report the number of passed applicable acceptance criteria divided by the number of applicable criteria; list blocked criteria separately.
- A function is **100% accepted** only when every applicable criterion passes and evidence points to the exact tested commit.
- A module is **100% accepted** only when all its functions are 100% accepted and module-level lifecycle/integration gates pass.
- NEXUS is **100% accepted** only when every in-scope module and system-wide release gate passes. An unavailable external dependency is BLOCKED, not silently excluded.
- Recalculate scores whenever source, tests, dependencies, configuration contracts or target runtime change.

## 6. First execution order

1. Resolve and validate PR #59 (AI providers, worker coordinator and connectors) without merging while CI/security findings remain.
2. Build the function inventory for core, wallet, mining supervisor and crypto engine; these are marked critical in the canonical module registry.
3. Audit integrations and AI provider paths against real configured services and local model runtime.
4. Run target Windows acceptance on the owner machine through the approved secure bridge; preserve the existing stale/dirty checkout and do not overwrite it.
5. Validate mining, EDGE and Fieldstation against actual devices and broker/pool services.
6. Complete the remaining module rows, attach CI/live/HIL evidence and only then calculate defensible percentages.

## 7. Current release decision

**NOT RELEASE-READY.** This matrix is a baseline and execution plan. It does not assert that all functions have been enumerated, that all tests have passed, or that any unperformed live/Windows/hardware checks succeeded. Keep PRs reviewable and isolated; do not merge or deliver a package solely because CI packaging succeeds.
