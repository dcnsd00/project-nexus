#!/usr/bin/env python3
"""NEXUS Wallet Benchmark — deterministic, offline, test-only wallet derivation.

This program creates ten deterministic wallets from two PUBLIC BIP39 test-vector
mnemonics: two wallets in each of five formats. It performs no network requests,
never broadcasts transactions, and does not attempt recovery against third-party
addresses. The mnemonic vectors and passphrase are public test data; NEVER fund
any generated address or reuse this code's test phrases for a real wallet.

Dependencies: Python >=3.10, cryptography >=41.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import hmac
import json
import math
import statistics
import time
import unicodedata
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

# secp256k1 domain parameters
SECP256K1_P = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFC2F
SECP256K1_N = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141

# Public BIP39 test vectors, deliberately not secrets.
TEST_VECTORS = [
    {
        "id": "TV-01",
        "mnemonic": "abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon about",
        "expected_seed_prefix": "c55257c360c07c72029aebc1b53c05ed",
    },
    {
        "id": "TV-02",
        "mnemonic": "legal winner thank year wave sausage worth useful legal winner thank yellow",
        "expected_seed_prefix": "2e8905819b8723fe2c1d161860e5ee18",
    },
]
TEST_PASSPHRASE = "TREZOR"  # Public BIP39 test-vector passphrase.

FORMATS = {
    "BTC_LEGACY_P2PKH": {"coin": 0, "purpose": 44, "description": "Bitcoin Legacy P2PKH"},
    "BTC_NESTED_SEGWIT_P2SH_P2WPKH": {"coin": 0, "purpose": 49, "description": "Bitcoin Nested SegWit P2SH-P2WPKH"},
    "BTC_NATIVE_SEGWIT_P2WPKH": {"coin": 0, "purpose": 84, "description": "Bitcoin Native SegWit P2WPKH"},
    "BTC_TAPROOT_BIP86": {"coin": 0, "purpose": 86, "description": "Bitcoin Taproot BIP86 P2TR"},
    "EVM_ETHEREUM": {"coin": 60, "purpose": 44, "description": "EVM / Ethereum (same key format across EVM chains)"},
}
EVM_NETWORKS = ["ETH", "BASE", "BNB", "POLYGON", "ARBITRUM"]


def sha256(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


def hash160(data: bytes) -> bytes:
    h = hashlib.new("ripemd160")
    h.update(sha256(data))
    return h.digest()


def bip39_seed(mnemonic: str, passphrase: str) -> bytes:
    """BIP39 mnemonic-to-seed (NFKD + PBKDF2-HMAC-SHA512/2048)."""
    mnemonic_nfkd = unicodedata.normalize("NFKD", mnemonic)
    salt = "mnemonic" + unicodedata.normalize("NFKD", passphrase)
    return hashlib.pbkdf2_hmac("sha512", mnemonic_nfkd.encode(), salt.encode(), 2048, 64)


def master_key(seed: bytes) -> tuple[int, bytes]:
    digest = hmac.new(b"Bitcoin seed", seed, hashlib.sha512).digest()
    key = int.from_bytes(digest[:32], "big")
    if key == 0 or key >= SECP256K1_N:
        raise ValueError("Invalid BIP32 master key; use another seed")
    return key, digest[32:]


def private_to_public(private_key: int):
    if not 1 <= private_key < SECP256K1_N:
        raise ValueError("Private scalar outside secp256k1 range")
    return ec.derive_private_key(private_key, ec.SECP256K1()).public_key()


def compressed_pubkey(private_key: int) -> bytes:
    return private_to_public(private_key).public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.CompressedPoint
    )


def uncompressed_xy(private_key: int) -> tuple[int, int]:
    nums = private_to_public(private_key).public_numbers()
    return nums.x, nums.y


def derive_child(parent_key: int, parent_chain: bytes, index: int) -> tuple[int, bytes]:
    if not 0 <= index <= 0xFFFFFFFF:
        raise ValueError("BIP32 child index must be uint32")
    if index >= 0x80000000:
        data = b"\x00" + parent_key.to_bytes(32, "big") + index.to_bytes(4, "big")
    else:
        data = compressed_pubkey(parent_key) + index.to_bytes(4, "big")
    digest = hmac.new(parent_chain, data, hashlib.sha512).digest()
    left = int.from_bytes(digest[:32], "big")
    if left >= SECP256K1_N:
        raise ValueError("Invalid BIP32 child (IL >= curve order); retry with next index")
    child_key = (left + parent_key) % SECP256K1_N
    if child_key == 0:
        raise ValueError("Invalid BIP32 child (zero key); retry with next index")
    return child_key, digest[32:]


def parse_path(path: str) -> list[int]:
    if path == "m":
        return []
    if not path.startswith("m/"):
        raise ValueError(f"Invalid derivation path: {path}")
    result = []
    for component in path[2:].split("/"):
        hardened = component.endswith(("'", "h", "H"))
        number = component[:-1] if hardened else component
        value = int(number)
        if not 0 <= value < 0x80000000:
            raise ValueError(f"Invalid path component: {component}")
        result.append(value + (0x80000000 if hardened else 0))
    return result


def derive_path(seed: bytes, path: str) -> int:
    key, chain = master_key(seed)
    for index in parse_path(path):
        key, chain = derive_child(key, chain, index)
    return key


def base58_encode(raw: bytes) -> str:
    alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    zeros = len(raw) - len(raw.lstrip(b"\x00"))
    n = int.from_bytes(raw, "big")
    encoded = ""
    while n:
        n, rem = divmod(n, 58)
        encoded = alphabet[rem] + encoded
    return "1" * zeros + (encoded or ("" if zeros else "1"))


def base58check(payload: bytes) -> str:
    return base58_encode(payload + sha256(sha256(payload))[:4])


def base58check_decode(text: str) -> bytes:
    alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    n = 0
    for char in text:
        if char not in alphabet:
            raise ValueError("Invalid Base58 character")
        n = n * 58 + alphabet.index(char)
    body = n.to_bytes((n.bit_length() + 7) // 8, "big") if n else b""
    zeros = len(text) - len(text.lstrip("1"))
    raw = b"\x00" * zeros + body
    if len(raw) < 5 or sha256(sha256(raw[:-4]))[:4] != raw[-4:]:
        raise ValueError("Base58Check checksum mismatch")
    return raw[:-4]


def bech32_polymod(values: Iterable[int]) -> int:
    generators = [0x3B6A57B2, 0x26508E6D, 0x1EA119FA, 0x3D4233DD, 0x2A1462B3]
    chk = 1
    for value in values:
        top = chk >> 25
        chk = ((chk & 0x1FFFFFF) << 5) ^ value
        for i in range(5):
            if (top >> i) & 1:
                chk ^= generators[i]
    return chk


def bech32_hrp_expand(hrp: str) -> list[int]:
    return [ord(x) >> 5 for x in hrp] + [0] + [ord(x) & 31 for x in hrp]


def convertbits(data: Iterable[int], frombits: int, tobits: int, pad: bool = True) -> list[int]:
    acc = 0
    bits = 0
    ret: list[int] = []
    maxv = (1 << tobits) - 1
    max_acc = (1 << (frombits + tobits - 1)) - 1
    for value in data:
        if value < 0 or (value >> frombits):
            raise ValueError("convertbits input value out of range")
        acc = ((acc << frombits) | value) & max_acc
        bits += frombits
        while bits >= tobits:
            bits -= tobits
            ret.append((acc >> bits) & maxv)
    if pad:
        if bits:
            ret.append((acc << (tobits - bits)) & maxv)
    elif bits >= frombits or ((acc << (tobits - bits)) & maxv):
        raise ValueError("Invalid incomplete bit group")
    return ret


def bech32_encode(hrp: str, witness_version: int, program: bytes) -> str:
    if not 0 <= witness_version <= 16:
        raise ValueError("Invalid witness version")
    data = [witness_version] + convertbits(program, 8, 5)
    const = 1 if witness_version == 0 else 0x2BC830A3
    values = bech32_hrp_expand(hrp) + data + [0] * 6
    polymod = bech32_polymod(values) ^ const
    checksum = [(polymod >> (5 * (5 - i))) & 31 for i in range(6)]
    alphabet = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"
    return hrp + "1" + "".join(alphabet[d] for d in data + checksum)


def bech32_decode(address: str) -> tuple[str, int, bytes]:
    if address.lower() != address and address.upper() != address:
        raise ValueError("Mixed-case Bech32 address")
    address = address.lower()
    pos = address.rfind("1")
    if pos < 1 or pos + 7 > len(address):
        raise ValueError("Malformed Bech32 address")
    hrp = address[:pos]
    alphabet = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"
    try:
        data = [alphabet.index(c) for c in address[pos + 1:]]
    except ValueError as exc:
        raise ValueError("Invalid Bech32 character") from exc
    if not data:
        raise ValueError("Missing Bech32 data")
    version = data[0]
    const = 1 if version == 0 else 0x2BC830A3
    if bech32_polymod(bech32_hrp_expand(hrp) + data) != const:
        raise ValueError("Bech32/Bech32m checksum mismatch")
    program = bytes(convertbits(data[1:-6], 5, 8, False))
    if not 2 <= len(program) <= 40:
        raise ValueError("Invalid witness program length")
    if version == 0 and len(program) not in (20, 32):
        raise ValueError("Invalid v0 witness program length")
    return hrp, version, program


# Keccak-256 (Ethereum's legacy Keccak padding, not standardized SHA3-256).
_KECCAK_RC = [
    0x0000000000000001, 0x0000000000008082, 0x800000000000808A,
    0x8000000080008000, 0x000000000000808B, 0x0000000080000001,
    0x8000000080008081, 0x8000000000008009, 0x000000000000008A,
    0x0000000000000088, 0x0000000080008009, 0x000000008000000A,
    0x000000008000808B, 0x800000000000008B, 0x8000000000008089,
    0x8000000000008003, 0x8000000000008002, 0x8000000000000080,
    0x000000000000800A, 0x800000008000000A, 0x8000000080008081,
    0x8000000000008080, 0x0000000080000001, 0x8000000080008008,
]
_KECCAK_R = [
    [0, 36, 3, 41, 18],
    [1, 44, 10, 45, 2],
    [62, 6, 43, 15, 61],
    [28, 55, 25, 21, 56],
    [27, 20, 39, 8, 14],
]
_MASK64 = (1 << 64) - 1


def _rol64(value: int, shift: int) -> int:
    if shift == 0:
        return value & _MASK64
    return ((value << shift) | (value >> (64 - shift))) & _MASK64


def _keccak_f1600(state: list[int]) -> None:
    for rc in _KECCAK_RC:
        c = [state[x] ^ state[x + 5] ^ state[x + 10] ^ state[x + 15] ^ state[x + 20] for x in range(5)]
        d = [c[(x - 1) % 5] ^ _rol64(c[(x + 1) % 5], 1) for x in range(5)]
        for y in range(5):
            for x in range(5):
                state[x + 5 * y] ^= d[x]
        b = [0] * 25
        for y in range(5):
            for x in range(5):
                new_x = y
                new_y = (2 * x + 3 * y) % 5
                b[new_x + 5 * new_y] = _rol64(state[x + 5 * y], _KECCAK_R[x][y])
        for y in range(5):
            for x in range(5):
                state[x + 5 * y] = b[x + 5 * y] ^ ((~b[(x + 1) % 5 + 5 * y]) & b[(x + 2) % 5 + 5 * y])
                state[x + 5 * y] &= _MASK64
        state[0] ^= rc


def keccak256(data: bytes) -> bytes:
    rate = 136
    padded = bytearray(data)
    padded.append(0x01)  # Keccak domain separator; SHA3 uses 0x06.
    while len(padded) % rate != rate - 1:
        padded.append(0)
    padded.append(0x80)
    state = [0] * 25
    for offset in range(0, len(padded), rate):
        block = padded[offset:offset + rate]
        for i in range(rate // 8):
            state[i] ^= int.from_bytes(block[i * 8:(i + 1) * 8], "little")
        _keccak_f1600(state)
    return b"".join(x.to_bytes(8, "little") for x in state)[:32]


def eip55_address(raw20: bytes) -> str:
    lower = raw20.hex()
    hashed = keccak256(lower.encode("ascii")).hex()
    checksummed = "".join(ch.upper() if ch in "abcdef" and int(hashed[i], 16) >= 8 else ch for i, ch in enumerate(lower))
    return "0x" + checksummed


def tagged_hash(tag: str, msg: bytes) -> bytes:
    tag_hash = sha256(tag.encode("ascii"))
    return sha256(tag_hash + tag_hash + msg)


def bitcoin_address(format_name: str, private_key: int) -> str:
    pub = compressed_pubkey(private_key)
    if format_name == "BTC_LEGACY_P2PKH":
        return base58check(b"\x00" + hash160(pub))
    if format_name == "BTC_NESTED_SEGWIT_P2SH_P2WPKH":
        redeem_script = b"\x00\x14" + hash160(pub)
        return base58check(b"\x05" + hash160(redeem_script))
    if format_name == "BTC_NATIVE_SEGWIT_P2WPKH":
        return bech32_encode("bc", 0, hash160(pub))
    if format_name == "BTC_TAPROOT_BIP86":
        # BIP86 uses the even-Y representative of the internal x-only key.
        x, y = uncompressed_xy(private_key)
        even_d = private_key if y % 2 == 0 else SECP256K1_N - private_key
        tweak = int.from_bytes(tagged_hash("TapTweak", x.to_bytes(32, "big")), "big")
        if tweak >= SECP256K1_N:
            raise ValueError("Invalid TapTweak scalar")
        output_key = (even_d + tweak) % SECP256K1_N
        if output_key == 0:
            raise ValueError("Invalid BIP86 output key")
        output_x, _ = uncompressed_xy(output_key)
        return bech32_encode("bc", 1, output_x.to_bytes(32, "big"))
    raise ValueError(f"Unsupported Bitcoin format: {format_name}")


def evm_address(private_key: int) -> str:
    x, y = uncompressed_xy(private_key)
    public_key = x.to_bytes(32, "big") + y.to_bytes(32, "big")
    return eip55_address(keccak256(public_key)[-20:])


def make_path(format_name: str, address_index: int = 0) -> str:
    spec = FORMATS[format_name]
    purpose = spec["purpose"]
    coin = spec["coin"]
    return f"m/{purpose}'/{coin}'/0'/0/{address_index}"


def validate_address(format_name: str, address: str) -> bool:
    if format_name in ("BTC_LEGACY_P2PKH", "BTC_NESTED_SEGWIT_P2SH_P2WPKH"):
        payload = base58check_decode(address)
        expected_version = b"\x00" if format_name == "BTC_LEGACY_P2PKH" else b"\x05"
        return len(payload) == 21 and payload[:1] == expected_version
    if format_name == "BTC_NATIVE_SEGWIT_P2WPKH":
        hrp, version, program = bech32_decode(address)
        return hrp == "bc" and version == 0 and len(program) == 20
    if format_name == "BTC_TAPROOT_BIP86":
        hrp, version, program = bech32_decode(address)
        return hrp == "bc" and version == 1 and len(program) == 32
    if format_name == "EVM_ETHEREUM":
        if len(address) != 42 or not address.startswith("0x"):
            return False
        raw = bytes.fromhex(address[2:])
        return eip55_address(raw) == address
    return False


@dataclass
class WalletResult:
    wallet_id: str
    format: str
    description: str
    vector_id: str
    derivation_path: str
    address: str
    validation_passed: bool
    derivation_ms: float
    networks: str
    test_only: bool = True
    funds_checked: bool = False


def generate_wallets() -> list[WalletResult]:
    results: list[WalletResult] = []
    for format_name, spec in FORMATS.items():
        for vector in TEST_VECTORS:
            seed = bip39_seed(vector["mnemonic"], TEST_PASSPHRASE)
            path = make_path(format_name, 0)
            start = time.perf_counter_ns()
            private_key = derive_path(seed, path)
            if format_name.startswith("BTC_"):
                address = bitcoin_address(format_name, private_key)
                networks = "BTC"
            else:
                address = evm_address(private_key)
                networks = ",".join(EVM_NETWORKS)
            elapsed_ms = (time.perf_counter_ns() - start) / 1_000_000
            valid = validate_address(format_name, address)
            if not valid:
                raise RuntimeError(f"Address validation failed for {format_name}/{vector['id']}: {address}")
            results.append(WalletResult(
                wallet_id=f"{format_name}-{vector['id']}",
                format=format_name,
                description=spec["description"],
                vector_id=vector["id"],
                derivation_path=path,
                address=address,
                validation_passed=valid,
                derivation_ms=round(elapsed_ms, 6),
                networks=networks,
            ))
    if len(results) != 10:
        raise AssertionError(f"Expected 10 wallets, got {len(results)}")
    return results


def run_benchmark(iterations: int) -> tuple[list[WalletResult], dict]:
    wallets = generate_wallets()
    format_stats = {}
    for format_name in FORMATS:
        timings_ns = []
        for vector in TEST_VECTORS:
            seed = bip39_seed(vector["mnemonic"], TEST_PASSPHRASE)
            for i in range(iterations):
                path = make_path(format_name, i % 1000)
                start = time.perf_counter_ns()
                private_key = derive_path(seed, path)
                address = bitcoin_address(format_name, private_key) if format_name.startswith("BTC_") else evm_address(private_key)
                ok = validate_address(format_name, address)
                elapsed = time.perf_counter_ns() - start
                if not ok:
                    raise RuntimeError(f"Benchmark validation failure: {format_name}")
                timings_ns.append(elapsed)
        total_s = sum(timings_ns) / 1_000_000_000
        count = len(timings_ns)
        format_stats[format_name] = {
            "derivations": count,
            "total_seconds": round(total_s, 6),
            "mean_ms": round(statistics.mean(timings_ns) / 1_000_000, 6),
            "median_ms": round(statistics.median(timings_ns) / 1_000_000, 6),
            "p95_ms": round(sorted(timings_ns)[math.ceil(0.95 * count) - 1] / 1_000_000, 6),
            "wallets_per_second": round(count / total_s, 2) if total_s else None,
            "all_validations_passed": True,
        }
    total_derivations = sum(item["derivations"] for item in format_stats.values())
    total_seconds = sum(item["total_seconds"] for item in format_stats.values())
    summary = {
        "engine": "NEXUS Wallet Benchmark",
        "version": "0.1.0",
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "environment": {
            "python": __import__("sys").version.split()[0],
            "cryptography": __import__("cryptography").__version__,
            "platform": __import__("platform").platform(),
        },
        "scope": {
            "networks": ["BTC", *EVM_NETWORKS],
            "wallet_formats": list(FORMATS.keys()),
            "wallets_created": len(wallets),
            "wallets_per_format": 2,
            "benchmark_iterations_per_vector_per_format": iterations,
            "benchmark_derivations": total_derivations,
            "mnemonic_source": "two public BIP39 test vectors; passphrase TREZOR",
            "network_requests": 0,
            "transactions_broadcast": 0,
            "third_party_wallets_accessed": 0,
            "funds_checked": False,
        },
        "format_results": format_stats,
        "aggregate": {
            "derivations": total_derivations,
            "total_benchmark_seconds": round(total_seconds, 6),
            "aggregate_derivations_per_second": round(total_derivations / total_seconds, 2) if total_seconds else None,
            "all_tests_passed": True,
        },
        "security_note": "TEST-ONLY. Public test vectors are not secure. Never fund generated addresses or use these vectors for a real wallet.",
    }
    return wallets, summary


def write_outputs(wallets: list[WalletResult], summary: dict, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    wallets_json = [asdict(w) for w in wallets]
    (output_dir / "wallets.json").write_text(json.dumps(wallets_json, indent=2), encoding="utf-8")
    (output_dir / "benchmark_results.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    with (output_dir / "wallets.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(wallets_json[0].keys()))
        writer.writeheader()
        writer.writerows(wallets_json)
    with (output_dir / "benchmark_summary.csv").open("w", newline="", encoding="utf-8") as f:
        fields = ["format", "derivations", "mean_ms", "median_ms", "p95_ms", "wallets_per_second", "all_validations_passed"]
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for name, row in summary["format_results"].items():
            writer.writerow({"format": name, **{k: row[k] for k in fields[1:]}})


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the offline NEXUS 10-wallet benchmark")
    parser.add_argument("--iterations", type=int, default=100, help="Benchmark iterations per vector per format (default: 100)")
    parser.add_argument("--output", default="results", help="Output directory (default: results)")
    args = parser.parse_args()
    if args.iterations < 1 or args.iterations > 10000:
        parser.error("--iterations must be between 1 and 10000")
    wallets, summary = run_benchmark(args.iterations)
    write_outputs(wallets, summary, Path(args.output))
    print(json.dumps({
        "wallets_created": len(wallets),
        "formats": len(FORMATS),
        "benchmark_derivations": summary["aggregate"]["derivations"],
        "benchmark_seconds": summary["aggregate"]["total_benchmark_seconds"],
        "aggregate_derivations_per_second": summary["aggregate"]["aggregate_derivations_per_second"],
        "all_tests_passed": summary["aggregate"]["all_tests_passed"],
        "output_dir": str(Path(args.output).resolve()),
    }, indent=2))


if __name__ == "__main__":
    main()
