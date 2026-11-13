# NEXUS Unified Architecture — canonical repository and data policy

Status: **architecture decision / implementation plan**. This document does not claim that the entire application source has already been imported or that all modules are integrated.

## Decision

The GitHub repository `dcnsd00/project-nexus` is the canonical source of truth for the complete NEXUS software product. NEXUS is developed as a **modular monolith** with explicit internal module boundaries and shared platform services, not as a collection of independently managed applications.

GitHub Codespaces is the primary reproducible development workspace. GitHub Actions is the automated build, test, regression and integration validation system.

## Repository layout target

```text
/
├── application/                 # canonical application source (import NEXUS MASTER here)
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

The exact placement of existing packages must be reconciled with the imported 0.10.25 source tree. Do not duplicate or blindly move existing modules simply to match this diagram. Preserve compatibility and use adapters where necessary.

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

The existing Lifecycle Manager remains the single owner of service startup/shutdown. The existing Module Registry remains the single module inventory and health surface. NEXUS EDGE, Wallet, Mining, RCSC, DePIN, Math and Research are registered through the shared runtime using explicit dependency declarations and truthful readiness states.

A module is not considered integrated merely because its source exists or its route is registered. Integration requires a reproducible contract/integration test. Operational validation requires a target-environment test.

## Test gates

Every pull request must:
1. compile all changed Python packages;
2. run focused unit and contract tests;
3. run integration/regression tests available in CI;
4. run security checks and secret scanning;
5. produce a clear pass/fail result and test summary.

The application-source test job must fail if the application source is expected but missing. Documentation-only setup must not be represented as a successful application test. EDGE tests run as their own job until the main application source is imported.

## Current verified blockers

- The application source archive is available in the project Library, but the 519 application files are not yet imported into this GitHub repository.
- The EDGE foundation currently lives in the feature branch and is not yet integrated into the 0.10.25 application runtime.
- The runtime database/event bus and production persistence adapters have not yet been implemented or validated.
- CI tests for EDGE are configured, but must be observed to complete successfully before their results are claimed.
- No Windows/hardware/live-pool/wallet payout validation is claimed.

## Required implementation order

1. Import the latest security-reviewed NEXUS MASTER 0.10.25 source bundle into this repository through Codespaces or a Git-capable workspace; verify its pinned SHA-256 and file inventory.
2. Run clean-checkout compileall and full test suite; record actual failures and durations.
3. Reconcile existing source modules with this unified layout without losing functionality.
4. Integrate EDGE as an optional Lifecycle Manager service and expose its status through the existing Module Registry.
5. Implement shared persistence/event contracts and migrations.
6. Connect modules one at a time through tested adapters; prohibit duplicate service infrastructure.
7. Run full CI, then Windows 11 and physical hardware validation.

## Completion vocabulary

- PLANNED: architecture or task described only.
- IMPLEMENTED: source code exists.
- TESTED: named automated tests passed in a recorded run.
- INTEGRATED: shared runtime connection verified by integration tests.
- VALIDATED: target deployment/hardware behavior verified with evidence.
