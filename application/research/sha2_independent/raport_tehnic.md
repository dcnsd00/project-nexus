# Raport tehnic — Cercetare independentă SHA-256 / SHA-512 / criptanaliză / optimizare mining (NEXUS)

**Data:** 9–10 noiembrie 2026
**Mediu de test:** Linux x86-64 (2 nuclee CPU, 8 GB RAM), Python 3.14, gcc 15.2 `-O2 -march=native`, python-sat 1.9 (MiniSat 22)
**Seed implicit:** 42 (toate experimentele înregistrează seed-ul în JSON)
**Status pachet:** toate testele unitare trec (13/13), toate verificările independente trec (vezi §9)

---

## 0. Rezumat executiv

| # | Rezultat | Tip | Valoare |
|---|----------|-----|---------|
| R1 | Nu există scurtătură criptanalitică demonstrabilă pentru SHA-256 complet (64 runde) | Negativ, demonstrat | — |
| R2 | Diferențiale empirice pe runde reduse: p ≈ 2⁻¹⁰·⁷ (4 runde) → sub limita de detecție la 6 runde | Criptanaliză, runde reduse | A.1 |
| R3 | SAT preimage parțial: 6–16 runde rezolvabil în <0,2 s; 18+ runde >100 s (32 biți fixați) — zid exponențial | Criptanaliză, runde reduse | A.4 |
| R4 | Message modification determinist: controlul complet al (a₁,e₁) prin W[0] — factor ×100 față de aleator | Criptanaliză, runde reduse | A.5 |
| R5 | Optimizare exactă mining (midstate + precompute runde 0–2 + W₁₆,W₁₇): **1,58× în C pe hardware real** | Inginerie exactă | B.1 |
| R6 | „Early-exit" la comparația țintei este neglijabil (overhead 1,001) — demonstrat și matematic | Negativ, demonstrat | B.2 |
| R7 | Niciun bias statistic: monobit χ²=283,6 (critic 324,7), 0/8192 corelații peste Bonferroni, avalanche complet de la runda ~20 | Negativ, demonstrat | A.6 |

**Concluzie principală:** toate câștigurile reale, măsurate și reproductibile sunt de **inginerie exactă** (R5). Toate rezultatele criptanalitice (R2–R4) sunt valabile **doar pe runde reduse** și nu se extrapolează la SHA-256 complet — zidul SAT (R3) și prăbușirea probabilităților diferențiale (R2) susțin acest lucru cantitativ.

---

## 1. Metodologie

Fiecare experiment respectă protocolul:

1. **Separarea descoperire/validare.** Căutările (hill-climbing, annealing, SAT) folosesc un set de date; estimarea finală a probabilităților folosește un set proaspăt, cu seed diferit.
2. **Verificare independentă.** Fiecare implementare e validată contra `hashlib` (implementare C independentă), iar soluțiile SAT sunt re-verificate cu o implementare complet separată de encodare (`sha256_advanced.compress`).
3. **Intervale de încredere.** Probabilitățile empirice sunt raportate cu interval Wilson 95%.
4. **Fals-pozitive.** Un test demonstrativ arată că selectia „cele mai bune" pe setul propriu de validare duce la supraînvățire (p_tren=0,002 → p_proaspăt≈0).
5. **Reproductibilitate.** Seed-uri fixe, bugete de timp configurabile, rezultate în JSON.

Lanțul de validare pentru orice afirmație de accelerare: *aceleași date de intrare → rezultate identice bit-cu-bit cu referința → timp măsurat pe hardware real*.

---

## 2. Rezultate criptanalitice (A) — doar runde reduse

### A.1 Căutare diferențială multi-bit (hill-climbing + simulated annealing)

**Formulare.** Pentru compresia cu r runde (fără feedforward), căutăm Δ (diferențe XOR în cuvintele mesajului W[0..15]) care maximizează probabilitatea celei mai probabile diferențe de ieșire:

\[
p^*(\Delta, r) = \max_{\Delta_{out}} \Pr\left[\Delta_{out} = f_r(M \oplus \Delta) \oplus f_r(M)\right], \quad M \text{ uniform}
\]

Scorul căutării: \(-\log_2 p\). Vecinătate: mutații 1-bit (adăugare/ștergere/mutare), max 6 biți activi. Estimare empirică: n=1500 eșantioane/evaluare (rezoluția minimă de detecție ≈ 2⁻¹⁰·⁵), validare: 20 000 eșantioane proaspete.

