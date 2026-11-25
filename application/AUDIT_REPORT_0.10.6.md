# NEXUS MASTER 0.10.6 — Audit tehnic și benchmark funcțional

**Data:** 2026-11-09  
**Build:** incremental peste 0.10.5; păstrează modulele anterioare.  
**Scop:** solver matematic hibrid, cercetare SHA-256 redus-round și digesturi complete, inventar coin/pool, setări SOLO, diagnostic Stratum și verificări de integrare.

## 1. Audit automat executat

| Suită | Trecute | Eșuate |
|---|---:|---:|
| NEXUS Master | 178 | 0 |
| MultiMiner X | 17 | 0 |
| Crypto Fieldstation | 12 | 0 |
| Wallet Benchmark | 15 | 0 |
| Wallet v0.5 | 7 | 0 |
| **Total** | **229** | **0** |

Verificări suplimentare:
- `python -m compileall -q .`: PASS.
- JavaScript dashboard verificat cu `node --check` (Node v22.16.0): PASS.
- Testele de catalog verifică ID-uri unice, câmpuri obligatorii, worker format SOLO și endpoint-uri TLS separate: PASS.
- Server Stratum local de test pentru `subscribe`/`authorize`: PASS.
- `run_full_audit.sh` a omis benchmark-ul nativ SHA-256d lung în mod implicit, pentru limitarea resurselor.

## 2. Catalog coin și pool

- 24 simboluri coin: 22 marcate PoW-mineable; ETH și SOL sunt marcate non-PoW.
- 69 profile/înregistrări de endpoint documentate în catalog.
- Furnizori: 2Miners, WoolyPooly, VeinPool, Public Pool, unMineable, MoneroOcean, F2Pool, ViaBTC, Braiins, CKPool, Kryptex, Luxor și Poolin.
- Profile noi în 0.10.6: Luxor BTC, LTC/DOGE merged mining, ZEC și SC; Poolin BTC.
- F2Pool BTC: endpoint global principal `btc.f2pool.com:1314`, failover `25,3333`, TLS `btcssl.f2pool.com:1300` (failover 1301), conform paginii operatorului actualizate 29 octombrie 2026.
- F2Pool ETC TLS hostname corectat la `etcssl.f2pool.com:8180`, backup 8181.
- ViaBTC: BTC, BCH, LTC, ZEC, DASH, KAS; porturile și host-urile TLS sunt stocate separat acolo unde sunt publicate.
- Luxor: host-urile BTC/LTC/ZEC/SC și login-ul `Subaccount.Worker` sunt stocate conform documentației Luxor.
- Poolin BTC: `btc.ss.poolin.me:443`, failover 1883/700 conform ghidului Poolin. Portul 443 nu este etichetat automat TLS, deoarece pagina citată îl prezintă ca `stratum+tcp`.

Catalogul reprezintă date de configurare documentate, nu o probă de conectivitate live, autentificare sau payout.

## 3. SOLO: moduri și setări

Șapte profile SOLO explicite:
1. Public Pool BTC SOLO.
2. Public Pool low-difficulty endpoint pentru NerdMiner.
3. ViaBTC BTC — SOLO selectabil numai după activarea modului în contul operatorului.
4. Braiins Solo BTC.
5. CKPool BTC.
6. 2Miners Ravencoin SOLO.
7. Kryptex Pearl SOLO.

Răspunsul de profil expune host/port primar, TLS disponibil și endpoint-ul TLS separat dacă există, failover host/port, format de username, tip de autentificare, identitate wallet/account, worker, parolă implicită doar ca hint, dificultate share când este publicată, comision și note payout, asset, clasă hardware și URL sursă.

Trei moduri rămân distincte:
- `SOLO_POOL`: endpoint SOLO extern administrat de operator.
- `LOCAL_REGTEST`: Bitcoin Core RPC + CPU SHA-256d; acceptă doar `regtest` și RPC loopback.
- `LOCAL_NODE_STRATUM_PROXY`: șablon de configurare CKPool pentru nod propriu. NEXUS nu instalează și nu pornește CKPool; pentru mainnet, pornirea manuală poate produce submit public dacă se găsește un bloc.

Un share acceptat într-un pool SOLO confirmă contribuția de lucru, dar nu este o recompensă de bloc. Recompensa există numai dacă blocul este găsit și confirmat.

## 4. Stratum și conexiuni

- Testele de integrare folosesc un server Stratum local controlat pentru `mining.subscribe` și `mining.authorize`.
- Probe-urile TCP/TLS verifică accesibilitatea socket-ului.
- Niciuna dintre aceste verificări nu este o probă de accepted share sau payout live.
- Niciun endpoint extern nu a fost raportat ca live-conectat în acest audit.

