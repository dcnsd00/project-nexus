# Consolidare centrală — ecosistemul Crypto / DePIN

**Data consolidării:** 7 noiembrie 2026  
**Scop:** unificarea strategiilor, cerințelor, prototipurilor și echipamentelor într-o singură direcție tehnică și operațională.

## 1. Concluzie executivă

Direcția care rezultă din proiectele și artefactele crypto disponibile este un **Crypto Intelligence & Resource Orchestration Platform**, cu **PROJECT NEXUS** drept nucleu unic.

Sistemul trebuie să:

1. descopere proiecte și oportunități relevante (PoW, pool-uri, DePIN, compute, storage, bandwidth, airdrop/points, bug bounty, puzzle rewards, token launches);
2. verifice identitatea proiectului, programul oficial, condițiile de eligibilitate, mecanismul de recompensă, transferabilitatea, retragerea și lichiditatea;
3. măsoare efectiv resursele fiecărui dispozitiv (hashrate pe algoritm, accepted/rejected shares, temperatură, putere, uptime, trafic și stocare);
4. calculeze randamentul net în RON, inclusiv energie, comisioane, gas, praguri de payout, uzură și amortizarea hardware-ului;
5. recomande și, numai după validarea regulilor și aprobarea proprietarului, să aloce dispozitivele către joburile compatibile;
6. înregistreze recompensele reale și să le reconcilieze cu claim-uri, tranzacții și credite efective.

**Nu este necesar un nou miner universal.** Există deja prototipuri care pot fi transformate în adaptoare. Problema principală este lipsa conectării lor într-un sistem comun și lipsa probelor de payout/venit net repetabil.

## 2. Ce a fost verificat și ce nu

Am căutat în Biblioteca de fișiere și am citit artefactele relevante disponibile: arhivele PROJECT NEXUS 0.1.1, 0.2, 0.2.1, 0.3.0 și 0.5.0; README-urile Crypto Fieldstation 1.0/1.1; pachetul MultiMiner X 1.0 și documentația sa; formulele matematice; workbook-urile Crypto Radar și DePIN; jurnalul de cercetare și notele de puzzle.

**Limită importantă:** aceasta este o reconciliere a fișierelor și informațiilor crypto care au fost accesibile în Library și a contextului recent. Nu am avut un export integral al tuturor celor aproximativ 30 de conversații și, prin urmare, nu afirm că am citit fiecare mesaj din toate firele istorice. Fișierul Excel conține registrul surselor și marchează această limită. Pentru audit conversație-cu-conversație este necesar exportul complet al istoricului ChatGPT.

De asemenea, citirea unui README sau existența unei arhive nu înseamnă că aplicația a fost instalată pe dispozitivul utilizatorului. În această consolidare nu am controlat telefoanele/PC-urile utilizatorului, nu am instalat software, nu am trimis tranzacții și nu am verificat un payout live. Unele README-uri declară teste locale, dar acestea nu constituie benchmark pe hardware-ul utilizatorului.

## 3. Evaluarea prototipurilor și software-ului

### 3.1 PROJECT NEXUS — nucleul recomandat

Au fost găsite cinci versiuni/iterații arhivate: Core 0.1.1, Local 0.2, 0.2.1, 0.3.0 și 0.5.0.

- **0.1.1:** starter FastAPI/SQLite, domenii de lucru, conversații persistente, adapter AI opțional și operare manuală.
- **0.2/0.2.1:** task-uri, knowledge vault, registru de agenți, coadă de aprobare și audit. Aprobarea este doar înregistrată; nu execută operațiunea.
- **0.3.0:** adaugă motorul matematic SymPy, matrici, probabilități, teoria numerelor și decodări limitate; SageMath este opțional. Nu există parsere generale pentru tranzacții/ABI/NFT sau recompense DePIN.
- **0.5.0:** cea mai bună bază actuală: reunește motorul matematic, aplicația locală, sandbox bancar sintetic și un registru cu 26 de definiții de integrări.

**Limitarea critică a 0.5.0:** registrul de 26 de integrări este un catalog/configuration detector, nu 26 de conectori funcționali. Codul returnează `connected=0`; API-urile publice, RPC-urile, OAuth și adaptoarele de recompense ale furnizorilor încă trebuie implementate și testate. Sandbox-ul bancar este sintetic și nu se conectează la conturi bancare reale.

**Decizie:** NEXUS 0.5.0 devine singura aplicație principală și baza pentru următoarele versiuni. Nu dezvoltăm încă un al doilea dashboard/bază de date.

