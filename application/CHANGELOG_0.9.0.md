# Changelog NEXUS 0.9.0

## Mining control
- Added supervised process lifecycle for XMRig (CPU), SRBMiner-MULTI and T-Rex (NVIDIA GPU).
- Added local miner inventory and detection for XMRig, SRBMiner-MULTI, T-Rex, lolMiner, GMiner, Rigel and TeamRedMiner.
- Added status, uptime, local hashrate, share counters, CPU/RAM/process metrics and NVIDIA telemetry where available.
- Added log capture, bounded tail view and error classification with corrective guidance.
- Added coin/pool/miner compatibility filtering in the dashboard and coin-to-mining shortcut from the catalog.

## Pool catalogue
- Added WoolyPooly RVN (`pool.woolypooly.com:55555`), ETC (`:35000`) and KAS (`:3112`) endpoints.
- Retained 2Miners RVN/KAS/ETC regional endpoints and custom Stratum option.
- TLS ports remain unset when not independently confirmed; selecting TLS without a known TLS port is rejected.

## Safety and scope
- No miner binary is bundled or downloaded automatically.
- T-Rex uses a local-only API and an 82°C GPU temperature limit / 72°C restart threshold.
- XMRig is restricted to CPU mode in this build.
- No automatic mining restart on failure; errors are classified and surfaced for user review.
- No public blockchain transactions or wallet keys are involved in mining control.
