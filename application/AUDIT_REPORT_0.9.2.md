# NEXUS MASTER 0.9.2 — audit tehnic

## Audit automat — PASS

`bash run_full_audit.sh` a fost executat integral:

- NEXUS master: 79 passed
- MultiMiner X: 17 passed
- Crypto Fieldstation: 12 passed
- Wallet benchmark: 15 passed
- Blockchain unit tests: 7 passed
- **Total: 130 passed, 0 failed**
- `compileall`: PASS
- Dashboard JavaScript: `node --check` PASS
- Research API run IDs: UUID uniqueness regression test PASS

Aceste teste nu reprezintă validare de hardware Windows, pool live sau mining live.

## Modificări 0.9.2

- Laborator SHA-256 diferențial integrat în dashboard și API.
- Teste de referință SHA-256 la 64 de runde comparate cu `hashlib` pe cinci vectori.
- Validare strictă a rundelor 1–64; 2000 de runde interne sunt respinse.
- Sweep 4–32 pentru W14 bit 0, câte 2000 probe per rundă.
- Sweep-uri W13/W14/W15 și opt modele XOR cu mai mulți biți, câte 2000 probe per configurație.
- Holdout-uri independente de 50.000 și 100.000 probe pentru candidații selectați.
- Profil W0–W63 și măsurarea diferențelor carry-out pentru cele trei adunări de extensie W16–W63.
- Test binomial exact și corecție Bonferroni; rezultatele nereplicate rămân etichetate ca atare.
- Persistență locală a rezultatelor în JSON.

## Amploarea experimentelor

- 1.158.000 probe pereche în sweep-uri exploratorii și holdout-uri independente; 2.316.000 evaluări ale căii de compresie.
- 2000 înseamnă probe pentru fiecare configurație, nu runde SHA-256. SHA-256 standard are 64 de runde.
- Benchmark-ul de throughput a fost executat în mediul de build, nu pe laptopul utilizatorului.

## Rezultate științifice: limite

Experimentele detectează difuzie incompletă și corelații în compresia SHA-256 cu runde reduse, inclusiv în jurul rundelor 15–21 când diferența este plasată în W13/W14/W15. Aceste rezultate nu demonstrează o vulnerabilitate a SHA-256 standard cu 64 de runde, nu arată preimagini/coliziuni și nu permit share-uri PoW valide cu algoritmi modificați. Modulul nu este conectat la execuția minerului.

## Nevalidat în acest audit

- Nu s-a rulat pe laptopul Windows al utilizatorului.
- Nu s-a conectat la un pool live și nu s-au trimis share-uri.
- Nu s-au măsurat hashrate-uri hardware.
- Nu s-au folosit SAT/SMT solvers în această versiune; acestea rămân etapa de cercetare următoare.
- Profilul carry acoperă extensia message schedule, nu carry-path-urile T1/T2 ale rundelor de compresie.
