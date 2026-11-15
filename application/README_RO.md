# NEXUS MASTER 0.10.6


This is the consolidated source bundle assembled from the prior PROJECT NEXUS workbench and the wallet / local-chain laboratory work.

## Included source

- `core/PROJECT-NEXUS-LOCAL`: FastAPI + SQLite, tasks, notes, agents, approvals, audit, SymPy math and synthetic banking sandbox.
- `adapters/multiminer_x/MULTIMINER_X_v1.0`: Windows controller source for XMRig CPU and SRBMiner GPU, mathematical models and offline research benchmarks.
- `adapters/fieldstation/crypto_fieldstation`: Android/Termux source and its unit tests.
- `modules/wallet_benchmark`: BTC address formats, EVM derivation, BIP39/BIP32-related recovery lab and earlier benchmark artifacts.
- `modules/blockchain_regtest`: Bitcoin Core Regtest + Anvil JSON-RPC integration source and Compose definition.
- `mining/profiles.json`: algorithm-specific profiles and requested hashrate targets.
- `modules/sha256_research`: SHA-256 reduced-round differential lab, exact binomial testing, W0–W63 message-schedule profile, multi-bit XOR pattern sweeps and saved reports.
- `nexus_master.py`: local control plane exposing manifest, readiness, mining, wallet, coin/pool, crypto benchmark and SHA-256 research endpoints.

## Important implementation status

A module being present does not mean its external provider is connected or its hardware path has run. The core plugin registry contains definitions; provider adapters are not all implemented. Crypto Fieldstation remains a separate Android/Termux edge process. Miner binaries are installed on demand through the NEXUS Miner Pack manager from configured official upstream sources; they are not embedded in the Python source ZIP. The local chain integration requires Docker, Bitcoin Core and Anvil; those daemons are not installed in every environment.

## Run NEXUS locally (Windows PowerShell)

```powershell
py -3 -m venv .venv
.\\.venv\\Scripts\\Activate.ps1
py -m pip install -r core\\PROJECT-NEXUS-LOCAL\\requirements.txt
py -m pip install pytest
$env:PYTHONPATH = (Resolve-Path .).Path
py -m uvicorn nexus_master:app --host 127.0.0.1 --port 8765
```

Open `http://127.0.0.1:8765`. New diagnostic endpoints:
- `/api/nexus/master`
- `/api/nexus/readiness`
- `/api/nexus/modules`
- `/api/mining/profiles`
- `/api/mining/hardware`

## Wallet Manager 0.6.1

Open `http://127.0.0.1:8765/wallet` after starting NEXUS.
- Creates a local EVM key and stores it encrypted with scrypt + AES-GCM.
- Unlock checks the encrypted keystore and verifies address/key correspondence.
- Supports a watch-only address book for Ethereum, Base, BNB, Polygon and Arbitrum.
- Does not expose private keys, generate a BIP39 phrase, or broadcast mainnet transactions.
- BTC recovery remains a separate offline local tool. Do not use this beta vault for material funds until an independent security audit.

## Tests

```powershell
py -m pip install pytest httpx
py -m pytest tests -q
```

Run the existing adapter tests separately:

```powershell
py -m pytest adapters\\multiminer_x\\MULTIMINER_X_v1.0\\tests -q
py -m pytest adapters\\fieldstation\\crypto_fieldstation\\tests -q
```

## Mining targets: do not conflate algorithms

The requested 2 MH/s CPU and 5 TH/s GPU targets are recorded but not marked achieved. Hashrate is algorithm-specific:
- the included SHA-256d benchmark measures synthetic 80-byte header hashing and is not pool mining;
- the SHA-512 test is digest throughput (MiB/s), not PoW;
- XMRig RandomX and SRBMiner PearlHash require the official external miner binaries and accepted shares from a pool to establish live mining rate;
- 5 TH/s SHA-256d is ASIC-class, not a generic consumer-GPU expectation. A GPU target is meaningless until an algorithm and GPU model are fixed.

A previous SHA-256d research run in a 5-logical-CPU container measured median 4,358,238 hashes/s in the midstate microbenchmark (four worker threads) and 2,483,729 hashes/s in the baseline. This does **not** prove 2 MH/s on the user's laptop, does not apply to RandomX, and does not prove pool shares or rewards.

## Safety / scope