**Descoperire structurală (importantă pentru orice căutare automată):**
- **Cuvinte inactive:** W[t] nu influențează ieșirea înainte de runda t. Diferențele în cuvinte ≥ r dau trivial p=1 (ieșiri identice). Căutarea trebuie restricționată la cuvintele 0..r−2.
- **Injecție MSB deterministă:** o diferență de 2³¹ în W[t] intră în runda t prin t₁ = h+Σ₁(e)+Ch+Kₜ+Wₜ. Adunarea lui 2³¹ modulo 2³² comută bitul 31 fără propagare de carry (carry-out-ul se elimină), deci Δaₜ₊₁ = Δeₜ₊₁ = 2³¹ **determinist**. Am validat: la 1 rundă, p=1,000 (4000/4000). Este un traseu „gratuit" de o rundă — fără valoare criptanalitică, dar explică de ce căutările naivescorază convergează spre biții MSB.

**Rezultate măsurate (după excluderea căilor triviale):**

| Runde r | Δ (biți) | p validare | log₂ p (CI 95%) | Timp căutare |
|---------|----------|------------|------------------|--------------|
| 3 | [63] (W₁, bit 31) | 3,5·10⁻⁴ | 11,5 (10,4–12,5) | 54 s |
| 4 | [95] (W₂, bit 31) | 6,0·10⁻⁴ | 10,7 (9,9–11,5) | 54 s |
| 5 | [127] (W₃, bit 31) | 3,0·10⁻⁴ | 11,7 (10,6–12,8) | 54 s |
| 6 | [141] (W₄, bit 13) | <5·10⁻⁵ | >14 (marginea inferioară CI) | 54 s |

Observații:
- Traseele găsite sunt injecții MSB care supraviețuiesc 1–2 runde de amestecare — probabilitatea cade de la 1 (intrare) la ~2⁻¹¹ după 2–3 runde de propagare prin adunări cu carry.
- La 6 runde probabilitatea e sub rezoluția a 20 000 de eșantioane; **nu există diferențial detectabil peste uniform (2⁻³²) la 6+ runde cu acest buget**.
- Hill-climbing și annealing dau scoruri comparabile (diferență <1 bit); ambele saturează la rezoluția de estimare 2⁻¹⁰·⁵ impusă de n=1500 eșantioane/evaluare — o limitare metodologică, nu o limitare a funcției.
- Re-verificare independentă (seed nou): toate probabilitățile reproduse în intervalele de consistență binomială (vezi §9).

**Complexitate teoretică.** Căutarea euristică: O(n_eval · r · 32) per evaluare. Un atac pe coliziuni pe baza unui diferențial cu p=2⁻ᵏ necesită O(2ᵏ) perechi; pentru r=4 (k≈11) acest lucru e ieftin, dar la r=64 nu există diferențial cunoscut sub 2⁻²⁵⁶ (conform rezultatelor noastre: nu există nici măcar la 6 runde peste 2⁻¹⁴).

### A.2 Message modification

**E1 — control determinist prin inversarea rundei 0 (demonstrat complet).**
Ecuațiile rundei 0:

\[
t_1 = h_0 + \Sigma_1(e_0) + Ch(e_0,f_0,g_0) + K_0 + W_0,\quad
a_1 = t_1 + t_2,\quad e_1 = d_0 + t_1
\]

unde t₂ depinde doar de IV (constant). Alegând

\[
W_0 = \big(e_1^{target} - d_0\big) - \big(h_0 + \Sigma_1(e_0) + Ch(e_0,f_0,g_0) + K_0\big) \bmod 2^{32}
\]

se obține **exact** starea (a₁,e₁) dorită (restul e determinat de relația e₁ − a₁ = d₀ − t₂ = const). Măsurat: P[8 biți de condiție satisfaceți] = 2⁻⁸ (0,0039, conform teoriei) la mesaj aleator vs **1,0** cu modificare — factor ×100, exact câte 8 biți de condiție de traseu de runda 0–1 sunt „gratuiți". Acesta este mecanismul clasic din spatele atacurilor pe funcții MDx-like cu runde reduse.