## 5. Benchmark funcțional matematic

### 5.1 Hash avalanche pe digesturi complete

256 probe deterministe per algoritm, payload 64 bytes, seed 20261109:

| Algoritm | Biți schimbați în medie | Reper ideal | În 3 erori standard |
|---|---:|---:|---|
| SHA-256 | 128.1055 | 128 | Da |
| SHA-512 | 255.8477 | 256 | Da |
| SHA3-256 | 128.0664 | 128 | Da |
| SHA3-512 | 255.3477 | 256 | Da |
| BLAKE2b-256 | 127.6250 | 128 | Da |

Acesta este diagnostic statistic asupra digestului complet, nu dovadă de securitate și nu hashrate PoW.

### 5.2 Solver hibrid

- Congruență modulară exactă: `14*x ≡ 30 (mod 100)` → soluție reprezentativă `x=45`, două soluții, verificare prin substituție PASS.
- Sistem liniar rațional SymPy: `[[2,1],[1,-1]] * x = [5,1]` → `(2,1)`, verificare exactă PASS.
- Z3 bit-vector și PySAT sunt back-end-uri opționale; nu au fost instalate în mediul de build, deci nu s-au raportat rezolvări SMT/SAT executate.

### 5.3 Codificare SAT SHA-256 cu runde reduse

Self-check prin propagare unitară comparat cu compresorul de referință:

| Runde | Variabile | Clauze | Concordanță |
|---:|---:|---:|---|
| 1 | 2.130 | 7.463 | Da |
| 4 | 4.701 | 19.241 | Da |
| 12 | 11.557 | 50.649 | Da |
| 20 | 20.065 | 89.409 | Da |

Este validată consistența codificării; nu a fost executată căutarea SAT, iar cercetarea reduced-round este separată de mining/consensus.

### 5.4 Differential search

Test limitat la 20 de runde, 20 pași, 8 blocuri de antrenament, un restart și 32 probe independente holdout. Candidatul nu a depășit baseline-ul aleator pe holdout și nu a fost promovat ca optimizare.

## 6. Adaptoare de recompense și mineri

Conectori read-only implementați în sursă: 2Miners public API, unMineable signed GET, Kryptex public GET și Braiins read-only endpoints. Tokenurile sunt request-scoped, nu persistate.

Conectorii de cont F2Pool și ViaBTC rămân pending validării exacte a rutelor/schemelor read-only. Luxor și Poolin sunt endpoint profiles în catalog, nu conectori de recompense.

Controllerul poate lansa numai adaptoarele care au `launch=true` în `mining/controller.py` (XMRig, T-Rex, SRBMiner-MULTI). lolMiner, GMiner, Rigel și TeamRedMiner rămân inventar/compatibility-only. ASIC/NerdMiner produc configurație externă, nu sunt pornite de NEXUS.

## 7. Ce nu a fost testat

- Mining fizic pe GTX 1650 Ti a utilizatorului.
- Conectare externă live la pool, accepted shares sau payout.
- API de cont cu tokenurile utilizatorului.
- Bitcoin Core daemon lifecycle real și proces CKPool live.
- Z3/PySAT solve, deoarece dependențele lipsesc din runtime.
- Executabil Windows `.exe` final compilat pe Windows.

## 8. Distribuție și date private

Arhiva de distribuție exclude bazele SQLite locale și `.env`; nu include seed phrase, chei private, parole sau API tokens. ZIP-ul este un pachet sursă cu installer Python desktop și scripturi de build; nu este un `.exe` standalone precompilat.

## 9. Surse oficiale pentru endpoint-uri noi/correctate

- Luxor Mining Pool Getting Started: https://docs.luxor.tech/platform/mining/getting-started
- Poolin Bitcoin Mining Guide: https://help.poolin.me/hc/en-us/articles/360032254652-Bitcoin-Mining-Guide-with-Bitmain-Antminer-S9
- F2Pool Pools info (updated 29 Oct 2026): https://f2pool.zendesk.com/hc/en-us/articles/360058887912-Mining-pools-info-payout-schemes-and-thresholds-at-f2pool
- ViaBTC Mining Pools Information (updated 2 Nov 2026): https://support.viabtc.com/hc/en-us/articles/14367481714191-Mining-Pools-Information
- Braiins Solo: https://academy.braiins.com/braiins-pool/solo-mining
- Kryptex API: https://pool.kryptex.com
- unMineable API: https://api.unmineable.dev/v1

## 10. Artefacte

- `results/BENCHMARK_REPORT_0.10.6_FUNCTIONAL.json`
- `CHANGELOG_0.10.6.md`
- `VERSION.json`
