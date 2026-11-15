"""Reference SHA-256 compression implementation used only for research.

The 64-round mode is checked against hashlib. Reduced-round modes are
non-standard research variants and must never be used for consensus mining.
"""
from __future__ import annotations
import hashlib
import struct

MASK32 = 0xFFFFFFFF
K = [
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
    0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
    0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
    0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
    0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
    0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2,
]
IV = [0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a,
      0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19]


def rotr(x: int, n: int) -> int:
    return ((x >> n) | (x << (32 - n))) & MASK32


def validate_rounds(rounds: int) -> None:
    if isinstance(rounds, bool) or not isinstance(rounds, int) or not 1 <= rounds <= 64:
        raise ValueError("rounds must be an integer between 1 and 64")


def expand_schedule(block_words: list[int] | tuple[int, ...]) -> list[int]:
    """Expand a 512-bit block into the 64 SHA-256 schedule words."""
    if len(block_words) != 16:
        raise ValueError("block_words must contain exactly 16 32-bit words")
    if any(isinstance(x, bool) or not isinstance(x, int) or not 0 <= x <= MASK32 for x in block_words):
        raise ValueError("each block word must be an unsigned 32-bit integer")
    w = list(block_words)
    for t in range(16, 64):
        s0 = rotr(w[t - 15], 7) ^ rotr(w[t - 15], 18) ^ (w[t - 15] >> 3)
        s1 = rotr(w[t - 2], 17) ^ rotr(w[t - 2], 19) ^ (w[t - 2] >> 10)
        w.append((w[t - 16] + s0 + w[t - 7] + s1) & MASK32)
    return w


def expand_schedule_with_carries(block_words: list[int] | tuple[int, ...]) -> tuple[list[int], list[tuple[int, int, int]]]:
    """Expand W0..W63 and retain carry-outs of the three modulo-2^32 additions."""
    if len(block_words) != 16:
        raise ValueError("block_words must contain exactly 16 32-bit words")
    if any(isinstance(x, bool) or not isinstance(x, int) or not 0 <= x <= MASK32 for x in block_words):
        raise ValueError("each block word must be an unsigned 32-bit integer")
    w = list(block_words)
    carries: list[tuple[int, int, int]] = [(0, 0, 0)] * 16
    for t in range(16, 64):
        s0 = rotr(w[t - 15], 7) ^ rotr(w[t - 15], 18) ^ (w[t - 15] >> 3)
        s1 = rotr(w[t - 2], 17) ^ rotr(w[t - 2], 19) ^ (w[t - 2] >> 10)
        v1 = w[t - 16] + s0
        v2 = (v1 & MASK32) + w[t - 7]
        v3 = (v2 & MASK32) + s1
        carries.append((v1 >> 32, v2 >> 32, v3 >> 32))
        w.append(v3 & MASK32)
    return w, carries


def compress_schedule(schedule: list[int] | tuple[int, ...], rounds: int = 64,
                      state: list[int] | tuple[int, ...] = IV) -> list[int]:
    """Run the compression rounds over an already-expanded schedule."""
    validate_rounds(rounds)
    if len(schedule) != 64:
        raise ValueError("schedule must contain exactly 64 words")
    if len(state) != 8:
        raise ValueError("state must contain exactly 8 32-bit words")
    if any(isinstance(x, bool) or not isinstance(x, int) or not 0 <= x <= MASK32 for x in state):
        raise ValueError("each state word must be an unsigned 32-bit integer")
    a, b, c, d, e, f, g, h = state
    for t in range(rounds):
        big1 = rotr(e, 6) ^ rotr(e, 11) ^ rotr(e, 25)
        ch = (e & f) ^ ((~e) & g)
        t1 = (h + big1 + ch + K[t] + schedule[t]) & MASK32
        big0 = rotr(a, 2) ^ rotr(a, 13) ^ rotr(a, 22)
        maj = (a & b) ^ (a & c) ^ (b & c)
        t2 = (big0 + maj) & MASK32
        h, g, f, e, d, c, b, a = g, f, e, (d + t1) & MASK32, c, b, a, (t1 + t2) & MASK32
    return [(x + y) & MASK32 for x, y in zip(state, (a, b, c, d, e, f, g, h))]


def compress(block_words: list[int] | tuple[int, ...], rounds: int = 64,
             state: list[int] | tuple[int, ...] = IV) -> list[int]:
    """Compress one 512-bit block with 1..64 rounds and SHA-256 feed-forward."""
    validate_rounds(rounds)
    return compress_schedule(expand_schedule(block_words), rounds, state)


def sha256_digest(message: bytes, rounds: int = 64) -> bytes:
    """SHA-256-style digest for research; only rounds=64 is standard SHA-256."""
    validate_rounds(rounds)
    bit_length = len(message) * 8
    padded = message + b"\x80" + b"\x00" * ((55 - len(message)) % 64) + struct.pack(">Q", bit_length)
    state = list(IV)
    for offset in range(0, len(padded), 64):
        words = struct.unpack(">16I", padded[offset:offset + 64])
        state = compress(words, rounds, state)
    return struct.pack(">8I", *state)


def verify_against_hashlib() -> dict:
    vectors = (b"", b"abc", b"x" * 100, bytes(range(256)), b"NEXUS" * 100)
    checks = []
    for payload in vectors:
        ours = sha256_digest(payload, 64)
        expected = hashlib.sha256(payload).digest()
        checks.append({"input_bytes": len(payload), "matches": ours == expected})
    return {"passed": all(x["matches"] for x in checks), "vectors": checks}


def compress_schedule_with_round_carries(schedule: list[int] | tuple[int, ...], rounds: int = 64,
                                         state: list[int] | tuple[int, ...] = IV) -> tuple[list[int], list[list[int]]]:
    """Compression with per-round carry-out traces for T1/T2 and state additions.

    Carry flags are recorded for: four sequential T1 additions, T2 addition,
    d+T1, and T1+T2. This is instrumentation only; arithmetic remains exact mod 2^32.
    """
    validate_rounds(rounds)
    if len(schedule) != 64:
        raise ValueError("schedule must contain exactly 64 words")
    if len(state) != 8 or any(isinstance(x, bool) or not isinstance(x, int) or not 0 <= x <= MASK32 for x in state):
        raise ValueError("state must contain exactly eight unsigned 32-bit words")
    a, b, c, d, e, f, g, h = state
    traces: list[list[int]] = []
    for t in range(rounds):
        big1 = rotr(e, 6) ^ rotr(e, 11) ^ rotr(e, 25)
        ch = (e & f) ^ ((~e) & g)
        acc = h
        t1_carries = []
        for term in (big1, ch, K[t], schedule[t]):
            acc += term
            t1_carries.append(1 if acc > MASK32 else 0)
            acc &= MASK32
        t1 = acc
        big0 = rotr(a, 2) ^ rotr(a, 13) ^ rotr(a, 22)
        maj = (a & b) ^ (a & c) ^ (b & c)
        t2_sum = big0 + maj
        t2_carry = 1 if t2_sum > MASK32 else 0
        t2 = t2_sum & MASK32
        e_sum = d + t1
        e_carry = 1 if e_sum > MASK32 else 0
        a_sum = t1 + t2
        a_carry = 1 if a_sum > MASK32 else 0
        traces.append(t1_carries + [t2_carry, e_carry, a_carry])
        h, g, f, e, d, c, b, a = g, f, e, e_sum & MASK32, c, b, a, a_sum & MASK32
    return [(x + y) & MASK32 for x, y in zip(state, (a, b, c, d, e, f, g, h))], traces