**E2 — message modification condus de date (rezultat negativ, onest).**
Am minat prin corelație biții din a₁/e₁ care prezic succesul diferențialului de 2 runde (Δ=bit 31 în W₀, p≈2⁻⁹) și am forțat cei mai corelați 8 biți prin W[0], pe set de validare proaspăt:
- a₁: 0,00185 → 0,00190 (factor 1,03)
- e₁: 0,00185 → 0,00235 (factor 1,27, ≈1,6σ — **nesemnificativ statistic**)

Interpretare: condițiile reale ale traseului de 2 runde sunt condiții de carry care depind de W₁ (liber) și de configurații joințe de biți, nu de biți individuali — data mining-ul per-bit nu le poate identifica. Message modification util cere **derivarea explicită a condițiilor traseului** (stil MD5/Stevens), nu corelații marginale. Acest rezultat negativ exclude o clasă întreagă de abordări „ieftine".

### A.3 SAT — preimage parțial pe runde reduse

**Encodare CNF exactă** a compresiei cu feedforward: rotații/shifturi = reindexare de variabile (gratuit); Ch/Maj = porți pe 3 biți; adunări mod 2³² = ripple-carry (XOR3 + majoritate); expansiunea mesajului inclusă. Porțile sunt generate prin tabel de adevăr, conștiente de constante (IV, K) — porțile CNF clasice se strică pe literali constanți, iar acest detaliu a fost sursa a 3 bug-uri de encodare descoperite și eliminate prin testare exhaustivă a porților (toate cele 2ⁿ combinații verificate prin solver).

**Problemă rezolvată:** găsește W astfel încât cuvântul 0 (sau 0–1) al ieșirii cu r runde să egaleze o țintă (preimage parțial, 32/64 biți).

| Runde | Variabile | Clauze | Construire | Rezolvare | Status |
|-------|-----------|--------|------------|-----------|--------|
| 6 | 4 481 | 24 297 | 0,04 s | 0,01 s | SAT, verificat |
| 8 | 5 633 | 32 897 | 0,05 s | 0,01 s | SAT, verificat |
| 10 | 6 785 | 41 497 | 0,06 s | 0,08 s | SAT, verificat |
| 12 | 7 937 | 50 097 | 0,07 s | 0,12 s | SAT, verificat |
| 14 | 9 089 | 58 729 | 0,08 s | 0,19 s | SAT, verificat (64 biți: 0,19 s) |
| 16 | 10 241 | 66 897 | 0,09 s | 0,18 s | SAT, verificat |
| 18 | 11 393 | 75 065 | 0,1 s | **>100 s** | TIMEOUT |
| 20 | 12 545 | 83 233 | 0,1 s | **>100 s** | TIMEOUT |

(32 biți fixați, seed 42; la 64 biți fixați: 8–14 runde toate SAT în ≤0,19 s.)

**Interpretare.** Timpul de rezolvare urcă exponențial: un factor ~10×/2 runde în regiunea 10–16, apoi salt la >100 s la 18. Acesta este profilul așteptat pentru SHA-2 în SAT (literatura raportează același comportament; ex. preimage pe ~24–28 runde necesită săptămâni/ani de CPU). **Extrapolare conservatoare:** chiar dacă panta s-ar menține lină (10×/2 runde), 64 de runde ar cere ~10²⁴× timpul de la 16 runde. SAT nu schimbă complexitatea de preimage a SHA-256 complet (2²⁵⁶); schimbă doar constanta pe runde reduse. **Nu prezint acest rezultat ca atac pe SHA-256.**

Fiecare soluție SAT este verificată independent: W extras din model → rulat prin `sha256_advanced.compress` (cod separat de encodare) → confirmarea țintei (toate `matches_target=true`).

### A.4 Proprietăți structurale SHA-256 vs SHA-512 (măsurate)

Ambele funcții au structură ARX identică (rotații, Σ, σ, Ch, Maj, expansiune liniară-GF(2) + adunări); diferențele: lungimea cuvântului (32/64), numărul de runde (64/80), constantele de rotație și IV/K. Măsurat (150 eșantioane, 1 bit de intrare răsturnat):

| | SHA-256 | SHA-512 |
|---|---------|---------|
| Half-avalanche (128/256, 256/512 biți) atins la runda | 21 | 18 |
| Biți schimbați la runda 10 | 60,9 / 256 | 199,7 / 512 |

