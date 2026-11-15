# NEXUS 0.10.23 — Ghid de utilizare (RO)

## 1. Moduri

NEXUS oferă două moduri exclusive:
- **Standard** — lansare miner CPU/GPU prin executabile detectate în inventarul local și compatibilitate pool/algoritm verificată.
- **Development** — experiment SHA-256d local pe CPU, limitat la Regtest/Testnet. Nu trimite share-uri către pool-uri publice. Development GPU este dezactivat până la integrarea unui backend experimental verificat.

Pentru schimbarea modului, oprește explicit modul activ și confirmă că worker-ele au fost oprite.

## 2. CPU și GPU independente

În modul Standard, selectează pool-ul și minerul pentru fiecare motor, apoi furnizează argumentele minerului ca JSON array de șiruri. Executabilul trebuie să apară ca disponibil în inventarul NEXUS. CPU și GPU rulează în procese OS separate și se pot opri independent.

`running` indică faptul că worker-ul și procesul miner copil sunt confirmate active. Nu înseamnă că pool-ul a autorizat wallet-ul sau a acceptat share-uri. Verifică separat `pool_connected`, `authorized`, `accepted_shares` și `rejected_shares`.

## 3. API

- `POST /api/mining/mode/standard/start`
- `POST /api/mining/mode/development/start`
- `POST /api/mining/mode/{mode}/stop`
- `GET /api/mining/mode/status`
- `POST /api/mining/hybrid/start`
- `POST /api/mining/hybrid/stop`
- `POST /api/mining/hybrid/engine/{cpu|gpu}/start`
- `POST /api/mining/hybrid/engine/{cpu|gpu}/stop`
- `POST /api/mining/hybrid/gpu/switch`
- `GET /api/mining/hybrid/status`
- `POST /api/mining/hybrid/optimize/plan`

`POST /api/mining/hybrid/plan` rămâne endpoint de preflight și nu pornește procese.

## 4. Optimizare

Evaluatorul cere minimum trei ferestre independente, ID-uri unice, același pool și aceeași dificultate de share pentru baseline și candidat, share-uri acceptate și zero încălcări de siguranță. Eficiența energetică este necunoscută dacă lipsesc măsurătorile de putere. Rezultatul este doar pentru revizie manuală; setările nu sunt aplicate automat.

## 5. Limite

Testele automate nu validează placa GPU fizică, driverele Windows, stabilitatea termică, consumul măsurat la priză, autorizarea pool-ului, share-uri live sau plăți. Aceste verificări trebuie făcute pe calculatorul țintă.

## Benchmark RandomX CPU
În secțiunea Mining există panoul „RandomX CPU · benchmark și optimizare fire”. Acesta folosește executabilul XMRig instalat și detectat în inventarul NEXUS, în modul său offline `--bench`. Introdu 1–8 valori distincte pentru firele CPU (de exemplu `1,2,4`) și selectează setul `1M` sau `10M`. NEXUS compară ratele raportate de XMRig și indică numărul de fire cu cea mai bună rată măsurată. Funcția nu configurează automat minerul activ și nu se conectează la pool. Dacă XMRig nu este instalat, răspunsul este `backend_unavailable`. Pentru o decizie de producție sunt necesare teste susținute pe calculatorul țintă, share-uri acceptate, temperatură și consum electric.


## RandomX nativ v1.2.3 și laboratorul cu 20 de antete

Sursa oficială RandomX v1.2.3 se află în `vendor/randomx-1.2.3/`. Pentru benchmarkul nativ:
- Linux: rulează `tools/build_randomx_benchmark.sh`.
- Windows: rulează `tools/build_randomx_benchmark.bat` dintr-un mediu în care CMake și compilatorul C/C++ Visual Studio sunt disponibile.
- Laborator 20 antete: Linux `tools/build_randomx_20block_benchmark.sh`; Windows `tools/build_randomx_20block_benchmark.bat` din Developer Command Prompt Visual Studio.

În dashboard, panoul „RandomX Development · laborator 20 antete” trimite cererea la `POST /api/mining/randomx/20block-benchmark`. Parametri: 1–64 fire, 100–50.000 hash-uri per antet. Motorul folosește modul fast (dataset complet 2.080 MiB), același seed pentru toate cele 20 de intrări sintetice și ținte experimentale de 8–14 biți zero inițiali. Răspunsul include H/s măsurat, hashes/targets găsite per antet și starea offline.

Atenție: aceste „antete” sunt blob-uri de test inventate pentru a exercita RandomX. Nu sunt block templates Monero, nu includ structura consensuală completă a unui bloc și nu sunt trimise pe o rețea. RandomX este algoritmul PoW folosit de Monero, iar în producție seed-ul/epoch-ul și hashing blob-ul trebuie să provină dintr-un nod sau pool real, printr-un adaptor compatibil cu protocolul Monero. Laboratorul nu demonstrează validitatea unui bloc Monero și nu generează recompense.

Dificultatea experimentală (8–14 biți zero la începutul hash-ului) afectează doar numărul statistic de candidați care trec ținta. Nu accelerează și nu încetinește calculul RandomX în H/s. Nu compara H/s RandomX cu H/s SHA-256d sau cu algoritmul unui alt miner.


## NEXUS 0.10.24 — RCSC integrat

RCSC este integrat în Research Hub. API: `GET /api/research/rcsc/status`, `POST /api/research/rcsc/collect` (1–200 blocuri), `POST /api/research/rcsc/analyze`, `POST /api/research/rcsc/verify-header` și `GET /api/research/rcsc/runs/{run_id}`. Datele sunt salvate în SQLite (`data/nexus_rcsc.sqlite3`). Colectarea folosește exclusiv date publice read-only. Taxele tranzacțiilor sunt raportate separat de subsidy. Analizele nonce/reward sunt exploratorii; split-ul cronologic 70/30 nu dovedește predictibilitate și nu demonstrează o slăbiciune SHA-256.

Detalii și limite: `RCSC_INTEGRATION_AUDIT_RO.md`.
