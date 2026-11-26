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

## Trivy coverage and findings

The initial Trivy run `45695527479` produced an empty SARIF report and logged `Number of language-specific files num=0`. The reason was identified: NEXUS dependency manifests used ranges such as `>=`, while Trivy defaults to `precise` mode, which by default parses only `==` requirements. Trivy's documented `comprehensive` mode also parses `>=` and `~=` specifiers.

After setting `TRIVY_DETECTION_PRIORITY=comprehensive`, run `45874983071` identified **5 language-specific files** and executed pip vulnerability detection. Its SARIF artifact (`nexus-trivy-baseline`, artifact ID `15143907987`) contained 12 findings:

| Severity | Findings | Package / inferred lower bound |
|---|---:|---|
| HIGH | 5 | `cryptography` at minimum version 41 |
| MEDIUM | 3 | `cryptography` at minimum version 41 |
| MEDIUM | 1 | `pytest` at minimum version 7 |
| LOW | 3 | `cryptography` at minimum version 41 |
| **Total** | **12** | 11 cryptography; 1 pytest |

These are findings against the **lowest version implied by the range**, not evidence of the exact version installed on a machine. The SARIF report lists remediation versions, including cryptography fixes through 48.0.1 and pytest 9.0.3. The NEXUS root runtime requirements already required `cryptography>=50.0.0,<51`, but the standalone Wallet Benchmark manifest was weaker (`cryptography>=41`, `pytest>=7`).

**Dependency remediation committed on this branch for re-validation:**
- `application/modules/wallet_benchmark/requirements.txt` now aligns with the root runtime crypto constraint (`cryptography>=50.0.0,<51`) and keeps `mnemonic` as a runtime dependency.
- Test tooling was moved to `application/modules/wallet_benchmark/requirements-dev.txt` with `pytest>=9.0.3,<10`.
- `application/requirements-dev.txt` was raised to `pytest>=9.0.3,<10`.
- The Wallet Benchmark README now distinguishes runtime from test dependencies.
- The Trivy SARIF step retains `TRIVY_DETECTION_PRIORITY=comprehensive`; the JSON-only `list-all-pkgs` input was removed after Trivy warned that package listing is automatic for SARIF output.

The previous Trivy run also logged `Unable to find python site-packages directory. License detection is skipped.` This remains a license-inventory limitation, separate from dependency vulnerability detection. Comprehensive mode estimates minimum versions from ranges and can increase false positives; a resolved, reproducible lock or environment inventory is still preferable for full transitive-dependency coverage. The 12 findings above are from the pre-remediation scan and must not be presented as the result after the current dependency changes.

Trivy reference: https://trivy.dev/docs/latest/guide/coverage/language/python/

## CodeQL coverage

The Python security-extended workflow completed successfully. C/C++ is explicitly deferred in the workflow, so this run does not establish native miner or vendored RandomX C/C++ analysis coverage. This note does not infer a zero-alert result from job success alone.

## Required follow-up before enforcing gates

1. Inspect the first post-remediation Trivy SARIF on the exact current branch HEAD; verify that the three direct dependency risk floors are gone and check for any remaining findings.
2. Confirm the three Gitleaks candidates as test/identifier false positives in review; do not suppress them globally.
3. Provide a resolved/locked dependency inventory to cover transitive Python dependencies and close the site-packages/license inventory gap.
4. Decide on a separately validated CodeQL C/C++ build mode for native code; retain the Python-only scope statement until then.
5. Keep Gitleaks and Trivy report-only until the baseline and coverage are reviewed. Convert selected severities to blocking policy only after findings and coverage are understood.

## Safety boundary

This triage did not change source code, remove files, rewrite history, rotate credentials, or alter wallet material. It records the observed scanner output and its limitations; it does not certify the repository as secret-free or vulnerability-free.
