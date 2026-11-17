# NEXUS EDGE Protocol v1 and persistence contract

Status: **implemented in source; awaiting GitHub Actions validation**.

## 1. Scope

This increment hardens the existing NEXUS EDGE control plane without adding a
network listener, broker, firmware, wallet capability, or miner control.
The manager remains transport-agnostic. Future MQTT/HTTPS adapters must
implement this protocol rather than changing scheduler semantics.

## 2. Protocol version 1

Authenticated messages use HMAC-SHA256 over canonical UTF-8 JSON:
sorted keys, compact separators, UTF-8 encoding, and NaN disallowed.

Heartbeat signature payload:

\`\`\`json
{
  "protocol_version": 1,
  "kind": "heartbeat",
  "node_id": "edge-c5-001",
  "timestamp": 1800000000.0,
  "sequence": 1
}
\`\`\`

Task-result signature payload:

\`\`\`json
{
  "protocol_version": 1,
  "kind": "task_result",
  "node_id": "edge-c5-001",
  "task_id": "opaque-task-id",
  "assignment_nonce": "fresh-random-value-from-task-claim",
  "sequence": 1,
  "result": {"status": "ok"}
}
\`\`\`

Each node maintains independent, monotonically increasing heartbeat and
result sequence counters. A sequence must be strictly greater than the last
accepted value; counters are persisted across host restarts. Timestamps still
enforce a bounded clock-skew window but do not replace sequence checks.

Every task claim receives a fresh cryptographically random assignment nonce.
The nonce is included in the signed result. Requeue after lease expiry clears
the old nonce; the next claim receives a new one. A delayed result from an
earlier assignment therefore cannot complete the task.

Before firmware is implemented, the node-side firmware contract must also
persist its counters safely across resets. A host-side counter alone cannot
prove replay protection for a physical node.

## 3. Persistence model

SQLite schema version 1 stores:
- node ID, declared capabilities and concurrency limit;
- last authenticated heartbeat time and accepted sequence counters;
- task payload, required capabilities, deadlines and task state;
- assignment nonce, result JSON and SHA-256 result fingerprint.

SQLite never stores node HMAC secrets. The EDGE manager refuses to use a
persistent store unless an external key provider is injected. On restore, every
persisted node must have a valid key available; otherwise initialization
fails closed rather than silently disabling authentication.

The in-memory key provider is for tests and ephemeral development only.
The OS keyring provider uses the active operating-system keyring backend.
On supported Windows environments this is backed by Windows Credential
Locker. Persistent runtime mode is opt-in through NEXUS_EDGE_DB_PATH;
without this variable, EDGE remains in its explicitly reported in-memory
pilot mode.

The keyring backend must report a positive priority. This rejects the
keyring fail-backend, but does not constitute a security certification of
every operating-system credential-store configuration. Production key
provisioning and key-rotation workflows remain a separate milestone.

## 4. Runtime configuration

For a Windows installation, set a writable application-data path:

\`\`\`powershell
$env:NEXUS_EDGE_DB_PATH = "$env:LOCALAPPDATA\NEXUS\edge.sqlite3"
\`\`\`

The runtime then uses SQLite for state and the OS keyring for node secrets.
Key provisioning must be performed through a trusted enrollment flow. Do
not copy keys into Git, SQLite, firmware images, logs, or a shared
fleet-wide secret.

## 5. Operational boundaries

Still not implemented by this increment:
- TLS MQTT/HTTPS transport and broker authentication;
- production node enrollment and key rotation ceremony;
- ESP-IDF firmware for ESP32/ESP32-C5;
- Windows installer/package and user-device validation;
- task-specific capability allow-list governance and multi-node load tests.

HMAC authenticates message origin and integrity; it does not encrypt message
contents. Transport encryption remains mandatory before remote nodes are
connected. EDGE remains unable to access wallet keys, sign transactions,
execute arbitrary shell commands, or auto-start miners.
