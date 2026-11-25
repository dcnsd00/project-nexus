# NEXUS Recovery Lab 0.3.0

Adds local BIP39 wordlist/checksum validation and authorized mnemonic-to-public-address derivation.

## Scope
- Requires the official matching BIP39 wordlist file (2048 unique words).
- Reads the mnemonic and optional BIP39 passphrase using hidden terminal prompts (`getpass`).
- Validates word count, word membership, entropy and checksum.
- Derives the first receiving address for BTC Legacy, Nested SegWit, Native SegWit, Taproot and EVM.
- Performs local ECDSA challenge signing/verification to demonstrate key/address derivation consistency.
- Exports only public addresses and validation metadata. It does not write the mnemonic, seed or private keys.
- No missing-word guessing, passphrase brute force, third-party address probing, RPC, signing for broadcast or transfers.

## Run locally
```bash
python -m pip install -r requirements.txt
python nexus_recovery_lab.py --wordlist /secure/path/to/bip39-english.txt --output public_inventory.json
```
Use only a wallet you own or are explicitly authorized to recover. Obtain the wordlist from the official BIP-39 repository and verify its source before use. Run on a trusted offline machine. Do not paste seed phrases into ChatGPT or store them in cloud-synced folders.

## Tests
```bash
pytest -q
```
The unit tests use a synthetic 2048-entry wordlist to test checksum mechanics; they do not replace validation against the official English wordlist.
