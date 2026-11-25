# MULTIMINER X 1.0 — Windows local mining controller

**Build:** 1.0.0 · **OS:** Windows 10/11 x64 · **Python:** 3.10+ cu Tkinter · **GPU profile:** NVIDIA GTX 1650 / PearlHash · **CPU profile:** RandomX / XMRig

## Ce este versiunea 1.0

Aceasta este o interfață locală care orchestrează două motoare consacrate, nu o implementare proprie a algoritmilor criptografici:

- CPU: XMRig pentru RandomX, conectat TLS la `rx.unmineable.com:443`.
- GPU: SRBMiner-MULTI pentru PearlHash/PearlPow, conectat TLS la `pearlpow.unmineable.com:4444`.
- Rulează CPU și GPU separat sau simultan; păstrează logurile în `logs/`.
- Folosește o limită orientativă CPU de 50% (`--cpu-max-threads-hint`) și intensitate GPU inițială 16/31. Intensitatea GPU nu este procent de utilizare și nu garantează 50% load.
- Verifică telemetria NVIDIA cu `nvidia-smi`, afișează temperatura/încărcarea/puterea/VRAM și poate opri GPU la pragul stabilit.
- Include un motor matematic auditabil: Poisson pentru șansa de bloc, Monte Carlo pentru verificarea numerică, Amdahl pentru paralelism, energie/cost, jouli/hash și un model termic RC cu parametri expliciți.

## Limitări care trebuie înțelese

1. **Nu există un algoritm matematic care să transforme 6 MH/s SHA-256d în 2 TH/s pe RandomX sau PearlHash.** Hashrate-urile sunt specifice algoritmului și hardware-ului. Rezultatul de 6.082 MH/s din arhiva v0.2 a fost măsurat pe un mediu virtualizat AMD EPYC, nu pe Asus TUF.
2. **2 TH/s nu este o țintă validată pentru toate monedele.** Capturile unMiner arată aproximativ 0,73–0,78 TH/s pentru PearlPow și aproximativ 690–849 H/s RandomX. Aceste valori trebuie revalidate prin shares acceptate și hashrate raportat de pool.
3. `--cpu-max-threads-hint 50` este un indiciu XMRig pentru autoconfigurare, nu o limită exactă de putere/consum. Dacă minerul are o configurație CPU salvată anterior, comportamentul poate diferi; porniți din folderul inclus în acest pachet și verificați thread count în log.
4. `--gpu-intensity 16` este un punct inițial conservator, nu 50% utilizare garantată. Ajustați numai după benchmark și temperatură.
5. Monte Carlo estimează probabilități Poisson; **nu găsește nonce-uri, nu reduce dificultatea și nu accelerează criptografia**. Aplicația v1.0 este un client de pool unMineable; nu implementează solo mining sau payout de bloc integral.
6. Moneda de payout pentru conturile unMineable se setează în dashboardul contului. Câmpul payout din această aplicație este doar o etichetă locală și nu schimbă moneda în cont.
7. Nu introduceți seed phrase/private key. Aplicația folosește doar aliasul public al contului unMineable sau formatul legacy wallet address. Nu păstrează parole de wallet.

## Instalare rapidă

1. Dezarhivați întregul pachet într-un folder local, de exemplu `C:\Mining\MULTIMINER_X_v1.0`.
2. Instalați Python 3.10 sau mai nou pentru Windows x64, cu Tcl/Tk. Verificați `py -3 -m tkinter`.
3. Click dreapta pe `INSTALL_BACKENDS.ps1` → **Run with PowerShell**. Scriptul descarcă doar din paginile oficiale și verifică SHA-256 pentru XMRig și MD5 publicat de SRBMiner pentru arhiva sa. Nu creează excluderi Windows Defender și nu cere oprirea antivirusului.
4. Rulați `RUN_MULTIMINER_X.bat`.
5. Introduceți aliasul contului unMineable și worker `TUF1650`. Nu introduceți mnemonic, private key sau parola walletului.
6. Confirmați în dashboardul unMineable moneda de payout pe care o doriți (de exemplu BONK). Aplicația nu schimbă setarea payout.
7. Începeți cu **START DUAL**. Presetul inițial este CPU 50% hint și GPU intensity 16/31. Urmăriți temperaturile, hashrate-ul și shares acceptate/respinse în ferestrele/jurnalele minerelor.

Dacă Windows Defender sau alt produs de securitate blochează un miner, nu dezactivați protecția și nu adăugați excluderi generale. Verificați fișierul, hashul și alerta în produsul de securitate; opriți instalarea dacă nu puteți valida proveniența.

## Setări tehnice

- XMRig 6.26.0 Windows x64 oficial: `https://github.com/xmrig/xmrig/releases/tag/v6.26.0`
- SRBMiner-MULTI 3.8.5 Windows x64 oficial: `https://github.com/doktor83/SRBMiner-Multi/releases/tag/3.8.5`
- unMineable XMRig CPU: `https://unmineable.com/support/article/how-to-setup-xmrig-for-cpu-mining`
- unMineable SRBMiner GPU/PearlPow: `https://unmineable.com/support/article/how-to-setup-srbminer-for-gpu-mining`

