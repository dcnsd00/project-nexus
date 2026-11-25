# NEXUS MASTER 0.10.14

## Milestone închis: Stratum V1 → SHA-256d → mining.submit

- Modul nou `mining/stratum_miner.py`: worker Stratum V1 cu TCP sau TLS verificat prin certificatele sistemului.
- Flux conectat: subscribe → authorize → set_difficulty → notify → coinbase/extranonce → Merkle root → header 80 bytes → scanare nonce → comparare share/block target → `mining.submit` → răspuns accepted/rejected.
- Suport `mining.set_extranonce`; rotație extranonce2 la epuizarea spațiului de nonce.
- Contorizare: hash-uri scanate, H/s, difficulty, shares submitted/accepted/rejected, job curent și jurnal de evenimente.
- Controller integrat: miner intern `nexus-btc-cpu`, pornire/oprire/status; fără executabil extern.
- Dashboard: selecție automată a motorului NEXUS când se alege BTC / SHA-256d / CPU; ESP32 și ASIC rămân opțiuni externe.
- Corecție header: version, ntime și nbits din `mining.notify` sunt serializate little-endian în header, iar nonce-ul este little-endian. Genesis block test reușește.

## Verificare locală

- 222 teste pentru întregul proiect PASS; 7 teste dedicate worker-ului Stratum PASS.
- Mock pool local reconstruiește independent coinbase, Merkle root și header-ul (cu prevhash nenul), verifică hash-ul prin hashlib și răspunde atât ACCEPTED, cât și REJECTED.
- Testele verifică și conexiunea/autorizația/stop prin controller și traseul API FastAPI start/status/stop.
- Corectitudinea byte-order este verificată inclusiv prin vector Genesis și test separat cu prevhash nenul.
- Nu a fost contactat pool public, nu a fost folosit wallet real și nu s-a trimis share extern.

## Limitări reale

- Motorul este CPU Python de referință, cu verificare `hashlib` pe fiecare nonce. Nu este competitiv pentru Bitcoin mainnet; benchmark-ul mediului de build a fost aproximativ 4,189 H/s pe 5.000 hash-uri. Acest număr nu este o măsurare pe laptopul utilizatorului.
- Nu include reconectare automată la `client.reconnect`, version-rolling BIP310, Stratum V2 sau optimizare GPU.
- Pentru șanse practice la un bloc BTC, folosește ASIC; pentru NerdMiner, păstrează firmware-ul și endpoint-ul extern dedicate. NEXUS poate urmări configurația și ulterior poate integra telemetria disponibilă.
