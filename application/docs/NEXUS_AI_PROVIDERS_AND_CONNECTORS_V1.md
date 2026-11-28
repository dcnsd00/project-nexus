# NEXUS MASTER — AI providers and external connectors v1

## Scope and status model

This change extends the existing NEXUS AI Worker Coordinator and integration registry. It does not create a parallel application or replace the existing service graph.

The worker registry contains 11 stateless profiles: one central coordinator and ten domain specialists. A profile is invoked for a bounded task; it is not a permanently running operating-system process. The provider adapter is text-only: it does not send tool definitions and grants no repository write, shell, miner, wallet, signing, transaction-broadcast or third-party write permission.

Connector adapters are read-only HTTP GET adapters. They do not submit jobs, change account settings, transfer tokens, sign transactions or issue mining commands.

NEXUS distinguishes the following states:

- `registered`: the provider/worker profile exists in source.
- `configured_not_live_verified`: required configuration is present and passes local validation.
- `live_verified`: an explicit request has completed a real bounded HTTP/model round-trip with a valid response.
- `operational_verified`: the service passes its applicable functional checks in its target runtime. A mocked unit test or environment-variable presence alone is not sufficient.

AI provider live verification and connector live verification are held in process memory and expire after 15 minutes. Restarting NEXUS therefore requires a new probe. This is intentional: the system does not persist a stale connectivity claim.


## Local open-weight AI runtime — NEXUS MASTER integration

NEXUS MASTER reuses the existing `application/core/PROJECT-NEXUS-LOCAL/app/lfm3_local.py` implementation and connects the same LFM3 model family to the shared AI Worker Coordinator provider contract. This avoids a second independent agent framework.

### Local model runtimes

- **llama.cpp server**: OpenAI-compatible local endpoint, default `http://127.0.0.1:8080/v1`. Select it with `NEXUS_AI_PROVIDER=lfm3-local`.
- **Ollama**: native local `/api/chat` endpoint, default `http://127.0.0.1:11434/api`. Select it with `NEXUS_AI_PROVIDER=ollama`.
- Both choices are local-first and require no hosted model API key when bound to loopback.
- Remote/private-network inference endpoints remain opt-in and must pass HTTPS, exact host allowlisting and API-key checks.

### First local model configuration

For the LFM3 Q4 GGUF through llama.cpp:

```dotenv
NEXUS_AI_PROVIDER=lfm3-local
NEXUS_LFM3_BASE_URL=http://127.0.0.1:8080
NEXUS_LFM3_MODEL=LiquidAI/LFM3-1.7B-GGUF:Q4_K_M
```

For LFM3 through Ollama:

```dotenv
NEXUS_AI_PROVIDER=ollama
NEXUS_AI_BASE_URL=http://127.0.0.1:11434/api
NEXUS_AI_MODEL=lfm3
```

The LFM3 Q4 GGUF published by LiquidAI is approximately 1.1 GB. Its advertised 256K context is not automatically enabled by NEXUS; the context and generation budget must be benchmarked against available VRAM/RAM. On a 4 GB GPU, start with a conservative context and CPU/GPU offload rather than assuming the full 256K context will fit.

### Local model roles in the catalogue

- `lfm3-text`: fast local coordinator/specialist model; 1.7B, agent-oriented and small enough for edge-style inference. Liquid AI does not recommend it as the sole model for difficult agentic coding or complex multi-step reasoning.
- `qwen3-4b`: balanced 4B local model for coding, maths, multilingual tasks and general reasoning. Ollama's library lists an approximately 2.5 GB package; model size is not total RAM/VRAM use.
- `deepseek-r1-1-5b`: small reasoning/distillation model for constrained devices and mathematical cross-checks; not a substitute for a larger coding model.
- `deepseek-r1-7b`: stronger reasoning option; its approximately 4.7 GB package already exceeds 4 GB VRAM before the runtime and KV cache, so expect CPU/partial GPU offload.
- `gpt-oss-20b`: higher-capacity local reasoning and agentic model; 21B total / 3.6B active, Apache 2.0 plus its usage policy. Ollama lists a 14 GB model package and 128K context. It is not suitable for full GPU residency on the GTX 1650 4 GB.
- `lfm3-vision`, `lfm3-audio`, `lfm3-omni`: listed as future specialist pipelines. They are not wired to the current text-only worker API. Each needs the right model artifacts, multimodal adapter and acceptance tests.

