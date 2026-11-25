# NEXUS 0.10.1 — cercetare SHA-256 avansată

## 1. Căutare diferențială multi-bit

Integrează ideea `sha256_search.py`: diferențe XOR pe 16 cuvinte de 32 biți, urmărire rundă cu rundă a stării interne și hill-climbing. Toți candidații sunt comparați pe același set de blocuri aleatoare (common random numbers), iar candidatul final este măsurat separat pe un holdout independent.

Metricile sunt greutatea Hamming medie a diferenței de stare și frecvența empirică a diferenței complete celei mai comune în eșantion. Frecvența modului NU este probabilitatea unei căi diferențiale; nu se înmulțesc frecvențele între runde.

Limitele implicite sunt deliberate: maximum 120 pași, 96 probe de căutare, 3 restart-uri și maximum 1.000.000 unități de lucru.

## 2. Codificare SAT/CNF

Integrează ideea `sha256_sat.py`: model Tseitin CNF pentru compresia SHA-256 cu IV standard și diferență XOR nenulă între două blocuri. Vectorii sunt stocați LSB-first, dar biții de ieșire impuși ca prefix sunt ordonați explicit MSB-first, la fel ca verificarea independentă a digestului. Această corecție evită o verificare inconsistentă a prefixului.

`selfcheck` atribuie toate cuvintele de intrare, rulează propagarea unitară a circuitului și compară digestul rezultat cu implementarea Python de referință. `solve` folosește opțional python-sat, limitează formula la 24 runde reduse, verifică independent modelul și aplică timeout 1–30 secunde. Exportul DIMACS funcționează fără python-sat.

## 3. API

- `GET /api/research/sha256/advanced/info`
- `POST /api/research/sha256/advanced/search`
- `POST /api/research/sha256/advanced/track`
- `POST /api/research/sha256/sat/selfcheck`
- `POST /api/research/sha256/sat/solve`
- `POST /api/research/sha256/sat/dimacs`

## 4. Semnificație și limite

SHA-256 standard rămâne 64 de runde. Căutarea diferențială și SAT operează pe variante reduced-round și sunt strict research-only. Nu demonstrează o scurtătură pentru SHA-256 complet, nu produc share-uri pool valide și nu intră în motorul de mining. Orice candidat de optimizare pentru mining trebuie să păstreze exact ieșirea algoritmului standard și să treacă teste A/B cu share-uri acceptate.

Solverul SAT este opțional: `INSTALL_RESEARCH_SOLVER.ps1` instalează `requirements-research.txt` în mediul virtual local. Self-check și DIMACS export nu necesită solver.