### 3.2 MULTIMINER X 1.0 — adaptorul de mining

Pachetul Windows 10/11 orchestrează:

- XMRig pentru CPU / RandomX;
- SRBMiner-MULTI pentru GPU / PearlHash/PearlPow;
- rulare separată sau simultană, loguri, telemetrie NVIDIA și oprire GPU la prag;
- formule Poisson, Monte Carlo, Amdahl, energie, J/hash și model termic RC.

Este un **controller pentru minere consacrate**, nu un algoritm propriu de hashing. Parametrul `--cpu-max-threads-hint 50` este un indiciu de autoconfigurare, nu o limită exactă de consum/încărcare de 50%; intensitatea GPU 16/31 nu garantează 50% utilizare.

Documentația clarifică explicit că 6.082 MH/s din arhiva v0.2 a fost obținut pe un mediu virtualizat AMD EPYC, nu pe laptopul Asus TUF. Nu există formulă care să transforme acel rezultat SHA-256d în 2 TH/s pe RandomX sau PearlHash. Capturile anterioare de 0.73–0.78 TH/s PearlPow și 690–849 H/s RandomX trebuie revalidate cu shares acceptate și hashrate raportat de pool.

**Decizie:** păstrăm MultiMiner X ca adaptor Windows; următorul pas este parserul de log/API și benchmark-ul real pe fiecare dispozitiv. Nu îl tratăm drept dovadă de profit.

### 3.3 Crypto Fieldstation 1.0/1.1 — adaptor mobil / Termux

Documentația descrie:

- jurnalizare de puzzle-uri publice și experimente;
- verificări exacte SHA-256, double SHA-256, SHA-512, MD5 și SHA-1;
- laborator AES-256-CBC pentru seturi finite de candidați;
- un mini-benchmark CPU care găsește nonce doar pentru puzzle demonstrativ, nu minează o criptomonedă;
- monitorizare read-only a adreselor publice pentru BTC, Ethereum, Base, Arbitrum, Optimism, BNB Chain, Polygon, Avalanche C-Chain și Solana, plus contracte ERC-20 cunoscute;
- urmărire de actualizări GitHub pentru repo-uri configurate;
- export JSON manual către ChatGPT;
- în 1.1, wrapper opțional pentru VerusHash care pornește un `ccminer` extern, verificat de utilizator.

Nu conectează wallet-uri prin WalletConnect, nu semnează, nu face claim-uri și nu trimite tranzacții. Binarul `ccminer`/`primo-arm-miner` nu este inclus în pachetul documentat și nu a fost verificat aici.

**Decizie:** păstrăm Fieldstation ca agent edge/mobil, cu jurnal local și telemetrie. Datele sale se sincronizează cu NEXUS; nu păstrăm o bază de oportunități separată.

### 3.4 Crypto Radar v2–v6 — motor de discovery și due diligence

Workbook-urile Radar reprezintă iterații ale aceluiași registru, nu produse distincte. Versiunea v6 este master-ul cel mai complet: are 13 tab-uri pentru tokenuri, pool-uri DEX, surse, checklist de verificare, watchlist, mining/rewards/wallets, registre de legitimitate, API-uri și schema proiectelor.

Sunt deja documentate surse pentru:

- tokenuri recent listate și pool-uri DEX noi;
- descoperire de contracte EVM și tokenuri Solana;
- directoare DePIN și registry-uri Cosmos;
- Acurast, Grass, AIOZ, Theta, Nodle, Monero și Ravencoin.

Limitele sunt documentate: unele API-uri sunt plătite, feed-urile sunt limitate la ultimele 48 de ore sau ultimele listări, iar un token nou listat ori un pool DEX nou nu confirmă legitimitatea, mining-ul sau o recompensă. Fără arhivare periodică nu poate fi reconstruit complet un interval istoric.

**Decizie:** păstrăm doar modelul de date și cele mai noi reguli din Radar v6; v2–v5 rămân arhive/snapshot-uri. Radar devine modul de ingestie NEXUS.

### 3.5 Utilitare specializate suplimentare

