# Integrare SHA-256 / SHA-512 Research în NEXUS MASTER 0.10.20

## Ce a fost conectat

Sursa canonică este `research/sha2_independent/`. NEXUS expune acum serviciul `modules/sha2_research_service.py` și API-ul:

- `GET /api/research/sha2/status`
- `POST /api/research/sha2/selftest`
- `POST /api/research/sha2/benchmark`
- `POST /api/research/sha2/avalanche`
- `POST /api/research/sha2/statistics`
- `POST /api/research/sha2/differential`
- `POST /api/research/sha2/message-modification`
- `POST /api/research/sha2/message-modification/e2`
- `POST /api/research/sha2/sat/solve`
- `POST /api/research/sha2/verify`

Dashboard-ul Research Hub are controale pentru status, self-test, verificarea rezultatelor salvate, benchmark CPU, avalanșă, statistici, căutare diferențială, message modification și SAT.

Experimentele sunt salvate local în `research/sha2_independent/results/nexus_api/`. Nicio acțiune nu pornește minerul, nu contactează pool-uri și nu aplică automat un candidat.

## Corecții de validare

- Verificatorul independent serializa nonce-ul Bitcoin big-endian. Corectat la little-endian (`struct.pack('<I', nonce)`).
- Directorul implicit de rezultate din orchestrator/verificator era dependent de directorul curent. Acum se rezolvă relativ la pachetul de cercetare.
- `message_modification.apply_modification` folosea un seed aleator extern chiar când experimentul avea seed fix. RNG-ul este acum injectabil și E1 este reproductibil pentru același seed.
- Copia secundară `nexus_research/nexus_sha` a fost sincronizată cu sursa canonică pentru a elimina diferențele de endianness.

## Rezultate verificate în acest build

- Suita independentă: 13 teste executate, 12 PASS și 1 SKIP dacă `python-sat` lipsește. Skip-ul este testul de rezolvare SAT reală; nu este raportat drept PASS.
- Verificarea rezultatelor salvate: PASS pe implementări SHA-256, Genesis, 500 nonce-uri noi, soluțiile SAT salvate, rezultatele diferențiale cu eșantioane noi și demonstrația de fals-pozitiv.
- Benchmark CPU midstate: se verifică identitatea rezultatului cu baseline-ul și `hashlib`; nu se prezintă drept hashrate GPU sau mining real.
- `python-sat` și Z3 nu sunt instalate în mediul de audit curent. Endpoint-ul SAT solve raportează explicit dependența lipsă (HTTP 501), nu produce rezultate simulate. Self-check/encoding și exportul DIMACS existent rămân disponibile.
- GCC este disponibil; CUDA `nvcc` nu este disponibil. Nu s-a compilat și nu s-a integrat minerul C în acest pas, conform deciziei de a aștepta fișierele minerului furnizate separat.

## Benchmark curent al adaptorului Python

Pe 2.000 de nonces în sandbox, adaptorul midstate Python a măsurat 1,621× față de varianta Python naivă. Primele 100 de nonces au fost comparate bit-cu-bit cu `hashlib`. Este o măsurătoare locală a codului Python de referință, nu un benchmark C/AVX, GPU sau al minerului de producție. Rezultatul este păstrat în `research/sha2_independent/results/nexus_api/`.

## Discrepanță în materialul furnizat

`OVERVIEW.txt` descrie un câștig până la aproximativ 20x pentru o variantă AVX-512 și menționează un `miner.c` cu cinci variante. Raportul tehnic detaliat din pachet menționează aproximativ 1,58x pentru benchmark-ul C, iar auditul de integrare 0.10.13 precizează că valorile vechi nu au fost acceptate după corectarea ordinii nonce-ului și cer rerulare. În arhiva NEXUS inspectată există `bench_c/miner_bench.c`, dar nu sursa completă `miner.c` descrisă în OVERVIEW.

Prin urmare, NEXUS nu declară câștigul de 20x ca validat în 0.10.20. Va fi reevaluat când utilizatorul furnizează minerul și scripturile reale; testul va folosi același header, nonce little-endian, verificare SHA-256d independentă și benchmark repetat pe hardware-ul țintă.

## Limite criptanalitice

Diferențialele, SAT și message modification sunt experimente pe compresii SHA-256 cu runde reduse. Ele nu reprezintă o scurtătură pentru SHA-256 complet și nu pot fi utilizate la validarea share-urilor sau blocurilor Bitcoin. SHA-256/512 complete rămân funcții exacte verificate cu `hashlib`.
