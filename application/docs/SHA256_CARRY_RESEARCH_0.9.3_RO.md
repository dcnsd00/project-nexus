# NEXUS SHA-256 carry research — 0.9.3 pre-release

## Scop
Extinde laboratorul diferențial cu observarea deciziilor de carry în operațiile interne ale rundelor SHA-256.

## Ce se măsoară
Pentru fiecare rundă, pe două blocuri pereche (original și modificat XOR), sunt urmărite șapte decizii:
1. cele patru transporturi succesive din suma T1: h + Σ1(e) + Ch(e,f,g) + K[t] + W[t];
2. transportul din T2: Σ0(a) + Maj(a,b,c);
3. transportul din actualizarea e: d + T1;
4. transportul din actualizarea a: T1 + T2.

Se raportează rata de dezacord a bitului carry între pereche, plus rata carry pentru blocul inițial și cel modificat. Aceste statistici descriu comportamentul traseului de calcul; nu demonstrează că un carry poate fi prezis sau eliminat.

## Invariante
- Operațiile rămân aritmetică exactă modulo 2^32.
- Instrumentarea trebuie să returneze exact același state final ca funcția de compresie de referință.
- Doar SHA-256 cu 64 de runde este standard. Runde reduse sunt exclusiv experimentale.
- Nicio măsurătoare de carry nu este exportată în miner ca scurtătură de calcul.

## Rulare
POST `/api/research/sha256/compression-carries` cu `rounds`, `samples`, `word`, `input_bit` și opțional `seed`.

Butonul „Analiză carry T1/T2” este în Laborator Matematic.
