# NEXUS 0.9.5 Audit

## Automated tests
- NEXUS master suite: 99 passed
- MultiMiner X: 17 passed
- Crypto Fieldstation: 12 passed
- Wallet benchmark: 15 passed
- Wallet v0.5 unit tests: 7 passed
- Total: 150 passed, 0 failed

## New Math Intelligence checks
- SHA-512 and SHA-3 exact hash benchmarks execute and return throughput + digest.
- Linear modular congruence solver verifies solution classes and no-solution cases.
- Candidate triage refuses promotion without exact equivalence, >=3 independent runs, >=180 seconds, accepted shares and <=1% rejects.
- API tests cover catalog, SHA-512 benchmark, modular solver and candidate triage.
- No candidate is automatically applied to mining.

## Scope not validated by this audit
- No physical GPU miner was started.
- No real pool share was submitted.
- No live payout was observed.
- Bitcoin Core regtest / Anvil require local daemons and were not exercised here.
- Windows desktop shell has not been installed/tested on the user's laptop.

The official audit was executed using `bash run_full_audit.sh`.
