# NEXUS security findings triage — 2026-11-25

**Target:** `dcnsd00/project-nexus`  
**Branch:** `experiment/lfm3-core-security-lab-v1`  
**Commit scanned:** scanner identified the branch; GitHub independently confirmed HEAD `7400d02c3f8a414db7feba1ce9283c300f22ae5b` at scan time. The scanner response itself did not include a commit SHA.  
**Scanner:** VisionEdge AIScan full GitHub repository scan

## 1. Scan result

| Severity | Count |
|---|---:|
| Critical | 0 |
| High | 0 |
| Medium | 11 |
| Low | 24 |
| Informational | 8 |

**Reported grade:** C (73/100)  
**Reported verdict:** `GO_WITH_CONDITIONS` — no P0/P1 findings; lower-priority findings remain.

AIScan returned detailed locations for 12 findings and reported 31 additional findings without exposing their individual details in this result. The 31 undisclosed findings remain untriaged; this report does not claim to close them.

## 2. Detailed manual triage of returned findings

### 2.1 Research randomness — 9 medium findings

Locations returned by AIScan:

- `application/adapters/multiminer_x/MULTIMINER_X_v1.0/research/legacy/mxx_sha256d_lab.py:228`
- `application/nexus_research/nexus_sha/benchmark.py:87`
- `application/nexus_research/nexus_sha/verify_results.py:44,57,142`
- duplicated benchmark/verifier copies under `application/research/sha2_independent/nexus_sha/`

**Assessment:** The inspected uses construct reproducible research/benchmark samples using seeded `random.Random` instances. These values are test vectors, simulation inputs, or research samples; they are not authentication tokens, encryption keys, session IDs, node secrets, or security nonces.

**Disposition:** Scanner false positive for the inspected call sites. Keep deterministic seeds so experiments and independent verifications remain reproducible. Do not replace research sampling with `secrets` merely to silence this rule. Any future security credential or unpredictable challenge must use a cryptographically secure generator and a separate code path.

### 2.2 SQL construction in Earnings Intelligence — 1 medium finding

Location: `application/modules/earnings_intelligence.py:219`

The interpolated table identifier comes from a fixed tuple of internal table names in the function body:

`("opportunities", "devices", "telemetry", "jobs", "reward_events", "payouts", "wallet_watches", "source_snapshots")`

It is not populated from request data, stored user input, an environment variable, or a remote provider. The query only performs a count over those fixed schema objects.

**Disposition:** No user-controlled SQL injection path was identified at this call site. Preserve the fixed allowlist. Do not rewrite the query using unsafe user-derived identifiers.

### 2.3 SQLite busy-timeout PRAGMA — 1 medium finding

Location: `application/nexus_edge/sqlite_store.py:137`

The interpolated value is `int(self.timeout_s * 1000)`. The constructor rejects non-positive `timeout_s` values and stores it as a float. The interpolated expression is therefore an integer derived from validated local configuration, not SQL text supplied by an API caller.

**Disposition:** Scanner false positive for the inspected call site. Retain the integer conversion and validated configuration boundary. Revisit if the timeout can ever be supplied directly by an untrusted request.

### 2.4 Mutable GitHub Action reference — 1 low finding

The latest scan returned `.github/workflows/nexus-full-benchmark.yml:37`. Earlier scan results also identified `.github/workflows/nexus-ci.yml` and `.github/workflows/nexus-desktop-package.yml:31`; both earlier references have since been pinned and are no longer returned by the latest scan.

**Remediation applied:** pinned `ilammy/msvc-dev-cmd` to immutable commit `0b201ec74fa43914dc39ae48a89fd1d8cb592756` in `.github/workflows/nexus-ci.yml`, `.github/workflows/nexus-desktop-package.yml`, and `.github/workflows/nexus-full-benchmark.yml`, with the upstream release label `v1.13.0`.

The referenced upstream release is signed and identifies this commit as v1.13.0. The same immutable commit is used in the main CI, desktop packaging and full benchmark workflows. These changes affect only the action references, not the MSVC architecture inputs or build behavior.

## 3. Residual status

- The 9 research-randomness reports, 2 SQL reports, and 1 action-pin report received individual review.
- The three returned MSVC action references across the sequential scans have now been pinned on this branch.
- The 11 medium findings are not all fixed: 11 is the scanner's total count, and only the returned locations above were manually triaged. The SQL/randomness call sites are assessed as false positives, not vulnerabilities.
- The remaining 25 low and 8 informational findings have not been individually reviewed in this report.
- No claim is made that static scanning proves runtime security or that every finding in the scan has been closed.

## 4. CI evidence at report time

