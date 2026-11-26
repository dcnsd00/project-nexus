# NEXUS Security Scan Baseline Triage — 2026-11-26

## Scope and evidence

This note records review of the report-only security workflow introduced by PR #26 at head commit `2456938133e55197307d4a7a038f112ee0027274`.

- Workflow run: `45695527479`
- Gitleaks scan: 783 commits and approximately 4,532,881 bytes scanned; 3 findings reported.
- Trivy scan: filesystem mode against repository root; SARIF artifact contains 0 results.
- CodeQL: Python security-extended analysis job completed successfully. The workflow explicitly does not include C/C++ analysis.

A successful job means the scanner executed and uploaded its output. It does not establish that the repository has no security findings.

## Gitleaks triage

All three reported findings use rule `generic-api-key` and point to the same historical source-import commit, `1724489bb045c1f9aabd6f1a12a5256edd95b8a9`.

| Location | Source context observed | Preliminary disposition |
|---|---|---|
| `application/modules/wallet_benchmark/nexus_wallet_search.py:32` | Set of supported wallet-format identifiers (`WEB3_SECRET_STORAGE_V3`, `NEXUS_AESGCM_V1`, `SOLANA_KEYPAIR_JSON`) | Likely false positive: format identifiers, not credential material |
| `application/tests/test_wallet_recovery_integration_016.py:88` | BIP38 integration-test fixture with a fixed test passphrase | Likely false positive: test-only fixture value |
| `application/vendor/randomx-1.2.3/src/tests/tests.cpp:1015` | RandomX upstream hash-test vector input/output in test source | Likely false positive: public test vector, not an application credential |

The SARIF artifact redacts matched content. No candidate value is reproduced in this report. These are source-context assessments, not a blanket suppression of the rule.

**No Gitleaks allowlist or ignore rule is added here.** Keep the baseline report available for review; only suppress a finding after confirming its exact source context and preserving a narrow, auditable rationale.

## Trivy coverage limitation

The Trivy artifact contains an empty SARIF result set. However, the job log also reports:

- `Unable to find python site-packages directory. License detection is skipped.`
- `Number of language-specific files num=0`

The scanned source branch contains Python dependency requirement files under `application/` (including `requirements.txt`, `requirements-dev.txt`, and `requirements-edge.txt`). The current run therefore does **not** provide reliable evidence that Python dependency vulnerabilities and licenses were inventoried. An empty SARIF result is not proof of zero vulnerable dependencies.

Before treating this as a dependency-security baseline, the workflow needs a validated dependency input that the scanner can resolve (preferably reproducible lock data or a separately installed/resolved dependency environment), and the output must demonstrate that the expected packages were enumerated.

## CodeQL coverage

The Python security-extended workflow completed successfully. C/C++ is explicitly deferred in the workflow, so this run does not establish native miner or vendored RandomX C/C++ analysis coverage. This note does not infer a zero-alert result from job success alone.

## Required follow-up before enforcing gates

1. Have a reviewer confirm the three Gitleaks candidates as test/identifier false positives; do not suppress them globally.
2. Make Trivy enumerate the actual Python dependency set and retain a machine-readable report with package inventory and vulnerability results.
3. Decide on a separately validated CodeQL C/C++ build mode for native code; retain the Python-only scope statement until then.
4. Keep Gitleaks and Trivy report-only until baseline triage is reviewed. Convert selected severities to blocking policy only after findings and coverage are understood.

## Safety boundary

This triage did not change source code, remove files, rewrite history, rotate credentials, or alter wallet material. It records the observed scanner output and its limitations; it does not certify the repository as secret-free or vulnerability-free.
