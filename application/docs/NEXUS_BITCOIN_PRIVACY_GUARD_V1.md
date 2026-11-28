# NEXUS Bitcoin Privacy Guard v1

## Purpose

The optional monitor highlights one network condition relevant to Bitcoin Core transaction-rebroadcast / IP-correlation reports: whether the current Bitcoin Core peer snapshot contains IPv4/IPv6 peers marked as transaction-relay capable.

It is an advisory monitor, not an anonymity system and not a complete mitigation.

## Activation

The feature is disabled unless the operator explicitly sets:

```text
NEXUS_BITCOIN_PRIVACY_GUARD=1
```

When enabled before NEXUS starts, the optional endpoint is registered:

```text
GET /api/blockchain/nodes/bitcoin/privacy
```

The endpoint performs no background polling. A request reuses the existing Bitcoin Core telemetry routine and its existing loopback-only RPC calls. No additional RPC methods are introduced.

## What is inspected

Only aggregate-safe fields from the existing `getpeerinfo` response are used:

- `network`: network family (for example `ipv4`, `ipv6`, `onion`, `i2p`).
- `relaytxes`: whether transaction relay is enabled for that peer.
- `connection_type`: used only to recognize an explicitly marked `block-relay-only` connection when `relaytxes` is absent.

Peer IPs, ports, IDs, user agents, wallet addresses, transaction IDs, raw peer objects and credentials are not returned or persisted by the analyzer.

## Assessment states

- `conditional_clearnet_relay_exposure`: at least one IPv4/IPv6 peer is marked transaction-relay capable. If a Bitcoin Core wallet tracks a previously used address and automatically rebroadcasts an unconfirmed transaction, a network observer may be able to correlate that activity with the node.
- `clearnet_peers_without_tx_relay_observed`: clearnet peers exist but none is marked transaction-relay capable in this snapshot. This is lower observed exposure, not a safety guarantee.
- `review_required`: clearnet peer relay metadata is incomplete.
- `no_clearnet_peers_observed`: no IPv4/IPv6 peers were observed in this particular snapshot. This does not prove Tor/I2P-only routing over time.
- `no_peer_evidence` / `insufficient_peer_data`: there is not enough evidence to assess the topology.

The output always identifies wallet state and wallet rebroadcast settings as `not_inspected`.

## Explicit non-actions

This feature does not:

- Read, unlock, decrypt, export, import or change any wallet or key material.
- Change wallet encryption/decryption, KDF, lock/unlock, backup, recovery, APIs or signing.
- Create, sign, broadcast or rebroadcast transactions.
- Read transaction history or tracked addresses.
- Change Bitcoin Core configuration, `-walletbroadcast`, firewall rules, Tor/I2P settings, routes or DNS.
- Start, stop, pause or restart NEXUS services, workers or miners.
- Register a Lifecycle Manager service or run any periodic/background task.

When disabled or when telemetry is unavailable, existing NEXUS behavior remains unchanged. Analyzer errors are contained and yield an unknown assessment.

## Important limitations

This is an on-demand peer-topology snapshot only. It cannot establish the public IP, prove the full network route, determine whether a wallet tracks an address, or inspect the effective `walletbroadcast` setting. It cannot guarantee that future peers will use the same network types. It must never label the wallet safe solely because no clearnet peer was observed.

Do not apply `-walletbroadcast=0` automatically: it also prevents a wallet from broadcasting its initial outgoing transactions. Any enforcement or Bitcoin Core configuration change requires a separate owner-approved task after an explicit compatibility review.

## Compatibility strategy

- Existing `GET /api/blockchain/nodes/bitcoin` response and default behavior remain unchanged.
- The new endpoint is registered only when `NEXUS_BITCOIN_PRIVACY_GUARD=1`.
- No new dependencies or lifecycle services are introduced.
- Unit tests exercise the pure analyzer with synthetic peer metadata; no real wallet, Bitcoin Core node, transaction or network probe is required.
