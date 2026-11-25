import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from nexus_wallet_benchmark import (
    FORMATS, TEST_VECTORS, TEST_PASSPHRASE, bip39_seed, generate_wallets,
    keccak256, master_key, derive_path, make_path, validate_address,
    bitcoin_address, evm_address, eip55_address, compressed_pubkey,
)


def test_keccak256_known_empty_vector():
    assert keccak256(b"").hex() == "c5d2460186f7233c927e7db2dcc703c0e500b653ca82273b7bfad8045d85a470"


def test_bip39_public_test_vector_seed_prefixes():
    for vector in TEST_VECTORS:
        seed = bip39_seed(vector["mnemonic"], TEST_PASSPHRASE)
        assert seed.hex().startswith(vector["expected_seed_prefix"])
        assert len(seed) == 64


def test_bip32_master_key_official_vector_one():
    seed = bytes.fromhex("000102030405060708090a0b0c0d0e0f")
    key, chain = master_key(seed)
    assert key.to_bytes(32, "big").hex() == "e8f32e723decf4051aefac8e2c93c9c5b214313817cdb01a1494b917c8436b35"
    assert chain.hex() == "873dff81c02f525623fd1fe5167eac3a55a049de3d314bb42ee227ffed37d508"


def test_exactly_ten_wallets_two_per_format():
    wallets = generate_wallets()
    assert len(wallets) == 10
    assert set(w.format for w in wallets) == set(FORMATS)
    for name in FORMATS:
        assert sum(w.format == name for w in wallets) == 2


def test_all_generated_addresses_validate():
    for wallet in generate_wallets():
        assert wallet.validation_passed
        assert validate_address(wallet.format, wallet.address)


def test_deterministic_derivation():
    vector = TEST_VECTORS[0]
    seed = bip39_seed(vector["mnemonic"], TEST_PASSPHRASE)
    for name in FORMATS:
        key1 = derive_path(seed, make_path(name, 0))
        key2 = derive_path(seed, make_path(name, 0))
        assert key1 == key2
        address1 = bitcoin_address(name, key1) if name.startswith("BTC_") else evm_address(key1)
        address2 = bitcoin_address(name, key2) if name.startswith("BTC_") else evm_address(key2)
        assert address1 == address2


def test_bip86_official_first_address_vector():
    # BIP-86 test vector uses the published mnemonic with an empty passphrase.
    mnemonic = TEST_VECTORS[0]["mnemonic"]
    seed = bip39_seed(mnemonic, "")
    private_key = derive_path(seed, "m/86\'/0\'/0\'/0/0")
    address = bitcoin_address("BTC_TAPROOT_BIP86", private_key)
    assert address == "bc1p5cyxnuxmeuwuvkwfem96lqzszd02n6xdcjrs20cac6yqjjwudpxqkedrcr"


def test_eip55_known_checksum_vector():
    raw = bytes.fromhex("52908400098527886e0f7030069857d2e4169ee7")
    assert eip55_address(raw) == "0x52908400098527886E0F7030069857D2E4169EE7"


def test_bip84_official_first_address_vector():
    # BIP-84 reference vector: same public mnemonic, empty passphrase.
    seed = bip39_seed(TEST_VECTORS[0]["mnemonic"], "")
    private_key = derive_path(seed, "m/84\'/0\'/0\'/0/0")
    assert compressed_pubkey(private_key).hex() == "0330d54fd0dd420a6e5f8d3624f5f3482cae350f79d5f0753bf5beef9c2d91af3c"
    assert bitcoin_address("BTC_NATIVE_SEGWIT_P2WPKH", private_key) == "bc1qcr8te4kr609gcawutmrza0j4xv80jy8z306fyu"


def test_bip49_official_testnet_child_key_vector():
    # BIP-49 reference vector uses testnet coin type 1 and empty passphrase.
    seed = bip39_seed(TEST_VECTORS[0]["mnemonic"], "")
    private_key = derive_path(seed, "m/49\'/1\'/0\'/0/0")
    assert private_key.to_bytes(32, "big").hex() == "c9bdb49cfbaedca21c4b1f3a7803c34636b1d7dc55a717132443fc3f4c5867e8"
    assert compressed_pubkey(private_key).hex() == "03a1af804ac108a8a51782198c2d034b28bf90c8803f5a53f76276fa69a4eae77f"
