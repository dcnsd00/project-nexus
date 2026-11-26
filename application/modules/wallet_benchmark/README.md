# NEXUS Wallet Benchmark 0.1.0

## Ce conține

Un benchmark local, determinist și offline pentru **10 wallet-uri de test**: câte două pentru fiecare dintre cinci formate.

1. Bitcoin Legacy P2PKH — BIP44 (`m/44'/0'/0'/0/0`)
2. Bitcoin Nested SegWit P2SH-P2WPKH — BIP49 (`m/49'/0'/0'/0/0`)
3. Bitcoin Native SegWit P2WPKH — BIP84 (`m/84'/0'/0'/0/0`)
4. Bitcoin Taproot P2TR — BIP86 (`m/86'/0'/0'/0/0`)
5. Ethereum / EVM — BIP44 (`m/44'/60'/0'/0/0`)

Aceeași adresă EVM este utilizabilă ca identitate de cont pe Ethereum, Base, BNB Chain, Polygon și Arbitrum. Rețelele nu necesită cinci chei diferite pentru aceeași adresă EVM.

## Siguranță și limitări

- Sunt utilizate două **mnemonice BIP39 publice, standard, de test**, plus parola publică de vector `TREZOR`.
- Aceste fraze sunt cunoscute public și **nu sunt secrete**. Adresele generate sunt exclusiv pentru test; nu depune fonduri la ele.
- Programul nu face solicitări RPC/API, nu scanează adrese ale terților, nu încearcă seed-uri împotriva wallet-urilor găsite, nu semnează și nu transmite tranzacții.
- Nu există verificare de sold; `funds_checked=false` în rezultate.
- Recuperarea seed-urilor/parolelor este în afara acestui benchmark. Testele demonstrează implementarea derivării pentru vectori cunoscuți, nu recuperarea unui wallet necunoscut.
- Taproot implementează derivarea de cheie BIP86 fără script tree (key-path only).

## Cerințe

- Python 3.10+
- `cryptography` 50+

Instalare într-un mediu Python local:

```bash
python -m pip install -r requirements.txt

For tests and development, also install:

```bash
python -m pip install -r requirements-dev.txt
```
```

## Rulare

Din folderul proiectului:

```bash
python -m pytest -q
python nexus_wallet_benchmark.py --iterations 100 --output results
```

`--iterations 100` rulează 100 de derivări pentru fiecare din cele două vectori în fiecare din cele cinci formate, adică **1.000 de derivări benchmark**, în plus față de generarea celor 10 wallet-uri de bază.

## Fișiere rezultate

- `results/wallets.json` — cele 10 adrese de test, căile de derivare și verificarea formatului.
- `results/wallets.csv` — același registru în CSV.
- `results/benchmark_results.json` — mediul, timpii și throughput-ul măsurat.
- `results/benchmark_summary.csv` — sumar CSV pe format.

## Interpretarea benchmarkului

Timpii reprezintă performanța locală a derivării BIP32 + calculului adresei + verificării checksum-ului, pe mașina care execută scriptul. Nu reprezintă performanță de mining, viteză de ghicire a seed-urilor sau probabilitate de recuperare.

## NEXUS Consolidation Benchmark 0.2.0

Run the offline synthetic consolidation benchmark:

```bash
python nexus_consolidation_benchmark.py --output results
pytest -q
```

This extension creates 19 deterministic source test wallets and five corresponding destination test wallets. It validates address derivation and proves local key/address correspondence using ECDSA challenge signing and verification. It then consolidates **synthetic test balances** into matching destinations and checks exact balance conservation per network and asset.

No RPC/network requests are made, no blockchain balances are read, no transactions are signed for broadcast, and no real funds are moved. The mnemonics are public test vectors and all generated addresses are test-only; never fund them.


## NEXUS Wallet Search & Recovery integration (0.10.17)

- Local file discovery: `nexus_wallet_search.py` scans only a user-selected folder, with depth/file caps, symlink exclusion and metadata-only results. It detects common JSON keystores, BIP38 strings, Bitcoin Core `wallet.dat`, Electrum/Monero file hints and MetaMask LevelDB extension storage locations.
- Recovery primitives: `nexus_wallet_formats.py` supports Ethereum Web3 Secret Storage V3 (`scrypt` or PBKDF2-HMAC-SHA256 + AES-128-CTR + Keccak MAC), BIP38 non-EC 0x0142, BIP39 checksum/seed and one-missing-word recovery filtered by an owner-provided address/path, Bitcoin Core loopback RPC passphrase check, and Solana keypair validation.
- API/UI: `/api/wallet/recovery/formats`, `/detect`, `/search`, `/decrypt`, `/bip39/check`, `/bip39/one-missing`, `/solana/validate`, `/bitcoin-core/check`; Wallet Manager includes local folder search and selected-file detection/decryption.
- CLI: `python nexus_recovery_cli.py --help`; passwords and mnemonic inputs are requested using hidden terminal prompts.
- Web3 V3 imports are immediately re-encrypted into the NEXUS local AES-GCM vault. BIP38 returns only the verified public address and does not export or persist the raw Bitcoin key.
- Recovery endpoints accept loopback clients only and require explicit owner authorization. No password brute-force, arbitrary blockchain address search, key export or transaction broadcast.
- `python-mnemonic` is a declared dependency for official BIP39 wordlists; install from `modules/wallet_benchmark/requirements.txt`.
- Test tooling is separate: install `modules/wallet_benchmark/requirements-dev.txt` to get the supported pytest range.
- Not native-decrypted: Electrum, MetaMask raw vault, Monero, BIP38 EC-multiplied 0x0143 and EIP-2335. Bitcoin Core password check requires a running local daemon and encrypted wallet.


## NEXUS 0.10.19 — owner-local wallet recovery

- Search is restricted to an explicitly selected local directory and reports only candidate metadata, bounded JSON/BIP38 marker detections, file age and SHA-256 fingerprints. A file's modification age is not an on-chain inactivity measurement.
- A `wallet.dat` filename is only a candidate hint; it must be opened in the owner's local Bitcoin Core node before wallet history can be inspected.
- BIP38 0x0142 private material is decrypted in memory, address-verified, and re-encrypted into a separate NEXUS Bitcoin vault. Raw private key/WIF is never returned by the API.
- Bitcoin vault unlock verifies the decrypted key against the stored P2PKH address. It does not sign or broadcast transactions.
- Bitcoin Core inspection is read-only and limited to an explicitly loaded wallet over loopback RPC. Old backup history may require a rescan/reindex.
- No blockchain-wide discovery of dormant third-party wallets, password guessing, raw key export, or wallet-dissolution claims.
