# NEXUS EDGE — foundation and integration contract

Status: **EDGE in-memory control plane integrated as an optional NEXUS runtime service; durable anti-replay guard implemented; task persistence and transport remain pending.**

## Repository baseline

The current `main` branch contains repository governance, source-import documentation and CI scaffolding. The NEXUS MASTER 0.10.25 application bundle is separately available in the project Library and is not yet committed to this repository. The latest local bundle includes the Lifecycle Manager, Module Registry, Runtime composition root, Wallet read-only adapter and Mining Supervisor read-only adapter.

The EDGE package is intentionally isolated so it can be merged into the application source after the verified source import. It does not replace or duplicate those runtime components.

## Target architecture

- **NEXUS CORE / LifecycleManager** owns application startup and service dependencies.
- **NEXUS EDGE Manager** owns node registry, capability matching, task leases, task state and result integrity.
- **EDGE Agent** on each ESP32/ESP32-C5 performs only explicitly assigned, bounded tasks.
- **Transport adapter** (future MQTT or HTTPS) carries versioned messages; transport is not coupled to scheduling logic.
- **Device adapters** expose telemetry from NerdMiner, sensors and other devices without granting wallet access or starting miners.

## First implementation boundary

The current Python package `nexus_edge/` is a transport-agnostic control-plane implementation. It provides:
- node registration with unique IDs, declared capabilities and per-node HMAC secret;
- signed heartbeat verification and online/offline status;
- capability-based FIFO task assignment;
- task state transitions: QUEUED → ASSIGNED → RUNNING → SUCCEEDED;
- task deadlines and worker leases, with requeue after lease expiry;
- HMAC-authenticated results and SHA-256 result fingerprints;
- bounded JSON payload/result sizes and a diagnostic snapshot.

It deliberately has **no network listener, firmware binary, wallet API, private-key handling, mining control or arbitrary command execution**. Node registry and task queue remain in memory and are lost on restart. The replay guard can persist monotonic heartbeat sequence numbers in SQLite, and NEXUS Runtime injects it under the canonical `NEXUS_DATA_DIR/db/edge_replay.sqlite3` path. Node secrets are not stored by this database. Task persistence, key provisioning/rotation, transport and physical-device validation remain incomplete.

## Security contract

1. Provision a unique random secret per node (minimum 32 bytes); never embed a fleet-wide shared secret in firmware.
2. Use TLS for transport. HMAC provides message authenticity, not confidentiality.
3. Heartbeats include a strictly increasing per-node sequence number and a bounded clock-skew timestamp. The replay guard rejects duplicate or out-of-order sequences and can persist the accepted sequence in SQLite. Key provisioning and rotation are still pending.
4. Never send wallet seeds, private keys, signing requests or unrestricted shell commands to EDGE nodes.
5. Node capabilities are allow-listed. Task payloads are typed data, not executable code.
6. CORE remains authoritative for approvals, persistent records, financial operations and miner start/stop actions.

## ESP32-C5 first target

The NM-CYD-C5 board is an ESP32-C5-WROOM-1 development board with display/touch, Wi-Fi 6 and peripheral connectors as advertised by the seller. Exact RAM/PSRAM, display driver and board revision must be confirmed against the received hardware and vendor schematic before firmware pin mapping. The first firmware milestone is Wi-Fi provisioning, authenticated heartbeat, status display and task receipt; no mining is planned on this board.

## Integration plan

1. Import and verify the exact NEXUS MASTER 0.10.25 source bundle in a Git-capable workspace.
2. Copy this package under the application source tree as `application/nexus_edge/` (or `nexus_edge/` if the application uses repository-root layout).
3. Add an optional `edge_manager` service to `modules/nexus_runtime.py`, dependent on the existing crypto engine and Lifecycle Manager; the runtime injects a SQLite replay guard under the canonical NEXUS data directory.
4. Expose read-only status through the existing Module Registry; do not duplicate the registry.
5. Extend durable storage from replay counters to node metadata, task state, leases and restart recovery; do not persist HMAC secrets in plaintext.
6. Add ESP-IDF firmware for NM-CYD-C5 and test against a local mock broker before connecting physical nodes.
7. Validate on Windows 11 and physical hardware. CI success alone is not hardware validation.

## Test

Run from the application directory:

```bash
python -m pytest tests/test_nexus_edge_manager.py tests/test_nexus_edge_replay_guard.py tests/test_nexus_edge_service.py -q
```

The manager tests validate scheduling and HMAC behavior; replay-guard tests validate sequence monotonicity and SQLite restart persistence. These tests do not validate MQTT/HTTPS, Windows deployment or physical ESP32 devices.
