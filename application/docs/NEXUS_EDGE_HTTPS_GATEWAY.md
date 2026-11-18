# NEXUS EDGE HTTPS Gateway — deployment contract

## State
This increment adds an opt-in FastAPI gateway factory. It is not automatically
mounted into NEXUS MASTER and does not establish an internet-facing deployment.
The gateway is intended to run behind a TLS terminator (reverse proxy or managed
load balancer). Do not expose plaintext HTTP to an untrusted network.

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
- `NEXUS_EDGE_PROVISIONING_TOKEN`: operator bearer token, minimum 32 characters.
- `NEXUS_EDGE_DATABASE`: optional SQLite path; defaults to
  `./data/db/edge_state.sqlite3`.

## Endpoints
- `GET /v1/edge/health`: read-only service status.
- `POST /v1/edge/nodes/provision`: operator-authenticated one-time node secret provisioning.
- `POST /v1/edge/tasks`: operator-authenticated task submission.
- `POST /v1/edge/nodes/{node_id}/heartbeat`: signed node heartbeat.
- `POST /v1/edge/nodes/{node_id}/claim`: signed, sequence-protected task claim.
- `POST /v1/edge/nodes/{node_id}/tasks/{task_id}/start`: signed task start.
- `POST /v1/edge/nodes/{node_id}/tasks/{task_id}/complete`: signed task completion plus separately verified result signature.

Node request signatures cover action, node ID, integer Unix timestamp (seconds), monotonic sequence
number, and payload. A durable replay guard rejects repeated or out-of-order
sequences. The provisioning response returns a node secret once; operators
must transfer it to the device through a separate authenticated channel.

The HTTPS gateway and optional MQTTS runtime are mounted from NEXUS
MASTER using the same LifecycleManager-owned `EdgeManager` instance. Both
require that manager to report `sqlite_persistent`; the online adapters do not
create independent in-memory schedulers pointed at the same database.

## Security boundaries
- The gateway never executes arbitrary shell commands or Python supplied in a task.
- Wallet access, private-key export, miner start/stop, and public-chain writes are
  not exposed by this gateway.
- Rotate node credentials through a separately audited provisioning workflow;
  key rotation is not yet implemented in this increment.
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