| Utilitar | Ce face conform documentației | Verdict |
|---|---|---|
| `crypto_zero_cost_watch.py` | urmărește solduri publice escrow, pagini claim/refund/bug bounty și experimente GSMG limitate | de integrat după ce codul-sursă este localizat și auditat |
| `mineable_coin_detector.py` | cercetare read-only pentru monede PoW, hashrate/dificultate/recompensă, pool și indicatori DEX | de integrat ca scanner PoW după verificarea codului și endpoint-urilor |
| GSMG Candidate Lab | seturi finite de candidați criptografici; testele documentate nu au produs soluție exactă | modul separat, nu motor de mining |
| Android Crypto Cockpit | calculator offline ACU/VRSC brut/net, energie și istoric | înlocuit de modulul economic NEXUS; valorile precompletate sunt snapshot-uri datate |
| Verus 10-minute wrapper | wrapper Termux cu timeout și limite, dar fără miner inclus | șablon de job mobil; nu este miner propriu-zis |
| NerdMiner / ESP32-S3 | proiect existent + 3 unități planificate; OLED extern necesită fork/build custom | laborator experimental, nu sursă de venit predictibil |
| Tari Universe + lolMiner | instalare raportată de utilizator în conversații | prezență și versiune neconfirmate în această verificare; inventar local necesar |
| Paper-trading bot | simulator cerut pentru 100 RON virtual pe BTC/ETH/SOL/BNB/XRP | nu a fost găsit un artefact implementat; se construiește separat în sandbox |

## 4. Evaluarea strategiilor

Registrul Excel conține **27 de direcții distincte**, separate astfel încât să nu amestecăm protocoale cu metode de recompensă:

### A. Mining și pool-uri

1. CPU PoW / RandomX (Monero) — păstrat condiționat de benchmark și payout.
2. GPU PoW / PearlHash/PearlPow — păstrat cu limitări termice și măsurare reală.
3. Pool selection și auto-switch — de integrat doar pe allowlist de pool-uri verificate.
4. BCH / SHA-256 pe HarloLabs — relevant numai pentru un ASIC adecvat; dashboard-ul din screenshot arăta hash-ul întregului pool, nu al echipamentului utilizatorului.
5. VerusHash Android — test controlat, nu mining continuu.
6. NerdMiner / ESP32 — laborator/lottery miner, nu venit.
7. Detector de monede PoW noi — util pentru discovery, dar niciun installer automat.

### B. DePIN / resurse distribuite

8. Acurast — pilot măsurat pe dispozitive, cu separarea scorurilor de tokenurile efectiv revendicabile.
9. Grass — punctele au valoare realizabilă zero până la conversie/claim/transfer confirmat.
10. AIOZ — verificarea rolului și a software-ului exact, inclusiv a stocării declarate.
11. Theta EdgeCloud — numai rolurile/programelor care plătesc efectiv operatorul.
12. Nodle — pilot secundar, după verificarea aplicației, tokenului și a regulilor din România.
13. GEODNET — map check înainte de orice antenă/stație GNSS.
14. Helium IoT — map check, model EU868 aprobat, densitate și trafic real.
15. WeatherXM — watchlist, necesită stație compatibilă, calibrare și date valide.
16. Wingbits — condiționat de hex coverage și eligibilitatea receptorului ADS-B.
17. Anyone — primul test de mini-PC, după verificarea IP public/CGNAT, porturi și regulile multi-relay.
18. Akash — amânat până la cerere/workload și randament verificat.
19. Nosana — amânat până la lista GPU compatibile și cerere reală.

### C. Recompense și oportunități

20. Wallet/NFT watch-only — de integrat în NEXUS cu adrese publice și contracte cunoscute.
21. Airdrops/quests/points — filtre stricte: fără depunere/cumpărare, eligibilitate România, fără activitate istorică dacă este cerută, token transferabil și claim funcțional.
22. Token/DEX radar — de integrat read-only; listing-ul nu este dovadă de legitimitate sau profit.
23. Puzzle/treasure hunts — modul separat de cercetare; fără promisiuni și cu verificarea live a escrow-ului.
24. Bug bounty — numai după scope, safe harbor, known issues și PoC reproductibil pe local fork.
25. Paper trading 100 RON — modul de simulare fără ordine reale.
26. Staking/DeFi — prioritate joasă din cauza lock-up, slashing, smart contract, gas și expunerii de capital.
27. Solo/lottery PoW demonstrativ — arhivat ca modul educațional, nu contabilizat ca venit.

## 5. Modelul economic obligatoriu

NEXUS nu trebuie să clasifice oportunitățile după hashrate, puncte sau prețul nominal al tokenului. Criteriul este valoarea netă, realizabilă și verificabilă.

Formula conceptuală:

`Net RON/zi = recompensă revendicabilă estimată × preț realizabil conservator × probabilitate payout × factor lichiditate − energie − pool fees − gas/withdrawal − bandwidth/storage − amortizare hardware`.

