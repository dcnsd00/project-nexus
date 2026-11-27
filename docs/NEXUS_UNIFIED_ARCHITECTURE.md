# NEXUS Unified Architecture — canonical repository and data policy

Status: **current verified architecture baseline — 2026-11-27**. The application source is present in `application/`; core services, mining, wallet recovery, EDGE, research, AI worker routing and the multi-method Puzzle Solver are in the canonical repository. This document distinguishes automated integration evidence from live target-environment validation.

## Decision

The GitHub repository `dcnsd00/project-nexus` is the canonical source of truth for the complete NEXUS software product. NEXUS is developed as a **modular monolith** with explicit internal module boundaries and shared platform services, not as a collection of independently managed applications.

GitHub Codespaces is the primary reproducible development workspace. GitHub Actions is the automated build, test, regression and integration validation system.

## Repository layout target

```text
/
├── application/                 # integrated canonical application source
│   ├── dashboard.html             # unified NEXUS control center
│   ├── puzzle_solver.html         # local multi-method puzzle UI
│   ├── wallet.html                # local wallet recovery UI
│   ├── nexus_master.py            # current application entry point
│   ├── modules/                   # Lifecycle Manager, Module Registry, services
│   ├── nexus_edge/                # EDGE manager, agents, transport adapters
│   ├── mining/                    # mining supervisor, pools, workers and Stratum
│   ├── research/                  # SHA-2, RCSC and research workflows
│   ├── nexus_master.py           # current application entry point
│   ├── core/                     # CORE, API, configuration, security
│   ├── modules/                  # Lifecycle Manager, Module Registry, runtime
│   ├── nexus_edge/               # EDGE manager, agents, transport adapters
│   ├── crypto/                   # crypto engine and chain interfaces
│   ├── mining/                   # mining supervisor, pools, workers
│   ├── wallet/                   # wallet abstractions and safe signing boundary
│   ├── math_engine/              # mathematical models and optimizers
│   ├── rcsc/                     # collection, chain analysis and validation
│   ├── depin/                    # device/node/DePIN integrations
│   ├── research/                 # AI and research workflows
│   ├── shared/                   # shared contracts, event bus, repositories
│   └── tests/                    # application tests
├── infrastructure/
│   ├── database/                 # migrations, schema, seed fixtures
│   ├── messaging/                # event-bus and transport configuration
│   └── deployment/               # reproducible deployment definitions
├── tests/
│   ├── integration/
│   ├── contract/
│   └── security/
├── docs/
├── scripts/
├── .github/workflows/
├── pyproject.toml
├── requirements*.txt
└── NEXUS_STATUS.md
```

The tree above is a navigation summary, not a mandate to create duplicate package roots such as `crypto/`, `wallet/` or `math_engine/` where equivalent modules already exist. Preserve the observed repository paths and use shared adapters; never move or duplicate a module solely to match a conceptual diagram.

## Shared platform services

All modules must use shared, versioned interfaces for:
- lifecycle and dependency management;
- module registration and health reporting;
- configuration and feature flags;
- structured logging, audit trail and metrics;
- event publication/subscription;
- persistence through shared repository interfaces and database migrations;
- identity, authorization and secret access;
- API contracts and error handling.

A module must not create an independent database, scheduler, configuration system, logging pipeline or lifecycle manager unless an explicit architecture decision approves it.

## Data placement policy

### Version-controlled in GitHub
- application source code and firmware source;
- tests, fixtures containing synthetic data, schemas and migrations;
- API/event contracts and module manifests;
- non-secret default configuration and configuration templates;
- reproducible build/test/deployment definitions;
- documentation, changelogs and validation evidence.

### Stored in central runtime persistence
- device registrations and EDGE telemetry;
- mining runs, pool/share observations and performance history;
- RCSC collection records and analysis metadata;
- research jobs, experiment metadata and reproducible result references;
- operational events, job state and audit records.

Runtime data is stored in a central database/object store selected by deployment profile. Database migrations and repository code remain in GitHub. GitHub is not the live database.

### Never committed to Git
- wallet seed phrases, private keys or decrypted keystores;
- API tokens, passwords, RPC credentials or signing secrets;
- production personal data and sensitive telemetry;
- live database files, WAL files, local state, caches and machine-specific artifacts.

Use GitHub Actions secrets for CI-only credentials and a dedicated runtime secret manager for deployed services. Do not place production wallet secrets in CI.

## Runtime composition

The existing Lifecycle Manager remains the single owner of service startup/shutdown. The existing Module Registry remains the single module inventory and health surface. Runtime registrations observed in `application/modules/nexus_runtime.py` include EDGE Manager, Mining Switch Controller, RCSC Research, Research Hub, Math Intelligence, Puzzle Solver, AI Worker Coordinator, DePIN Fieldstation and local Blockchain Regtest. Wallet recovery is exposed through the shared FastAPI application and local-only API/UI; it is not represented as a separately managed runtime service.

A module is not considered integrated merely because its source exists or its route is registered. Integration requires a reproducible contract/integration test. Operational validation requires a target-environment test.

## Test gates

Every pull request must:
1. compile all changed Python packages;
2. run focused unit and contract tests;
3. run integration/regression tests available in CI;
4. run security checks and secret scanning;
5. produce a clear pass/fail result and test summary.

