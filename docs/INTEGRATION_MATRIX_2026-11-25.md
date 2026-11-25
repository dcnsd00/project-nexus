# NEXUS MASTER — integration and tool matrix (2026-11-25)

## Connected project sources

| Tool | Current state | Verified capability in this session | NEXUS boundary |
|---|---|---|---|
| GitHub | Connected and functional | Read repository, branches, PRs, issues, commits, workflow runs; create isolated branches and PRs | Source of truth for code, CI and release state. No merge to main without review. |
| Notion | Connected and functional | Read architecture/audit/handoff pages and append a continuity update | Documentation and planning; not a substitute for repository state. |
| Unabyss | Connected and functional | whoami/query/agentic_query/store; latest store operations queued for indexing | Durable cross-tool context. GitHub remains code source of truth. |
| Binance | Public market-data tools active | Live read-only data returned for BTC, ETH, SOL, BNB, XRP, ZEC, DOGE and LINK | No account credentials, order placement, transfers or signing. App-side adapter is in PR #23, not yet on main. |
| Gate Info | Public market-data tools active | Live read-only market overview and snapshots returned | No account credentials, order placement, transfers or signing. Shared app-side adapter is in PR #23, not yet on main. |
| VisionEdge AIScan | Connected and functional | Current-main full scan B/78; targeted PR #23 scan A/100 | Findings require manual triage; no automatic code remediation. |
| Blockscout | MCP initialized; PRO quota exhausted | Initialization succeeded; Base chain read failed with HTTP 402 (PRO credits exhausted) | No chain data validated. Restore PRO credits before claiming operational. Keep read-only. |

## Deployment and host access

| Tool | Current state | Verified capability | Boundary |
|---|---|---|---|
| AppDeploy | Crypto Agent is deployed | Existing Crypto Agent deployment is the only deployment asserted here | NEXUS Control Center is NOT declared deployed. Do not move secrets, wallets or mining processes to AppDeploy. |
| Bridge | Direct mode enabled | Host discovery returned zero registered hosts | Cannot install or validate the Windows package on the owner's laptop until a host is registered. |
| Supabase | Plugin installed/enabled | Project listing returned an empty project list | No NEXUS Supabase project exists in the connected account result. Do not create a new backend without architecture review. |
| Vercel | Plugin installed/enabled | Team/deployment context returned no teams | No NEXUS Control Center deployment is established. |

## Additional available research/build tools

- Data, Firecrawl and TinyFish are installed/enabled and can support analysis or public-site research; they are not NEXUS runtime integrations by themselves.
- GitLab is available, but the canonical NEXUS repository is GitHub: dcnsd00/project-nexus.
- MagicPath, Lovable, Replit and other app-building tools are not a reason to create a parallel NEXUS app. Keep the modular monolith and existing desktop path.
- No video generation, InVideo, YouTube or Unseen Frontier activity was performed; those projects remain HOLD.

## Operating rules

1. Distinguish a connected ChatGPT tool from an adapter implemented inside NEXUS.
2. Distinguish source presence, route registration, runtime registration, tests, integration tests and real-host validation.
3. Keep Binance/Gate research public and read-only. Paper trading remains virtual with 100 RON; no real orders.
4. Keep wallet signing, transfers, public-pool payouts, hardware activation, VPN, WAF enforcement and CrowdSec disabled until their separate acceptance gates pass.
5. Do not store or expose API keys in chat, source control, issue comments or deployment logs. Configure secrets only through an approved local/secret-manager flow.
6. Do not claim NEXUS Control Center is deployed based on Crypto Agent deployment.