# NEXUS MASTER 0.10.22

## Hybrid CPU/GPU orchestration foundation
- Added `mining/hybrid_orchestrator.py` to model CPU RandomX and independent GPU PoW engines.
- Added `/api/mining/hybrid/plan` preflight endpoint. It selects only installed backends that pass the existing pool/device compatibility gate.
- GPU algorithms can be planned independently of the CPU RandomX engine; the policy requires pool/algorithm match, DAG/VRAM margin, thermal/power limits and accepted-share evidence before any future automatic switching.
- The endpoint is explicitly **plan-only**. It does not start miners. The legacy `mining.controller` still supervises one process, so simultaneous CPU+GPU execution is not claimed or enabled in this release.
- Added tests for independent engine routing, unsupported CPU algorithm rejection and unavailable GPU backend handling.
