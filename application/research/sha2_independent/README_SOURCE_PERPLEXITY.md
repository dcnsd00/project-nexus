# NEXUS - pachet de cercetare SHA-256/SHA-512: criptanaliza, SAT, mining

Pachet de cercetare reproductibil, cu seed-uri fixe, verificare independenta
(`hashlib`) si separare clara intre: **(A)** criptanaliza reala, **(B)** optimizare
exacta a implementarii, **(C)** euristici experimentale, **(D)** ipoteze nevalidate.
Vezi `RAPORT_TEHNIC.md` pentru concluzii si recomandari.

## Instalare

### Linux / WSL2
```bash
sudo apt-get install -y build-essential python3
pip install -r requirements.txt   # optional: python-sat, pt solver SAT real
```

### Windows
Doua optiuni:
- **WSL2** (recomandat): instaleaza Ubuntu din Microsoft Store, apoi pasii de mai sus.
- **MSYS2/MinGW** (fara WSL): instaleaza [MSYS2](https://www.msys2.org/), apoi:
  ```
  pacman -S mingw-w64-x86_64-gcc python
  ```

`python-sat` (necesar pt rezolvare SAT reala, nu doar toy-solver-ul inclus):
```bash
pip install python-sat[pblib,aiger]
```

## Structura

| Fisier | Ce face | Categorie |
|---|---|---|
| `sha256_advanced.py` | SHA-256 referinta, runde configurabile, verificat vs `hashlib` | infrastructura |
| `sha512_advanced.py` | SHA-512 referinta, runde configurabile, verificat vs `hashlib` | infrastructura |
| `diffusion_common.py` | test de avalansa generalizat (compara SHA-256 vs SHA-512) | A (criptanaliza) |
| `differential_search.py` | cautare diferentiala cu simulated annealing + verificare independenta | A (criptanaliza) |
| `message_modification.py` | tehnica de corectie a mesajului (stil Wang et al.), testata empiric | A (criptanaliza) |
| `sat_smt_solver.py` | codificare SAT (Tseitin) + solver DPLL propriu + export DIMACS | A + B |
| `miner.c` | miner Bitcoin real (5 variante), validat pe blocul genesis | B (optimizare) |
| `benchmark.py` | ruleaza tot, cu limite de timp, scrie JSON/CSV | infrastructura |
| `verify_results.py` | verificare independenta, detectie fals-pozitive | infrastructura |
| `research_main.py` | orchestrator CLI | infrastructura |

## Rulare rapida (sanity check, ~1 minut)

```bash
python research_main.py all --quick --timeout 300
```
Ruleaza selftest-urile, apoi un benchmark redus, si tipareste un rezumat din `results/`.

## Rulare completa

```bash
python research_main.py all --full --timeout 3600
```

## Rulare module individuale

```bash
# Avalansa / difuzie (compara SHA-256 cu SHA-512)
python diffusion_common.py

# Cautare diferentiala la un numar de runde
python differential_search.py --rounds 20 --steps 2000 --samples 80 --out results/diff_r20.json

# Message modification
python message_modification.py --rounds 16 --n-conditions 8 --trials 500

# SAT: verificare encoding (fara solver)
python sat_smt_solver.py selfcheck 20

# SAT: rezolvare cu solverul propriu (doar instante mici, ~runde<=4)
python sat_smt_solver.py solve --engine dpll --rounds 4 --bits 16 --timeout 60

# SAT: export DIMACS pt un solver extern (kissat, cadical, etc.)
python sat_smt_solver.py dimacs --rounds 20 --bits 256 --out results/r20.cnf
# apoi, cu solverul instalat separat:
#   kissat results/r20.cnf

# SAT: rezolvare cu python-sat (daca e instalat)
python sat_smt_solver.py solve --engine pysat --rounds 16 --bits 64 --timeout 600

# Minerul C
gcc -O3 -march=native -pthread -o miner miner.c
./miner bench 40000000
./miner run 3 8 400000000   # varianta AVX2, 8 thread-uri

# Verificare independenta completa
python verify_results.py
```

## Limite de mediu cunoscute (vezi RAPORT_TEHNIC.md pt detalii)

- Solverul SAT inclus (`dpll_solve`) e scris in Python pur si NU e potrivit
  pentru instante mari (>~12 runde SHA-256). E inclus doar ca sa demonstreze
  ca intreg pipeline-ul (formula -> rezolvare -> verificare independenta)
  functioneaza corect. Pentru rezultate reale, instaleaza `python-sat` sau
  exporta DIMACS si foloseste `kissat`/`cadical`.
- Nu exista varianta GPU/CUDA inclusa (necesita hardware NVIDIA pt compilare
  si testare, indisponibil in mediul in care a fost scris acest pachet).
  `miner.c` are variante CPU (scalar, AVX2, AVX-512) validate real.
