# NEXUS private mesh policy scaffold

This directory contains a deliberately **deny-all** Headscale policy starting
point. It is not a complete working VPN deployment and is not loaded by NEXUS
automatically.

## Why this file starts with deny-all

Headscale allows traffic between nodes when no policy is loaded. A policy file
that omits both `acls` and `grants` also defaults to allow-all. The empty
`grants` array below is an explicit deny-all policy.

Do not replace it with `{}`, remove the policy file, or expose Headscale before
an explicit least-privilege policy is reviewed.

## Intended NEXUS topology

- Control plane: self-hosted Headscale service on a hardened host.
- Supported user devices: Windows/Linux devices running supported Tailscale clients.
- Application access: allow only the specific NEXUS CORE/EDGE service ports needed
  by designated peer identities.
- ESP32/ESP32-C5 nodes: do not assume a Tailscale/Headscale client is available.
  Keep their transport on the EDGE HTTPS/MQTTS adapter with HMAC identity,
  anti-replay, leases and capability checks; if router-level site-to-site
  connectivity is required, evaluate WireGuard on the routers rather than on
  the microcontroller.
- Public ingress: do not publish NEXUS management endpoints. Reach them through
  the private mesh and a separate authentication layer.

## Before adding any allow rule

1. Assign stable Headscale tags to the NEXUS control host and each managed peer.
2. Define exact source and destination tags, protocol and destination ports.
3. Keep peer-to-peer traffic denied by default.
4. Keep control-plane administration separate from application traffic.
5. Test policy parsing and connectivity with a non-production peer first.
6. Verify node revocation, key expiry, backup/restore and recovery.
7. Review the current Headscale release notes and client compatibility before
   deployment; this repository does not pin or deploy Headscale itself.

The initial policy is intentionally unusable for data-plane communication
until explicit rules are added. This is safer than silently inheriting
Headscale's no-policy allow-all behavior.
