# NEXUS Security Scan Baseline Triage — 2026-11-26

## Scope and current evidence

This report records the security workflow and dependency remediation introduced by PR #26, re-evaluated against its current head:

- PR #26 branch: `security/supply-chain-scans-v1`
- Current PR head: `da0c7440d0fea8a49467e90a645ba5073387d50c`
- Security workflow run: `45876052297`
- Main NEXUS CI run: `45876052356`

The security workflow completed all three jobs successfully: Gitleaks, Trivy and CodeQL Python. The main NEXUS CI completed 14/14 jobs successfully, including Python tests, Coraza build, Windows runtime/compatibility and all eight Windows application shards.

A successful scanner job means the scanner executed and uploaded its output. It does not establish that the repository has no security findings.

## Gitleaks

The current run scanned 848 commits and approximately 4,739,342 bytes (4.74 MB), and reported **3 findings**. The redacted SARIF artifact is `nexus-gitleaks-baseline` (artifact ID `15145117727`).

The earlier source-context triage associated the three `generic-api-key` findings with the historical source-import commit `1724489bb045c1f9aabd6f1a12a5256edd95b8a9`:

| Location | Source context observed | Preliminary disposition |
|---|---|---|
| `application/modules/wallet_benchmark/nexus_wallet_search.py:32` | Supported wallet-format identifiers (`WEB3_SECRET_STORAGE_V3`, `NEXUS_AESGCM_V1`, `SOLANA_KEYPAIR_JSON`) | Likely false positive: format identifiers, not credential material |
| `application/tests/test_wallet_recovery_integration_016.py:88` | BIP38 integration-test fixture with a fixed test passphrase | Likely false positive: test-only fixture value |
| `application/vendor/randomx-1.2.3/src/tests/tests.cpp:1015` | RandomX upstream hash-test vector input/output | Likely false positive: public test vector, not an application credential |

These remain preliminary source-context assessments. The current artifact was uploaded with matched content redacted; this report does not reproduce candidate values or claim independent human confirmation. No Gitleaks allowlist or ignore rule is added. Keep the baseline report available and suppress a finding only after exact source-context confirmation and a narrow, auditable rationale.

## Trivy

The current Trivy run (`45876052297`) recognized **5 language-specific files** and executed pip vulnerability detection. The SARIF artifact `nexus-trivy-baseline` is available as artifact ID `15144204346`. Its SARIF contents were not parsed during this integration review; therefore this report makes **no zero-findings claim** for the current run.

The run logged:

```
Unable to find python site-packages directory. License detection is skipped.
```

This is a license-inventory limitation, separate from dependency vulnerability detection. The workflow sets `TRIVY_DETECTION_PRIORITY=comprehensive`, so range-based requirements are included in pip vulnerability detection. Comprehensive mode may infer the lowest version permitted by a range; it does not prove the exact version installed on a machine. A resolved, reproducible lock or environment inventory remains preferable for complete transitive-dependency and license coverage.

The earlier pre-remediation scan `45874983071` was recorded as finding 12 issues against the lowest versions implied by then-current ranges (11 cryptography and 1 pytest). Those are historical pre-remediation results and must not be presented as the current scan result.

## CodeQL

The current CodeQL job completed successfully with the `security-extended` query set for **Python only**. The workflow explicitly records that C/C++ analysis is deferred until a separately validated build-mode configuration is available. This run does not establish native miner or vendored RandomX C/C++ analysis coverage.

## Dependency remediation

The PR changes the dependency boundaries as follows:

- `application/modules/wallet_benchmark/requirements.txt` now declares `cryptography>=50.0.0,<51` and `mnemonic>=0.21` as runtime dependencies.
- Wallet benchmark test tooling is separated into `application/modules/wallet_benchmark/requirements-dev.txt` with `pytest>=9.0.3,<10`.
- `application/requirements-dev.txt` is raised to `pytest>=9.0.3,<10`.
- The Wallet Benchmark README now distinguishes runtime and development installation commands. The code fences around both commands have been corrected.
- Dependabot adds weekly grouped Python dependency updates for the application, local core, FieldStation, MultiMiner X, Wallet Benchmark, Wallet Benchmark v05, NEXUS research and independent SHA-2 research directories.

The current PR head's CI is green, but that does not substitute for reviewing individual scanner findings or testing every resolved dependency combination on every supported host.

## Workflow and policy boundaries

- Gitleaks and Trivy remain report-only (`--exit-code 0` / `exit-code: "0"`) while the baseline is reviewed. They are not yet blocking security gates.
- The workflow pins GitHub Actions to full commit SHAs.
- Current runner logs warn that several pinned actions target Node.js 20 and are being forced to run on Node.js 24. This is a forward-compatibility warning to address by verifying and adopting supported action revisions; it did not fail the current run.
- The Trivy license-inventory warning remains open.
- CodeQL C/C++ coverage remains deferred.
- Gitleaks' three findings still require human confirmation before any suppression or clean-baseline claim.

## Required follow-up before enforcing gates

1. Review the three Gitleaks findings in their exact source context and record reviewer disposition; do not suppress them globally.
2. Inspect the current Trivy SARIF artifact and record actual finding counts/severities before making any zero-finding or remediation claim.
3. Provide a resolved dependency inventory and investigate the missing site-packages/license inventory.
4. Verify supported Node.js 24-compatible revisions for the affected pinned actions before changing their SHAs.
5. Decide on a separately validated CodeQL C/C++ build mode for native code.
6. Keep Gitleaks and Trivy report-only until the baseline and coverage limitations are understood.

## Safety boundary

This triage did not change source code, remove files, rewrite history, rotate credentials or alter wallet material. It records observed scanner output and limitations; it does not certify the repository as secret-free or vulnerability-free.
