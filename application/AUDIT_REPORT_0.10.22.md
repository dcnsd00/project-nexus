# NEXUS MASTER 0.10.22 — audit of hybrid mining foundation

## Scope changed
- Added `mining/hybrid_orchestrator.py`.
- Added `POST /api/mining/hybrid/plan`.
- Added manifest entry and dashboard version bump to 0.10.22.
- Added unit/API tests and release notes.

## Architecture
- CPU lane: RandomX, routed to an installed XMRig or SRBMiner backend.
- GPU lane: independently routed to an installed GPU backend (SRBMiner, Rigel, BzMiner, lolMiner, GMiner, T-Rex or TeamRedMiner) only when the pool declaration and existing compatibility gate agree.
- The existing compatibility gate continues to enforce device/algorithm restrictions and available DAG/VRAM checks.
- GPU switching is represented as a policy only; automatic switching is disabled pending measured profitability, thermal/power controls and accepted-share validation.

## Critical execution limitation
The current legacy `mining.controller` owns one managed process (`_proc` and one `_state`). Therefore 0.10.22 deliberately returns `execution=plan_only` and `simultaneous_execution_enabled=false`. The new endpoint does not launch either engine. A real dual-run requires a multi-process supervisor with per-engine lifecycle, independent stop/restart/rollback, telemetry aggregation and safe shutdown. This release does not claim simultaneous CPU+GPU mining.

## Verification
- `python -m pytest -q`: 277 passed.
- `python -m compileall -q mining nexus_master.py`: passed.
- API smoke test for `/api/mining/hybrid/plan`: HTTP 200; returned `plan_only`; no backends were detected in the build container, so both lanes reported `no_compatible_backend`.
- No user hardware, public pool authorization, accepted shares, payouts, thermal stability or power draw were tested in this environment.