Reguli:

- punctele, scorurile, test token-urile și NFT-urile fără cale de vânzare nu sunt venit realizat;
- un payout se marchează „realizat” doar după creditare/claim și dovada tranzacției sau a creditului în cont;
- lipsa prețului, lichidității, ratei de recompensă, eligibility sau payout-ului produce statusul **NECALCULABIL / NEVERIFICAT**, nu profit pozitiv;
- se calculează scenarii conservator, bază și optimist, cu costurile introduse separat;
- energia se calculează pe puterea măsurată la priză, nu doar pe telemetria GPU;
- hashrate-urile SHA-256, RandomX și PearlHash nu se compară numeric ca și cum ar fi aceeași unitate de muncă.

Monte Carlo este potrivit pentru a simula probabilitatea de payout sau variabilitatea recompensei. Nu găsește nonce-uri mai repede, nu reduce dificultatea și nu accelerează SHA-256/RandomX/PearlHash. Legea lui Amdahl indică limitele teoretice ale paralelizării; modelul termic RC trebuie calibrat din temperaturi și putere măsurate.

## 6. Arhitectura unică recomandată

```text
                     PROJECT NEXUS — CORE / SYSTEM OF RECORD
                                      |
               +----------------------+----------------------+
               |                      |                      |
        CRYPTO RADAR             MATH & ECONOMICS       KNOWLEDGE / AUDIT
       discovery sources        net RON, odds, heat      source snapshots
               |                      |                      |
               +----------------------+----------------------+
                                      |
                            OPPORTUNITY VERIFIER
             source • contract • operator • country/device rules
             claim • transferability • liquidity • payout • costs
                                      |
                              DEVICE / JOB SCHEDULER
                  capability • profile • limits • switch cost
                                      |
        +------------------+----------+----------+------------------+
        |                  |                     |                  |
   MULTIMINER X       FIELDSTATION          DEPIN ADAPTERS       ESP32 / MINI-PC
   XMRig/SRBMiner      Android / Termux      Acurast/Grass/...   telemetry/jobs
        |                  |                     |                  |
        +------------------+----------+----------+------------------+
                                      |
                         WALLET WATCH + REWARD LEDGER
                   estimate vs claimable vs realized / on-chain
```

NEXUS păstrează datele canonice. Crypto Radar descoperă, MultiMiner X rulează job-uri de mining pe PC, Fieldstation este client mobil, iar telefoanele/mini-PC-urile/ESP32 sunt worker agents. Adaptoarele fiecărui DePIN sunt implementate individual, în conformitate cu API-ul și regulile oficiale ale furnizorului.

### Entități de bază necesare în baza de date

`Project`, `SourceSnapshot`, `Opportunity`, `Device`, `CapabilityProfile`, `Job`, `Pool`, `WalletWatch`, `RewardEvent`, `CostEvent`, `Payout`, `Claim`, `Connector`, `SoftwareRelease`, `Approval`, `AuditEvent`.

Orice job trebuie să aibă Device_ID, Worker_ID, Project_ID, software release/hash, pool/provider, profile de resurse, start/stop, telemetry, accepted/rejected work, reward event și cost event.

## 7. Hardware și infrastructură — ce folosim și ce amânăm

Inventarul disponibil în surse indică Asus TUF cu GTX 1650, laptopuri HP/Lenovo raportate, 4 mini-PC-uri HP/Lenovo, telefoane Android multiple, NerdMiner/ESP32, HDD-uri externe și fibră de 1 Gbps declarată pentru locațiile candidate. O parte din modelele exacte nu sunt documentate.

Există o neconcordanță care trebuie rezolvată: workbook-ul DePIN menționează 2 laptopuri plus 4 mini-PC-uri, în timp ce informațiile recente sugerează Asus TUF + HP + Lenovo și 4 mini-PC-uri. Numărul real și specificațiile trebuie inventariate individual.

PC-ul RTX 5060 Ti 16GB + Ryzen 5 7600 + 32 GB DDR5 este **planificat**, nu achiziționat/verificat. Cele 3 plăci ESP32-S3, fork-ul cu SSD1306 și hub-ul USB sunt tot planuri de implementare. Nu trebuie incluse ca resurse active până la inventariere fizică.

Pentru cele 3 locații, planul curent este:

