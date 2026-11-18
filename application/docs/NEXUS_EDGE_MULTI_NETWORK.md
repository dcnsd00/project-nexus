# NEXUS EDGE multi-network and multi-server deployment contract

## IP connectivity
LAN, WAN and mobile-data clients use the same HTTPS API and/or MQTTS broker.
The network path changes; the application protocol and node identity do not.
Remote access must terminate TLS with valid certificate verification. Do not
expose the development Uvicorn listener directly to the public internet.

## Host integration and evidence boundary

The NEXUS MASTER lifespan injects one LifecycleManager-owned EDGE manager
instance into both the HTTPS gateway and the optional MQTTS runtime. The
network adapters must not create separate managers against the same SQLite
file: their independent in-memory snapshots could overwrite one another.
Online gateway/MQTTS startup therefore requires the shared manager to report
`sqlite_persistent`, which in turn requires a stable
`NEXUS_EDGE_STORAGE_KEY`.

MQTTS startup state and broker connectivity are reported separately. An
initialized client is not reported as connected until the broker accepts the
connection and the uplink subscription succeeds. Malformed or unauthenticated
uplinks are rejected in the network callback and counted without logging their
payloads.

**Current ingress boundary:** authenticated HTTPS/MQTTS uplinks are validated
and accepted, but the MQTTS runtime currently retains accepted uplinks only in
a bounded in-memory diagnostics queue. It is not yet a durable telemetry
ingestion pipeline and does not automatically feed Mining, Earnings
Intelligence, Research Hub, or device inventory. LoRaWAN Network Server
integration, IoT vendor adapters, payload decoders, downlink device protocol,
and physical-node validation remain separate implementation gates.

## LoRaWAN
LoRaWAN devices do not connect directly to the HTTPS gateway. The intended
path is:

`LoRaWAN sensor/node -> LoRaWAN gateway -> LoRaWAN Network Server -> authenticated HTTPS uplink adapter -> NEXUS EDGE`.

A supported deployment will need a LoRaWAN radio module, regional frequency-plan
compliance, a Network Server integration (for example a validated ChirpStack
or The Things Stack adapter), payload decoder, device/application keys, and
hardware-in-the-loop tests. Raw LoRa P2P is a separate radio mode and must not
be described as LoRaWAN.

## MQTT / IoT
The optional `MQTTBridge` uses MQTTS (TLS, certificate verification enabled),
QoS 1, bounded JSON messages and explicit start/stop. It is not started by
NEXUS runtime automatically. Install `paho-mqtt>=2,<3` in the gateway
environment to enable the production client. Node messages must still be
authenticated and anti-replay checked by EDGE before actions are accepted.

## Multi-server target
The first two-server target is primary/standby, not active-active:
- Server A: primary NEXUS API, EDGE scheduler and dashboard.
- Server B: standby API/runtime, health monitor and documented failover role.
- Shared/replicated transactional state and tested backups are prerequisites.
Local SQLite is supported for a single-server pilot only. It is not a safe
shared multi-writer store for two active schedulers.
Active-active remains blocked until distributed task claims, shared database
transactions, idempotency, leader/fencing or equivalent coordination, and
failover tests are implemented.

## Deployment topology validation

NEXUS MASTER validates `NEXUS_DEPLOYMENT_MODE`, `NEXUS_SERVER_COUNT`,
`NEXUS_STATE_BACKEND`, `NEXUS_SHARED_STATE`, and
`NEXUS_DISTRIBUTED_TASK_CLAIMS` during startup. The validated declaration is
reported by `GET /api/edge/topology`, the `nexus_cli.py edge` command, and the
unified operator snapshot.

Only single-server mode with the local SQLite state backend is currently
supported by the runtime. PostgreSQL or other unimplemented state backends are
rejected rather than silently reported while SQLite is still in use.
Primary/standby and active-active declarations fail closed, even when their
prerequisite settings are present, because the shared database adapter,
distributed atomic claims, leader/fencing, replication, and failover
orchestration are not implemented. The topology endpoint reports
`operational_failover_verified=false`; a declaration is never represented as
an operational cluster.

## Security and rollout gates
No WAN listener, MQTT broker, LoRaWAN Network Server or hardware is assumed
present. Network adapters are opt-in. Before remote exposure require TLS,
rate limits, strict firewall rules, secret rotation, audit logs, backup/restore
tests, monitoring, and a recovery drill. Hardware node pairing and physical
radio tests are separate validation gates.
