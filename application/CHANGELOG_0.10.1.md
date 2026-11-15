# NEXUS MASTER 0.10.1 — SHA-256 Advanced Research & Resource Budgets

## Added
- Advanced multi-bit differential search using common training blocks and independent holdout validation.
- Round-by-round internal-state difference tracking and empirical modal-difference frequency.
- Tseitin CNF encoding for reduced-round SHA-256 compression collisions with nonzero XOR delta.
- SAT circuit self-check through unit propagation and independent comparison with the reference compressor.
- Optional python-sat backend, bounded solver timeout and safe DIMACS export.
- Dashboard controls for advanced differential search, track, SAT self-check, solve and DIMACS.
- Independent scrolling for dashboard content while keeping navigation and section header stable.

## Correctness / guardrails
- Fixed output-prefix bit ordering in SAT model: MSB-first to match digest serialization and independent verification.
- Search compares candidates on the same fixed training set, then validates the best candidate on an independent holdout.
- Empirical modal difference frequency is explicitly not labelled as differential path probability.
- Reduced-round results remain isolated from mining and consensus.
- Explicit work, rounds, clauses and timeout budgets protect CPU and memory.

## Not claimed
- No full SHA-256 shortcut or mining acceleration is claimed.
- SAT solver is optional; without it, self-check and DIMACS export remain available.
- No live pool share or GPU benchmark is inferred from these local research tests.
