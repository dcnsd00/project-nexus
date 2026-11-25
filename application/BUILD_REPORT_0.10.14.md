# NEXUS MASTER 0.10.14 — raport build și verificare

Data build: 10 noiembrie 2026

## Rezultat
- 222 teste automate pentru proiect: PASS.
- 7 teste dedicate worker-ului Stratum V1: PASS.
- `py_compile` pentru controller, API, sesiunea Stratum și motorul SHA-256d: PASS.
- `node --check` pentru JavaScript-ul dashboard-ului: PASS.
- Arhiva ZIP: verificare integritate PASS.

## Flux verificat local
Dashboard/API → controller → worker Stratum TCP → subscribe → authorize → set_difficulty/notify → coinbase/extranonce → Merkle root → header 80 bytes → scanare nonce SHA-256d → mining.submit → răspuns ACCEPTED sau REJECTED → status/metrics.

Pool-ul mock este pe loopback `127.0.0.1`. El reconstruiește independent coinbase, Merkle root și header-ul din valorile transmise la `mining.submit`, folosește prevhash nenul și verifică SHA-256d separat. Include răspunsuri de acceptare și respingere.

## Byte order
- version, ntime, nbits, nonce: serializare little-endian în header.
- prevhash: bytes din câmpul Stratum păstrați în ordinea de serializare transmisă; implementare comparată cu CGMiner, care concatenează câmpul `prev_hash` în header înainte de hex decode: https://raw.githubusercontent.com/ckolivas/cgminer/master/util.c (funcția parse_notify, aproximativ liniile 2261–2271).
- Merkle root: hash-ul dublu SHA-256 al coinbase combinat cu branches, în byte order intern.
- Genesis block regression test: PASS.

## Performanță observată
Benchmark de 2.000 nonce-uri: 4.082,31 H/s în mediul Linux de build, cu comparație `hashlib` la fiecare nonce. Aceasta nu este o măsurare pe laptopul utilizatorului și nu este hashrate competitiv pentru Bitcoin.

## Limite
- Nu s-a conectat pool public în această verificare.
- Nu s-a folosit wallet real și nu s-a trimis share extern.
- TLS folosește validarea certificatelor. TCP simplu este disponibil doar când operatorul pool-ului documentează acel endpoint.
- Fără reconectare automată la `client.reconnect`, fără BIP310 version rolling, fără Stratum V2.
- Motor CPU Python este pentru referință/test de protocol, nu alternativă la ASIC sau miner ESP32.
