# SHA-256d CPU – benchmark experimental

Acest cod este importat din materialul de cercetare primit. În forma actuală este un benchmark de verificare pe antetul fix al blocului Genesis Bitcoin, NU un miner Stratum și NU primește job-uri de la pool.

## Compilare Linux / WSL2
```bash
gcc -O3 -march=native -pthread -Wall -Wextra -o miner_genesis_bench miner_genesis_bench.c
./miner_genesis_bench bench 200000
```

Pe Windows se recomandă WSL2 sau MSYS2/MinGW cu suportul intrinsecelor necesare. AVX2/AVX-512 trebuie verificate pe CPU. Nu rula varianta AVX-512 dacă procesorul și sistemul de operare nu o suportă.

## Limite cunoscute
- Antetul și ținta sunt fixate pe Genesis.
- Nu există Stratum subscribe/authorize/job/submit.
- `run` nu este un miner de producție.
- Testele de performanță trebuie repetate și comparate pe același interval.
- NEXUS nu pornește automat acest executabil; este un instrument de cercetare izolat.
