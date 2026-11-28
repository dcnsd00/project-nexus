# NEXUS MASTER 0.10.28 — RainbowMiner and Mining Profit Intelligence

## Purpose and provenance

NEXUS consumes RainbowMiner as an optional telemetry source; it does not embed the RainbowMiner runtime. The implementation in NEXUS is an independent Python implementation of documented telemetry fields and general profitability concepts. No RainbowMiner source files or PowerShell modules are copied into NEXUS.

RainbowMiner is GPL-3.0. The NEXUS repository is public, so source transplantation requires a separate licensing decision and is intentionally excluded from this increment. RainbowMiner's miner executables retain their own upstream licenses.

## Data flow

1. RainbowMiner sends its documented form-encoded HTTP POST report.
2. RainbowMiner selects the destination API URL through its own `Data/reportapi.json` mapping. `MinerStatusURL` is matched as a substring; it is not necessarily the final POST URL.
3. NEXUS accepts the report at `POST /api/mining/rainbowminer/report`.
4. NEXUS verifies the shared report key using constant-time comparison.
5. NEXUS validates and filters the report, then stores up to 500 records under the central NEXUS data directory in `mining/rainbowminer_telemetry.sqlite3`.
6. NEXUS never executes commands, changes a pool, changes miner settings, unlocks wallets or contacts a pool because a report arrived.

## Local-only configuration

This first integration intentionally accepts reports from loopback clients only. Place RainbowMiner and NEXUS on the same Windows computer and keep the NEXUS API bound to localhost.

Configure the NEXUS process environment with a strong random value named:

- `NEXUS_RAINBOWMINER_REPORT_KEY`

Do not commit this value, put it in a support ticket or expose it in screenshots. Use the same value in RainbowMiner's `MinerStatusKey`.

In RainbowMiner's `config.txt`, enable reporting and set the status URL to a distinctive local match string:

```text
"EnableMinerStatus": "1",
"MinerStatusURL": "http://127.0.0.1:8765/api/mining/rainbowminer",
"MinerStatusKey": "<same-secret-configured-in-NEXUS>",
"ShowRemoteMachines": "0"
```

The RainbowMiner default `Data/reportapi.json` does not contain a NEXUS target. Add this object to its array, retaining the existing provider entries:

```json
{
  "match": "127.0.0.1:8765/api/mining/rainbowminer",
  "apiurl": "http://127.0.0.1:8765/api/mining/rainbowminer/report",
  "web": "http://127.0.0.1:8765",
  "desc": "NEXUS local telemetry"
}
```

Confirm that NEXUS is actually listening on port 8765 before enabling RainbowMiner reporting. If the desktop app selected an ephemeral fallback port because 8765 was occupied, use that actual local port in both values. Do not expose this endpoint to the LAN or internet; remote ingestion is not implemented in this increment.

For privacy, leave RainbowMiner email and Pushover notification settings empty unless they are independently needed. NEXUS drops those values, as well as machine IP, raw console logs, crash detail paths, raw file paths and the report key. The normalized miner/device records retain only an explicit telemetry allowlist.

## Endpoints

- `POST /api/mining/rainbowminer/report`: authenticated, loopback-only ingestion.
- `GET /api/mining/rainbowminer/status`: loopback-only ingestion and storage status.
- `GET /api/mining/profit-intelligence/status`: profitability engine capabilities.
- `POST /api/mining/profit-intelligence/rank`: score up to 64 candidate configurations.

## Profitability model

The scoring interface requires explicit evidence and unit-labelled inputs:

- daily coin reward;
- stable and live coin prices in RON;
- measured power in watts;
- electricity price in RON/kWh;
- pool accuracy and accepted/rejected share counts;
- measured and benchmark hashrate in H/s;
- source age in seconds.

The NEXUS default live-price blend weight is 0.5 and the default switch hysteresis is 3%. Those are NEXUS policy parameters, not asserted RainbowMiner defaults. Source freshness is limited to 900 seconds by default. Revenue is confidence-weighted using pool accuracy, reject ratio, measured/benchmark hashrate and source freshness. Electricity cost is calculated as `W / 1000 × 24 × RON/kWh`; fixed daily cost is an explicit optional input.

The engine returns a ranked estimate and a manual-review recommendation. It does not fetch exchange prices or pool statistics, does not infer missing values, and does not connect to or control miners. An operator must supply independently verified values; a displayed estimate is not a payout forecast.

## Validation boundaries

Automated tests cover form parsing, authentication, secret/PII filtering, size limits, SQLite retention, price blending, energy-cost arithmetic, stale-evidence rejection, switch hysteresis and the recommendation-only API.

These tests do not prove that RainbowMiner has been configured on the operator's computer, that any report has arrived, that a GPU/ASIC is physically reachable, or that a pool has accepted shares. Those require separate host and hardware validation after this PR is merged and a matching local configuration is supplied.
