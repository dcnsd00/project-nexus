# NEXUS MASTER 0.9.3 — audit și cercetare SHA-256

## Audit automat

Executat `bash run_full_audit.sh` după integrarea carry tracing:
- NEXUS master: 82 passed
- MultiMiner X: 17 passed
- Crypto Fieldstation: 12 passed
- Wallet benchmark: 15 passed
- Blockchain unit tests: 7 passed
- **Total: 133 passed, 0 failed**
- Python compileall: PASS
- Dashboard JavaScript `node --check`: PASS

Acest audit este offline. Nu validează instalarea Windows pe laptop, GPU, miner real sau pool live.

## Extindere 0.9.3

- Carry tracing pe rundă pentru cele patru adunări secvențiale din T1, T2, `d + T1` și `T1 + T2`.
- Endpoint `POST /api/research/sha256/compression-carries`.
- Buton dashboard „Analiză carry T1/T2”.
- Test de echivalență: funcția instrumentată returnează exact aceeași stare finală ca implementarea de referință.
- 7 decizii carry înregistrate per rundă; toate operațiile rămân aritmetică exactă modulo 2^32.

## Experimente carry efectuate

Explorare: 12 combinații (runde 20, 21, 32, 64 × W13, W14, W15), 2.000 probe pereche/configurație. Rata de dezacord carry a variat aproximativ între 43,95% și 54,35% în operațiile/rundele cu cele mai mari valori observate.

Un candidat ales din explorare (64 runde, W13 bit 0, runda 19, operația `T1 + T2`) a arătat 52,14% în primul set de 20.000 probe (z≈6,05 față de ipoteza simplificată 50%). Acest rezultat **nu s-a replicat**: două seturi independente de 10.000 probe au dat 49,30% și 49,75%. Prin urmare, este clasificat drept candidat nereplicat / probabil efect de selecție sau fluctuație, nu descoperire.

Un control 64-runde pentru W14 bit 0, runda 50, `T1:add2`, a dat 50,10% în 20.000 probe (z≈0,28; p normal brut≈0,777). Controlul W14 la runda 19 a dat 50,40% în 10.000 probe (z≈0,80; p≈0,424).

Aceste teste arată de ce trebuie holdout independent și corecție pentru selecția multiplă. Rata de mismatch carry nu are automat distribuție Bernoulli(0,5) pentru fiecare operație condiționată; testul simplu față de 0,5 este doar screening, nu concluzie criptanalitică.

## Interpretare și limite

- Nu s-a demonstrat scurtătură, coliziune, preimagine sau reducere de complexitate pentru SHA-256 complet.
- Nu s-a găsit o optimizare validă pentru mining în aceste experimente.
- Variantele cu runde reduse rămân non-standard și necompatibile cu pool-urile.
- Carry tracing este instrumentare descriptivă; nu elimină sau aproximează operațiile.
- Nu au fost folosite încă SAT/SMT solvers.

## Laptopul utilizatorului

NEXUS nu a fost instalat și nu a fost rulat pe laptopul utilizatorului. Toate rezultatele acestui raport provin din mediul de test al construirii pachetului. Nu există încă măsurători locale de CPU/GPU, temperatură, hashrate sau shares.