For the current low-VRAM target, use LFM3 or DeepSeek-R1 1.5B for lightweight tasks and benchmark Qwen3-4B with a small context/CPU offload. Keep GPT-OSS 20B as an optional target for a larger-memory host. Do not infer model suitability from parameter count alone; measure RAM, VRAM, context, throughput and thermal behaviour on the target computer.

The relevant model-weight licenses are distinct: LFM3 uses **LFM Open License v1.0** (not standard Apache 2.0, with a USD 10 million annual company-revenue condition for free commercial use); GPT-OSS uses Apache 2.0 plus its usage policy; Qwen3 uses Apache 2.0; DeepSeek-R1 declares MIT, while the distilled Qwen variants also require preserving the Qwen2.5 base-model licensing notice. The **Ollama runtime** and **llama.cpp runtime** are MIT-licensed. A runtime's MIT license does not replace a model's weight license.

### Full coordinated dispatch across all 11 profiles

The coordinated execution endpoint accepts up to all 10 specialist domains in one request. With all ten selected, NEXUS invokes:
1. the central coordinator for task decomposition;
2. nine specialist profiles sequentially;
3. the QA/security profile once, as the final independent reviewer.

This is exactly 11 model calls across the 11 registered profiles; the QA profile is not called twice. The response includes an `execution_manifest` listing requested/invoked profiles, call count and sequential execution status. The API remains loopback-only and all calls are text-only. It does not create 11 permanent background processes.

The full specialist domain list is: `mining`, `cryptography`, `blockchain`, `wallet`, `edge`, `integrations`, `dashboard`, `earnings`, `ai_platform`, `quality`. A full run can be slower and consume more tokens than a single-specialist dispatch.

### Worker-specific model selection

The 11 stateless profiles use these domains for model overrides:

- `NEXUS_AI_MODEL_COORDINATION`
- `NEXUS_AI_MODEL_MINING`
- `NEXUS_AI_MODEL_CRYPTOGRAPHY`
- `NEXUS_AI_MODEL_BLOCKCHAIN`
- `NEXUS_AI_MODEL_WALLET`
- `NEXUS_AI_MODEL_EDGE`
- `NEXUS_AI_MODEL_INTEGRATIONS`
- `NEXUS_AI_MODEL_DASHBOARD`
- `NEXUS_AI_MODEL_EARNINGS`
- `NEXUS_AI_MODEL_AI_PLATFORM`
- `NEXUS_AI_MODEL_QUALITY`

Example for Ollama multi-model routing:

```dotenv
NEXUS_AI_PROVIDER=ollama
NEXUS_AI_MODEL=lfm3
NEXUS_AI_CONTEXT_TOKENS=8192
NEXUS_AI_MODEL_COORDINATION=lfm3
NEXUS_AI_MODEL_MINING=qwen3:4b
NEXUS_AI_MODEL_CRYPTOGRAPHY=deepseek-r1:7b
NEXUS_AI_MODEL_AI_PLATFORM=gpt-oss:20b
NEXUS_AI_MODEL_QUALITY=gpt-oss:20b
```

Only set a per-domain model after it is installed and validated by the Ollama runtime. For a single-model `llama.cpp` server, NEXUS pins every worker to the loaded LFM3 model and ignores per-domain overrides; a separate server/port is required to host a different checkpoint independently.

For Ollama, `NEXUS_AI_CONTEXT_TOKENS` defaults to 8192 and is bounded from 1024 to 262144. This controls the `num_ctx` option; a model's advertised maximum context is not automatically allocated.

### Owner-controlled instructions

Set `NEXUS_AI_OWNER_INSTRUCTIONS` in the machine-local environment to give the coordinator and all 10 specialist profiles persistent working preferences (maximum 4,000 characters). For example:

```dotenv
NEXUS_AI_OWNER_INSTRUCTIONS=Răspunde în română. Prioritizează implementarea NEXUS MASTER. Pentru cererile tehnice permise, oferă cod complet, teste și căi exacte din repository. Separă faptele verificate de ipoteze.
```

These instructions are injected into the coordinator and each specialist system prompt. They can change language, domain priorities, response style and the degree of implementation detail. They do not silently grant shell, repository-write, miner, wallet-signing or external-write permissions. Model behaviour still depends on the selected model's own training and license; running locally does not guarantee that every model has no built-in refusals.

### Local AI endpoints

- `GET /api/nexus/workers/local-models` — catalogue, model roles, runtime IDs and license notes. No downloads occur.
- `GET /api/nexus/workers/local-runtime-status` — checks only loopback Ollama and llama.cpp endpoints, and reports installed model IDs. It does not load a model or start a runtime.
- `POST /api/nexus/workers/local-models/{profile_id}/pull` — explicitly asks an already-running local Ollama instance to pull one of five allowlisted text models (LFM3, Qwen3-4B, DeepSeek-R1 Distill 1.5B/7B or GPT-OSS-20B). It does not install Ollama or start the Ollama service.
- `GET /api/nexus/workers/local-models/pulls/{profile_id}` — reports the local Ollama pull status and byte progress while NEXUS remains running.
- `GET /api/nexus/workers/provider-status` — status of the selected provider.
- `POST /api/nexus/workers/provider-test` — a real inference round-trip against the selected model.
- `POST /api/nexus/workers/self-test` — provider probe plus one actual model call through each of the 11 worker profiles.
- `POST /api/nexus/workers/coordinate` — central decomposition, up to all ten specialist profiles, and a final QA/security review; the full 11-profile run returns an execution manifest.

The model catalogue and runtime discovery do not install weights, run shell commands, start background daemons or download model artifacts. Model downloads and runtime installation remain explicit owner actions.

Model pulls are explicit, local-only owner actions. NEXUS first verifies that the configured Ollama API is already reachable on loopback, then sends the fixed catalog model name to Ollama's `/api/pull` stream. Only one model pull may run at a time. The pull endpoint accepts a profile ID, not an arbitrary model name or URL. It does not use a shell, install the Ollama runtime, or start a service. Pull progress is held in memory and is available while this NEXUS process is running; a NEXUS restart does not preserve the in-memory progress handle. A completed download is not an inference test and does not set `operational_verified`.

Example: after Ollama is already installed and running on the same computer, request one catalogued model download and poll its progress:

```powershell
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/api/nexus/workers/local-models/qwen3-4b/pull"
Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:8000/api/nexus/workers/local-models/pulls/qwen3-4b"
```

Replace `qwen3-4b` with another profile ID from the catalog. This is an owner-initiated download request, not a command that NEXUS runs automatically. The API returns only the model pull state; run the provider test and all-worker self-test after the pull has completed.


### Owner-controlled model behaviour

Running the weights locally removes a dependency on hosted model APIs and their account/rate-limit layer. It does not guarantee a model has no trained-in refusals or limitations. NEXUS can expose owner instructions and choose models with different instruction-following behaviour, but system-level execution controls remain separate: no implicit shell access, arbitrary repository writes, wallet signing, transaction broadcast, external writes or miner start. These controls protect the local machine and funds; they are not a hosted model content filter.

## AI model provider configuration

All providers use the existing local NEXUS API:

- `GET /api/nexus/workers` — worker catalogue and safe readiness summary, including the latest 11-profile self-test status.
- `GET /api/nexus/workers/local-models` — local model catalogue and license details.
- `GET /api/nexus/workers/local-runtime-status` — loopback-only discovery of Ollama and llama.cpp servers.
- `GET /api/nexus/workers/provider-status` — provider configuration/live status (loopback-only).
- `POST /api/nexus/workers/provider-test` — perform a real minimal prompt/response probe (loopback-only).
- `POST /api/nexus/workers/self-test` — perform one provider probe and invoke all 11 profiles sequentially (loopback-only). This requires a configured, live-verified provider and consumes 12 model requests in total (one provider probe plus 11 worker calls).
- `POST /api/nexus/workers/execute` — dispatch one specialist (loopback-only).
- `POST /api/nexus/workers/coordinate` — central coordinator + up to all ten specialist domains + one final QA/security review (loopback-only).