- Wallet recovery only for wallets owned by the user or with explicit authorization.
- Never paste a real seed phrase or private key into chat.
- The local-chain benchmark must use Bitcoin `regtest` and Anvil development accounts only.
- No mainnet write endpoint is included in this master API.
- No external miner is started automatically by the diagnostic endpoints.
- The core approvals table records decisions; it is not a production transaction-signing policy engine.

## Crypto Engine 0.7.0

New endpoints:
- `/api/crypto/algorithms`
- `/api/crypto/hash`
- `/api/crypto/benchmark`

Supported primitives include SHA-2, SHA-3, SHAKE, BLAKE2, SHA-256d and HMAC-SHA256. The experimental `hybrid_sha256_blake2b` is research-only and must not be used for consensus, signatures, key derivation or protecting funds. See `docs/CRYPTO_ENGINE_0.7.0_RO.md` and `results/crypto_engine_benchmark_0.7.0.json`.

## Version 0.7.0 test additions

Run `bash run_full_audit.sh` on Linux or `RUN_ALL_TESTS.ps1` on Windows. Offline test success does not imply that live provider adapters, GPU mining, public-chain transfers or payouts have been validated.


## NEXUS 0.8.0 — interfață Windows și cataloage

1. Extrage arhiva într-un folder local, de exemplu `C:\NEXUS`.
2. Deschide PowerShell în folder și rulează `Set-ExecutionPolicy -Scope Process Bypass`, apoi ` .\INSTALL_NEXUS_WINDOWS.ps1`.
3. Pornește `START_NEXUS_WINDOWS.bat` sau scurtătura de pe Desktop.
4. Interfața este la `http://127.0.0.1:8765/api/nexus/dashboard`.

Dashboard-ul include cele cinci domenii: Mining & Pool-uri, Catalog Crypto, Laborator Matematic, Blockchain & Wallet și diagnostice. Catalogul crypto se sincronizează la cerere din CoinPaprika și este păstrat local 6 ore. Lista de pool-uri este un catalog inițial verificat documentar pentru endpoint-urile 2Miners RVN/KAS/ETC; nu reprezintă toate pool-urile existente. Pentru orice altă monedă se poate introduce endpoint personalizat după verificarea documentației operatorului. Configurația generată nu pornește minerul.

Instalarea Python și dependențele sunt automate după instalarea inițială a Python 3.11+. Miner binaries, drivere GPU, Docker/Bitcoin Core/Anvil și servicii externe rămân componente separate și trebuie instalate/verificate conform documentației lor.


## NEXUS 0.9.1 — Mining control, pool-uri și diagnostic live

- Selector coin → pool → miner → CPU/GPU; monedele din catalog fără pool cunoscut rămân catalogate, dar nu sunt marcate automat ca minabile.
- Catalogul de pool-uri include endpoint-uri 2Miners și WoolyPooly pentru RVN, KAS și ETC, plus endpoint Stratum personalizat. Lista este parțială, nu un index exhaustiv al tuturor pool-urilor.
- Control START/STOP pentru XMRig și SRBMiner-MULTI dacă executabilele oficiale sunt instalate local. XMRig este limitat în acest build la profil CPU; GPU CUDA necesită plugin extern. lolMiner, GMiner, Rigel și TeamRedMiner sunt detectate în inventar, dar adaptoarele lor de lansare nu sunt încă activate.
- Statusul se actualizează la 2,5 secunde: proces, PID, uptime, hashrate dacă API-ul minerului îl expune, share-uri, CPU/RAM și telemetrie NVIDIA disponibilă.
- Diagnostic de erori pentru executabil lipsă, conectivitate pool, autentificare, algoritm, VRAM, drivere GPU, share-uri respinse și TLS; jurnal local în `mining/runtime/miner.log`.
- Nu descarcă automat binare și nu execută comenzi arbitrare din pool. Instalează minerii numai din sursele oficiale și indică executabilul local.

### Limite de validare 0.9.1

Testele automate validează API-ul, controlul de stare, validările și diagnosticul offline. Nu au fost pornite miner reale în acest mediu, nu s-au trimis share-uri către pool și nu s-au verificat temperaturile pe laptopul Windows. Valorile de hashrate/share apar numai dacă API-ul minerului le raportează; datele GPU necesită `nvidia-smi`, iar CPU/RAM detaliate necesită `psutil`.


## NEXUS 0.9.1 – Miner Pack Manager

