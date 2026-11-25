# NEXUS security findings triage — 2026-11-25

**Target:** `dcnsd00/project-nexus`  
**Branch:** `experiment/lfm3-core-security-lab-v1`  
**Commit scanned:** branch HEAD at scan time; the scan tool reported the branch target but did not return a commit SHA in its result.  
**Scanner:** VisionEdge AIScan full GitHub repository scan

## 1. Scan result

| Severity | Count |
|---|---:|
| Critical | 0 |
| High | 0 |
| Medium | 11 |
| Low | 26 |
| Informational | 8 |

**Reported grade:** C (73/100)  
**Reported verdict:** `GO_WITH_CONDITIONS` — no P0/P1 findings; lower-priority findings remain.

AIScan returned detailed locations for 12 findings and reported 33 additional findings without exposing their individual details in this result. The 33 undisclosed findings remain untriaged; this report does not claim to close them.

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

Location returned by AIScan: `.github/workflows/nexus-ci.yml`, Windows MSVC setup.

**Remediation applied:** pinned `ilammy/msvc-dev-cmd` to immutable commit `0b201ec74fa43914dc39ae48a89fd1d8cb592756`, with the upstream release label `v1.13.0`.

The referenced upstream release is signed and identifies this commit as v1.13.0. This change is limited to the action reference; it does not change the MSVC architecture input or build behavior.

## 3. Residual status

- The 9 research-randomness reports, 2 SQL reports, and 1 action-pin report received individual review.
- The action-pin item is remediated in this branch.
- The 11 medium findings are not all fixed: 11 is the scanner's total count, and only the returned locations above were manually triaged. The SQL/randomness call sites are assessed as false positives, not vulnerabilities.
- The 26 low and 8 informational findings have not been individually reviewed in this report.
- No claim is made that static scanning proves runtime security or that every finding in the scan has been closed.

## 4. CI evidence at report time

GitHub Actions run `45570216391` completed successfully on commit `33a4cebec35b1ebb0fffc712350279cf5bb3db90`:
- source detection: PASS;
- Linux Python tests: PASS;
- Windows dependency and runtime preparation: PASS;
- Windows compatibility: PASS;
- Windows application shards 1–8: PASS;
- Coraza WAF build and Caddyfile validation: PASS.

This run predates the MSVC action pin made alongside this report. A new CI run is required to validate the pinned reference.

## 5. Operational boundaries

The Coraza Caddy pilot is built/validated in CI but is not installed or started on the user's machine. The WAF remains DetectionOnly and loopback-only in the scaffold. CrowdSec is represented by an acquisition template and README only; its Security Engine and Windows Firewall remediation component are not installed or active. No VPN is configured or exposed. The local LFM3 model/runtime has not yet been installed or benchmarked.