The NEXUS specialist-worker provider defaults to disabled until the owner configures a provider. This does not replace or reconfigure the existing NEXUS host application's central orchestration path. To use a local Ollama endpoint for the specialist profiles, configure the values in the machine-local environment (do not commit secrets):

```dotenv
NEXUS_AI_PROVIDER=ollama
NEXUS_AI_MODEL=llama3.2:1b
# Optional; defaults to http://127.0.0.1:11434/api
NEXUS_AI_BASE_URL=http://127.0.0.1:11434/api
```

Native remote provider examples:

```dotenv
# OpenAI
NEXUS_AI_PROVIDER=openai
NEXUS_AI_MODEL=<model-id>
NEXUS_AI_API_KEY=<secret>
NEXUS_AI_ALLOW_REMOTE=1
NEXUS_AI_REMOTE_HOST_ALLOWLIST=api.openai.com

# Anthropic
NEXUS_AI_PROVIDER=anthropic
NEXUS_AI_MODEL=<model-id>
NEXUS_AI_API_KEY=<secret>
NEXUS_AI_ALLOW_REMOTE=1
NEXUS_AI_REMOTE_HOST_ALLOWLIST=api.anthropic.com
NEXUS_AI_ANTHROPIC_VERSION=2026-10-21

# Gemini
NEXUS_AI_PROVIDER=gemini
NEXUS_AI_MODEL=<model-id>
NEXUS_AI_API_KEY=<secret>
NEXUS_AI_ALLOW_REMOTE=1
NEXUS_AI_REMOTE_HOST_ALLOWLIST=generativelanguage.googleapis.com
```

Provider-native model/key fallback environment variables are also accepted where implemented: `OPENAI_MODEL`/`OPENAI_API_KEY`, `ANTHROPIC_MODEL`/`ANTHROPIC_API_KEY`, and `GEMINI_MODEL`/`GEMINI_API_KEY`. The generic `NEXUS_AI_MODEL` and `NEXUS_AI_API_KEY` take precedence.

OpenAI-compatible providers: `openai_compatible`, `groq`, `openrouter`, `mistral`, `together`, `deepseek`, `fireworks`, and `cerebras`. They use `NEXUS_AI_BASE_URL`, `NEXUS_AI_MODEL`, and `NEXUS_AI_API_KEY`, with the provider's exact API hostname in `NEXUS_AI_REMOTE_HOST_ALLOWLIST`. Local OpenAI-compatible runtimes (for example, a local inference server) may use a loopback URL and do not require remote access to be enabled.

Remote-provider safety checks require all of the following: HTTPS, port 443, `NEXUS_AI_ALLOW_REMOTE=1`, exact hostname allowlisting and an API key. Redirects are rejected; proxy environment variables are ignored by the transport; response bodies are bounded; error details do not include upstream response bodies or credentials.

Never put a production API key in a source file, Git commit, issue, chat message or test fixture. Use the machine-local environment or an approved secret manager.

### Worker domains

The 11 profiles are:

1. Central Coordinator — task decomposition, cross-domain synthesis and dependency planning.
2. Mining & Compute — mining algorithms, backend compatibility, benchmarks, pools and thermal/electric safety.
3. Cryptography & Mathematics — cryptographic review, hash benchmarks, statistics, mathematics and reproducible experiments.
4. Blockchain & On-chain Data — chain telemetry, block validation, RPC contracts and read-only data.
5. Wallet & Key Safety — vault integrity, key safety, watch-only analysis and recovery test design.
6. NEXUS EDGE & DePIN — EDGE protocols, replay protection, node lifecycle, telemetry and device integration.
7. Integrations & Market Data — provider contracts, freshness, source provenance and API research.
8. Dashboard & Synapse — dashboard UX, graph visualisation, replay and accessibility.
9. Earnings, Economics & Opportunity — rewards, profitability, power costs and payout evidence.
10. AI Worker Platform — orchestration, model adapters, tool permissions and agent evaluation.
11. QA, Security & Release Validation — test design, security, compatibility, build and release gates.

