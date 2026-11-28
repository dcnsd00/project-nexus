# NEXUS MASTER — Changelog

## 0.10.28 — 2026-11-28 · RainbowMiner telemetry, profit intelligence and central AI coordination

- Added a bounded, offline PHY Challenge structural analyzer through the existing Multi-Method Puzzle Solver: Unicode 18.0 feature tests, geometric pairing hypotheses, supplied ECDSA-s bit-window comparison and compressed secp256k1 public-point validation. It does not derive private keys or confirm a final puzzle solution.
- Added authenticated, loopback-only RainbowMiner Report API ingestion with strict field allowlists, PII/secret/log filtering, bounded payloads and SQLite retention under the central NEXUS data directory.
- Added ingestion of RainbowMiner's six-hour `minerdata` and `poolsdata` multipart file uploads; normalized pool price, stable price, penalty and error-ratio fields are now available through read-only endpoints.
- Added an independent stable/live price and pool-confidence scoring engine with RON/kWh electricity cost, stale-evidence rejection and configurable switching hysteresis. Results are recommendations only; no automatic pool or miner switching is performed.
- Connected the RainbowMiner telemetry router to FastAPI, Lifecycle Manager health checks and Module Registry.
- Added central-first multi-specialist AI execution for up to three domains per request, branch-aware integration routing and QA/security review for multi-domain or mutating task classes.
- AI calls remain opt-in, sequential and text-only. No repository writes, shell execution, miner starts, wallet access or provider writes are available to model workers.
- RainbowMiner source is GPL-3.0; this increment uses an independent implementation and does not copy RainbowMiner source code.
- Tests added for telemetry authentication/privacy, profit calculations/hysteresis, module registry integration, branch routing and central/specialist/QA orchestration.
- Live RainbowMiner reports, configured model provider, target Windows installation, external pool shares, physical ASIC/GPU communication and profitability are not yet validated.

## 0.10.27 — 2026-11-26 · AI worker routing and mining safety

- Added an 11-domain specialist-worker registry and deterministic central task-routing preview by repository path, feature branch or explicit domain. Model invocation remains disabled until a provider adapter is configured and validated.
- Injected one shared HybridSupervisor instance into the API and lifecycle runtime.
- Added fail-closed CPU/GPU thermal preflight and an idle-while-stopped local monitor for NEXUS-managed mining workers.
- Added an external RandomX reference benchmark record with source provenance; it is not a result from this NEXUS installation.
- Added regression coverage for worker routing, runtime injection, thermal checks and reference-benchmark provenance.
- No miner was started, no public pool was contacted, and no wallet or external-provider writes occurred.


## 0.10.23 — 2026-11-11 · Hybrid Mining Supervisor
- Implemented exclusive Standard / Development modes with independent CPU/GPU worker processes.
- Added worker-owned miner child lifecycle, separate logs/status/runtime directories, heartbeat checks, bounded shutdown and opt-in bounded restart.
- Added local Development SHA-256d CPU experiment for Regtest/Testnet only; public-pool submission is disabled and Development GPU reports backend unavailable.
- Added VRAM/thermal safety checks and evidence-gated optimizer with unique measurement windows, same pool/share difficulty, robust medians/MAD, accepted-share throughput and energy-efficiency objective when power is measured.
- Added FastAPI endpoints and dashboard controls for mode, CPU/GPU lane lifecycle, GPU switching, status and recommendation-only optimization.
- Preserved legacy single-process controller and plan-only `/api/mining/hybrid/plan` endpoint.
- Verification: 311 tests passed; compileall passed; dashboard JavaScript syntax passed; API smoke checks returned HTTP 200.
- Hardware GPU load, live pool authorization/shares, payout, sustained thermals and wall-power remain unverified on target hardware.


# NEXUS MASTER 0.10.1 — SHA-256 Advanced Research & Resource Budgets

## Added
- Advanced multi-bit differential search using common training blocks and independent holdout validation.
- Round-by-round internal-state difference tracking and empirical modal-difference frequency.
- Tseitin CNF encoding for reduced-round SHA-256 compression collisions with nonzero XOR delta.
- SAT circuit self-check through unit propagation and independent comparison with the reference compressor.
- Optional python-sat backend, bounded solver timeout and safe DIMACS export.
- Dashboard controls for advanced differential search, track, SAT self-check, solve and DIMACS.
- Independent scrolling for dashboard content while keeping navigation and section header stable.

