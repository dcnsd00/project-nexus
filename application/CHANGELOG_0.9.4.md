# NEXUS MASTER 0.9.4

## Mining control and dashboard
- Added global mining dashboard: managed miner, coin/algorithm, local hashrate, accepted/rejected shares, uptime, CPU/RAM/GPU telemetry and detected external mining processes.
- Added read-only 2Miners account lookup for RVN/KAS/ETC with balance, immature, paid and 24h reward fields. The API returns raw provider units plus configured decimal conversion and source metadata.
- Added strict coin/pool/algorithm/miner/device compatibility endpoint and server-side launch gate. XMRig is CPU-only and no longer advertised as a KawPoW miner.
- Corrected SRBMiner command construction: wallet and worker are separate arguments; TLS, API and log flags are explicit.
- Added measured A/B optimization ledger with hashrate delta, accepted/rejected share rates, power efficiency and temperature fields. No automatic tuning or unverified math kernel is applied.
- Fixed configuration output rendering and stale fake command logs.

## Desktop
- Added optional pywebview desktop shell using the same local FastAPI API and existing web integrations.
- Windows installer creates a `NEXUS Desktop` shortcut targeting pythonw, keeping the console window hidden. Browser BAT remains a fallback.

## Safety and validation
- Pool algorithm cannot be silently overridden in a normal pool profile.
- A/B trials are measurement-only and never marked eligible for live mining automatically.
- Pool account integration is read-only and only supports 2Miners in this milestone.

- Added dated DAG/VRAM gate: current RVN KawPoW and ETC Etchash jobs are blocked on GPUs whose VRAM is below the DAG plus runtime reserve.
