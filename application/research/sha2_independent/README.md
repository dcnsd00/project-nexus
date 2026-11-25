# NEXUS Research — pachet de cercetare SHA-256 / SHA-512 (criptanaliză + optimizare mining)

Pachet executabil pentru cercetarea independentă a SHA-256/SHA-512: criptanaliză pe
runde reduse (diferențial, message modification, SAT), analiză statistică și
optimizări exacte de mining (midstate, precompute nonce-invariant), cu validare
independentă contra `hashlib` și a blocului Genesis Bitcoin.

**Citește `raport_tehnic.md` pentru rezultatele complete, măsurătoare și limite.**
Rezultatul central: nu există scurtătură criptanalitică pentru SHA-256 complet;
câștigurile reale, măsurate, sunt de inginerie exactă (1,58× în C pe hardware real).

## Cerințe

- Python 3.10+ (testat pe 3.14)
- `pip install -r requirements.txt` (doar `python-sat`, pentru modulul SAT)
- opțional: gcc/clang (pentru `bench_c/`, benchmark pe hardware real)

## Instalare

Linux / macOS:
```bash
cd research/sha2_independent
python3 -m venv .venv && source .venv/bin/activate   # opțional
pip install -r requirements.txt
python3 research_main.py test
```

Windows (PowerShell):
```powershell
cd research/sha2_independent
python -m venv .venv; .\.venv\Scripts\Activate.ps1    # opțional
pip install -r requirements.txt
python research_main.py test
```

Pentru benchmark-ul C:
- Linux: `gcc -O2 -march=native -o bench_c/miner_bench bench_c/miner_bench.c && ./bench_c/miner_bench`
- Windows: `gcc -O2 -o bench_c/miner_bench.exe bench_c/miner_bench.c` (MinGW-w64 / MSYS2)
  apoi `.\bench_c\miner_bench.exe`

## Utilizare

```bash
python3 research_main.py <comanda> [--seed 42] [--time-budget 180] [--out-dir results] [--quick]
```

| Comandă | Ce face |
|---|---|
| `test` | 13 teste unitare: vectori NIST SHA-256/512, echivalență hashlib, midstate, Genesis, runde reduse, SAT |
| `stats` | monobit χ², corelații intrare-ieșire (Bonferroni), independentă nonce |
| `avalanche` | biți schimbați per rundă (difuzie) |
| `differential` | căutare diferențială hill-climbing + annealing, runde 3–6, validare pe set proaspăt |
| `msgmod` | message modification: E1 (control determinist (a₁,e₁)) + E2 (data-driven, runde 2–3) |
| `sat` | SAT preimage parțial pe 6–12 runde (build/solve/verificare raportate separat) |
| `benchmark` | benchmark Python: naiv vs midstate vs hashlib (rezultate identice verify) |
| `verify` | re-verificare independentă a rezultatelor din `results/` |
| `all` | totul, în ordine |

Exemple:
```bash
python3 research_main.py sat --quick
python3 research_main.py differential --rounds 3 4 5 --time-budget 120   # via modul direct
python3 -m nexus_sha.differential_search --rounds 3 4 5 6 --n-validation 20000
python3 -m nexus_sha.sat_smt_solver --rounds 6 8 10 12 --fixed-words 1
python3 -m nexus_sha.benchmark --n 20000
```

Modulele au CLI propriu (seed-uri fixe, bugete de timp, output JSON):

```bash
python3 -m nexus_sha.differential_search --seed 42 --out results/differential.json
python3 -m nexus_sha.message_modification --seed 42
python3 -m nexus_sha.stats_analysis --seed 42
```

## Reproducerea rezultatelor din raport

```bash
python3 research_main.py all          # ~10-15 min cu --quick; ~40-60 min complet
```

Fiecare experiment scrie JSON în `results/` cu: configurație, seed, timpi,
intervale de încredere Wilson 95% și setul de validare separat de cel de căutare.
`python3 research_main.py verify` re-verifică rezultatele salvate pe date noi și
iese cu cod ≠0 dacă orice verificare eșuează.

## Garanții metodologice

- fiecare afirmație de accelerare e măsurată contra unui baseline corect, pe
  aceleași date, cu rezultate identice bit-cu-bit cu `hashlib`;
- soluțiile SAT sunt verificate cu o implementare separată de encodare;
- diferențialele raportate sunt re-estimate pe date care nu au fost folosite la
  căutare (intervale de consistență binomială);
- un test inclus (`verify_results.false_positive_demo`) demonstrează detectarea
  supraînvățării pe setul propriu;
- coliziunile/preimage-urile pe runde reduse NU sunt prezentate ca atacuri pe
  SHA-256 complet; benchmark-urile sintetice NU sunt prezentate ca rezultate
  hardware reale (benchmark-ul C este măsurat pe CPU real, scalar).

## Structură

Vezi §10 din `raport_tehnic.md`.


> Integrare NEXUS MASTER: sursa canonică este `research/sha2_independent`; copia `nexus_research` este păstrată sincronizată pentru compatibilitate.
