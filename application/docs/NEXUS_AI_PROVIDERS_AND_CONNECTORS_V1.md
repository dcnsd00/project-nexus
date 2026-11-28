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

## AI model provider configuration

All providers use the existing local NEXUS API:

- `GET /api/nexus/workers` — worker catalogue and safe readiness summary.
- `GET /api/nexus/workers/provider-status` — provider configuration/live status (loopback-only).
- `POST /api/nexus/workers/provider-test` — perform a real minimal prompt/response probe (loopback-only).
- `POST /api/nexus/workers/execute` — dispatch one specialist (loopback-only).
- `POST /api/nexus/workers/coordinate` — central coordinator + up to three specialist domains + quality review (loopback-only).

The default is disabled. To use a local Ollama endpoint, configure the values in the machine-local environment (do not commit secrets):

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

Existing provider base URL and token environment variables remain the source of credentials. The adapter also requires a resource path for each operation.

For example, Acurast:

```dotenv
NEXUS_ACURAST_API_URL=https://<official-api-host>/<base-path>
NEXUS_ACURAST_API_TOKEN=<secret>
NEXUS_CONNECTOR_ALLOWED_HOSTS_ACURAST=<official-api-host>
NEXUS_ACURAST_HEALTH_PATH=<documented-health-path>
NEXUS_ACURAST_ACCOUNT_PATH=<documented-account-path>
NEXUS_ACURAST_REWARDS_PATH=<documented-rewards-path>
NEXUS_ACURAST_DEVICE_STATUS_PATH=<documented-device-status-path>
```

For a public endpoint that requires no token, set its provider URL and allowlisted hostname, then define only the resource paths the provider actually documents. The examples above are configuration shapes, not assertions that these particular vendor paths exist.

Host allowlisting can be shared using `NEXUS_CONNECTOR_ALLOWED_HOSTS` or set per connector using `NEXUS_CONNECTOR_ALLOWED_HOSTS_<PROVIDER_ID>`. Remote hosts must use HTTPS on port 443 and match the allowlist exactly. A loopback endpoint may use HTTP for local development.

For token-backed providers, the default header is `Authorization: Bearer <token>`. Optional per-connector settings are:

- `NEXUS_<PROVIDER_ID>_API_TOKEN_HEADER`: one of `Authorization`, `X-API-Key`, or `API-Key`.
- `NEXUS_<PROVIDER_ID>_API_AUTH_SCHEME`: defaults to `Bearer`.

The API surface is local-only:

- `GET /api/integrations/catalog` — connector list and readiness.
- `GET /api/integrations/status` — counts by readiness state.
- `POST /api/integrations/{provider_id}/probe` — real GET to the configured health resource.
- `GET /api/integrations/{provider_id}/read/{resource}` — read the configured resource.

The `health` resource is configured with `NEXUS_<PROVIDER_ID>_HEALTH_PATH`. Other permitted resource names are in the provider catalog and their paths are configured with `NEXUS_<PROVIDER_ID>_<RESOURCE>_PATH`.

The adapter enforces GET-only requests, loopback-only API access, exact host allowlisting, HTTPS for remote services, no redirects, no proxy environment inheritance, a 12-second timeout, a 1 MB response bound and JSON content-type/parse validation. Error payloads and secrets are not returned to clients.

## Vendor-specific integration boundary

This release implements a shared guarded JSON REST adapter contract for all 12 connector profiles. It is not a claim that every vendor's private/account API schema has been reverse-engineered or validated. Before declaring an individual connector complete, NEXUS must add/verify that provider's official endpoint paths, authentication method, response schema, pagination/rate-limit behaviour, freshness semantics and error mapping. Do not guess endpoint paths from the examples above.

The generic connector returns validated JSON under a resource envelope. A provider-specific normalization layer should only be added when there is an official API contract or user-provided endpoint specification and test evidence.

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
