"""Bitcoin header, proof-of-work, subsidy and coinbase helpers.

All amounts are represented as integer satoshis. Display-order block hashes are
hexadecimal big-endian strings; serialized header hash fields are little-endian.
"""
from __future__ import annotations

import hashlib
from typing import Any

SATOSHIS_PER_BTC = 100_000_000
INITIAL_SUBSIDY_SATS = 50 * SATOSHIS_PER_BTC
HALVING_INTERVAL = 210_000


def sha256d(payload: bytes) -> bytes:
    """Return the raw 32-byte double-SHA-256 digest (not display-reversed)."""
    return hashlib.sha256(hashlib.sha256(payload).digest()).digest()


def decode_compact_target(bits: int) -> int:
    """Decode Bitcoin's compact nBits representation into the target integer."""
    exponent = (bits >> 24) & 0xFF
    mantissa = bits & 0x007FFFFF
    negative = bool(bits & 0x00800000)
    if negative or mantissa == 0:
        raise ValueError(f"Invalid compact target: 0x{bits:08x}")
    if exponent <= 3:
        target = mantissa >> (8 * (3 - exponent))
    else:
        target = mantissa << (8 * (exponent - 3))
    if target <= 0 or target >= 1 << 256:
        raise ValueError(f"Target out of range: 0x{bits:08x}")
    return target


def subsidy_sats(height: int) -> int:
    """Return scheduled block subsidy at height; zero after 64 halvings."""
    if height < 0:
        raise ValueError("Block height cannot be negative")
    halvings = height // HALVING_INTERVAL
    if halvings >= 64:
        return 0
    return INITIAL_SUBSIDY_SATS >> halvings


def parse_header(header_hex: str) -> dict[str, Any]:
    """Parse an 80-byte serialized Bitcoin header and independently hash it."""
    raw = bytes.fromhex(header_hex)
    if len(raw) != 80:
        raise ValueError(f"Bitcoin header must be 80 bytes, received {len(raw)}")

    version = int.from_bytes(raw[0:4], "little", signed=True)
    previous_hash = raw[4:36][::-1].hex()
    merkle_root = raw[36:68][::-1].hex()
    timestamp = int.from_bytes(raw[68:72], "little")
    bits = int.from_bytes(raw[72:76], "little")
    nonce = int.from_bytes(raw[76:80], "little")
    digest = sha256d(raw)
    block_hash = digest[::-1].hex()
    target = decode_compact_target(bits)
    hash_int = int(block_hash, 16)

    return {
        "header_hex": raw.hex(),
        "version": version,
        "previous_block_hash": previous_hash,
        "merkle_root": merkle_root,
        "timestamp": timestamp,
        "bits": bits,
        "nonce": nonce,
        "nonce_hex": f"{nonce:08x}",
        "block_hash": block_hash,
        "target_hex": f"{target:064x}",
        "pow_valid": hash_int <= target,
    }


def verify_coinbase_reward(height: int, vout: list[dict[str, Any]]) -> dict[str, int]:
    """Sum coinbase outputs and compare them with scheduled subsidy.

    The difference is NOT guaranteed to equal transaction fees: a miner may
    voluntarily underclaim part of the subsidy or fees. Exact block fees must
    be obtained from per-transaction input/output accounting or a trusted
    block-level fee field.
    """
    total_sats = 0
    for output in vout:
        value = output.get("value")
        if not isinstance(value, int):
            raise ValueError("Coinbase output value must be integer satoshis")
        total_sats += value
    subsidy = subsidy_sats(height)
    difference = total_sats - subsidy
    return {
        "coinbase_total_sats": total_sats,
        "scheduled_subsidy_sats": subsidy,
        "coinbase_minus_scheduled_subsidy_sats": difference,
        "subsidy_underclaim_sats": max(0, -difference),
        "claimed_above_subsidy_sats": max(0, difference),
    }


def merkle_root_from_txids(txids: list[str]) -> str:
    """Rebuild Bitcoin Merkle root from display-order txid hex strings."""
    if not txids:
        raise ValueError("At least one txid is required")
    layer = [bytes.fromhex(x)[::-1] for x in txids]
    if any(len(x) != 32 for x in layer):
        raise ValueError("Every txid must be 32 bytes")
    while len(layer) > 1:
        if len(layer) & 1:
            layer.append(layer[-1])
        layer = [sha256d(layer[i] + layer[i + 1]) for i in range(0, len(layer), 2)]
    return layer[0][::-1].hex()


def verify_merkle_root(header_merkle_root: str, txids: list[str]) -> dict[str, Any]:
    calculated = merkle_root_from_txids(txids)
    return {"calculated_merkle_root": calculated, "header_merkle_root": header_merkle_root,
            "merkle_root_valid": calculated.lower() == header_merkle_root.lower(),
            "transaction_count": len(txids)}
