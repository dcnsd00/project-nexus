# NEXUS AI Workers and Mining Safety — 0.10.27

**Base:** `main` at `516bb3ca7859159c962b455e55cded01e51d9224`  
**Candidate:** `feature/nexus-ai-worker-mining-safety-v1`  
**Status:** candidate implementation; CI and target laptop validation remain separate gates.

## AI worker architecture

This increment adds a framework-neutral registry for 11 domain specialists and deterministic task routing by repository path, feature branch or explicit domain. Mutating tasks request QA/security review and require human review.

It is **not yet a running multi-agent system**: the registry reports zero configured model providers, zero active agents and route-preview-only mode. No model is invoked, and no worker can write to GitHub, execute shell commands, start miners, unlock wallets, sign transactions or broadcast transactions. Provider adapters must be configured, tested and permissioned in a separate increment.

Frameworks to evaluate as optional integrations:

- [LangGraph](https://github.com/langchain-ai/langgraph): MIT, stateful agent/workflow graph and checkpointing; brings LangChain runtime dependencies.
- [CrewAI](https://github.com/crewAIInc/crewAI): MIT, agent/task/flow structure and local-model connectors; assess its runtime and permission model before adoption.
- [Microsoft Agent Framework](https://github.com/microsoft/agent-framework): MIT, Python/.NET agent runtime; retain as optional until the dependency footprint and Windows frozen-package compatibility are tested.

The registry is deliberately dependency-free and preserves the local-first modular-monolith design.

## Mining safety changes

- One `HybridSupervisor` instance is injected into the API and lifecycle runtime.
- CPU preflight requires identifiable local CPU temperature telemetry.
- GPU preflight requires NVIDIA telemetry, VRAM headroom and temperature below the configured ceiling.
- A local monitor watches only NEXUS-managed workers. It remains idle while no worker is active and stops the affected CPU/GPU lane if temperature exceeds the ceiling or required telemetry disappears.
- Default CPU/GPU ceiling: 85°C. Optional overrides: `NEXUS_MINING_CPU_MAX_TEMP_C` and `NEXUS_MINING_GPU_MAX_TEMP_C`, accepted range 50–105°C.
- No automatic overclock, undervolt, fan-curve change or power-limit increase is performed.

Windows CPU sensors are read through the configured LibreHardwareMonitor WMI source when available. GPU telemetry uses `nvidia-smi`. Missing sensors fail closed.

## Benchmark provenance

The external XMRig benchmark record `5dq62x` reports RandomX 1,747.75 H/s, 4 worker threads, an ASUS TUF Gaming F15 FX506LHB and Intel Core i5-10300H with 16 GB RAM. XMRig marks it validated by its benchmark service. It is an external record submitted approximately two years before retrieval on 2026-11-26, not a measurement from this NEXUS laptop session.

Source: https://xmrig.com/benchmark/5dq62x

## Source reuse policy

- [XMRig](https://github.com/xmrig/xmrig) is GPL-3.0 and supports RandomX and other PoW algorithms including KawPoW. NEXUS retains process adapters by default; code copying/static linking needs a GPL compliance review.
- [3d-force-graph](https://github.com/vasturiano/3d-force-graph) is MIT and uses Three.js/WebGL for a 3D force-directed graph. It is a candidate for Synapse Explorer; pin a version, vendor locally and include its MIT notice before packaging.
- Mining binaries remain sourced from official releases and must undergo hash/signature and compatibility checks. This increment does not download or execute miners.

## Validation boundary

- Unit/API tests use simulated telemetry and mock workers; they do not validate physical laptop temperatures or sustained hashrate.
- Pool reachability, authorization, accepted shares and payout remain untested until a separately authorized live-pool session.
- GitHub Actions success is not proof of a Windows laptop installation or hardware validation.