All specialist profiles are registered in code. Actual model execution requires a configured and live-tested provider. The central coordinator and specialists are stateless request handlers; the `active_ai_agents` count therefore remains zero for persistent background agents.

## External connector configuration

The registry contains 12 connector profiles: Acurast, Grass, AIOZ, Theta, Nodle, Helium IoT, GEODNET, Anyone, WeatherXM, Wingbits, Akash and Nosana.

Nine profiles now have at least one official API contract mapped to an explicit endpoint and response schema. Three profiles remain contract-pending: Acurast, Grass and Wingbits. Nodle now supports only the documented public token-supply endpoints; this does not implement personal device/reward data.

The following official, read-only contracts are mapped:
- **AIOZ:** `https://rpc-dataseed.aioz.network/status` — Tendermint status response (`node_info` and `sync_info`).
- **Theta:** `https://eth-rpc-api.thetatoken.org/rpc` — JSON-RPC POST using the read-only `eth_chainId` health method and `eth_blockNumber` public-chain resource.
- **Helium IoT:** `https://entities.nft.helium.io/v2/hotspots?subnetwork=iot` — hotspot entity list. The Helium Entity API does not itself expose the full rewards/oracle history, so this adapter does not claim rewards integration.
- **GEODNET:** `https://rawdata.geodnet.com/api/rawdata/v1/stations` — station list using HTTP Basic authentication with owner-supplied username/password.
- **Anyone:** `https://api.ec.anyone.tech/total-relays-latest` — public network relay counts.
- **WeatherXM:** `https://api.weatherxm.com/api/v1/network/stats` — public network statistics; account-specific station/reward reads require a user access token and still need resource-level schema acceptance.
- **Akash:** `https://console-api.akash.network/v1/providers` — public, read-only indexed provider data. This is not a chain node and cannot broadcast transactions.
- **Nosana:** `https://api.nosana.com/jobs/count` — read-only job counts, with an owner-supplied API key.

The nine default base URLs are trusted only when NEXUS itself selects the exact hard-coded documented default. If an owner overrides a base URL, the replacement host must be HTTPS on port 443 and explicitly allowlisted.

For a provider without a documented HTTP contract, configuration alone proves only reachability. Example shape for a future Acurast HTTP adapter:

```dotenv
NEXUS_ACURAST_API_URL=https://<official-api-host>/<base-path>
NEXUS_ACURAST_API_TOKEN=<secret>
NEXUS_CONNECTOR_ALLOWED_HOSTS_ACURAST=<official-api-host>
NEXUS_ACURAST_HEALTH_PATH=<documented-health-path>
```

Acurast's currently documented public mainnet RPC is WebSocket (`wss://public-rpc.mainnet.acurast.com`); this HTTP REST adapter does not yet implement the WebSocket protocol. Do not set an invented REST URL. Grass and Wingbits remain contract-pending until their official API endpoint, authentication and response schemas are established. Nodle's public `GET /v1/total-issuance` and `GET /v1/circulating-supply` return numeric supply values and are implemented as read-only resources. Nodle's separate IoT API is described as private beta and requires account onboarding/API-key setup; personal device/reward resources remain out of scope until their response schema and authorization are confirmed. Source: https://docs.nodle.com/nodle-apis.

Host allowlisting can be shared using `NEXUS_CONNECTOR_ALLOWED_HOSTS` or set per connector using `NEXUS_CONNECTOR_ALLOWED_HOSTS_<PROVIDER_ID>`. Remote hosts must use HTTPS on port 443 and match the allowlist exactly. A loopback endpoint may use HTTP for local development.

For token-backed providers, the default header is `Authorization: Bearer <token>`. Nosana requires `NEXUS_NOSANA_API_TOKEN`; WeatherXM accepts an optional access token for account resources. GEODNET uses `NEXUS_GEODNET_USERNAME` and `NEXUS_GEODNET_PASSWORD` and sends HTTP Basic authentication. Optional per-connector token settings are:

