# NEXUS 0.9.2 — Raport SHA-256 Differential Research

## Domeniu și interpretarea lui „2000”

SHA-256 standard are **64 de runde interne**. În aceste experimente, valoarea 2000 înseamnă **2000 de probe independente** (blocuri aleatoare de 512 biți) pentru fiecare configurație. Variantele cu 1–63 runde sunt funcții de compresie reduse, nestandardizate, folosite exclusiv în cercetare.

Pentru fiecare probă se aplică o diferență XOR fixată blocului de intrare, apoi se compară cele 256 de biți ai ieșirilor funcției de compresie, cu starea inițială SHA-256 standard. Se măsoară distanța Hamming, rata de flip pentru fiecare bit de ieșire, numărul ieșirilor diferențiale identice și propagarea diferenței în message schedule W0–W63.

P-value-ul pentru bitul cu abaterea maximă este calculat prin test binomial bilateral exact. Se aplică o corecție Bonferroni pentru cei 256 de biți testați și, în sweep-uri, pentru toate configurațiile din sweep. Seturile de confirmare folosesc seed-uri noi și nu reutilizează blocurile din setul de explorare.

## Amploarea benchmark-ului

Au fost rulate **1.158.000 de probe pereche** în total, însumând sweep-urile exploratorii, controlul la 64 de runde și seturile independente de confirmare. Fiecare probă pereche compară blocul de bază cu blocul modificat XOR, deci au fost evaluate 2.316.000 de căi de compresie. Valorile de throughput sunt benchmark-uri în mediul de build și nu reprezintă performanța laptopului utilizatorului.

## Rezultatele principale — diferența W14 bit 0

| Runda | Distanță Hamming medie | Observație |
|---:|---:|---|
| 4–14 | 0 / 256 | W14 nu a fost încă consumat de prefixul de runde executat |
| 15 | 3,99 / 256 | Primul efect apare când este procesat W14 |
| 16 | 25,37 / 256 | Difuzie încă foarte incompletă |
| 17 | 55,85 / 256 | Difuzie în creștere |
| 18 | 88,05 / 256 | Difuzie parțială |
| 19 | 115,92 / 256 | Aproape de medie, dar cu biți puternic părtinitori |
| 20 | 126,36 / 256 | Apare o abatere puternică la nivelul unor biți; bitul de ieșire 6 are rată de flip 21,25% în setul de 2000 |
| 21 | 128,16 / 256 | Media este aproape 128, dar un test separat cu 100.000 de probe găsește o corelație mai slabă pe bitul de ieșire 31 |
| 22–32 | Aproximativ 128 / 256 | În sweep-ul W14 de 2000 probe, niciun maxim pe bit nu rămâne semnificativ după corecția pentru multiple teste |
| 64 | 127,81 / 256 | Controlul standard, compatibil cu comportamentul așteptat pentru ieșiri SHA-256 |

Confirmarea independentă pentru W14 bit 0 la 20 de runde a măsurat rata de flip de **22,286%** pe bitul de ieșire 6 în 100.000 de probe. La 21 de runde, pentru bitul de ieșire 31, rata a fost **52,488%** în 100.000 de probe. Acest ultim efect este mult mai mic și nu a fost evident în sweep-ul de numai 2000 de probe.

## Poziția cuvântului și message schedule

Au fost comparate diferențe de un bit în W13, W14 și W15. Prima rundă la care diferența intră în calcul corespunde indicelui cuvântului: W13 este consumat în runda 14, W14 în runda 15, iar W15 în runda 16. Acest lucru explică de ce primele rezultate identice din rundele reduse nu reprezintă un „bit slab” sau o vulnerabilitate, ci faptul că diferența nu a intrat încă în calcul.

Laboratorul raportează pentru fiecare W0–W63 frecvența cu care se schimbă cuvântul și numărul mediu de biți schimbați. În plus, măsoară diferențele dintre carry-out-urile celor trei adunări modulo 2^32 folosite la extinderea fiecărui cuvânt W16–W63. Carry-urile din adunările T1/T2 ale rundelor nu sunt încă incluse în acest profil.

## Diferențe cu mai mulți biți

La 20 și 21 de runde au fost testate opt configurații: un bit, doi biți adiacenți, doi biți distanțați, patru biți într-un cuvânt și diferențe combinate între W13/W14/W15. Mai multe tipare au avut abateri mari după corecția Bonferroni. Șase candidați au fost apoi retestați pe seturi independente de 50.000 de probe și au reprodus direcția și amplitudinea generală a corelației:

- W14 bit 0, 20 runde: bitul de ieșire 6 ≈ 22,532% flip;
- W14 biții 0 și 1, 20 runde: bitul de ieșire 6 ≈ 28,690%;
- W14 biții 0 și 16, 20 runde: bitul de ieșire 20 ≈ 59,548%;
- W15 bit 0, 20 runde: bitul de ieșire 21 ≈ 99,966%;
- W14 bit 0 plus W15 bit 0, 20 runde: bitul de ieșire 6 ≈ 23,034%;
- W15 bit 0, 21 runde: bitul de ieșire 6 ≈ 22,382%.

O observație exploratorie slabă la W15/24 runde nu s-a reprodus în holdout-ul independent de 50.000 de probe și este păstrată ca rezultat nereplicat, nu ca descoperire.

## Ce înseamnă și ce nu înseamnă

Rezultatele arată propagare incompletă și corelații puternice în variantele cu runde reduse, în special când diferența este introdusă târziu în bloc. Ele nu arată o vulnerabilitate a SHA-256 complet, nu găsesc preimagini sau coliziuni și nu reduc munca necesară pentru un share valid în mining. Un pool verifică algoritmul complet și respinge orice hash obținut printr-o variantă redusă sau modificată.

De aceea, laboratorul este conectat la NEXUS ca modul de cercetare, cu rapoarte reproductibile, dar este izolat de minerul activ. Pentru Mining Engine pot fi promovate doar optimizări care păstrează exact rezultatul algoritmului standard cu 64 de runde și care trec benchmark-uri independente.

## Verificare și integrare

- Implementarea la 64 de runde a fost comparată cu `hashlib.sha256` pe cinci vectori; toate au corespuns.
- Numărul de runde este validat între 1 și 64; o cerere pentru 2000 de runde interne este respinsă.
- Dashboard: Laborator Matematic → SHA-256 · Laborator diferențial.
- API: `/api/research/sha256/info`, `/differential`, `/sweep`, `/multi-delta` și `/results` sub prefixul `/api/research/sha256`.
- Rezultatele sunt salvate local în `modules/sha256_research/results/`.
- `consensus_compatible` este întotdeauna `false` pentru aceste experimente.
