# RCSC collector retry hardening — 2026-11-12

Local NEXUS 0.10.25 source changes:
- Retry HTTP 429 and 5xx responses with bounded backoff; honor numeric Retry-After for 429 (maximum 30 seconds).
- Do not retry permanent HTTP 4xx responses.
- Retry malformed/truncated JSON responses a bounded number of times.
- Add deterministic regression tests for 404, 429, and invalid JSON behavior.

Validation:
- compileall: PASS.
- `pytest tests/rcsc`: 27 passed in 1.97s.

Scope: this patch and tests are in the local extracted source tree. They have not been imported into the GitHub application source tree. Tests mock HTTP; no live Mempool.space request was made.
