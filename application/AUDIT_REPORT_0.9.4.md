# NEXUS 0.9.4 audit report

## Automated checks
- NEXUS suite: 89 passed
- MultiMiner X: 17 passed
- Crypto Fieldstation: 12 passed
- Wallet benchmark: 15 passed
- Local blockchain unit tests: 7 passed
- Total: 140 passed, 0 failed
- Python compileall: passed
- Dashboard JavaScript `node --check`: passed
- HTML structure: 6 sections, no duplicate IDs

## Verified in test environment
- Compatibility gate rejects XMRig + KawPoW/GPU and blocks KawPoW on a 4 GB GPU because the measured DAG requirement is about 5,944 MiB; accepts the compatibility case with a mocked 8 GB GPU.
- Manual algorithm override rejected.
- 2Miners account response parser tested using mocked provider data; no real wallet/account query performed by audit.
- Optimization A/B calculations and minimum 30-second validation tested.
- Desktop launcher syntax compiled; pywebview runtime was not installed/launched in this Linux test environment.

- DAG/VRAM compatibility guard tested with mocked 4 GB and 8 GB NVIDIA telemetry.

## Not verified
- No real miner process or Stratum connection/share submission launched in this build environment.
- No real 2Miners wallet account queried.
- Windows desktop WebView2 runtime and shortcut not tested on the user's laptop.
- Pool rewards unit conversion must be compared with a known pool account response before treating coin-denominated values as financial records.
- DAG size data is a dated snapshot and must be refreshed as epochs advance.
- No GPU mining performance or profitability claims.
