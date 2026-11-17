# NEXUS EDGE multi-network and multi-server deployment contract

## IP connectivity
LAN, WAN and mobile-data clients use the same HTTPS API and/or MQTTS broker.
The network path changes; the application protocol and node identity do not.
Remote access must terminate TLS with valid certificate verification. Do not
expose the development Uvicorn listener directly to the public internet.

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

## Security and rollout gates
No WAN listener, MQTT broker, LoRaWAN Network Server or hardware is assumed
present. Network adapters are opt-in. Before remote exposure require TLS,
rate limits, strict firewall rules, secret rotation, audit logs, backup/restore
tests, monitoring, and a recovery drill. Hardware node pairing and physical
radio tests are separate validation gates.
