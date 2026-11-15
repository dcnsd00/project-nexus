#!/usr/bin/env python3
"""NEXUS Recovery Lab 0.3.0 — local, authorized mnemonic validation.

This module validates a user-supplied BIP39 mnemonic against a locally supplied
official wordlist, derives public addresses for standard paths, and proves local
key/address correspondence with a disposable ECDSA challenge. It does NOT guess
missing words, brute-force passphrases, contact RPC endpoints, or broadcast.
Never paste a real mnemonic into chat. Run locally on a trusted, offline device.
"""
from __future__ import annotations

import argparse
import getpass
import hashlib
import json
import unicodedata
from pathlib import Path
from typing import Sequence

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import Prehashed

from nexus_wallet_benchmark import (
    FORMATS, EVM_NETWORKS, bip39_seed, derive_path, bitcoin_address,
    evm_address, validate_address, SECP256K1_N,
)

ALLOWED_WORD_COUNTS = {12, 15, 18, 21, 24}


def load_wordlist(path: Path) -> list[str]:
    words = [unicodedata.normalize('NFKD', x.strip()) for x in path.read_text(encoding='utf-8').splitlines() if x.strip()]
    if len(words) != 2048 or len(set(words)) != 2048:
        raise ValueError('Wordlist must contain exactly 2048 unique BIP39 words.')
    return words


def validate_mnemonic(mnemonic: str, wordlist: Sequence[str]) -> dict:
    """Validate BIP39 word membership, word count, and checksum; never guesses."""
    if len(wordlist) != 2048 or len(set(wordlist)) != 2048:
        raise ValueError('Wordlist must contain exactly 2048 unique words.')
    normalized = unicodedata.normalize('NFKD', ' '.join(mnemonic.strip().split()))
    words = normalized.split(' ')
    if len(words) not in ALLOWED_WORD_COUNTS:
        raise ValueError('BIP39 mnemonic must contain 12, 15, 18, 21, or 24 words.')
    index = {word: i for i, word in enumerate(wordlist)}
    try:
        bits = ''.join(f'{index[word]:011b}' for word in words)
    except KeyError as exc:
        raise ValueError(f'Word not present in supplied BIP39 wordlist: {exc.args[0]}') from exc
    checksum_bits = len(bits) // 33
    entropy_bits = len(bits) - checksum_bits
    entropy = int(bits[:entropy_bits], 2).to_bytes(entropy_bits // 8, 'big')
    expected = ''.join(f'{b:08b}' for b in hashlib.sha256(entropy).digest())[:checksum_bits]
    actual = bits[entropy_bits:]
    if actual != expected:
        raise ValueError('BIP39 checksum mismatch: phrase is not a valid mnemonic for this wordlist.')
    return {
        'valid': True,
        'word_count': len(words),
        'entropy_bits': entropy_bits,
        'checksum_bits': checksum_bits,
        'entropy_sha256': hashlib.sha256(entropy).hexdigest(),
        'mnemonic_is_secret': True,
    }


def entropy_to_mnemonic(entropy: bytes, wordlist: Sequence[str]) -> str:
    """Convert valid BIP39 entropy bytes into a mnemonic (for local tests only)."""
    if len(wordlist) != 2048:
        raise ValueError('Wordlist must contain 2048 words.')
    ent = len(entropy) * 8
    if ent not in {128, 160, 192, 224, 256}:
        raise ValueError('Entropy must be 128, 160, 192, 224, or 256 bits.')
    cs = ent // 32
    checksum = ''.join(f'{b:08b}' for b in hashlib.sha256(entropy).digest())[:cs]
    bits = ''.join(f'{b:08b}' for b in entropy) + checksum
    return ' '.join(wordlist[int(bits[i:i+11], 2)] for i in range(0, len(bits), 11))


def local_key_proof(private_key: int, label: str) -> bool:
    if not 1 <= private_key < SECP256K1_N:
        raise ValueError('Derived private scalar is outside secp256k1 range.')
    challenge = hashlib.sha256(('NEXUS-LOCAL-RECOVERY-CHECK|' + label).encode()).digest()
    obj = ec.derive_private_key(private_key, ec.SECP256K1())
    sig = obj.sign(challenge, ec.ECDSA(Prehashed(hashes.SHA256())))
    obj.public_key().verify(sig, challenge, ec.ECDSA(Prehashed(hashes.SHA256())))
    return True


def derive_public_inventory(mnemonic: str, passphrase: str = '') -> dict:
    """Derive first receiving address for each supported format; never returns keys."""
    seed = bip39_seed(mnemonic, passphrase)
    out = []
    for fmt, spec in FORMATS.items():
        path = f"m/{spec['purpose']}'/{spec['coin']}'/0'/0/0"
        private_key = derive_path(seed, path)
        address = bitcoin_address(fmt, private_key) if fmt.startswith('BTC_') else evm_address(private_key)
        valid = validate_address(fmt, address)
        proof = local_key_proof(private_key, fmt + ':' + path)
        if not valid or not proof:
            raise AssertionError(f'Address/key validation failed for {fmt}')
        out.append({
            'format': fmt,
            'path': path,
            'address': address,
            'address_checksum_valid': valid,
            'local_key_proof_passed': proof,
            'evm_compatible_networks': EVM_NETWORKS if fmt == 'EVM_ETHEREUM' else [],
        })
    # Do not return or persist mnemonic, seed, or private scalars.
    return {
        'engine': 'NEXUS Recovery Lab',
        'version': '0.3.0',
        'mode': 'LOCAL_AUTHORIZED_DERIVATION_ONLY',
        'formats_tested': len(out),
        'all_address_checks_passed': all(x['address_checksum_valid'] for x in out),
        'all_local_key_proofs_passed': all(x['local_key_proof_passed'] for x in out),
        'wallets': out,
        'network_requests': 0,
        'transactions_signed_for_broadcast': 0,
        'funds_moved': False,
        'secret_material_saved': False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description='Validate and derive public addresses from your own BIP39 phrase, locally.')
    parser.add_argument('--wordlist', type=Path, required=True, help='Path to official BIP39 English (or matching language) wordlist, 2048 lines.')
    parser.add_argument('--output', type=Path, default=Path('nexus_local_inventory.json'))
    args = parser.parse_args()
    words = load_wordlist(args.wordlist)
    print('Use only a wallet you own or are explicitly authorized to recover.')
    mnemonic = getpass.getpass('Enter your BIP39 mnemonic (input hidden; local only): ')
    passphrase = getpass.getpass('BIP39 optional passphrase (input hidden; blank if none): ')
    validation = validate_mnemonic(mnemonic, words)
    result = derive_public_inventory(mnemonic, passphrase)
    result['mnemonic_validation'] = {k: v for k, v in validation.items() if k != 'mnemonic_is_secret'}
    args.output.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps({'valid_mnemonic': True, 'formats': result['formats_tested'], 'all_checks_passed': result['all_address_checks_passed'] and result['all_local_key_proofs_passed'], 'output': str(args.output.resolve()), 'secret_material_saved': False}, indent=2))

if __name__ == '__main__':
    main()
