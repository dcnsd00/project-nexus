# Crypto Fieldstation — Termux / Android și desktop

**Versiune:** 1.1.0 · **Cost obligatoriu:** 0 RON · **Dependențe de bază:** numai biblioteca standard Python.

Crypto Fieldstation este un panou local pentru cercetare reproductibilă a puzzle-urilor publice, verificări hash exacte, experimente AES opționale pe candidați furnizați, un benchmark CPU SHA-256 demonstrativ, un lansator opțional pentru minare reală VerusHash cu binar adus/verificat de utilizator, urmărire read-only de adrese publice și export de jurnale către ChatGPT.

## Instalare pe Android (Termux)

1. Instalează Termux și aplicația **Termux:API** din aceeași sursă oficială (F-Droid sau GitHub). Nu combina APK-uri semnate din surse diferite. Referință: <https://github.com/termux/termux-app> și <https://github.com/termux/termux-api>.
2. Deschide Termux și instalează Python și pachetul API:

   ```sh
   pkg update
   pkg install python unzip termux-api
   ```

3. Copiază arhiva ZIP în telefon, apoi dezarhiveaz-o într-un folder accesibil din Termux. Exemplu, dacă arhiva este în `Download`:

   ```sh
   termux-setup-storage
   mkdir -p ~/crypto-fieldstation
   cd ~/crypto-fieldstation
   unzip /sdcard/Download/crypto_fieldstation_android.zip
   ```

   Dacă dezarhivarea creează un subfolder `crypto_fieldstation`, intră în acel subfolder înainte să rulezi comanda următoare.

4. Pornește:

   ```sh
   chmod +x start.sh stop.sh
   ./start.sh
   ```

   Browserul poate fi deschis automat de Termux. Dacă nu se deschide, navighează manual la **http://127.0.0.1:8765**. Menține sesiunea Termux activă cât timp rulează calculele. `Ctrl+C` în terminal, butonul „Oprește utilitarul” sau `./stop.sh` opresc serverul.

Nu este necesar root. Nu sunt necesare conturi, chei API, abonamente sau pachete cloud.

## Modul AES opțional

Verificatorul de hash și restul utilitarului funcționează fără biblioteci externe. Doar AES Lab cere PyCryptodome. Versiunea opțională este fixată în `requirements-optional.lock` pentru a evita rezolvarea unei versiuni noi, nevalidate:

```sh
python -m pip install -r requirements-optional.txt
```

Instalează-l doar dacă ai un ciphertext public de puzzle și ai nevoie de această funcție. Nu introduce parole personale, seed phrase-uri sau chei de portofel. AES Lab lucrează numai cu o listă finită de candidați introdusă de utilizator; nu generează automat wordlist-uri.

## Ce face

- **Jurnale separate:** Aoi Nakamoto, GSMG, Smith/Lyle/Moore, ProofOfSolve și cazuri noi introduse manual. Fiecare experiment înregistrează timpul, candidații testați, resursele folosite efectiv, rezultatul și următorul pas justificat.
- **Verificator de hash exact:** SHA-256, double SHA-256, SHA-512, MD5, SHA-1 și transformări text explicite. O potrivire este raportată numai după compararea exactă a digestului hex.
- **AES Lab opțional:** AES-256-CBC în format OpenSSL Base64 `Salted__`, cu KDF legacy MD5/SHA-1/SHA-256. Padding-ul valid **nu** este dovadă de soluție. Pentru statut „verificat” este necesar SHA-256-ul exact al plaintextului așteptat. Plaintext-ul nu este afișat, iar aplicația nu derivează chei de wallet.
- **Benchmark CPU:** procese paralele găsesc un nonce pentru un puzzle PoW local de demonstrație. Acesta nu minează o monedă și nu produce recompense.
- **Minare reală (opțională):** panoul poate lansa un binar `ccminer` compatibil VerusHash pe care utilizatorul îl plasează manual în `miners/ccminer`, după verificarea sursei și integrității. Profil mobil conservator: maximum 2 thread-uri, maximum 30 minute/rulare, implicit 1 thread și 15 minute. În Termux, modulul cere Termux:API și refuză pornirea dacă nu poate citi temperatura/procentul/starea bateriei. Refuză pornirea la baterie ≥37°C, sub 30%, în timpul alimentării sau dacă health nu este GOOD; oprește automat la baterie ≥39°C, nivel ≤20%, conectare la alimentare, health nesigur, eroare a senzorului ori senzor CPU/SoC accesibil ≥75°C. Temperatura bateriei nu este temperatura CPU; senzorul CPU/SoC este opțional și poate fi blocat de Android. Niciun watchdog nu poate garanta evitarea uzurii sau deteriorării, deci oprește și manual la căldură neobișnuită. Utilitarul nu descarcă minerul, nu ascunde procesul, nu ocolește antivirusul, nu păstrează adresa wallet în jurnal/export și nu semnează/trimite tranzacții. Share-urile nu echivalează cu payout.
- **Monitor read-only:** sold nativ public pentru Bitcoin, Ethereum, Base, Arbitrum, Optimism, BNB Chain, Polygon, Avalanche C-Chain și Solana. Permite urmărirea unui contract ERC-20 cunoscut prin `balanceOf` pe rețelele EVM suportate. Nu descoperă automat toate tokenurile tuturor adreselor și nu acoperă toate blockchain-urile existente.
- **Detector de actualizări:** verifică modificări publice în câteva repository-uri GitHub configurate. Este un detector de schimbări ale surselor, nu un crawler global și nu declară automat oportunitățile profitabile.
- **Pachet de predare către ChatGPT:** exportă starea, jurnalele, sursele urmărite și ultimele citiri publice într-un JSON. Adresele `watch_only` sunt excluse din exportul standard.

