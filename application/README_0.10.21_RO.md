# NEXUS MASTER 0.10.21

Versiune de remediere bazată pe NEXUS MASTER 0.10.20. Arhiva 0.10.20 originală rămâne neschimbată.

## Modificări principale

1. **Miner SHA-256d C:** repară distribuirea nonce-urilor între fire, procesează cozile AVX2/AVX-512, validează capabilitățile CPU și verifică targetul poolului fără a pierde share-uri valide.
2. **Integrare Stratum:** workerul Python existent folosește opțional backend-ul C pentru scanare; subscribe, authorize, notify și mining.submit rămân în workerul existent. Fallback-ul Python exact este păstrat.
3. **CoinPaprika:** cache atomic, fallback la cache stale și catalog local NEXUS etichetat clar când API-ul extern nu este disponibil.
4. **Wallet:** schema EVM/watch/Bitcoin este inițializată la pornire fără decriptarea sau rescrierea vault-urilor.
5. **Desktop:** shell loopback-only cu port alternativ dacă 8765 este ocupat; pachetul PyInstaller include resursele `research/` și exclude bazele de date locale.
6. **Blockchain local:** verificare de disponibilitate și script de cleanup pentru Bitcoin Core Regtest și cinci noduri Anvil.

## Benchmark nativ măsurat în mediul de build

Compilare GCC portabilă: `-O3 -pthread`, 20.000.000 nonce-uri, antet și target Genesis, verificare a nonce-ului real `2083236893`.

| Variantă | MH/s, 1 fir |
|---|---:|
| Scalar naiv | 1,38 |
| Midstate | 2,16 |
| Midstate + early exit | 2,27 |
| AVX2 x8 | 13,88 |
| AVX-512 x16 | 24,23 |

AVX-512 a fost de aproximativ 17,54× mai rapid decât scalar în această rulare. La AVX-512, măsurătorile multi-thread au fost 24,50 / 39,54 / 68,69 / 76,81 MH/s pentru 1 / 2 / 4 / 8 fire. Acestea sunt rezultate ale containerului Linux de build, nu ale laptopului Windows și nu reprezintă o estimare de recompensă sau un test de pool public.

## Teste

- NEXUS root: 273 teste trecute.
- MultiMiner X: 17 teste trecute.
- Crypto Fieldstation: 12 teste trecute.
- Wallet Benchmark: 15 teste trecute.
- Wallet Benchmark v0.5: 7 teste trecute.
- SHA-2 independent: 13 teste executate, 12 trecute, 1 omis pentru lipsa `python-sat`.
- `compileall`: trecut.
- Sintaxă JavaScript dashboard și wallet: trecută.
- YAML Docker Compose: șase servicii, rețea izolată, trecut.

## Ce trebuie verificat pe laptop

- Build DLL cu MSYS2 UCRT64 GCC/winpthreads și Edge WebView2 Runtime.
- Hashrate, temperatură, consum și stabilitate pe CPU-ul laptopului.
- Nodurile Bitcoin Core/Anvil locale: Docker Desktop nu a fost disponibil în mediul de build.
- Pool public: nu a fost efectuat handshake, authorize, share sau payout în această versiune.

## Siguranță

Nu au fost trimise share-uri către pooluri publice, nu au fost efectuate transferuri publice și nu au fost decriptate wallet-uri. Testele au folosit baze temporare, pool mock pe loopback și fonduri de test numai în descrierea laboratorului local.
