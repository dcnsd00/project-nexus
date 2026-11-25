# NEXUS 0.5.0 — Local-node integration

See [`v05/README_v0.5.md`](v05/README_v0.5.md) for setup and execution instructions.

This release adds a Bitcoin Core Regtest + five local Anvil-node integration harness. The harness is restricted to loopback endpoints and test accounts. It does not connect to public chains, import user seeds, or move real cryptocurrency.

Workspace validation: [`results/VALIDATION_V05_ENVIRONMENT.md`](results/VALIDATION_V05_ENVIRONMENT.md). The real-node integration has not yet been run in this environment because Docker, Bitcoin Core and Anvil are unavailable here.
