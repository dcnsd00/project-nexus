import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from nexus_recovery_lab import entropy_to_mnemonic, validate_mnemonic, derive_public_inventory


def synthetic_wordlist():
    return [f'w{i:04d}' for i in range(2048)]


def test_bip39_checksum_roundtrip_12_words():
    words = synthetic_wordlist()
    mnemonic = entropy_to_mnemonic(bytes(16), words)
    assert len(mnemonic.split()) == 12
    result = validate_mnemonic(mnemonic, words)
    assert result['valid'] is True
    assert result['entropy_bits'] == 128
    assert result['checksum_bits'] == 4


def test_bip39_checksum_rejects_mutated_last_word():
    words = synthetic_wordlist()
    mnemonic = entropy_to_mnemonic(bytes(16), words)
    parts = mnemonic.split()
    parts[-1] = words[(words.index(parts[-1]) + 1) % 2048]
    try:
        validate_mnemonic(' '.join(parts), words)
    except ValueError as exc:
        assert 'checksum mismatch' in str(exc)
    else:
        raise AssertionError('Mutated mnemonic checksum should fail.')


def test_derivation_inventory_never_exports_secret_material():
    mnemonic = 'abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon about'
    result = derive_public_inventory(mnemonic, 'TREZOR')
    assert result['formats_tested'] == 5
    assert result['all_address_checks_passed']
    assert result['all_local_key_proofs_passed']
    assert result['secret_material_saved'] is False
    assert all('private_key' not in x and 'mnemonic' not in x for x in result['wallets'])