## Correctness / guardrails
- Fixed output-prefix bit ordering in SAT model: MSB-first to match digest serialization and independent verification.
- Search compares candidates on the same fixed training set, then validates the best candidate on an independent holdout.
- Empirical modal difference frequency is explicitly not labelled as differential path probability.
- Reduced-round results remain isolated from mining and consensus.
- Explicit work, rounds, clauses and timeout budgets protect CPU and memory.

## Not claimed
- No full SHA-256 shortcut or mining acceleration is claimed.
- SAT solver is optional; without it, self-check and DIMACS export remain available.
- No live pool share or GPU benchmark is inferred from these local research tests.

## 0.10.2 — 2026-11-09
- Added full-standard SHA-256/SHA-512/SHA-3/BLAKE2 avalanche diagnostics with deterministic sampling and statistical interpretation.
- Added Math Intelligence API and dashboard controls.
- Preserved the 0.10.1 research, mining, pool, earnings and wallet modules.
- Offline audit: 193 passed, 0 failed.

# NEXUS MASTER 0.10.5 — Hybrid Solver & Mining/Pool Validation

## Added and integrated
- Extended hybrid solver API and dashboard route for exact modular congruences, exact rational linear systems (SymPy), and optional bounded bitvector XOR (Z3); the existing reduced-round SHA-256 SAT lab remains a separate optional backend.
- Expanded SOLO profile responses with primary/TLS endpoint, backup hosts/ports, auth type, username format, password hint, share difficulty, payout asset/rule, minimum payout metadata when published, fee note, hardware class and provider-specific activation notes.
- Added the ViaBTC account-mode warning: SOLO must be selected in the operator account before Stratum use.
- Corrected Stratum TLS diagnostics to use the operator-specific `ssl_host` and `ssl_port` when published.
- Kept the curated 24-symbol coin classification and 59 pool endpoint catalog, including Bitcoin, BCH, LTC/DOGE, XMR, RVN, ETC, KAS, VTC, ZEC, DASH, ALPH, NEXA, CKB, CFX, ETHW, KDA, SC, ALEO and PRL. ETH and SOL remain explicitly non-PoW.
- Added API and regression tests for all seven catalog SOLO profiles, pool login formatting, catalog override protection, local Regtest/Mainnet separation, hybrid solver results, and Stratum TLS routing.

## Validation limits
- Pool endpoint listing is curated from operator documentation; a catalog entry does not imply live reachability, Stratum authorization, accepted shares or payout.
- Implemented read-only reward connectors: 2Miners, unMineable, Kryptex and Braiins. F2Pool and ViaBTC account APIs remain pending exact read-only route/auth validation.
- Miner launch support remains limited to the adapters whose launch controller is implemented; inventory-only miners are not falsely reported as runnable.
- No physical GPU benchmark, live accepted share, external account payout, CKPool installation, or public-chain block submission was executed in the build environment.

# NEXUS MASTER 0.10.6 — pool catalog and SOLO settings
- Catalog extended to 69 endpoint records across 24 coin symbols and 13 catalogued operators.
- Added official Luxor BTC/LTC/ZEC/SC and Poolin BTC connection profiles.
- Reconciled F2Pool BTC/ETC TLS endpoints and ViaBTC endpoint matrix with current operator documentation.
- Preserved seven SOLO profiles and all three separate SOLO execution modes.
- Full audit: 229 passed, 0 failed; live pool shares and payouts remain untested.


# NEXUS MASTER 0.10.8 — release notes

