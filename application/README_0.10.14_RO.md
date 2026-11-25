# NEXUS MASTER 0.10.14 — Stratum Bitcoin integrat

## Motor nou

În tab-ul Mining, selectează `BTC` și un endpoint Stratum V1, apoi alege `CPU`. Dashboard-ul selectează `NEXUS Bitcoin SHA-256d CPU (experimental)`. Introdu adresa Bitcoin publică de payout, worker și parola furnizate de pool. Activează TLS numai dacă endpoint-ul are port TLS publicat de operator. Pentru pool SOLO, selectează modul `Solo pool`.

`START MINER` pornește worker-ul intern. `STOP MINER` închide sesiunea. Monitorizarea raportează rata locală H/s, difficulty, job ID, hash-uri scanate și share-uri trimise/acceptate/respinse. Un share este considerat acceptat numai după răspunsul `mining.submit` al pool-ului.

## Limitări

Acesta este un motor CPU Python de referință, nu un miner Bitcoin competitiv. Rata măsurată în mediul de build a fost ~4.189 H/s; rata pe sistemul Windows va fi diferită. La această rată, motorul nu este o alternativă practică la ASIC și nu promite recompense. Pentru NerdMiner ESP32 folosește setarea de endpoint din firmware; pentru ASIC folosește software-ul/firmware-ul oficial al dispozitivului.

Nu introduce seed phrase sau private key. NEXUS are nevoie doar de adresa publică BTC pentru autentificarea worker-ului la pool. Verifică atent adresa, host-ul și portul înainte de pornire. TLS folosește validarea normală a certificatelor.

## Testare

Rularea țintită a suitei: `python -m pytest -q tests/test_stratum_session_01010.py tests/test_bitcoin_pow_engine_0113.py tests/test_sha2_research_bridge_0113.py tests/test_mining_controller_090.py tests/test_mining_catalog_099.py tests/test_pool_connectors_0104.py tests/test_stratum_miner_014.py`

Pentru întregul proiect: `python -m pytest -q` (222 teste PASS în build-ul verificat). Testele folosesc pool mock pe `127.0.0.1`; nu conectează contul utilizatorului și nu trimit share-uri publice.

Testele de integrare reconstruiesc header-ul independent în serverul mock, cu `prevhash` nenul și Merkle branch, apoi verifică hash-ul SHA-256d și răspunsurile ACCEPTED/REJECTED.