The NEXUS CI workflow validates the integrated application, Python tests, JavaScript pages, Windows compatibility and sharded Windows tests, native SHA-256d build and Coraza configuration. Separate workflows verify the pinned RandomX upstream reference and Gate Info/Paper Trading contracts. A green CI result proves the tested repository snapshot and CI environment only; it does not prove successful operation on the user's hardware, a public mining pool, a production wallet or a deployed EDGE network.

## Current verified capability and validation boundaries

### Integrated and CI-tested

- Puzzle Solver API: `GET /api/puzzles/capabilities`, `POST /api/puzzles/solve`; UI: `/puzzles`. Supports local classical decoders, known-parameter classical ciphers, exact modular/linear/XOR methods and bounded finite-domain CSP. Natural-language logic-grid parsing is not implemented. Reduced-round SHA-256 SAT research is not a full SHA-256 attack.
- AI Worker API: `/api/nexus/workers/provider-status`, `/api/nexus/workers/execute`; provider supports local Ollama/OpenAI-compatible chat, is disabled by default, is loopback-only, text-only and has a QA review path. No model is installed/configured or live-tested by CI.
- Mining: backend discovery/capabilities, CPU/GPU supervisor, Stratum V1 and pool failover/safety control paths exist. CI uses synthetic/loopback paths; accepted public-pool shares, payout, user hardware benchmark, thermal limits and sustained uptime remain unverified.
- Wallet: local recovery UI/API supports NEXUS AES-GCM, Ethereum Web3 V3, BIP38 non-EC and BIP39 operations; Solana is validate-only and Bitcoin Core inspection is local read-only. BIP38 EC-multiply and EIP-2335 are inactive. No user wallet or secret was processed in CI.
- Math/RCSC/SHA-2 research: exact vector and benchmark paths are tested; SAT/differential experiments are reduced-round. Optional `python-sat` is not installed in CI, so the SAT preimage test is skipped.

### Operational gaps

- No registered Bridge host is available for commands or diagnostics on the user's Windows machine. CI Windows runners are not the user's laptop.
- No live pool connection, accepted share, mining payout or hardware thermal/uptime run has been evidenced.
- No live Ollama/LM Studio or remote model has been configured and invoked.
- No user wallet file, seed phrase, private key or decrypted keystore has been opened; the owner checkbox is an explicit UI attestation, not cryptographic process authentication. Recovery remains loopback-only.
- EDGE physical ESP32-C5/HIL, public TLS/MQTTS ingress and provider-specific LoRaWAN/IoT network validation remain external gates.
- Central runtime database/event-bus/production persistence and deployment profile still require target-environment evidence; GitHub is not the runtime data store.

## Next implementation order

1. Run the existing application on the user's Windows 11 machine through an authorized local execution channel; verify startup, Module Registry health, `/puzzles`, `/wallet` and mining read-only status. A Bridge host is not currently registered.
2. Run mining preflight and benchmark-only measurements on the actual hardware. Live mining remains a separate, explicitly approved operator action; collect pool reachability, accepted shares and payout evidence only after approval.
3. Review wallet recovery authorization and local process boundary. Keep all real wallet material local; never send seed phrases or private keys to AI workers or CI.
4. Configure and test a local AI provider only after explicit approval and model availability; provider remains disabled by default.
5. Extend puzzle solving by domain-specific backends (SAT/SMT, graph/constraint, symbolic and natural-language parsing) with explicit dependencies, limits and test vectors. Do not describe unsupported methods as available.
6. Complete EDGE physical/HIL and provider network validation; establish and verify production persistence/event contracts.
7. Keep each domain change on a focused branch/PR, preserve original worker branches, and merge only after full CI and compatibility evidence.

## Recent integration baseline (2026-11-27)

The following merges are on `main` and were independently verified after each merge:

| PR | Integrated capability | Merge commit |
| --- | --- | --- |
| [#31](https://github.com/dcnsd00/project-nexus/pull/31) | Security Baseline, immutable-action policy aligned scanning | `3ea880ee9234cc8bbcf9c30b47ab6cecc4210e` |
| [#46](https://github.com/dcnsd00/project-nexus/pull/46) | Multi-Method Puzzle Solver API and runtime registration | `5f5e9bc4be234da722fbd769cbd5b5d0275d1e51` |
| [#50](https://github.com/dcnsd00/project-nexus/pull/50) | Opt-in, text-only AI Worker provider and guarded dispatch | `d958bab1fdaa89441e774972dad979e69779d4da` |
| [#51](https://github.com/dcnsd00/project-nexus/pull/51) | Puzzle Solver page, dashboard shortcut and JS CI validation | `6280cccc78f68a5857a75452b671feb8e509c30d` |

Current `main` at this documentation refresh: `6280cccc78f68a5857a75452b671feb8e509c30d`.

## Completion vocabulary

- PLANNED: architecture or task described only.
- IMPLEMENTED: source code exists.
- TESTED: named automated tests passed in a recorded run.
- INTEGRATED: shared runtime connection verified by integration tests.
- VALIDATED: target deployment/hardware behavior verified with evidence.