- `NEXUS_<PROVIDER_ID>_API_TOKEN_HEADER`: one of `Authorization`, `X-API-Key`, or `API-Key`.
- `NEXUS_<PROVIDER_ID>_API_AUTH_SCHEME`: defaults to `Bearer`.

The API surface is local-only:

- `GET /api/integrations/catalog` — connector list and readiness.
- `GET /api/integrations/status` — counts by readiness state.
- `POST /api/integrations/self-test` — probe the health resource of each of the 12 registered connectors (loopback-only). Only configured connectors with a valid health path can pass.
- `POST /api/integrations/{provider_id}/probe` — execute the provider's configured health operation (GET for REST connectors; a fixed read-only JSON-RPC POST for Theta).
- `GET /api/integrations/{provider_id}/read/{resource}` — read the configured resource. A resource is operationally verified only when its provider-specific response schema is also validated.

The `health` resource is configured with `NEXUS_<PROVIDER_ID>_HEALTH_PATH`. Other permitted resource names are in the provider catalog and their paths are configured with `NEXUS_<PROVIDER_ID>_<RESOURCE>_PATH`.

The adapter enforces loopback-only API access, exact host allowlisting, HTTPS for remote services, no redirects, no proxy environment inheritance, a 12-second timeout, a 1 MB response bound and JSON content-type/parse validation. It uses GET for REST and a fixed allowlisted read-only JSON-RPC POST for Theta. GEODNET's Basic credentials are encoded at runtime and never returned. Error payloads and secrets are not returned to clients.

## Vendor-specific integration boundary

The connector registry distinguishes three levels:
1. **Adapter registered** — NEXUS knows the provider ID and exposes the guarded connector surface.
2. **Reachability verified** — the configured endpoint returned bounded valid JSON.
3. **Contract verified / operational verified** — the response matched the provider-specific schema and the live proof is current.

A generic HTTP 200 or arbitrary JSON response is not enough for `operational_verified`. Acurast, Grass and Wingbits may report `reachable_contract_pending`, but remain pending until an official endpoint/auth/schema contract is implemented. Nodle's public supply API is validated against a numeric response contract; this must not be interpreted as personal account/reward verification. For the nine documented providers, only documented health schemas are accepted. User-specific resources that do not yet have their own response schema remain `read_succeeded_contract_pending`.

The current implementation does not claim provider-specific pagination, rate-limit/backoff, reward calculation, account normalization or freshness semantics for every vendor. Those require separate vendor contract work and real account/API tests.

## Acceptance gates

A provider can be considered live-verified only after a real provider call succeeds. A connector can be considered live-verified only after a real configured resource GET succeeds. CI contract tests use synthetic transport responses to validate request shape, fail-closed behaviour and safety boundaries; they do not prove that an external account/provider is reachable.

Before NEXUS can be labelled 100% operational, the release acceptance record must include:

1. Green Linux and Windows CI on the exact candidate commit.
2. All 11 profiles exercised through the real configured model provider, including coordinated specialist runs and QA review.
3. Real endpoint probes for every connector the owner intends to use, followed by schema-specific validation.
4. Windows local runtime start/stop and desktop/WebView acceptance on the target computer.
5. Hardware-in-the-loop tests for mining, EDGE/DePIN devices and any local broker/transport in scope.
6. Security review, regression suite and a current module/function acceptance matrix.

Until those gates have evidence, the correct state is partial implementation or pending operational validation—not 100%.


## Runtime operational verification

- `GET /api/nexus/module-registry` now includes per-module `operational_verified`, `verification_reason`, and external dependency evidence.
- `GET /api/nexus/module-registry/health` returns module-level verified/pending counts and the aggregate system gate.
- Runtime service health is sampled from the lifecycle manager's read-only health probes. A module is not marked operational just because its source file exists or a router is mounted.
- The AI Worker Coordinator requires both a successful provider probe and a successful live self-test for all 11 worker profiles.
- The Provider Integrations module requires all 12 catalogued connectors to pass their configured live health probes.
- Modules without a mapped runtime health probe, missing route registration, or missing external evidence remain pending. `system_operational_verified` stays false until every registered module satisfies its acceptance requirements.