## Integrated
- Completată interfața 0.10.7 cu endpoint-urile backend lipsă: registru PoS, merged-mining și unMineable public payout metadata.
- Cosmos ATOM este înregistrat ca asset Proof-of-Stake și destinație de payout unMineable, nu ca algoritm PoW. Ruta ATOM este marcată PAUSED conform paginii oficiale verificate la 2026-11-09; configurarea și pornirea job-urilor cu payout suspendat sunt blocate.
- Adăugate rute de payout ATOM pentru PRL/PearlPow și XEL/XelisHash, cu host/port/TLS documentate, dar dezactivate până la reactivarea payout-urilor.
- Catalogul PoW extins cu Ergo, Xelis, Quantus, Zephyr, Salvium, Verus, Warthog, Beam, MWC, Neurai, Neoxa, Meowcoin, Clore, Tari, Conceal și Ryo. În lipsa unui pool documentat, acestea sunt catalog-only și nu pot fi pornite.
- Registru separat pentru active Cosmos/IBC PoS și merged mining DOGE/LTC.
- BzMiner adăugat în căutarea și instalarea din release-ul oficial GitHub; adaptor de lansare GPU implementat pentru Pearl, KawPoW, Etchash, RandomX, XelisHash, Quantus, NexaPow și Autolykos2.
- Dashboard-ul separă algoritmul/moneda efectiv minată de asset-ul de payout și permite reîmprospătarea listei publice unMineable fără chei API.

## Security / behavior
- Descărcările minerelor rămân acțiune explicită a utilizatorului; executabilele descărcate nu sunt lansate automat.
- Nu se descarcă software de pe oglinzi neoficiale. BzMiner este identificat prin repo-ul upstream `bzminer/bzminer`.
- Payout-urile suspendate sunt blocate la API de config și la controller, nu doar ascunse în UI.
- UnMineable public metadata este read-only și nu solicită API key. Interogarea contului/recompenselor rămâne separată și necesită credențiale read-only.

## Limits
- Catalogul este extensibil și include asset-urile de mining cunoscute din pool/miner registries; nu pretinde că inventariază literalmente fiecare criptomonedă existentă.
- Catalog-only nu înseamnă pool activ sau job pornibil.
- BzMiner a fost verificat structural și prin teste de generare a comenzii; nu a fost descărcat ori rulat în mediul de build, iar benchmark GPU real necesită laptopul utilizatorului.
- ATOM payout was paused at verification time; do not start that route until operator reactivates it.

## 0.10.9 – incremental miner adapter integration
See `CHANGELOG_0.10.9.md` and `AUDIT_REPORT_0.10.9.md` for adapter details, test counts, measured SHA-256d benchmark, and unverified live-network limitations.

# NEXUS MASTER 0.10.19 — local wallet recovery hardening

See `CHANGELOG_0.10.19.md` and `AUDIT_REPORT_0.10.19.md` for implementation details, exact test counts, and limitations. Owner-supplied BIP38 keys can now be re-encrypted into a dedicated NEXUS Bitcoin vault without raw-key export. Local wallet search is metadata/candidate discovery only; Bitcoin Core history inspection requires an explicitly loaded local wallet.


# NEXUS MASTER 0.10.20 — SHA-2 Research Integration

- Integrat pachetul independent SHA-256/SHA-512 în API și Research Hub UI.
- Adăugate endpoint-uri pentru status, self-test, benchmark CPU, avalanșă, statistici, căutare diferențială reduced-round, message modification E1/E2, SAT și verificare independentă.
- Corectată serializarea nonce-ului în verificator la Bitcoin little-endian; corectată rezolvarea directorului de rezultate.
- RNG-ul din message modification E1 este acum injectabil și reproductibil pe seed fix.
- Nicio modificare a minerului; cercetarea reduced-round nu poate fi aplicată automat la mining.
- Audit: NEXUS 259/259; MultiMiner X 17/17; Fieldstation 12/12; Wallet Benchmark 15/15; Wallet v0.5 7/7; pachet independent 12 PASS + 1 SKIP (python-sat absent). Verificatorul independent: PASS.
- SAT real rămâne indisponibil până la instalarea python-sat; CUDA Toolkit nu este prezent.


# NEXUS MASTER 0.10.21 — native miner and reliability fixes

- Fixed nonce partition loss and SIMD tail handling in the supplied C SHA-256d miner.
- Added native C ABI, runtime AVX2/AVX-512 dispatch, safe thread fallback, generic pool share-target comparison and independent hashlib candidate verification.
- Connected the native scanner to the existing Stratum V1 worker; Python reference remains the fallback.
- CoinPaprika now serves stale cache or an explicitly labeled bundled fallback on upstream errors.
- Wallet DB schema is initialized at app startup without decrypting or rewriting vault records.
- Desktop shell chooses a free loopback port and the Windows package includes the independent research resources without local wallet databases.
