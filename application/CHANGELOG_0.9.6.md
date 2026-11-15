# NEXUS MASTER 0.9.6

- Added explicit `POOL` and `SOLO_POOL` mining modes.
- Solo mode is accepted only for catalog entries whose mode explicitly includes `SOLO`.
- Added `/api/mining/solo-readiness`; local-node solo mining is honestly marked unavailable until a synchronized full node, authenticated RPC and Stratum/proxy adapter are integrated.
- Mining dashboard now hides custom host/port/algorithm fields unless the Custom endpoint is selected; TLS is disabled when the catalog has no confirmed TLS port.
- Added Windows x64 PyInstaller onedir build spec, Windows build script, installer script and Python/pywebview fallback.
- Added tests for solo-pool eligibility, safe config generation and version endpoint.

## Important
Solo mining changes reward variance; it does not increase hash throughput or mathematical solver speed. No actual block was mined or payout claimed in offline benchmark tests.
