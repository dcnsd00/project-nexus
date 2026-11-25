# NEXUS 0.8.0 — implementare și limite verificate

## Cele cinci domenii funcționale în această versiune

1. **Mining & Pool-uri:** catalog JSON selectabil, filtrare după monedă, endpoint-uri TCP/TLS, porturi, adresă publică de payout, worker și generare configurație. Configurația nu pornește procese de mining. Miner binaries nu sunt incluse și nu se descarcă automat.
2. **Catalog Crypto:** sincronizare la cerere cu CoinPaprika `/v1/coins`, stocare locală cu cache 6 ore, căutare după nume/simbol/ID și marcaje activ/inactiv. Catalogul providerului nu garantează existența fiecărui proiect istoric sau scam token de pe piață.
3. **Laborator Matematic:** UI pentru algoritmii din Crypto Engine 0.7.0, calcul hash și benchmark digest. Benchmark-ul nu este hashrate PoW.
4. **Blockchain & Wallet:** diagnostic dependențe și acces la Wallet Manager local existent. Regtest/Anvil necesită servicii externe; scrierile pe mainnet nu sunt activate.
5. **Dashboard & Sistem:** stare module, CPU/GPU telemetry, diagnoză, teste și linkuri către componente.

## Pool-uri incluse

Pool-urile inițiale 2Miners pentru RVN/KawPoW, KAS/KHeavyHash și ETC/Etchash au fost introduse din documentația oficială a operatorului. Regiuni EU/US/Asia sunt incluse unde pagina operatorului publică endpoint-uri. Fiecare rând are URL de documentație și dată de verificare. Lista nu este exhaustivă pentru industria mining; nu există o bază universală stabilă a tuturor pool-urilor și endpoint-urilor. Pentru alte proiecte se folosește host/port personalizat după verificarea operatorului.

Surse pool: https://rvn.2miners.com/help ; https://kas.2miners.com/help ; https://etc.2miners.com/help .
Sursa catalog: https://coinpaprika.com/api și https://docs.coinpaprika.com .

## Instalare Windows

Necesită Windows 10/11 și Python 3.11+. Rulează `INSTALL_NEXUS_WINDOWS.ps1` din PowerShell. Scriptul creează venv, instalează dependențele Python și scurtătura Desktop. Apoi rulează `START_NEXUS_WINDOWS.bat`. UI: `http://127.0.0.1:8765/api/nexus/dashboard`.

## Verificări efectuate în acest build

- Python compileall: PASS.
- NEXUS master tests: 57 PASS.
- MultiMiner X tests: 17 PASS.
- Crypto Fieldstation tests: 12 PASS.
- Wallet benchmark tests: 15 PASS.
- Local-chain unit tests: 7 PASS.
- **Total: 108 teste PASS.**
- API TestClient: dashboard route, pool catalogue, pool config generation, custom pool validation și cache coin catalogue (mock HTTP): PASS.

## Ce nu este validat încă

- Sincronizarea live CoinPaprika nu a fost testată din runtime-ul de build; testul de connector folosește răspuns HTTP simulat. La prima utilizare, calculatorul Windows are nevoie de internet.
- Nu a fost testată conectarea Stratum reală și nu au fost trimise shares.
- Nu s-a lansat un miner real. Executabilele XMRig/SRBMiner/lolMiner etc. trebuie instalate separat din surse oficiale și verificate.
- Nu s-au executat tranzacții mainnet.
- Nu s-a testat instalarea pe laptopul ASUS sau pe alt Windows fizic.
