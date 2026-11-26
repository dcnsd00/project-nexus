# NEXUS AI Worker Execution — 0.10.28 candidate

## Scope

This increment turns the 0.10.27 worker-routing preview into an opt-in, text-only model call. The branch router still chooses a specialist by repository path, branch pattern or explicit domain. Mutating task kinds automatically request a second QA/security review call.

The model cannot use tools. No tool schemas are sent, and its output is only a recommendation/report. The application does not write repository files, execute shell commands, start miners, unlock wallets, sign transactions, broadcast transactions or write to external services.

## Supported provider modes

### Ollama (local)

Set the following environment variables before starting NEXUS:

- `NEXUS_AI_PROVIDER=ollama`
- `NEXUS_AI_MODEL=<installed-model-tag>`
- Optional: `NEXUS_AI_BASE_URL=http://127.0.0.1:11434/api`
- Optional: `NEXUS_AI_TIMEOUT_SECONDS=60`

Ollama uses its native local `/api/chat` endpoint. The default host is loopback only. NEXUS does not download or install models.

### OpenAI-compatible endpoint

- `NEXUS_AI_PROVIDER=openai_compatible`
- `NEXUS_AI_MODEL=<model-id>`
- `NEXUS_AI_BASE_URL=http://127.0.0.1:1234/v1` for a local service such as LM Studio
- `NEXUS_AI_API_KEY=<secret>` only when required by the provider

Remote connections are blocked unless all conditions are met:

- `NEXUS_AI_ALLOW_REMOTE=1`
- base URL uses HTTPS on port 443
- hostname is listed in `NEXUS_AI_REMOTE_HOST_ALLOWLIST`
- `NEXUS_AI_API_KEY` is present

The key is read from the process environment and is never returned by the status API or written into worker logs.

## Per-domain model selection

Optional model overrides use the worker domain, for example:

- `NEXUS_AI_MODEL_MINING`
- `NEXUS_AI_MODEL_CRYPTOGRAPHY`
- `NEXUS_AI_MODEL_EDGE`
- `NEXUS_AI_MODEL_DASHBOARD`
- `NEXUS_AI_MODEL_QUALITY`

If a worker-specific model is absent, NEXUS uses `NEXUS_AI_MODEL`. All workers share the configured endpoint in this increment. Separate endpoints per domain are not implemented yet.

## API

- `GET /api/nexus/workers/provider-status`: reports safe configuration metadata; it does not contact the provider.
- `GET /api/nexus/workers`: shows whether text-only invocation is configured.
- `POST /api/nexus/workers/route`: deterministic routing preview; no model invocation.
- `POST /api/nexus/workers/execute`: explicitly invokes the selected worker, and optionally the QA reviewer, using text-only requests.

Provider health is **configured, not live verified** until an explicit execute request succeeds. Model status does not imply a long-running agent process.

## Security and resource policy

- No automatic model call occurs at app startup.
- Only one request runs at a time in the NEXUS provider adapter to avoid concurrent VRAM pressure on small GPUs.
- Input/output sizes and timeout are bounded.
- Remote provider egress requires an explicit enable flag, exact hostname allowlist, HTTPS and an API key.
- Model outputs must be treated as untrusted recommendations.
- Human review is required for implementation, merge, mining, wallet, provider-write and deployment suggestions.
- NEXUS does not execute model-generated code or call tools in this increment.

## Validation

Tests use a fake HTTP transport and synthetic provider responses. They do not contact a local Ollama server or remote provider and do not prove a model is installed.
