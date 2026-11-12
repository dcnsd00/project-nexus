# RCSC common-ancestor recovery — 2026-11-12

Implemented locally in NEXUS 0.10.25:
- On a stored-anchor mismatch, historical overlap expands backwards in bounded steps (2x, capped at 200 blocks).
- Searches for the highest collected height whose block hash matches the stored hash.
- Accepts a replacement branch only when every subsequent block is eligible and parent-linked contiguously.
- Exposes common_ancestor_height, recovery_attempts and recovery_status in collection results and run metadata.
- Fails closed and preserves stored records if no common ancestor is found.
- Status advertises automatic_common_ancestor_recovery.

Validation:
- compileall: PASS.
- RCSC tests in an isolated overlay of extracted source: 33 passed in 1.28s.
- Regression tests cover successful recovery below the initial window and fail-closed behavior when no ancestor is found.

Limitations:
- Overlap is capped at 200 blocks per run; deeper forks require a later deeper collection and remain fail-closed.
- No live public API collection or independent provider replication was performed.
- No nonce prediction or mining advantage is claimed.
- Application source patch is local/Library only; GitHub currently has documentation, not the full app source.
