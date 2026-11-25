# PROJECT NEXUS LOCAL 0.5.0

Local-first NEXUS workbench. This milestone consolidates the mathematical engine, a synthetic banking test environment, and a 26-entry integration/plugin registry.

## Windows 11 setup

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn app.main:app --host 127.0.0.1 --port 8765
```
Open `http://127.0.0.1:8765`.

## Network boundary

CORE installs an ASGI loopback guard in addition to the documented loopback
bind. Requests are accepted only when both the TCP peer and the Host authority
are loopback addresses or `localhost`. A request from a LAN/WAN peer is
rejected with HTTP 403 even if it forges `X-Forwarded-For` or supplies a
loopback Host value. Proxy headers are not used as client identity.

Any future private-network access must pass through the NEXUS Caddy/Coraza
proxy. Caddy rewrites the upstream Host authority to `127.0.0.1:8765`, while
the local proxy remains the TCP peer seen by CORE.

This guard is an exposure boundary, **not user authentication**. It does not
protect against other software already running on the same host. Keep CORE
bound to loopback and do not expose the listener directly to LAN/WAN.

## Milestone 0.5 additions

- Plugin Manager: 26 integration definitions across AI, EVM, Bitcoin, Solana, Binance public data, DePIN, NFT/IPFS, banking sandbox, GitHub/GitLab, Microsoft/Google, messaging, monitoring, SageMath and Wolfram.
- Connector states distinguish configured credentials, public endpoint availability, and adapters still pending. A configured key does not mean the connector is operational.
- Synthetic banking sandbox with 3 fictional accounts and 5 fictional transactions; exact-decimal ledger and cash-flow analysis.
- Banking simulation suite with 6 deterministic checks.
- Read-only-first integration policy. No signing, transfers, payment execution, or unattended device control.

## Current API

- `GET /api/health`
- `GET /api/plugins`
- `GET /api/banking/sandbox`
- `GET /api/banking/analysis`
- `POST /api/banking/simulate`
- `GET /api/math/status`
- `POST /api/math/compute`
- `POST /api/math/matrix`
- `POST /api/math/probability`
- `POST /api/math/number-theory`
- `POST /api/math/optimize`
- `POST /api/math/decode`
- `POST /api/math/sage` (requires separately installed SageMath)

## Important integration status

The registry is a catalogue and configuration detector, not 26 fully implemented live connectors. Public market/blockchain adapters and each provider-specific DePIN parser still need implementation against official documentation and credentials. ChatGPT's own connected plugins/connectors are not automatically exposed to a separate local Python program; they require their own supported APIs, OAuth flows, or MCP servers. Never paste API secrets, passwords, wallet private keys or seed phrases into the chat or browser UI.

Open Banking is currently a synthetic sandbox only. Real bank data requires a regulated Open Banking provider, user consent, OAuth and provider sandbox certification. This build does not connect to BRD or any live bank and cannot initiate payments.

## Simulation / verification performed for this milestone

- Python compilation passed for main application, mathematical engine, banking sandbox and plugin registry.
- FastAPI TestClient returned HTTP 200 for health, plugin registry, banking ledger, banking analysis and math status.
- Banking simulation: 6/6 passed. It verifies synthetic-only isolation, three accounts, exact cash-flow arithmetic, transaction/account references, positive amounts and deterministic replay.
- No real banking API, DePIN provider, blockchain RPC or OAuth integration was called in this test suite.
- SageMath remains optional and must be installed separately.

## Security posture

- Local bind to `127.0.0.1`.
- No private-key storage or transaction signing.
- External write operations require a fresh, operation-specific owner approval in the future integration layer.
- This is a development build, not a production-certified financial application. Do not expose it to the public internet without authentication, TLS, rate limiting, secret management and security review.
