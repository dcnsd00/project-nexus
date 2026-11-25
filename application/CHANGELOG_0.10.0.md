# NEXUS MASTER 0.10.0 — Earnings Intelligence & Resource Orchestration

## Added
- Unified local intelligence ledger for opportunities, devices, telemetry, shadow jobs, reward events, costs, payouts, public wallet watches and source snapshots.
- Opportunity due-diligence fields: category, network, asset, algorithm, device compatibility, expected token rate, RON price, confidence, transferability, eligibility, payout verification, liquidity, minimum payout and evidence URL/time.
- Device inventory for CPU/GPU/ASIC/Android/ESP32/mini-PC/storage/bandwidth workers with measured power and electricity tariff.
- Economics evaluator that computes gross estimate, energy cost, fees and net RON/day. Missing reward, price, power, tariff, transferability, eligibility, payout or liquidity evidence blocks a positive recommendation.
- Reward states remain distinct: estimated, claimable, claimed and realized. Payouts require a transaction hash and verification state. Duplicate transaction hashes are rejected.
- Shadow scheduler ranks opportunity/device combinations but never starts or stops a miner.
- Read-only public wallet watch; private keys and seed phrases are not accepted.
- Dashboard tab: “Inteligență & Recompense” for registering opportunities/devices, viewing ledger status and generating shadow plans.

## Explicitly not connected in 0.10.0
- `provider_connectors_live=0`: no provider reward API or DePIN account connector is claimed live.
- No automated claims, transaction signing, transfers, miner auto-switching or external process execution from the new module.
- Source snapshots can be recorded with provenance; live feed polling is a subsequent adapter task.
- Revenue is not considered realized without an on-chain/provider payout record.

## Validation
- New API tests cover positive/negative economics, missing-evidence hard gates, shadow-only scheduling, duplicate reward/payout transaction handling and read-only wallet watch.
