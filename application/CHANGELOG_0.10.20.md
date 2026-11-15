# NEXUS MASTER 0.10.20

## Implementat
- Serviciu de integrare pentru pachetul independent SHA-256/SHA-512 în `modules/sha2_research_service.py`.
- API pentru status, self-test, benchmark CPU exact, avalanșă SHA-256/SHA-512, statistici, diferențiale reduced-round, message modification E1/E2, SAT solve și verificarea rezultatelor salvate.
- Controale noi în Research Hub UI.
- Persistență locală a experimentelor în `research/sha2_independent/results/nexus_api/`.
- Sursă canonică documentată și copia `nexus_research` sincronizată.

## Corecturi
- `verify_results.py`: nonce Bitcoin numeric serializat little-endian.
- `research_main.py`: director implicit de rezultate relativ la pachet, nu la directorul curent.
- `message_modification.apply_modification`: RNG injectabil pentru reproductibilitate.
- Teste istorice actualizate pentru versiunea manifestului 0.10.20.

## Validare
- NEXUS root: 259 PASS, 0 FAIL.
- MultiMiner X: 17 PASS.
- Crypto Fieldstation: 12 PASS.
- Wallet Benchmark: 15 PASS.
- Wallet v0.5: 7 PASS.
- SHA-2 research: 13 executate, 12 PASS, 1 SKIP (python-sat absent).
- Verificatorul independent pe rezultatele arhivate: PASS.
- Sintaxă JavaScript dashboard/wallet și compilare Python: PASS.

## Limitări
- `python-sat` și Z3 nu sunt instalate; SAT real nu este executat, endpoint-ul răspunde 501.
- `nvcc`/CUDA nu este disponibil.
- Minerul și scripturile de mining nu au fost modificate sau înlocuite; integrarea lor va fi făcută după primirea surselor dedicate de la utilizator.
- Câștigul AVX-512 de 20x menționat în OVERVIEW nu este validat în acest build. Raportul tehnic și auditul 0.10.13 au cifre divergente și cer rerulare după corectarea endian. Sursa `miner.c` descrisă în OVERVIEW nu este inclusă în arhiva proiectului verificată.
- Reduced-round SHA-256 rămâne exclusiv cercetare și nu poate modifica rezultatul PoW de consens.