Interfața Mining include un manager de pachete pentru XMRig, SRBMiner-MULTI, T-Rex, lolMiner, GMiner și Rigel, prin API-ul oficial GitHub Releases. TeamRedMiner are momentan doar legătură spre pagina oficială; nu se descarcă din mirror-uri terțe. Arhivele ZIP sunt verificate pentru path traversal, limită de dimensiune, executabilul așteptat și SHA-256 atunci când upstream publică digest. Dacă upstream nu publică digest, NEXUS raportează explicit `local_sha256_only`; hash-ul local nu dovedește autenticitatea. Executabilele sunt extrase, nu lansate automat.

Endpoint-uri: `GET /api/mining/installers`, `GET /api/mining/installers/{id}/latest`, `POST /api/mining/installers/{id}/install`.


## SHA-256 Differential Research Lab 0.9.2

Open Dashboard → Laborator Matematic → SHA-256 · Laborator diferențial. The UI defaults to 2,000 independent probes per configuration. SHA-256 itself has 64 internal rounds; “2,000” refers to the number of statistical samples, not the number of rounds. The lab supports reduced-round compression research, output-bit bias, exact binomial p-values, Bonferroni correction, W0–W63 message-schedule propagation, schedule carry-out comparisons, curated multi-bit XOR patterns, and local JSON reports.

The lab is **research-only**. Reduced-round results are not pool-compatible and are never passed to active mining. The 64-round implementation is checked against Python `hashlib.sha256` using five test vectors. Only optimizations that preserve exact standard 64-round outputs may be considered for a mining adapter. See `docs/SHA256_DIFFERENTIAL_REPORT_0.9.2_RO.md` and `modules/sha256_research/results/NEXUS_SHA256_RESEARCH_MASTER_REPORT.json`.

Research API endpoints:
- `GET /api/research/sha256/info`
- `POST /api/research/sha256/differential`
- `POST /api/research/sha256/sweep`
- `POST /api/research/sha256/multi-delta`
- `GET /api/research/sha256/results`


## SHA-256 Compression Carry Lab 0.9.5

The differential lab now includes per-round carry-decision telemetry for the four sequential additions in T1, the T2 addition, and the state updates `d + T1` and `T1 + T2`. The new dashboard action is **Analiză carry T1/T2** and the API endpoint is `POST /api/research/sha256/compression-carries`. Carry tracing is observational; it uses exact modulo-2^32 arithmetic and is regression-tested to return the same compression state as the reference implementation. It is not a mining shortcut.


## NEXUS 0.9.5
Vezi `CHANGELOG_0.9.5.md`, `AUDIT_REPORT_0.9.5.md` și `docs/NEXUS_0.9.5_MINING_DASHBOARD_RO.md`. Pentru aplicația desktop rulează instalatorul Windows actualizat și pornește scurtătura `NEXUS Desktop`; motorul FastAPI local și conexiunile web existente sunt păstrate.


## NEXUS 0.9.5 – Math Intelligence

- Benchmark exact SHA-256/SHA-512/SHA-3/BLAKE2 throughput in Laborator Matematic → Research Hub.
- Solver modular pentru congruențe liniare, cu verificare exactă.
- Evaluator Turbo cu criterii stricte și fără aplicare automată.
- Experimentele rămân locale; throughput hash nu este hashrate PoW.
- Audit: 146 teste trecute; vezi `AUDIT_REPORT_0.9.5.md`.


## NEXUS 0.9.7 — Solo Pool, formular dinamic și pachet Windows

- Selectorul de pool ascunde câmpurile custom dacă endpoint-ul este predefinit și alege automat un miner compatibil cu algoritmul/dispozitivul, cu prioritate pentru un executabil detectat.
- Host, port și algoritm sunt preluate din catalog; câmpurile custom apar numai pentru endpoint-ul Custom. TLS este dezactivat când nu există port TLS catalogat. Wallet-ul de payout rămâne introdus de utilizator.
- `POOL` și `SOLO_POOL` sunt moduri distincte. SOLO este permis numai pentru pool-uri marcate astfel în catalog.
- Solo local cu nod propriu nu este încă activ: necesită nod complet sincronizat, RPC securizat și adaptor Stratum/proxy.
- Pentru Windows x64: `BUILD_NEXUS_WINDOWS.ps1` generează distribuția PyInstaller pe un calculator Windows; `INSTALL_NEXUS_WINDOWS.ps1` o instalează și creează shortcut. În lipsa buildului EXE, scriptul oferă instalarea Python/pywebview. Vezi `packaging/README_WINDOWS_BUILD_RO.md`.
- Pentru Linux: `./INSTALL_NEXUS_LINUX.sh`.
- Benchmark-uri: `results/benchmark_0.9.7_scenarios.json`. Include hash exact SHA-256/SHA-512/SHA-3/BLAKE2, solver modular, evaluator A/B, puzzle PoW local, coliziune digest trunchiat, dry-run de configurare POOL/SOLO.
- Audit offline: 154 teste trecute, 0 eșecuri. Nu echivalează cu test GPU, share real, payout sau bloc găsit.