The last fully green GitHub Actions run before the latest WAF/log and packaging changes was `45570216391`, on commit `33a4cebec35b1ebb0fffc712350279cf5bb3db90`:
- source detection: PASS;
- Linux Python tests: PASS;
- Windows dependency and runtime preparation: PASS;
- Windows compatibility: PASS;
- Windows application shards 1–8: PASS;
- Coraza WAF build and Caddyfile validation: PASS.

Run `45578415772` was queued on commit `60ef246a172981f76bb9b83568c9e3d8147131f4` after the latest scan and the final workflow pin. This report update creates another commit, so CI for the final branch head must be checked separately; do not infer a pass from the earlier fully green run.

## 5. Operational boundaries

The Coraza Caddy pilot is built/validated in CI but is not installed or started on the user's machine. The WAF remains DetectionOnly and loopback-only in the scaffold. CrowdSec is represented by an acquisition template and README only; its Security Engine and Windows Firewall remediation component are not installed or active. No VPN is configured or exposed. The local LFM3 model/runtime has not yet been installed or benchmarked.


## 6. Current-main scan — 2026-11-25

**Target:** `dcnsd00/project-nexus` / `main`  
**Exact HEAD:** `516bb3ca7859159c962b455e55cded01e51d9224`  
**Scanner:** VisionEdge AIScan full GitHub repository scan  
**Grade:** B (78/100)  
**Verdict:** `GO_WITH_CONDITIONS`

| Severity | Count |
|---|---:|
| Critical | 0 |
| High | 0 |
| Medium | 11 |
| Low | 17 |
| Informational | 9 |

AIScan returned 12 detailed findings and indicated 25 additional findings without individual detail in the response. The 25 not individually returned are not marked resolved by this document.

### 6.1 Medium findings — manual review

**Nine deterministic randomness findings.** Locations include the SHA-256d research/benchmark and result-verification modules under `application/nexus_research/nexus_sha`, `application/research/sha2_independent/nexus_sha`, and the legacy MULTIMINER X research lab. The inspected calls use explicitly seeded `random.Random` instances to produce repeatable benchmark samples, nonce windows, or verification subsets. They do not generate authentication tokens, encryption keys, session identifiers, node secrets or security challenges.

**Disposition:** Provisional false positives for the inspected call sites. Preserve deterministic seeds for reproducibility. Any future security credential or unpredictable challenge must use a cryptographically secure generator and a separate code path.

**Earnings Intelligence SQL identifier.** Location: `application/modules/earnings_intelligence.py:219`. The table name is selected from a fixed tuple of internal table identifiers; request/provider data cannot populate the identifier. Query values remain bound parameters.

**EDGE SQLite busy-timeout PRAGMA.** Location: `application/nexus_edge/sqlite_store.py:137`. The interpolated expression is `int(self.timeout_s * 1000)`, a numeric conversion of local configuration. SQLite PRAGMA does not accept a bind parameter for this setting. No user-controlled SQL string was identified. A finite-positive timeout validation remains a robustness improvement, not a confirmed injection fix.

**Disposition for the two SQL findings:** No SQL injection confirmed at the inspected call sites. Keep the fixed identifier allowlist and numeric conversion; add/retain tests that prevent untrusted identifiers or raw SQL values from entering these paths.

### 6.2 Low findings and remaining review

One detailed low finding concerns open version ranges in `application/core/PROJECT-NEXUS-LOCAL/requirements.txt`. The application requirements also use bounded version ranges rather than an exact hash-locked environment. This is a reproducibility and dependency-drift risk; it is not by itself proof of a vulnerable package. Add pip Dependabot coverage and generate a reviewed lockfile with hashes before claiming deterministic dependency resolution.

The remaining 16 low and 9 informational findings were not individually exposed in the current scan response and remain untriaged. No claim is made that the entire low/informational backlog is resolved.

### 6.3 Comparison with earlier snapshots

The earlier grade C/73 scan in this file targeted an older LFM3 experiment-branch snapshot. The 24 November Notion snapshot targeted a different branch/commit and reported a different finding distribution. These are separate scans; count/grade differences are not a security trend unless target commit, scanner version, scan configuration and detailed findings are aligned.

### 6.4 Current targeted scan

PR #23's shared market-data adapter and Gate paper-trading refactor received a targeted AIScan result of grade A/100 with zero findings. This is scoped to those files and does not replace the full repository scan.

### 6.5 CI coverage gap

Current GitHub Actions includes Coraza/Caddy configuration validation but no dedicated Gitleaks, Trivy filesystem/dependency, or CodeQL workflow. Dependabot currently covers GitHub Actions only; pip ecosystems are not configured. These remain explicit follow-up items. Do not claim supply-chain scanning is complete until the workflows are added, run, and findings triaged.
