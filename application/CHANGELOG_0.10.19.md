# NEXUS MASTER 0.10.19 — local wallet recovery hardening

Data: 10 noiembrie 2026

## Implementat

- Căutarea de wallet-uri locale este limitată la un director ales de utilizator, la adâncimea și numărul de fișiere configurate. Nu face scanare blockchain după adrese.
- Căutarea recunoaște structuri JSON Web3 V3/NEXUS, markeri BIP38 în fișiere text și candidate `wallet.dat`, Electrum, Monero și MetaMask. Rezultatele bazate doar pe nume/cale sunt marcate `CANDIDATE_UNVERIFIED`.
- Fiecare candidat poate include hash SHA-256 de fișier și vârsta fișierului în zile. Vârsta fișierului nu este confundată cu ultima activitate on-chain.
- Corectat clasificatorul generic `.dat`: doar numele `wallet.dat` produce un candidat Bitcoin Core, niciodată o confirmare de format.
- Cheile BIP38 non-EC 0x0142 furnizate explicit de proprietar pot fi decriptate în memorie, validate prin adresa derivată și recriptate într-un tabel separat `bitcoin_vaults` cu scrypt + AES-GCM.
- Adăugate endpoint-urile `/api/wallet/recovery/import-bip38`, `/api/wallet/bitcoin/vaults` și `/api/wallet/bitcoin/vault/unlock`.
- La deschiderea unui vault BTC NEXUS, cheia este decriptată temporar, verificată față de adresa P2PKH și nu este returnată către UI/API.
- Auditul vault verifică separat envelope-urile Bitcoin criptate; nu decriptează și nu modifică baza.
- Inspectorul Bitcoin Core calculează inactivitatea pe baza tranzacțiilor din wallet-ul încărcat local. Corectată paginarea tranzacțiilor și întărită raportarea blocării wallet-ului după verificarea parolei.
- Adăugat fixture pytest cu bază izolată pentru ca testele să nu modifice baza de date inclusă în arhivă.

## Limite explicite

- Nu există căutare blockchain-wide de wallet-uri dormante aparținând terților, ghicire de parole, export de chei private brute sau rută de transfer automat.
- Bitcoin Core `wallet.dat` nu este decriptat nativ de NEXUS în această versiune; trebuie încărcat într-un nod Bitcoin Core local și inspectat prin RPC loopback.
- Istoricul unui backup vechi poate fi incomplet până la rescan/reindex. `NO_TRANSACTION_HISTORY` nu este o concluzie definitivă fără verificarea completitudinii.
- BIP38 EC-multiplied 0x0143, EIP-2335, decriptarea nativă MetaMask/Electrum/Monero nu sunt implementate.
- Nu s-au efectuat tranzacții reale și nu s-a conectat un nod Bitcoin Core live în mediul de build.

## Testare

- NEXUS root: 249 PASS
- MultiMiner X: 17 PASS
- Crypto Fieldstation: 12 PASS
- Wallet Benchmark: 15 PASS
- Wallet Benchmark v0.5: 7 PASS
- Total: 300 PASS, 0 FAIL
- `compileall`: PASS
- Sintaxă JavaScript pentru `dashboard.html` și `wallet.html`: PASS
- Audit read-only al bazei distribuite: 32 envelope-uri EVM valide, 16 adrese watch-only, zero câmpuri plaintext; baza nu a fost modificată.
- `run_full_audit.sh`: PASS, execuția agregată completă s-a încheiat; benchmarkul nativ SHA-256d opțional a fost omis intenționat.
