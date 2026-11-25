# NEXUS EDGE — foundation and integration contract

Status: **Host-side EDGE control plane is integrated into NEXUS MASTER as an optional service.** The current branch includes durable SQLite state, encrypted node credentials, persistent anti-replay, an opt-in HTTPS gateway, an opt-in MQTTS adapter, authenticated/idempotent telemetry ingestion, bounded telemetry history, node provision/rotate/revoke operations, and read-only operator inventory. This is a **single-host pilot**, not a public or multi-server production deployment.

## Repository and runtime ownership

- Repository: `dcnsd00/project-nexus`
- Active branch: `feature/edge-replay-protection-sqlite-v1`
- NEXUS CORE / `LifecycleManager` owns service startup, dependencies, health and shutdown.
- The existing `edge_manager` service owns one shared `EdgeManager` instance.
- HTTPS and MQTTS adapters receive that same instance; they do not create parallel managers when started by NEXUS MASTER.
- `NEXUS_EDGE_DATABASE` overrides the database path. Otherwise the canonical NEXUS data-path service resolves it.
- The replay guard and state store must use the same SQLite database. The runtime reports `sqlite_persistent` only when both are durable and share the same path.
- NEXUS MASTER creates one shared EDGE manager and passes it to the HTTPS/MQTTS adapters; this is verified by host-side runtime integration tests. Run the SQLite-backed service as one NEXUS process/worker only. Multiple independent manager processes sharing this database are not validated or supported.

## Implemented host-side capabilities

### Control plane and task lifecycle

- Node registration with safe unique IDs, declared capabilities, per-node HMAC secrets and bounded parallelism.
- Signed protocol-v1 heartbeats with finite timestamps, clock-skew limits and strictly increasing per-node sequences.
- `protocol_version: 1` is included in the canonical JSON covered by HMAC-SHA256 for heartbeat, node-request, task-result and telemetry envelopes. HTTPS and MQTT reject missing, boolean or unsupported versions.
- Capability-based FIFO task assignment.
- Task states: `QUEUED → ASSIGNED → RUNNING → SUCCEEDED`, with deadline expiry and lease requeue.
- Signed task results and SHA-256 result fingerprints.
- Node credential rotation invalidates the old secret and requires a fresh heartbeat.
- Node revocation requeues unfinished tasks (or expires overdue tasks).
- Re-provisioning a revoked node ID preserves its anti-replay counter; the operator receives the minimum next sequence.
- Payload and result size limits; no arbitrary command execution.

### Persistence and security

- `SQLiteReplayGuard` persists the highest accepted sequence per node.
- `SQLiteEdgeStore` persists nodes, tasks, leases, results and telemetry. Schema migrations are versioned through v4.
- Node HMAC secrets are encrypted at rest with a stable operator-provisioned Fernet key.
- Storage-key rotation is implemented as an offline, atomic re-encryption utility:
  `python -m nexus_edge.rotate_storage_key`.
- The utility requires the NEXUS processes to be stopped and a verified database backup before rotation.
- Only node authentication secrets are encrypted by the current store. Task payloads, task results and telemetry payloads are stored as canonical JSON; protect the database with restrictive filesystem ACLs, host disk encryption and controlled backups.
- Telemetry history retains the newest 10,000 events by default. Anti-replay sequence state is retained separately from telemetry pruning.

### Transport and telemetry

- HTTPS gateway is opt-in through `NEXUS_EDGE_GATEWAY_ENABLED=true`; inside NEXUS MASTER it is mounted under `/edge`.
- MQTTS is opt-in through `NEXUS_EDGE_MQTT_ENABLED=true`; TLS certificate verification and broker authentication are required.
- MQTT QoS acknowledgements are manual. The broker message is acknowledged only after the telemetry event and replay sequence commit atomically. Redelivery is idempotent by node, sequence, transport and canonical payload digest.
- HTTPS, MQTTS, generic LoRaWAN-bridge webhook and IoT webhook telemetry ingress are authenticated and persisted.
- Authenticated telemetry refreshes durable node `last_seen`, allowing the shared scheduler to recognize active nodes.
- Operator APIs expose node/task inventory without secrets or raw results. Raw telemetry history is behind the operator-authenticated EDGE gateway. NEXUS MASTER's unauthenticated status endpoint exposes telemetry metadata only.
- The CLI and dashboard expose runtime, transport, topology, node, task and telemetry status.

## Required environment configuration

