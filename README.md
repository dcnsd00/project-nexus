# NEXUS

NEXUS is a modular research and software project. This repository is the canonical GitHub workspace for source code, implementation notes, tests, and release history.

## Development rules

- Treat implementation, integration, testing, and hardware validation as separate states.
- Never mark a feature complete without reproducible evidence.
- Keep changes small, reviewable, and covered by tests.
- Do not disable Windows Defender or add broad security exclusions.
- Preserve Windows 11 and Python 3.12 compatibility where applicable.
- Record each implementation step in `NEXUS_STATUS.md` and a dated changelog under `changelog/`.
- Do not commit secrets, wallet seed phrases, private keys, API tokens, or personal data.

## Current state

The repository was verified as accessible through the GitHub connector on 2026-11-12. At that time it contained no source files. The NEXUS 0.10.25 archive and earlier audit evidence exist separately; they have not yet been imported into this repository.

## Next engineering step

Import and inspect the exact NEXUS 0.10.25 source archive, establish a reproducible baseline, run the existing tests, then integrate changes in reviewable commits.
