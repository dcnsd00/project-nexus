# NEXUS Bitcoin Privacy Guard v1

## Purpose

The optional monitor highlights one network condition relevant to Bitcoin Core transaction-rebroadcast / IP-correlation reports: whether the current Bitcoin Core peer snapshot contains IPv4/IPv6 peers marked as transaction-relay capable.

It is an advisory monitor, not an anonymity system and not a complete mitigation.

## Activation

The feature is disabled unless the operator explicitly sets:

\x60\x60\x60text
NEXUS_BITCOIN_PRIVACY_GUARD=1
\x60\x60\x60

When enabled before NEXUS starts, the optional endpoint is registered:

\x60\x60\x60text
GET /api/blockchain/nodes/bitcoin/privacy
\x60\x60\x60

The endpoint performs no background polling. A request reuses the existing Bitcoin Core telemetry routine and its existing loopback-only RPC calls. No additional RPC methods are introduced.

## What is inspected

Only aggregate-safe fields from the existing \x60getpeerinfo\x60 response are used:

- \x60network\x60: network family (for example \x60ipv4\x60, \x60ipv6\x60, \x60onion\x60, \x60i2p\x60).
- \x60relaytxes\x60: whether transaction relay is enabled for that peer.
- \x60connection_type\x60: used only to recognize an explicitly marked \x60block-relay-only\x60 connection when \x60relaytxes\x60 is absent.

Peer IPs, ports, IDs, user agents, wallet addresses, transaction IDs, raw peer objects and credentials are not returned or persisted by the analyzer.

## Assessment states

- \x60conditional_clearnet_relay_exposure\x60: at least one IPv4/IPv6 peer is marked transaction-relay capable. If a Bitcoin Core wallet tracks a previously used address and automatically rebroadcasts an unconfirmed transaction, a network observer may be able to correlate that activity with the node.
- \x60clearnet_peers_without_tx_relay_observed\x60: clearnet peers exist but none is marked transaction-relay capable in this snapshot. This is lower observed exposure, not a safety guarantee.
- \x60review_required\x60: clearnet peer relay metadata is incomplete.
- \x60no_clearnet_peers_observed\x60: no IPv4/IPv6 peers were observed in this particular snapshot. This does not prove Tor/I2P-only routing over time.
- \x60no_peer_evidence\x60 / \x60insufficient_peer_data\x60: there is not enough evidence to assess the topology.

The output always identifies wallet state and wallet rebroadcast settings as \x60not_inspected\x60.

## Explicit non-actions

This feature does not:

- Read, unlock, decrypt, export, import or change any wallet or key material.
- Change wallet encryption/decryption, KDF, lock/unlock, backup, recovery, APIs or signing.
- Create, sign, broadcast or rebroadcast transactions.
- Read transaction history or tracked addresses.
- Change Bitcoin Core configuration, \x60-walletbroadcast\x60, firewall rules, Tor/I2P settings, routes or DNS.
- Start, stop, pause or restart NEXUS services, workers or miners.
- Register a Lifecycle Manager service or run any periodic/background task.

When disabled or when telemetry is unavailable, existing NEXUS behavior remains unchanged. Analyzer errors are contained and yield an unknown assessment.

## Important limitations

This is an on-demand peer-topology snapshot only. It cannot establish the public IP, prove the full network route, determine whether a wallet tracks an address, or inspect the effective \x60walletbroadcast\x60 setting. It cannot guarantee that future peers will use the same network types. It must never label the wallet safe solely because no clearnet peer was observed.

Do not apply \x60-walletbroadcast=0\x60 automatically: it also prevents a wallet from broadcasting its initial outgoing transactions. Any enforcement or Bitcoin Core configuration change requires a separate owner-approved task after an explicit compatibility review.

## Compatibility strategy

- Existing \x60GET /api/blockchain/nodes/bitcoin\x60 response and default behavior remain unchanged.
- The new endpoint is registered only when \x60NEXUS_BITCOIN_PRIVACY_GUARD=1\x60.
- No new dependencies or lifecycle services are introduced.
- Unit tests exercise the pure analyzer with synthetic peer metadata; no real wallet, Bitcoin Core node, transaction or network probe is required.