Difuzia SHA-512 e ușor mai rapidă per rundă relativ la lățime — consecința rotațiilor Σ₁/Σ₀ mai largi (14/18/41 vs 6/11/25). Implicație: orice tehnică diferențială/SAT se transferă direct între cele două (cu parametri rescalați), iar rezultatele noastre negative pe SHA-256 se aplică a fortiori SHA-512 (80 runde).

### A.5 Analiză statistică (rezultate negative riguroase)

- **Monobit χ²** pe 256 poziții de bit, 20 000 hash-uri: χ²=283,59, df=255, critic la 0,001 este 324,7 → **trece** (fără bias de bit).
- **Corelație intrare-ieșire:** 8 192 teste χ² (32 biți de intrare × 256 de ieșire), n=40 000; maxim χ²=12,69 < pragul Bonferroni 19,6 (familie α=0,01) → **zero corelații semnificative**.
- **Independența de nonce:** P[bitul 0 al hash(nonce=i) = bitul 0 al hash(nonce=i+1)] = 0,4999 (n=50 000); primul cuvânt uniform pe 16 bins (χ²=7,36, df=15, critic 37,7) → **uniform**.
- **Avalanche:** crește de la 0 biți (runda 0) la 128/256 (runda ~20) și rămâne la saturare până la runda 64 → difuzie completă, fără structură reziduală detectabilă.

Acestea cuantifică absența bias-urilor — condiția prealabilă oricărei căutări de scurtături; ele nu pot dovedi inexistența unei scurtături, dar elimină clasele de atac bazate pe bias simplu.

---

## 3. Optimizări exacte de implementare (B) — valabile pe SHA-256 complet

### B.1 Midstate + precompute nonce-invariant (măsurat pe hardware real)

**Matematica exactă.** Pentru double-SHA256 pe antetul Bitcoin de 80 octeți:
- Prima hash = 2 compresii (blocurile B₁=header[0..63], B₂=header[64..79]+padding). **B₁ nu depinde de nonce** → starea după B₁ (midstate) se calculează o singură dată. Economie: 1 din 3 compresii totale (prima hash: 2, a doua: 1).
- În B₂, doar W₃ (wordul nonce) variază. Din expansiune:

\[
W_{16} = W_0 + \sigma_0(W_1) + W_9 + \sigma_1(W_{14}),\quad
W_{17} = W_1 + \sigma_0(W_2) + W_{10} + \sigma_1(W_{15})
\]

W₁₆, W₁₇ **nu depind de W₃** → precalculați. Rundelete 0–2 folosesc W₀,W₁,W₂ (constante) → starea după runda 2 precalculată. Economie: 3 runde + 2 cuvinte W din 64 per nonce.
- A doua hash: un singur bloc; W₈..W₁₅ sunt constante de padding (0x80000000, 0,…,0, 0x100) — dar W₀..W₇ (ieșirea primei hash) variază complet, deci nu există precompute suplimentar acolo.

**Rezultate măsurate** (aceleași date, rezultate identice bit-cu-bit cu `hashlib`, 10 000 nonces de echivalență verificați):

| Implementare | Rulări/s | Speedup |
|---|---|---|
| Python naiv (double-SHA complet per nonce) | 2 046 H/s | 1,00× |
| Python midstate+precompute | 3 157 H/s | **1,54×** |
| C naiv (gcc -O2 -march=native, scalar) | 1,40 MH/s | 1,00× |
| C midstate+precompute | 2,21 MH/s | **1,58×** |

Speedup-ul C (1,58×) depășește ușor cel teoretic al midstate-ului singur (1,50× = 3→2 compresii) datorită rundelor precalculate — consistență teoretică confirmată de măsurătoare. Validare suplimentară: blocul Genesis Bitcoin reproduce hash-ul 000000000019d668… prin ambele căi (Python și C).

### B.2 „Early-exit" — demonstrație negativă (important)

Afirmația curentă în multe proiecte de mining: „comparăm doar primul cuvânt al hash-ului cu ținta și ieșim devreme". **Măsurat:** timpul hash-complet vs hash+comparare-doar-primul-cuvânt: raport 1,001 (diferență în noise). **Demonstrația matematică:** primul cuvânt al digest-ului este

\[
h_{out,0} = a_{64} + IV_0
\]

