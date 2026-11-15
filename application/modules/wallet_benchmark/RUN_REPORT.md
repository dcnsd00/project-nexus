# NEXUS Wallet Benchmark — Raport de execuție

**Stare:** executat local  
**Versiune:** 0.1.0  
**Rezultat:** 10/10 wallet-uri de test generate și validate; 10/10 teste automate trecute.

## Configurația rulării

- 5 tipuri de wallet, câte 2 fiecare (total 10)
- 2 mnemonice BIP39 publice de test; passphrase publică `TREZOR`
- 100 iterații pentru fiecare vector în fiecare format
- 5 formate × 2 vectori × 100 iterații = **1.000 derivări benchmark**
- 0 solicitări de rețea, 0 tranzacții, 0 solduri verificate, 0 wallet-uri terțe accesate

Mediu: Python 3.13.5, `cryptography` 46.0.4, Linux x86_64.

## Cele 10 adrese generate

Acestea sunt adrese deterministe derivate din vectori publici de test. Nu sunt portofele sigure și nu trebuie alimentate.

| Format | Vector | Derivation path | Adresă generată | Checksum/format |
|---|---|---|---|---|
| BTC Legacy P2PKH | TV-01 | `m/44'/0'/0'/0/0` | `1PEha8dk5Me5J1rZWpgqSt5F4BroTBLS5y` | PASS |
| BTC Legacy P2PKH | TV-02 | `m/44'/0'/0'/0/0` | `18MNH3xiSXsYNYxCvwQ6JouW2RkWwStSwy` | PASS |
| BTC Nested SegWit | TV-01 | `m/49'/0'/0'/0/0` | `3Aho3kS7vgVWKTpRHjcqBoPXiCujiSuTaZ` | PASS |
| BTC Nested SegWit | TV-02 | `m/49'/0'/0'/0/0` | `3HLYoykVrarXnoJF1fwu5YV7EzZiihQr5R` | PASS |
| BTC Native SegWit | TV-01 | `m/84'/0'/0'/0/0` | `bc1qv5rmq0kt9yz3pm36wvzct7p3x6mtgehjul0feu` | PASS |
| BTC Native SegWit | TV-02 | `m/84'/0'/0'/0/0` | `bc1qcgphwddfcv5pax0agdw697rd8ewde8r02nwrex` | PASS |
| BTC Taproot BIP86 | TV-01 | `m/86'/0'/0'/0/0` | `bc1p3ryfth56dp058avv97ppn065ctsk263puvwp4rcka3wpg6cudp9qd3jsuu` | PASS |
| BTC Taproot BIP86 | TV-02 | `m/86'/0'/0'/0/0` | `bc1py95g80zqw74m0tcy8dhnmhqcgty36tfrfunu908tmnk9xslvy62sfgpnqr` | PASS |
| EVM | TV-01 | `m/44'/60'/0'/0/0` | `0x9c32F71D4DB8Fb9e1A58B0a80dF79935e7256FA6` | PASS |
| EVM | TV-02 | `m/44'/60'/0'/0/0` | `0x6006ef1944FB519A746d00cDAf715Cbd27a5a008` | PASS |

Adresa EVM este compatibilă ca adresă de cont pe Ethereum, Base, BNB Chain, Polygon și Arbitrum. Aceleași chei EVM nu se derivă din nou doar pentru că se schimbă chain ID-ul.

## Performanța măsurată

| Format | Derivări măsurate | Medie / derivare | Mediană | P95 | Derivări/secundă |
|---|---:|---:|---:|---:|---:|
| BTC Legacy P2PKH | 200 | 2,547 ms | 2,445 ms | 3,223 ms | 392,59 |
| BTC Nested SegWit | 200 | 2,737 ms | 2,504 ms | 4,331 ms | 365,35 |
| BTC Native SegWit | 200 | 2,639 ms | 2,510 ms | 3,590 ms | 378,94 |
| BTC Taproot BIP86 | 200 | 4,388 ms | 4,150 ms | 6,109 ms | 227,87 |
| EVM Ethereum | 200 | 4,547 ms | 3,977 ms | 7,700 ms | 219,95 |
| **Total** | **1.000** | — | — | — | **296,59 agregat** |

Timpul total al celor 1.000 de derivări benchmark: **3,371623 secunde**.

## Validare automată

`python -m pytest -q` → **10 passed in 0.24s**.

Testele validează:

- vectorul Keccak-256 pentru mesaj gol;
- vectorii seed BIP39 cu passphrase `TREZOR`;
- vectorul master BIP32;
- vectori oficiali BIP84 și BIP86 pentru prima adresă;
- vectorul de cheie copil BIP49 pe testnet;
- checksum EIP-55;
- generarea exactă a celor 10 wallet-uri și verificarea formatului/checksum-ului adreselor;
- caracterul determinist al derivării.

## Ce NU a fost testat

- Nu s-a verificat soldul vreunei adrese.
- Nu s-a făcut scanare blockchain/RPC/API.
- Nu s-a încercat recuperarea unui wallet necunoscut.
- Nu s-au ghicit seed-uri sau parole pentru adrese terțe.
- Nu s-a semnat și nu s-a transmis nicio tranzacție.
- Nu există încă implementare completă de validare generică BIP39 pentru orice frază: wordlist-ul complet de 2.048 de cuvinte și validarea checksum-ului nu sunt incluse în această versiune de benchmark. Au fost folosiți vectori BIP39 publici cunoscuți și seed-urile lor au fost verificate față de rezultatele de referință.

## Concluzie tehnică

Benchmark-ul demonstrează că fluxul local BIP39-seed → BIP32 derivation → cheie secp256k1 → adresă BTC/EVM funcționează pentru cele cinci formate testate și reproduce vectorii de referință selectați. Timpii sunt specifici mediului Linux x86_64 în care a rulat testul; nu reprezintă performanța laptopului utilizatorului și nu măsoară viteză de căutare/brute-force sau șanse de recuperare.
