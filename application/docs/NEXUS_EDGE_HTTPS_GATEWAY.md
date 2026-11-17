# NEXUS EDGE HTTPS Gateway — deployment contract

## State
This increment adds an opt-in FastAPI gateway factory. It is not automatically
mounted into NEXUS MASTER and does not establish an internet-facing deployment.
The gateway is intended to run behind a TLS terminator (reverse proxy or managed
load balancer). Do not expose plaintext HTTP to an untrusted network.

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
