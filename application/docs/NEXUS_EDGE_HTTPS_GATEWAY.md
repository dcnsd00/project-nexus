# NEXUS EDGE HTTPS Gateway — deployment contract

## State
The FastAPI gateway is mounted into NEXUS MASTER only when
`NEXUS_EDGE_GATEWAY_ENABLED=true`; it can also run as a standalone alternative.
Neither mode establishes an internet-facing deployment by itself. The gateway
is intended to run behind a TLS terminator (reverse proxy or managed load
balancer). Do not expose plaintext HTTP to an untrusted network.

## Start the gateway

From the `application` directory, after provisioning the required environment variables:

```powershell
python -m uvicorn nexus_edge.server:app --host 127.0.0.1 --port 8765
```

The server binds to loopback by default. Put a TLS reverse proxy in front of it
for remote access; do not bind directly to a public interface during this pilot.

## Required environment
- `NEXUS_EDGE_STORAGE_KEY`: stable Fernet URL-safe base64 key; provision via
  an OS secret store, never commit it or store it in the SQLite database.

Generate a key once with
`python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`.
Store the result in the protected service environment and reuse it across
restarts; do not generate a new key on each launch.
- `NEXUS_EDGE_PROVISIONING_TOKEN`: operator bearer token, minimum 32 characters.
- `NEXUS_EDGE_DATABASE`: optional SQLite path; defaults to the canonical
  NEXUS data-path service location shared by MASTER and standalone adapters.

The standalone Uvicorn entrypoint and the NEXUS MASTER-mounted gateway are
alternative launch modes. Do not run both simultaneously against the same
`NEXUS_EDGE_DATABASE`: the current SQLite store is a single-process scheduler
and does not provide cross-process task-claim coordination or shared in-memory
manager state.

## Endpoints
- `GET /v1/edge/health`: read-only service status.
- `GET /v1/edge/nodes`: operator-authenticated node inventory (secrets excluded).
- `GET /v1/edge/tasks`: operator-authenticated task inventory (payloads and raw results excluded).
- `POST /v1/edge/nodes/provision`: operator-authenticated one-time node secret provisioning.
- `POST /v1/edge/nodes/{node_id}/rotate-secret`: operator-authenticated one-time credential rotation.
- `POST /v1/edge/nodes/{node_id}/revoke`: operator-authenticated node revocation and unfinished-task recovery.
- `POST /v1/edge/tasks`: operator-authenticated task submission.
- `POST /v1/edge/nodes/{node_id}/heartbeat`: signed node heartbeat.
- `POST /v1/edge/nodes/{node_id}/claim`: signed, sequence-protected task claim.
- `POST /v1/edge/nodes/{node_id}/tasks/{task_id}/start`: signed task start.
- `POST /v1/edge/nodes/{node_id}/tasks/{task_id}/complete`: signed task completion plus separately verified result signature.

Node request signatures cover action, node ID, integer Unix timestamp (seconds), monotonic sequence
number, and payload. A durable replay guard rejects repeated or out-of-order
sequences. Provisioning and rotation responses return a node secret once;
operators must transfer it to the device through a separate authenticated
channel. Rotation invalidates the previous secret immediately and preserves
the monotonic sequence counter; the response reports the minimum next sequence
the device must use. Revocation removes the node credential, requeues its
unfinished tasks (or expires overdue tasks), and retains the replay counter.
Re-provisioning the same node ID therefore starts at the next unused sequence,
not at one.

The HTTPS gateway and optional MQTTS runtime are mounted from NEXUS
MASTER using the same LifecycleManager-owned `EdgeManager` instance. Both
require that manager to report `sqlite_persistent`; the online adapters do not
create independent in-memory schedulers pointed at the same database.

## Security boundaries
- The gateway never executes arbitrary shell commands or Python supplied in a task.
- Wallet access, private-key export, miner start/stop, and public-chain writes are
  not exposed by this gateway.
- Node credentials can be rotated through the operator-authenticated
  `/nodes/{node_id}/rotate-secret` endpoint. The sequence counter is preserved.
- Rotate the at-rest encryption key only while all EDGE processes are stopped:
  back up the SQLite database, run
  `python -m nexus_edge.rotate_storage_key`, enter the current and new keys at
  the hidden prompts, then update `NEXUS_EDGE_STORAGE_KEY` before restarting.
  The utility re-encrypts all stored node secrets in one SQLite transaction;
  it never writes either key into the database.
- SQLite is a single-host durable store, not a distributed multi-writer database.
- Before public deployment add rate limiting, request-size limits at the proxy,
  TLS certificate automation, backup/restore drills, audit-log retention,
  and multi-process claim coordination.
- Hardware-in-the-loop validation is still required for ESP32-C5 and Android agents.

Task completion requires both an authenticated request envelope and the existing task-result HMAC. This prevents an unauthenticated client from submitting a result and preserves the manager's result-integrity contract.


## NEXUS MASTER lifecycle integration

The gateway can be mounted as a sub-application of the main NEXUS MASTER
control plane. It remains disabled unless `NEXUS_EDGE_GATEWAY_ENABLED=true`.
When enabled, its routes are available under
`/edge/v1/edge/*`; the read-only lifecycle state is exposed at
`GET /api/edge/gateway`. Startup fails closed for missing/weak operator
credentials or missing durable-storage encryption key. NEXUS MASTER records
only the exception type in its status and continues its other local services.
The mounted gateway is removed during application shutdown.

Set these environment values in the protected service environment:
- `NEXUS_EDGE_GATEWAY_ENABLED=true`
- `NEXUS_EDGE_PROVISIONING_TOKEN` (at least 32 characters)
- `NEXUS_EDGE_STORAGE_KEY` (Fernet URL-safe base64 key)
- Optional: `NEXUS_EDGE_DATABASE`

This integration does not enable WAN exposure. Keep the MASTER listener on
loopback or a trusted LAN and use a verified TLS reverse proxy for remote
access. Live network, node, and hardware validation remain separate gates.
