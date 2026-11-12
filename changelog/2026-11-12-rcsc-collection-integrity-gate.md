# RCSC collection integrity gate — 2026-11-12

Local NEXUS 0.10.25 implementation:

- Collection persistence now requires a non-negative integer height, valid proof of work, exact reported-hash/header match, exact reported summary/header-field match, provider `in_best_chain=true`, and no collection error.
- Invalid or incomplete records remain visible in the collection response but are rejected from the analysis database.
- Collection results expose `records_rejected` and `records_saved`; run metadata records both counts.
- `start_height` and `count` reject booleans and invalid types/ranges.

Validation:
- `compileall`: PASS.
- RCSC tests: **29 passed in 1.37s**.
- Added regression tests for hash mismatch persistence rejection and invalid start heights.

Scope:
- This patch is in the local extracted source tree and Library → NEXUS. It is not yet imported as application source in this GitHub repository.
- No live public API collection or independent provider replication was performed.
- This is data-integrity hardening, not evidence of nonce prediction or mining advantage.
