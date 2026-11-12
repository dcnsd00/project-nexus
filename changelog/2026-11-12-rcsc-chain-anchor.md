# RCSC stored-chain anchor verification — 2026-11-12

Implemented locally in NEXUS 0.10.25:
- Partial collection windows are anchored against the stored block at (lowest_collected_height - 1), when that anchor exists.
- A parent-hash mismatch rejects the entire incoming eligible window without modifying existing stored records.
- Collection response and run metadata expose anchor_verified, anchor_height and anchor_mismatch.
- Status reports stored_chain_anchor_verification capability.
- This prevents accepting an unanchored partial segment when a possible fork/common ancestor is outside the fetched window.

Validation:
- compileall: PASS.
- RCSC suite: 32 passed in 1.48s.
- Regression test verifies anchor mismatch rejection and preservation of prior stored records.

Limitations:
- No automatic deep fork resolver yet. On mismatch, a deeper overlapping collection is required to locate a common ancestor.
- No live public API call was performed.
- Application source patch is local/Library only; GitHub contains documentation, not the full application source.
- No mining prediction advantage is claimed.
