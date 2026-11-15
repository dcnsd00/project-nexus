# NEXUS MASTER 0.9.2

- Added SHA-256 reduced-round differential research module.
- Added exact 64-round SHA-256 validation against hashlib using five test vectors.
- Added input-bit differential testing with reproducible seeds and configurable sample counts.
- Added round sweep 1–64, default 2,000 independent probes per configuration.
- Added exact two-sided binomial p-values, Wilson confidence intervals, and Bonferroni multiple-testing corrections.
- Added W0–W63 message-schedule propagation and three schedule-addition carry-out mismatch profiles.
- Added curated one-/multi-bit XOR pattern sweeps for W13/W14/W15.
- Added local research-result persistence and API endpoints.
- Connected SHA-256 lab controls to the Laborator Matematic dashboard.
- Kept all reduced-round findings isolated from active mining and marked consensus_compatible=false.

- Completed 1,158,000 paired exploratory and independent-holdout probes (2,316,000 compression-path evaluations); retained non-replicating candidates as negatives.
- Hardened research result IDs with UUID-based uniqueness.
- Full offline audit: 130 passed, 0 failed; Python compile and dashboard JavaScript syntax checks passed.

## 0.9.3 research extension (pre-release)
- Added round-by-round carry-decision telemetry for T1, T2, d+T1 and T1+T2.
- Added API route `/api/research/sha256/compression-carries` and dashboard control.
- Added equivalence tests proving instrumentation returns the same compression output as the reference implementation.
- Carry telemetry is observational; it does not replace exact modular arithmetic and is not a mining shortcut.
