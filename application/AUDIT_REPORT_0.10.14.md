# Audit milestone NEXUS 0.10.14

## Acoperire

Implementarea conectează controllerul NEXUS la un worker Stratum V1 intern pentru Bitcoin SHA-256d pe CPU. Fluxul include TCP/TLS, subscribe, authorize, set_difficulty, notify, set_extranonce, coinbase cu extranonce, Merkle branch, header de 80 bytes, target de share, target de bloc, scanare nonce și mining.submit.

## Corectitudine byte-order

Header-ul Bitcoin serializează version, ntime, nbits și nonce little-endian. Stratum furnizează prevhash și Merkle branches în ordinea de serializare a protocolului; codul păstrează acești bytes. Genesis block regression test verifică header-ul de referință și hash-ul Genesis.

## Integrare

`/api/mining/start` → `_compatibility()` → `mining.controller.start()` → `StratumBitcoinWorker.start()` → Stratum job → `scan_nonce_range()` → `mining.submit` → contor accepted/rejected în `/api/mining/status`. Stop este conectat la același lifecycle controller. Dashboard-ul poate selecta motorul intern pentru BTC/SHA-256d/CPU.

## Teste executate

222 teste pentru întregul proiect PASS; 7 teste dedicate worker-ului Stratum PASS. Testul integrat pornește controllerul/API-ul cu un mock pool TCP, validează subscribe și authorize, reconstruiește independent coinbase/Merkle/header (inclusiv prevhash nenul) din câmpurile submit-ului, verifică hash-ul cu SHA-256d și testează răspuns acceptat și respins. Un test verifică Genesis header și digest, precum și serializarea prevhash/nonce pe câmpuri nenule.

## Limitări

Nu a fost executat un test pe un pool public deoarece acest test trebuie făcut cu wallet-ul BTC public și endpoint-ul ales de operator, cu acordul utilizatorului. Motorul CPU Python este pentru validarea protocolului și experimentare, nu pentru mining BTC competitiv. Nu există încă reconectare automată, Stratum V2, BIP310 version rolling sau backend nativ C/GPU.


## Măsurare de performanță în mediul de build

Un benchmark cu 2.000 nonce-uri a măsurat 4.082 H/s cu verificare `hashlib` pe fiecare nonce. Este o măsurare a mediului Linux de build, nu a laptopului utilizatorului; confirmă doar că motorul este funcțional și lent, nu performanță competitivă Bitcoin.