## NEXUS 0.9.8 — Verthash, preflight și diagnostic Stratum

- Adăugat pool-uri Vertcoin VeinPool EU (3710/TLS 13710) și WoolyPooly (3102; fără TLS adăugat deoarece portul nu a fost confirmat), conform paginii operatorului.
- SRBMiner-MULTI include Verthash în algoritmii NEXUS și comandă dedicată GPU, cu worker în login și slow table build.
- START execută acum același gate de compatibilitate ca formularul și blochează algoritmii cu VRAM insuficient.
- Adăugat test TCP de conectivitate pentru endpoint-ul pool; testul nu autentifică Stratum și nu pretinde că a trimis share-uri.
- Separată clar interogarea recompenselor (activă doar pentru 2Miners) de configurarea minerului. Pentru alți operatori nu se afișează solduri simulate.
- Panourile de output au derulare internă; bara laterală rămâne fixată.
- Verthash dataset este estimat la circa 1,2 GB; valoarea de catalog păstrează marjă de 256 MiB.

Limitări verificate: nu s-a rulat încă un mining real pe laptopul utilizatorului din acest mediu; GPU-ul GTX 1650 Ti și SRBMiner 3.8.5 au fost detectate de utilizator în Windows, iar testele automate de aici nu pot substitui testul CUDA/Stratum local.

### Audit și date locale

Auditul pentru 0.9.8 este în `AUDIT_REPORT_0.9.8.md` (166 teste automate trecute). Arhiva de distribuție nu include bazele locale `data/nexus_wallets.db` și `data/nexus_intelligence.db`; prima poate conține seifuri de wallet, iar a doua poate conține istoric de operare. Păstrează și fă backup separat pentru bazele din instalarea existentă; nu le suprascrie la actualizare.

Pentru build Windows x64: rulează `BUILD_NEXUS_WINDOWS.ps1`, apoi `INSTALL_NEXUS_WINDOWS.ps1`. Arhiva sursă nu pretinde că include deja un `NEXUS.exe` compilat; executabilul se construiește pe Windows.


## SHA-256 Advanced Research 0.10.1

Căutare diferențială multi-bit cu holdout independent, self-check SAT/CNF, solver opțional și export DIMACS sunt disponibile în Laborator Matematic. Toate experimentele reduced-round sunt research-only și izolate de mining. Pentru solver: rulează `INSTALL_RESEARCH_SOLVER.ps1` după instalarea NEXUS.


## NEXUS 0.10.1 — cercetare SHA-256 avansată

- Căutare diferențială multi-bit cu candidați evaluați pe blocuri comune și validare pe holdout independent.
- Domeniu de căutare implicit W14/W15; prefixul de runde fără efect este exclus din funcția obiectiv, iar runda de activare este raportată.
- SAT/CNF redus-round cu self-check prin propagare unitară, verificare independentă și export DIMACS.
- Solverul `python-sat` este opțional; pentru instalare rulează `INSTALL_RESEARCH_SOLVER.ps1` după instalarea NEXUS. Fără solver, self-check și exportul DIMACS funcționează în continuare.
- Derulare independentă a conținutului secțiunilor dashboard-ului.

Toate experimentele reduced-round sunt exclusiv de cercetare. Nu accelerează SHA-256 standard, nu sunt compatibile cu consensul și nu sunt trimise către miner. Raportul și seed-urile reproducibile se află în `results/advanced_research_0.10.1.json`.

Auditul implicit execută toate suitele automate, dar omite benchmark-ul nativ SHA-256d lung pentru a limita consumul de resurse. Pentru benchmark-ul separat setează `NEXUS_RUN_NATIVE_BENCHMARK=1` înainte de `bash run_full_audit.sh`.