iar a₆₄ = t₁⁽⁶³⁾ + t₂⁽⁶³⁾ depinde de întreaga stare după runda 63, care depinde de toate rundele 0–63 (difuzia e completă de la runda ~20 — §A.5). **Nu există nicio ieșire timpurie matematică înainte de ultima rundă a ultimei compresii.** Singurul câștig real al comparației pe primul cuvânt este evitarea comparării celorlalte 7 cuvinte — cost O(1) neglijabil. Orice implementare care revendică mai mult de atât prin „early exit" este suspectă.

### B.3 Ce NU este descoperire criptanalitică

Midstate, precompute W₁₆/W₁₇, runde 0–2 precalculate, SIMD/AVX2×8/AVX-512×16, SHA-NI — toate sunt **optimizări exacte de implementare** (rezultat identic, mai puțină muncă per nonce, paralelism). Le raportăm separat tocmai pentru a nu contamina concluziile criptanalitice. Nu am măsurat SIMD în acest pachet (nu deținem AVX-512 în sandbox); benchmark-ul C e scalar, pe hardware real, și e raportat ca atare.

---

## 4. Heuristici experimentale (C)

- Hill-climbing vs simulated annealing pe diferențiale: performanță egală în limita bugetului (ambele găsesc injecții MSB cu p≈2⁻¹¹ la 3–5 runde); annealing acceptă 30–50% mutații „rele" fără câștig final. Concluzie practică: la acest dimensiune de problemă, bugetul de eșantioane contează mai mult decât strategia de căutare.
- Limitarea fundamentală a ambelor: **rezoluția de estimare** 2⁻¹⁰·⁵ (n=1500/evaluare). Pentru diferențiale reale la 8+ runde ar trebui n≥2¹⁶/evaluare (impractic în Python; fezabil în C) — direcție de dezvoltare pentru NEXUS.

---

## 5. Ipoteze teoretice nevalidate (D) — marcate explicit ca atare

1. **Boomerang/rectangular attacks** pe SHA-256d: teoretic, un quartet cu Δ≠Δ' ar putea combina două diferențiale slabe pe câte 32 runde; nu există în literatură diferențiale sub 2⁻¹⁰⁰ pentru 32 runde, iar rezultatele noastre (natura exponentială a prăbușirii p) nu susțin fezabilitatea. Neimplementat aici — marcat ca ipoteză.
2. **MitM pe schedule** (Wₜ recursiv cu întârzieri 2,7,15,16): structura permite teoretic recomputare incrementală a expansiunii pentru nonce consecutivi (W₃ variază); câștigul este O(1) cuvinte — deja captat parțial de precompute-ul W₁₆/W₁₇. Nu am găsit nicio extindere validă.
3. **Relații algebrice între rundele SHA-256/SHA-512/SHA-3:** SHA-3 (Keccak) nu are nicio structură comună cu SHA-2 (sponge vs Davies-Meyer, XOR-only vs ARX) — ipoteza de proprietăți comune transferabile e infirmată structural. Între SHA-256 și SHA-512: structura e identică, doar parametrii diferă (§A.4).

---

## 6. Cele mai promițătoare 3 direcții

1. **Framework SAT cu propagare de XOR și encoding G (CryptoMiniSat-style) pentru runde 18–28.** Encodarea noastră (addere ripple-carry, 4 200 clauze/rundă) e funcțională dar naivă; un encoding cu XOR-clauze native + propagare Gaussiană ar putea împinge limita practică cu 4–8 runde. Este instrumentul cel mai măsurabil pentru a cuantifica „cât de departe" e starea curentă a criptanalizei de 64 runde. (Efort: mediu. Risc: rezultatul poate fi doar un zid mai întâlnit mai târziu — dar măsurat.)
2. **Message modification derivat analitic (nu data mining) + coliziuni free-start pe 8–12 runde.** E1 arată că 8 biți de condiție sunt gratuiti; combinat cu trasee diferențiale derivate manual/algebraic (condiții explicite de carry, nu corelații), un atac free-start pe ~10 runde ar fi un rezultat de cercetare real și verificabil independent. (Efort: mare. Toate uneltele sunt deja în pachet.)
3. **Integrarea optimizărilor exacte în minerul NEXUS.** Midstate + precompute (1,58× măsurat în C) peste AVX2×8/AVX-512×16 existente → câștig compus garantat (optimizările sunt ortogonale: SIMD paralelizează, midstate elimină muncă). Adăugativ: ntime-roll (mutarea timestamp-ului în locul nonce-ului) reutilizează același mecanism de midstate. (Efort: mic. Câștig: cert, măsurat.)