## Legătura cu ChatGPT

Nu există o conexiune directă bidirecțională între un proces Termux local și această conversație. ChatGPT nu poate porni de la distanță calcule pe telefon și utilitarul nu poate trimite automat mesaje în chat.

Fluxul cu cost zero este:

1. Rulezi verificările în Termux.
2. Apeși **Descarcă pachet ChatGPT**.
3. Atașezi JSON-ul în această conversație.
4. ChatGPT analizează rezultatele și propune experimente noi fără a repeta testele deja jurnalizate.

Nu am inclus OpenAI API deoarece aceasta este o interfață separată, necesită o cheie API și poate avea costuri de utilizare. Nu introduce o cheie API în codul aplicației.

## Minare reală VerusHash — configurare și limite

Verus este un candidat valid pentru testare pe telefon deoarece documentația proiectului indică explicit dispozitive ARM/telefoane și minare CPU, iar Verus permite merge-mining pentru unele chain-uri/pooluri: <https://verus.io/mining>. Aceasta nu înseamnă că o sesiune pe telefon va produce un payout util; recompensele depind de hashrate, pool, share-uri, dificultate, comisioane și praguri. Pentru a folosi panoul trebuie un executabil nativ, compatibil cu Android/ARM64 și protocolul poolului, numit exact `miners/ccminer`. Nu este inclus în ZIP și nu se descarcă automat.

1. Deschide mai întâi ghidul Verus și alege un pool din lista/documentația oficială: <https://docs.verus.io/economy/start-mining.html>.
2. Verifică sursa, codul, release-ul și checksum-ul minerului. Nu folosi scripturi necunoscute cu `curl | bash`; nu dezactiva Play Protect/Defender pentru a-l instala.
3. Pune binarul verificat în `crypto_fieldstation/miners/ccminer`, apoi în Termux folosește `chmod +x miners/ccminer`.
4. Instalează aplicația Termux:API din aceeași sursă ca Termux, apoi rulează `pkg install termux-api`. Introdu numai adresa publică de primire VRSC și hostname/portul oficial al poolului. Începe cu 1 thread și 15 minute. Startul este blocat dacă telefonul este la încărcat, temperatura bateriei ≥37°C sau bateria sub 30%. Verifică share-urile acceptate înainte de o altă rundă.
5. Confirmă payout-ul în panoul poolului și tranzacția în explorer/wallet. Panoul Fieldstation nu determină automat pragul sau taxa fiecărui pool și nu poate garanta recompense.

**Nu este inclus un binar de minare.** Este intenționat: binarele comunitare pot fi schimbate sau compromise, iar eu nu am verificat criptografic un release binar anume pentru acest pachet. Controlul de rulare folosește argumente separate (fără shell) și numai calea fixă `miners/ccminer`; procesul are timer automat, buton STOP, log redacționat pentru adresa introdusă și watchdog termic. Protecția monitorizează bateria la intervale de circa 20 secunde; dacă senzorul nu răspunde, oprește. Unele telefoane nu expun temperatura CPU/SoC către Termux, caz în care protecția folosește doar temperatura bateriei și nu poate garanta că procesorul rămâne rece. Minerul rămâne vizibil sistemului și aplicațiilor de securitate; nu încerca să ascunzi procesul sau să dezactivezi protecțiile Android.

