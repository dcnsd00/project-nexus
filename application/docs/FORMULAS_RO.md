# Formule implementate în MULTIMINER X 1.0

## Probabilitatea de a găsi un bloc (model Poisson)

Pentru același algoritm și aceeași unitate de hashrate:

- `H_u`: hashrate-ul minerului;
- `H_n`: hashrate-ul total al rețelei;
- `T_b`: timpul mediu de bloc;
- `T`: intervalul analizat.

`lambda = (H_u / H_n) * (T / T_b)`

`E[blocuri] = lambda`

`P(cel puțin un bloc în T) = 1 - exp(-lambda)`

`Timp mediu până la un bloc = T_b * H_n / H_u`

Formula presupune că rata de hash și dificultatea sunt staționare pe interval. Nu include stale/orphan blocks, pool fee, reorgs sau variația viitoare a dificultății.

## Monte Carlo

Se repetă de 100.000 de ori un experiment Bernoulli cu probabilitatea analitică `p = 1 - exp(-lambda)`. Frecvența observată estimează p, iar eroarea standard este `sqrt(p_hat * (1-p_hat) / N)`. Seed-ul implicit este fix pentru reproductibilitate.

**Monte Carlo nu este un algoritm de mining.** Nu prezice nonce-uri, nu reduce SHA-256/RandomX/PearlHash și nu oferă un avantaj față de dificultatea PoW.

## Paralelism: legea lui Amdahl

`Speedup(N) = 1 / ((1 - f) + f/N)` unde f este fracția paralelizabilă și N numărul de worker threads. Este o limită teoretică; memoria, cache-ul, temperaturile, power limit și sincronizarea reduc viteza reală.

## Energie

`kWh = P_watts * hours / 1000`

`Cost = kWh * tariff_RON_per_kWh`

`J/hash = P_watts / H_hashes_per_second`

Folosiți puterea măsurată la priză pentru întreg laptopul. Telemetria GPU nu reprezintă consumul total al laptopului.

## Model termic concentrat RC (sensibilitate)

`T(t) = T_ambient + P * R_theta * (1 - exp(-t / (R_theta * C_theta)))`

`R_theta` este rezistența termică în °C/W, `C_theta` capacitatea termică în J/°C. Ambele trebuie calibrate din măsurători. Modelul nu substituie senzorul real al GPU/CPU.

## Limita fizică a optimizării

Optimizările de paralelism, alocare, precomputare, memorie, instrucțiuni SIMD și control termic reduc overhead-ul ori cresc eficiența. Nu schimbă funcția PoW și nu elimină necesitatea calculării hashurilor complete. Un rezultat de benchmark pentru SHA-256d nu poate fi transferat ca hashrate pentru RandomX sau PearlHash.