- `NEXUS_EDGE_STORAGE_KEY`: stable Fernet URL-safe base64 key. Generate once, store in a protected service environment and reuse across restarts. Never commit it or store it in SQLite.
- `NEXUS_EDGE_PROVISIONING_TOKEN`: high-entropy operator bearer token, minimum 32 characters. Rotate by replacing the protected environment value and restarting the gateway.
- `NEXUS_EDGE_DATABASE`: optional SQLite path; otherwise the canonical NEXUS data path is used.
- `NEXUS_EDGE_GATEWAY_ENABLED=true`: enables the HTTPS gateway.
- `NEXUS_EDGE_MQTT_ENABLED=true`: enables MQTTS. Configure `NEXUS_EDGE_MQTT_HOST` and either username/password or client certificate/key credentials. Install `paho-mqtt>=2,<3`.
- Install the optional MQTTS runtime dependency set from `application/` with `pip install -r requirements-edge.txt`; this includes `paho-mqtt>=2,<3`. Both network adapters remain disabled unless explicitly enabled. Missing storage encryption or weak/missing operator credentials fail the optional network service closed; they do not authorize an in-memory online gateway.

## Security and deployment boundaries

1. Use a unique random secret per node; never embed a fleet-wide shared secret in firmware.
2. HMAC provides authenticity, not confidentiality. HTTPS must sit behind a TLS terminator or managed load balancer; do not expose plaintext HTTP.
3. Keep operator and storage secrets out of source control, logs, dashboard responses and SQLite.
4. Do not send wallet seeds, private keys, signing requests or unrestricted shell commands to EDGE nodes.
5. Node capabilities are allow-listed. Task payloads are typed data, not executable code.
6. CORE remains authoritative for approvals, persistent records, financial operations and miner start/stop actions.
7. Local SQLite is a single-host durable store, not a distributed multi-writer database. Active-active/multi-server task claims are rejected by topology validation.
8. Before remote exposure, configure reverse-proxy rate limits, strict firewall rules, database ACLs, backups/restore drills, monitoring and an incident-recovery procedure.

## Explicit external validation gates

These are not represented as completed merely because host endpoints exist:

- **ESP32 firmware:** no production firmware binary is included yet. The first target remains the NM-CYD-C5 board; confirm the received board revision, RAM/PSRAM, display controller and vendor schematic before pin mapping. First firmware milestone: Wi-Fi provisioning, secure key provisioning, authenticated heartbeat, status display, telemetry and bounded task receipt.
- **LoRaWAN provider integration:** the generic signed webhook ingress exists, but provider-specific ChirpStack / The Things Stack adapters, network-server credentials, regional radio plan and payload decoders are not configured.
- **IoT vendor adapters:** the generic signed webhook ingress exists; vendor-specific authentication and payload decoders remain deployment-specific.
- **Physical validation:** pairing, reconnect behavior, power-loss recovery, radio range, device-side sequence persistence and downlink behavior require hardware-in-the-loop tests.
- **Public deployment hardening:** TLS termination, rate limiting, firewall rules, backup/restore and monitoring must be verified in the target environment.
- **CI evidence (2026-11-19, active HEAD `5bd6133e4eeeb2629a7641a45fa528d29f2af07b`):** Linux full suite 624 passed, 1 warning, 10 subtests passed; Windows compatibility 623 passed, 1 skipped, 1 warning, 10 subtests passed; Windows frozen desktop build, executable self-test, installer validation and artifact upload all succeeded. GitHub Actions runs: [NEXUS CI 44492144115](https://github.com/dcnsd00/project-nexus/actions/runs/44492144115), [Windows Desktop Package 44492144055](https://github.com/dcnsd00/project-nexus/actions/runs/44492144055).
- These are hosted-runner results. The desktop installer test used `-NoLaunch`; it did not verify interactive desktop UI startup on the user's laptop. No physical ESP32-C5, real broker, provider-specific LoRaWAN/IoT or live public ingress validation is claimed.
- **Branch integration:** this feature branch is 291 commits ahead and 0 behind `integration/source-import-safe-0.10.25`; it has not yet been merged into that integration branch. `main` remains untouched.

## Verification suite

Run from the application directory:

```bash
python -m pytest \
  tests/test_nexus_edge_manager.py \
  tests/test_nexus_edge_persistence.py \
  tests/test_nexus_edge_gateway.py \
  tests/test_nexus_edge_gateway_runtime.py \
  tests/test_nexus_edge_master_integration.py \
  tests/test_nexus_edge_runtime.py \
  tests/test_nexus_edge_sqlite_store.py \
  tests/test_nexus_edge_transports.py \
  tests/test_nexus_edge_service.py -q
```

The suite covers control-plane scheduling, persistence and migrations, key rotation, node lifecycle, authenticated telemetry, idempotent MQTT redelivery, manual QoS acknowledgements, gateway behavior and shared-manager integration. CI and physical hardware validation remain separate evidence requirements.
