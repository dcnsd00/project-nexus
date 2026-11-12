# RCSC collector integrity patch — 2026-11-12

## Implemented locally in NEXUS 0.10.25

The public Bitcoin collector now:
- validates each TXID as 64 hexadecimal characters;
- detects duplicate TXIDs case-insensitively;
- requires the coinbase TXID at index 0;
- checks returned TXID count against the block summary's `tx_count`;
- rebuilds the Merkle root only when the TXID list passes completeness checks;
- checks each transaction page against the exact ordered TXID slice;
- rejects malformed pages and invalid, negative, or boolean fee values;
- sets the fee total to null and marks it incomplete if any page fails, rather than exposing a partial sum as a complete total.

## Verification

- Compile check: PASS.
- RCSC tests: **24 passed in 1.26s**.
- Added regression tests for incomplete TXID lists, mismatched fee-page ordering, and incorrect coinbase ordering.

## Limitations

No live API collection or independent provider replication was performed. The patch is saved in Library under `/NEXUS/NEXUS_0.10.25_RCSC_COLLECTOR_INTEGRITY.zip`. Application source has not yet been committed to this GitHub repository. No predictive mining advantage is claimed.