## NEXUS 0.10.2 — Hash Avalanche Research

În Math Intelligence există acum un test statistic de avalanșă pentru digesturile complete standard SHA-256, SHA-512, SHA3-256, SHA3-512 și BLAKE2b-256. Modifică un singur bit din mesaj și măsoară distanța Hamming dintre digesturi. Testul este reproductibil prin seed și limitat la 16–4096 probe și payload de 1–4096 bytes. O medie apropiată de 50% este doar un diagnostic statistic, nu o dovadă de securitate și nu reprezintă hashrate PoW.

## NEXUS MASTER 0.10.6 — solver hibrid, pool-uri și SOLO

- Solver hibrid: arithmetică modulară nativă, sisteme liniare raționale prin SymPy, bitvector XOR prin Z3 opțional; back-end-ul SAT pentru SHA-256 reduced-round este opțional și separat.
- `requirements-research.txt` instalează opțional `python-sat` și `z3-solver`; în Windows rulează `INSTALL_RESEARCH_SOLVER.ps1` numai după instalarea NEXUS.
- Catalog curatat: 24 de simboluri clasificate și 59 intrări de endpoint pool, cu BTC/ASIC, NerdMiner/Public Pool, RandomX CPU, monede GPU și profiluri de pool SOLO.
- 7 profile SOLO includ Public Pool BTC, Public Pool low-difficulty NerdMiner, ViaBTC account-mode selectable, Braiins Solo, CKPool, 2Miners RVN Solo și Kryptex PRL Solo.
- Configurația SOLO afișează endpoint primar/TLS, backup, format username/worker, autentificare, parolă implicită indicativă, dificultate, fee note, payout rule, device class și sursa operatorului.
- Modurile sunt distincte: `SOLO_POOL` (operator extern), `LOCAL_REGTEST` (Bitcoin Core local, regtest), `LOCAL_NODE_STRATUM_PROXY` (profil CKPool pentru nod propriu; CKPool nu este instalat sau pornit de NEXUS).
- Conectorii read-only implementați sunt 2Miners, unMineable, Kryptex și Braiins. API-urile F2Pool și ViaBTC sunt afișate ca pending, nu simulate.
- Adaptoarele de lansare efectivă rămân cele marcate `launch=true` în `mining/controller.py`; ceilalți mineri rămân inventory-only până când au argumente, parser și teste dedicate.

### Benchmark 0.10.5

- 172/172 teste NEXUS Master.
- 17/17 MultiMiner X, 12/12 Crypto Fieldstation, 15/15 Wallet Benchmark și 7/7 Wallet v0.5.
- Total audit: 223 teste, 0 eșecuri.
- Benchmark funcțional separat: 5 hash-uri complete, 256 probe/algoritm; modular și linear SymPy verificate; SHA-256 SAT encoding self-check la 1/4/12/20 runde; differential search bounded cu holdout.
- `results/BENCHMARK_REPORT_0.10.5_FUNCTIONAL.json` păstrează rezultatele și limitările.

Nu au fost rulate pe hardware-ul utilizatorului GPU mining, pool shares, payout real, solver SAT/SMT extern (dependențele nu erau instalate) sau nod Bitcoin Core/CKPool live. Un endpoint catalogat și un test Stratum local simulativ nu reprezintă dovada unui pool live.


## NEXUS MASTER 0.10.6 — extindere pool catalog

- Catalog: 24 simboluri coin, 22 PoW-mineable și 69 de profile/endpoint-uri de pool documentate.
- Furnizori noi adăugați în această versiune: Luxor BTC/LTC/ZEC/SC și Poolin BTC.
- Endpoint-urile F2Pool BTC/ETC și ViaBTC BTC/KAS au fost reconciliate cu documentația operatorilor consultată la 2026-11-09.
- 7 profile SOLO rămân disponibile: Public Pool BTC, endpoint NerdMiner Public Pool, ViaBTC BTC (mod cont), Braiins Solo, CKPool, 2Miners RVN SOLO și Kryptex PRL SOLO.
- Modurile SOLO_POOL, LOCAL_REGTEST și LOCAL_NODE_STRATUM_PROXY rămân separate; proxy-ul CKPool este numai configurație, nu proces pornit de NEXUS.
- Audit complet: 229 teste trecute, 0 eșecuri. Acesta nu validează share-uri sau payout-uri live.
- Raport: `results/BENCHMARK_REPORT_0.10.6_FUNCTIONAL.json`.


