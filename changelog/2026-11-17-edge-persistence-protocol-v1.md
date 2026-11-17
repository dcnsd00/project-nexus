# 2026-11-17 — NEXUS EDGE persistence and protocol v1

## Implemented in source
- SQLite schema version 1 for EDGE node metadata, monotonic counters, task state, leases and result fingerprints.
- Injected key-provider contract and OS keyring-backed provider; node HMAC keys are excluded from SQLite.
- Fail-closed recovery if a persisted node has no corresponding OS key.
- Protocol version 1 fields in heartbeat and task-result signatures.
- Strictly increasing heartbeat and result sequence checks.
- Per-assignment random nonces, rotated on task requeue to reject stale worker results.
- Runtime opt-in for persistent EDGE state through NEXUS_EDGE_DB_PATH.
- Regression tests for replay protection, restart restoration, key separation and schema compatibility.
- GitHub Actions Windows test job for the full Python suite.

## Not included
- MQTT/HTTPS transport, TLS broker connection, ESP-IDF firmware, production enrollment/key rotation UI, wallet access, mining control, or physical hardware validation.

## Validation
- Awaiting Linux and Windows GitHub Actions results. No PASS claim until both jobs complete successfully.