GTX 1650 laptop este folosită aici cu PearlHash deoarece acesta este algoritmul GPU din configurația anterioară a utilizatorului. Nu forțați KawPow pe unMineable dacă placa are 4 GB: documentația poolului indică minimum 6 GB VRAM pentru KawPow.

## Teste offline

Rulați `TEST_CORE.bat`. Testele verifică formulele și reproducibilitatea simulării; nu pornesc mining și nu validează performanța hardware.

## Structură

- `app/main.py` — GUI și orchestration.
- `app/miner_controller.py` — pornire/oprire procese și loguri.
- `core/mining_math.py` — probabilitate Poisson, Monte Carlo, Amdahl, energie.
- `core/physics_engine.py` — jouli/hash și model termic RC + Monte Carlo.
- `core/optimizer.py` — planificare thread-uri CPU și estimare Amdahl.
- `research/legacy/` — cod și note relevante din arhivele anterioare.
- `miners/` — binarele oficiale se instalează local prin scriptul PowerShell.

## Roadmap realist v1.1+

- citire structurată a statisticilor din API/logurile SRBMiner și XMRig;
- profiluri multiple pool/coin după validarea fiecărui endpoint și algoritm;
- calculator separat pentru solo mining pe baza hashrate-ului și a dificultății curente furnizate de rețeaua exactă;
- benchmark pe hardware-ul Asus și calibrare model termic cu temperaturi și putere măsurate;
- auto-switch doar între joburi compatibile și numai cu reguli clare; niciodată schimbare automată către un pool necunoscut.

## 1.1 — schimbare payout + laborator criptografic

- Câmpul „Monedă payout” permite selectarea/editarea tickerului (BTC, LTC, DOGE, XMR, RVN, ETC, ERG, KAS, BONK). Lista este orientativă; verifică disponibilitatea, rețeaua, adresa și regulile payout în dashboard-ul unMineable înainte de pornire. Dacă introduci direct `COIN:ADRESĂ`, acesta are prioritate.
- CPU live rămâne RandomX/XMRig; GPU live rămâne PearlHash/SRBMiner. SHA-256d și SHA-512 sunt profiluri de cercetare offline, nu algoritmi conectați la pool în această versiune.
- `config/mining_profiles.json` descrie profilurile și statutul lor.
- `research/CRYPTO_LAB_RO.md` explică hash vs criptare, materialele unei chei și limitele SHA-256/SHA-512.
- `python research/crypto_cli.py hash --algorithm SHA-512 --text "test"`
- `python research/crypto_cli.py verify --algorithm SHA-256 --candidate "known text" --digest <hex>`
- `python research/crypto_cli.py derive-key --salt-hex <salt-hex> --iterations 600000 --bytes 32`
- `python research/crypto_cli.py decrypt-aes-gcm --key-hex <key> --nonce-hex <nonce> --ciphertext-b64 <ciphertext+tag>` (necesită `cryptography`; decriptează numai cu cheia corectă)
- `python research/run_benchmarks.py` compilează și rulează benchmark-ul nativ SHA-256d și benchmark-ul digest SHA-512.
- Ipotezele matematice neconvenționale sunt izolate în `research/hypothesis_lab.py`; nu influențează shares, nonce-uri sau protocolul PoW.

Pentru AES-GCM opțional: `python -m pip install cryptography`. Nu introduce seed phrase/private key și nu pune chei reale în argumente CLI care pot rămâne în istoricul shell.
- Test statistică avalanche: `python -c "from research.special_math import avalanche_experiment; print(avalanche_experiment('SHA-256', trials=1000))"`. Catalogul de ipoteze (chaotic nonce ordering, spectral bias, SAT/SMT reduced-round, modular differential, p-adic) este doar de cercetare, nu de optimizare PoW demonstrată.

**Limită pentru schimbarea monedelor:** selectorul schimbă tickerul payout în formatul contului unMineable, dar păstrează algoritmii curenți (RandomX pe CPU și PearlHash pe GPU). Nu comută automat către alte familii PoW precum KawPow, Autolykos, KHeavyHash, Scrypt sau SHA-256d. Acestea cer miner, pool, wallet, parametri de job și benchmark separate; nu le activăm prin simpla schimbare a tickerului.


## 1.1.1 — verificare release 8 noiembrie 2026

- Installerul folosește SRBMiner-MULTI 3.8.5 din release-ul oficial și verifică MD5-ul arhivei publicat de dezvoltator.
- Configurația observată pe ASUS TUF GTX 1650 4 GB este păstrată ca măsurătoare furnizată de utilizator: PearlHash GPU 0,76 TH/s local și 2,5 TH/s effective; RandomX CPU 612 H/s local și 861 H/s effective. Aceste valori nu sunt reinterpretate sau convertite.
- Pentru confirmarea performanței susținute, NEXUS trebuie să citească logurile minerului și shares acceptate/respinse de pool; un screenshot singur nu validează intervalul de 24 h.