## Wallet Search & Recovery (0.10.17)

Wallet Manager include căutare locală de fișiere wallet, detectare format și fluxuri de recuperare pentru NEXUS AES-GCM, Ethereum Web3 V3, Bitcoin BIP38 non-EC, BIP39 și Solana. Bitcoin Core are verificare de parolă prin RPC loopback. Rulează NEXUS pe `127.0.0.1`; parolele se introduc local și nu sunt salvate sau afișate. Vezi `AUDIT_REPORT_0.10.17.md` și `modules/wallet_benchmark/README.md` pentru formate active și limitări.


## Recuperare wallet locală și vault BTC (0.10.19)

NEXUS poate inventaria fișiere wallet dintr-un director ales de utilizator, cu limite de adâncime și număr de fișiere. Recunoaște structuri Ethereum Web3 V3/NEXUS keystore, candidate Bitcoin Core `wallet.dat`, candidate Electrum/Monero/MetaMask și markeri BIP38 în fișiere text. Un nume de fișier nu confirmă singur formatul. Vârsta fișierului (`file_age_days`) este doar metadata locală și nu este vechimea ultimei tranzacții.

Cheile BIP38 0x0142 furnizate explicit de proprietar pot fi decriptate în memorie, validate prin adresa derivată și recriptate într-un vault Bitcoin NEXUS separat. Cheile private/WIF nu sunt returnate de API. Vault-ul Bitcoin poate fi redeschis prin parola proprie, cu verificare de adresă.

Bitcoin Core poate inspecta numai un wallet încărcat explicit într-un nod local, prin RPC loopback. Raportul afișează solduri, adrese publice, tranzacții înregistrate și o estimare a inactivității. Pentru backup-urile vechi, lipsa tranzacțiilor în istoricul wallet-ului nu este concludentă fără rescan/reindex.

NEXUS nu caută pe blockchain portofele dormante aparținând terților, nu ghicește parole și nu exportă chei private brute. Un transfer real este o tranzacție publică permanentă: ștergerea unui wallet local sau a unei chei nu șterge istoricul blockchain și nu face adresa să dispară.


## SHA-2 Research Package integrat (0.10.20)

Pachetul independent de cercetare SHA-256/SHA-512 este conectat la API și la Research Hub. Sursa canonică este `research/sha2_independent/`; detalii și limite în `docs/SHA2_RESEARCH_INTEGRATION_0.10.20_RO.md`.

API disponibil: `/api/research/sha2/status`, `/selftest`, `/benchmark`, `/avalanche`, `/statistics`, `/differential`, `/message-modification`, `/message-modification/e2`, `/sat/solve` și `/verify`. Experimentele sunt salvate local, sunt limitate ca resurse și nu pornesc sau modifică minerul.

Verificatorul folosește nonce Bitcoin little-endian și confirmă SHA-256d independent cu `hashlib`. SAT real necesită `python-sat`; în lipsa lui, endpoint-ul de rezolvare răspunde explicit cu HTTP 501. Rezultatele reduced-round rămân cercetare, nu optimizări compatibile cu consensul Bitcoin.


## NEXUS MASTER 0.10.21 — remedieri și motor SHA-256d nativ

Versiunea 0.10.21 adaugă backend-ul C opțional pentru SHA-256d, conectat la workerul Stratum V1 intern. Selecția SIMD este făcută după capabilitățile CPU; dacă biblioteca nativă nu se poate construi sau încărca, se folosește motorul Python de referință. Vezi `CHANGELOG_0.10.21.md`, `AUDIT_REPORT_0.10.21.md` și `mining/native/BUILD_WINDOWS_RO.md`.

Catalogul CoinPaprika folosește acum cache stale-if-error și fallback explicit la catalogul local NEXUS. Schema Bitcoin vault este inițializată la pornirea aplicației fără decriptarea sau rescrierea înregistrărilor. Desktop shell selectează un port loopback liber dacă portul 8765 este ocupat.

## Release 0.10.23

Versiunea 0.10.23 adaugă supervisorul de mining hibrid Standard/Development, procese CPU/GPU independente, cercetare SHA-256d locală Regtest/Testnet, protecții de resurse și optimizare bazată pe măsurători. Consultă `README_0.10.23_RO.md` pentru API, operare și limite.
