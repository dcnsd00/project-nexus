# RCSC chain continuity and reorganization handling — 2026-11-12

Implemented in local NEXUS 0.10.25 source:
- Check adjacent eligible block records form a contiguous height sequence and each child references the preceding block hash.
- Reject the full eligible batch when a broken link is found.
- Detect a changed hash at an already-stored height.
- On detected reorganization, atomically delete stored records from the earliest changed height onward and replace them with the newly collected canonical segment.
- Persist and return reorg_detected, reorg_from_height and broken_chain_links diagnostics.

Validation:
- compileall: PASS.
- RCSC tests: 31 passed in 1.42s.
- Regression coverage: changed block hash plus descendant replacement; broken chain batch rejected.

Limitations:
- Detection is limited to the collected height window; a fork beginning below that window requires a deeper overlapping collection to detect.
- No live API collection or independent provider replication was performed.
- No predictive mining advantage is claimed.
- Patch is local and in Library; application source is not yet imported into GitHub.