### Recompensa, profitul și legalitatea

Minarea pool poate plăti în VRSC direct către walletul indicat. Nu înseamnă că plata va fi frecventă: depinde de hashrate-ul telefonului, dificultatea rețelei, noroc/ponderarea poolului, comisioane și pragul de retragere. Înainte de a lăsa telefonul să mineze multe ore, măsoară hash/s și consumul real; costul electric se estimează ca `kWh × tariful tău`, iar uzura bateriei este un cost separat.

Acest utilitar nu constituie consultanță juridică/fiscală. La cercetarea din 20 octombrie 2026 nu am identificat o licență dedicată exclusiv minării personale cu dispozitiv propriu; asta nu este o confirmare juridică generală. Folosește numai dispozitive, electricitate și rețele asupra cărora ai dreptul să operezi. Veniturile și recompensele trebuie documentate, iar tratamentul fiscal al monedelor primite prin mining poate fi diferit de impozitarea câștigului realizat ulterior la transfer/vânzare. Codul fiscal român și regulile privind câștigurile din transferul monedelor virtuale s-au modificat pentru 2026; verifică situația exactă cu ANAF/contabil, mai ales înainte de vânzare. Surse oficiale de pornire: <https://legislatie.just.ro/Public/DetaliiDocument/305208> și ghidul ANAF privind transferul monedei virtuale <https://static.anaf.ro/static/10/Brasov/Brasov/imp_moneda_virtuala.pdf>.

## Adrese și walleturi

- Aplicația cere doar **adrese publice**. Nu conectează MetaMask, Trust Wallet sau alte walleturi prin WalletConnect și nu solicită aprobări.
- Nu există semnare, broadcast de tranzacții, claims automate, sweep-uri sau recuperare de chei.
- Nu introduce niciodată seed phrase/private key în câmpuri, fișiere sau jurnal.
- O adresă publică, un sold pozitiv sau un UTXO disponibil nu dovedesc proprietatea ori dreptul legal de revendicare a unei recompense.
- Exportul standard exclude adresele personale marcate `watch_only`. Verifică fișierul exportat înainte să-l partajezi.

## Rețea și confidențialitate

Serverul web ascultă doar la `127.0.0.1`, nu la adresa IP a telefonului. Nu este conceput să fie accesibil din LAN/internet. Soldurile și verificările de surse trimit cereri către endpointurile publice ale explorerelor/RPC-urilor/GitHub; acei furnizori pot vedea adresele interogate și IP-ul de internet. Unele endpointuri pot limita cererile sau pot fi indisponibile. O eroare RPC nu trebuie interpretată drept sold zero.

Datele locale sunt ținute în `data/addresses.json`, `data/journals.json` și `data/leads.json`. Fă o copie de siguranță înainte de modificări. Nu încărca în chat fișiere care conțin informații de adresare pe care dorești să le păstrezi private.

## Precizia rezultatelor

- `VERIFIED_EXACT_DIGEST_MATCH`: digestul candidatului coincide exact cu ținta configurată; trebuie confirmat că algoritmul/ținta sunt cele oficiale ale puzzle-ului.
- `PADDING_VALID_UNVERIFIED`: un candidat AES a produs padding valid, dar nu dovedește plaintext-ul și nici soluția.
- `NO_MATCH_IN_TESTED_SET`: nu a existat potrivire în setul finit de candidați/transformări testate.
- Sold on-chain: snapshot din endpoint public cu timestamp; nu stabilește eligibilitate sau ownership.
- Actualizare GitHub: indiciu de cercetare; verifică postarea/commit-ul original, regulile, claim-ul, KYC, jurisdicțiile, lichiditatea și retragerea înainte de orice concluzie.

## Verificare locală

În folderul proiectului:

```sh
python -m unittest discover -s tests -v
python -m py_compile app.py
```

Testele sunt locale și nu cer să rulezi un miner, să introduci o adresă personală sau să efectuezi vreo tranzacție.

## Surse primare folosite pentru protocoale

- Termux oficial: <https://github.com/termux/termux-app>
- API Esplora (Bitcoin): <https://github.com/Blockstream/esplora/blob/master/API.md>
- Ethereum JSON-RPC: <https://ethereum.org/developers/docs/apis/json-rpc/>
- Solana RPC getBalance: <https://solana.com/docs/rpc/http/getbalance>
- GitHub REST API: <https://docs.github.com/en/rest>