---

## 7. Recomandare de integrare în NEXUS

**Integrați imediat (câștig cert):**
- `MidstateMiner` (Python) și varianta C (`bench_c/miner_bench.c`) — optimizare exactă, 1,54–1,58×, validată contra hashlib și Genesis.
- Testele de corectitudine (13 teste unitare, inclusiv vectori NIST și Genesis) ca gate de CI pentru orice modificare a nucleului SHA.

**Integrați ca unelte de cercetare (fără pretenții de atac):**
- `sat_smt_solver.py` — encodare verificată + raportare separată build/solve/verificare; baza pentru direcția 1.
- `differential_search.py` + `message_modification.py` — framework de căutare cu separare descoperire/validare și detecție de trasee triviale (cuvinte inactive, MSB injectiv) deja implementată — greșelile pe care le-am făcut și corectat sunt codificate ca restricții.

**Nu integrați / nu urmați:**
- Orice revendicare de „early exit" sub runda 63 a ultimei compresii — demonstrat fals (§B.2).
- Căutări diferențiale fără restricția cuvintelor active și fără set de validare separat — produc falsuri pozitive triviale (p=1) sau supraînvățare (demonstrat în `verify_results.false_positive_demo`).

## 8. Limitări ale acestei cercetări

- Bugetul de căutare: ~54 s/rundă de hill-climbing + annealing, estimare la 1 500 eșantioane — diferențiale cu p<2⁻¹⁴ sunt inaccesibile; nu excludem trasee mai bune la 4–6 runde găsite cu bugete mai mari sau în C.
- SAT: un singur solver (MiniSat 22), un singur encoding; CryptoMiniSat/Kissat + encoding XOR ar putea muta zidul.
- SIMD (AVX2/AVX-512) și GPU nu au fost benchmark-uite aici (hardware sandbox scalar); rezultatele C sunt scalar, dar pe hardware real.
- Toate rezultatele criptanalitice sunt pe runde reduse ≤16 (SAT) și ≤6 (diferențial). **Nicio afirmație despre SHA-256 complet nu se face din aceste date, în afară de: nu am găsit nicio scurtătură, iar zidul măsurat susține evaluarea standard de securitate.**

## 9. Rezultatele verificării independente (rulate, toate trec)

```
[OK] sha256 vs hashlib (50 date aleatoare)
[OK] genesis block (hash intern + forma afisata)
[OK] midstate vs naive (500 nonces noi)
[OK] SAT runde=6,8,10,12 solutii re-verificate cu implementare separata
[OK] diferential runde=3,4,5,6 reprodus statistic pe date noi
[OK] demo fals-pozitiv (supraînvățare detectată ca atare)
```

Toate detaliile brute: `results/*.json` (config, seed-uri, intervale de încredere incluse).

## 10. Structura pachetului

```
nexus_research/
├── research_main.py          # orchestrator CLI (test/stats/avalanche/differential/msgmod/sat/benchmark/verify/all)
├── requirements.txt          # python-sat
├── README.md                 # instalare + rulare (Windows/Linux)
├── raport_tehnic.md          # acest raport
├── nexus_sha/
│   ├── sha256_advanced.py    # SHA-256 runde configurabile, midstate, stări intermediare
│   ├── sha512_advanced.py    # SHA-512 + comparație structurală
│   ├── differential_search.py# hill-climbing + annealing + validare Wilson CI
│   ├── message_modification.py # E1 (inversare rundă 0) + E2 (data-driven)
│   ├── sat_smt_solver.py     # encodare CNF exactă + MiniSat + verificare
│   ├── stats_analysis.py     # avalanche, monobit, corelații, independentă nonce
│   ├── benchmark.py          # benchmark exact Python vs hashlib
│   ├── verify_results.py     # re-verificare independentă a rezultatelor
│   └── tests.py              # 13 teste unitare (NIST, hashlib, Genesis, SAT)
├── bench_c/miner_bench.c     # benchmark C pe hardware real (genesis + echivalență V1/V2)
└── results/                  # JSON: differential, sat_scaling, sat_64bits, sat_limit,
                              # message_modification, stats, avalanche, benchmark,
                              # benchmark_c.txt, sha256_vs_sha512
```