- un pilot de relay/mini-PC la locația centrală;
- verificarea hărților de acoperire Helium și GEODNET înainte de cumpărarea gateway-urilor/antenelor;
- WeatherXM/Wingbits doar dacă harta, echipamentul și condițiile de payout trec criteriile;
- confirmarea IP-ului public/CGNAT, upload-ului, porturilor, accesului la acoperiș și acordului de montaj pentru fiecare locație;
- extindere după 30–60 de zile de măsurare a payout-urilor efective, costului energetic și uptime-ului.

Tariful de 1,50 RON/kWh apare în fișiere ca ipoteză. Trebuie înlocuit cu tariful real din factură. Nu recomand achiziții noi de ASIC, GPU sau antene înainte de trecerea testelor de eligibilitate și economie.

## 8. Cerințe de siguranță care rămân obligatorii

- watch-only pentru adrese publice în primele versiuni;
- nicio seed phrase, cheie privată sau parolă wallet în aplicație, chat sau fișiere;
- fără semnare, transfer, sweep sau claim automat în MVP;
- chei API în secret store / variabile de mediu locale, cu least privilege;
- niciun installer automat și nicio dezactivare Defender/Play Protect;
- numai pool-uri/proiecte allowlisted, software cu provenance și hash;
- temperatură, baterie, consum și timeout cu oprire fail-safe;
- respectarea regulilor anti-sybil, multi-device, locație și IP ale fiecărui proiect;
- toate operațiunile cu efect extern cer aprobare explicită și audit trail;
- paper trading izolat de wallet-urile reale.

## 9. Roadmap central

| Milestone | Rezultat | Criteriu de trecere |
|---|---|---|
| M0 — Audit | inventar software/hardware, versiuni și surse reconciliate | identificăm exact ce este instalat, ce există în zip și ce este doar plan |
| M1 — NEXUS schema | entități comune, DB, migrations, audit și approvals | date unificate pentru proiecte, devices, job-uri, rewards și costuri |
| M2 — Radar ingestion | feed-uri read-only cu snapshots și deduplicare | sursă/timestamp/contract păstrat; erori RPC nu devin sold zero |
| M3 — Verifier + economics | criterii obligatorii și scor net RON | necunoscut = necalculabil; punctele nu sunt cash |
| M4 — Wallet/reward read-only | balances, claim status, payout events | orice payout realizat are timestamp și tx hash/credit evidence |
| M5 — Mining telemetry | XMRig/SRB logs, hashrate, shares, watt, temperaturi | benchmark local repetabil per dispozitiv și algoritm |
| M6 — DePIN pilots | Acurast, un relay Anyone, verificare hărți Helium/GEODNET | 30 zile de telemetrie și payout claimable/realizat |
| M7 — Scheduler shadow mode | recomandări automate fără pornire/oprire reală | 14–30 zile în care predicțiile sunt comparate cu rezultatul real |
| M8 — Execuție limitată | start/stop doar pe job-uri allowlisted și aprobate | kill switch, limite resurse, audit și fail-safe validate |
| M9 — Extindere | 3 locații și/sau PC GPU | scenariu conservator pozitiv demonstrat 30–60 zile |

## 10. Decizia finală

1. **PROJECT NEXUS 0.5.0 devine platforma centrală și singura sursă de adevăr.** Se dezvoltă versiunea următoare prin integrare, nu prin rescriere paralelă.
2. **Crypto Radar v6 se integrează în NEXUS.** Se arhivează v2–v5 și se păstrează istoricul snapshot-urilor.
3. **MULTIMINER X se păstrează ca adaptor Windows de mining.** Se adaugă telemetrie structurată și benchmark real; se elimină orice presupunere de 2 TH/s sau profit neconfirmat.
4. **Crypto Fieldstation se păstrează ca adaptor mobil.** Datele și jurnalul se sincronizează în NEXUS; Verus rămâne test cu binar verificat.
5. **DePIN începe cu experimente măsurabile, nu cu achiziții.** Acurast pe dispozitive individuale, un singur relay mini-PC, map check pentru Helium/GEODNET.
6. **Puzzle-urile, bug bounty și paper trading rămân module separate.** Nu sunt amestecate cu venitul predictibil din compute/DePIN.
7. **Nu se pornește auto-switch și nu se trimit tranzacții** până când există payout monitorizat, job allowlisting, shadow mode, aprobări și audit.

Aceasta este direcția unificată. Măsura de succes nu este numărul de minere pornite, de tokenuri urmărite sau de puncte acumulate; este valoarea netă care poate fi revendicată, transferată și verificată, după toate costurile.
