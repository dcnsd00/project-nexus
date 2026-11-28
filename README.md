# NEXUS MASTER

NEXUS is a local-first, modular-monolith research and software project. This repository is the canonical source for application code, implementation notes, tests, CI evidence, and release history.

## Development rules

- Treat source presence, implementation, testing, integration, and hardware validation as separate states.
- Never mark a feature operational without reproducible evidence from the relevant boundary.
- Keep changes small, reviewable, and covered by tests; integrate through focused pull requests.
- Preserve existing package ownership and module boundaries. Do not create parallel CORE, EDGE, mining, wallet, or provider implementations.
- Preserve Windows 11 and Python 3.12 compatibility where applicable.
- Record material implementation steps in `NEXUS_STATUS.md` and a dated entry under `changelog/`.
- Do not disable Windows Defender or add broad security exclusions.
- Never commit wallet seeds, private keys, pool credentials, API tokens, or personal data.

## Repository state — 2026-11-27

- Canonical repository: `dcnsd00/project-nexus`.
- Default branch: `main`.
- Current main HEAD at this documentation checkpoint: `700978e829b75888216785d874cb2cbbc7a4e6b2`.
- NEXUS MASTER remains a modular monolith; GitHub is authoritative for code, branches, commits, pull requests and CI.
- PR #53 merged mining credential log/handoff protections. See [Mining credential handling](docs/MINING_CREDENTIAL_HANDLING.md) and [NEXUS status](NEXUS_STATUS.md).
- The detailed status document distinguishes TESTED, INTEGRATED and VALIDATED evidence and lists remaining Windows, hardware, provider and deployment acceptance work.

## Working safely

Use a focused feature or documentation branch from the latest appropriate base. Inspect the exact diff and commit, run the relevant test suites and CI, and promote through a reviewed pull request. Keep `main` unchanged during development. Do not infer physical hardware operation, live mining rewards, wallet signing, or production security deployment from source files or CI alone.
