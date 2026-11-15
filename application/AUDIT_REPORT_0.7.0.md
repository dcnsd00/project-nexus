# NEXUS MASTER 0.7.0 — audit de integrare

**Data:** 2026-11-08  
**Bază:** NEXUS MASTER 0.6.2  
**Modificare:** Crypto Engine modular + API + benchmark + teste

## Rezultate teste executate

| Suită | Rezultat |
|---|---:|
| NEXUS master / core / wallet / crypto (pytest root) | 53 PASS |
| MultiMiner X | 17 PASS |
| Crypto Fieldstation | 12 PASS |
| Wallet benchmark / recovery | 15 PASS |
| Local-chain unit suite | 7 PASS |
| **Total** | **104 PASS / 104** |

`run_full_audit.sh` a rulat `compileall` și toate cele cinci suite. Rezultatul a fost PASS. Acestea sunt teste offline/unitare, nu teste pe dispozitivul utilizatorului.

## Crypto Engine 0.7.0

- SHA-224/256/384/512 și SHA-512/256 dacă este disponibil în runtime.
- SHA3-224/256/384/512.
- SHAKE128/256 cu lungime de ieșire configurabilă.
- BLAKE2b-256/512 și BLAKE2s-256.
- SHA-256d.
- HMAC-SHA256.
- Compozit experimental SHA-256 + BLAKE2b, cu domain separation și prefixarea lungimii intrării.
- BLAKE3 detectat doar ca opțional dacă pachetul extern este instalat.
- API: `/api/crypto/algorithms`, `/api/crypto/hash`, `/api/crypto/benchmark`.

## Benchmark măsurat

Container Linux, Python 3.13.5, 5 CPU logice; payload 1024 bytes; 3000 iterații per rundă; 3 runde per algoritm; mediană. Valorile complete sunt în `results/crypto_engine_benchmark_0.7.0.json`.

| Algoritm | Median H/s | Median MiB/s |
|---|---:|---:|
| SHA-256 | 611,476 | 597.14 |
| SHA-256d | 621,881 | 607.31 |
| SHA-512 | 393,363 | 384.14 |
| SHA3-256 | 282,911 | 276.28 |
| SHA3-512 | 189,091 | 184.66 |
| BLAKE2b-512 | 520,793 | 508.59 |
| BLAKE2s-256 | 370,936 | 362.24 |
| SHAKE256 (32-byte output) | 286,505 | 279.79 |
| Experimental hybrid | 484,423 | 473.07 |

**Limitări:** microbenchmark CPU în container; nu este hashrate de mining, nu este GPU, nu a fost rulat pe ASUS TUF și nu indică profitabilitate. Eșantionul este scurt și trebuie repetat pe hardware-ul țintă cu încălzire și măsurare de durată.

## Limite de integrare rămase

- Nu s-au executat tranzacții Bitcoin Regtest / Anvil în acest mediu; daemon-urile nu sunt instalate.
- Nu s-a făcut benchmark GPU; `nvidia-smi` nu este disponibil în runtime.
- Conectorii live ai providerilor rămân 0; catalogul de conectori nu trebuie confundat cu adaptoare funcționale.
- Wallet manager persistence/UI încă necesită retest Windows, în urma erorii SQLite readonly raportate în auditul 0.6.2.
- Nicio tranzacție mainnet, broadcast public, claim DePIN sau payout nu a fost executat.
- Compozitul experimental nu este certificat și nu se folosește pentru consens, semnături, derivare de chei sau protejarea fondurilor.

## Concluzie

Milestone-ul 0.7.0 adaugă și testează un motor hash modular și endpoint-uri de benchmark. NEXUS rămâne un workbench local în dezvoltare, nu un sistem complet de mining, wallet production sau conectori DePIN live.
