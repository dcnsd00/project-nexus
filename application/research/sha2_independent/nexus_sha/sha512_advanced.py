"""
SHA-512 avansat pentru NEXUS (comparativ cu SHA-256).
- Numar configurabil de runde (rounds=80 -> SHA-512 standard).
- intoarce starile intermediare pentru criptanaliza comparativa.
- Verificat contra hashlib in tests.py / verify_results.py.
"""

import struct
import hashlib

MASK64 = 0xFFFFFFFFFFFFFFFF
K512 = [
    0x428a2f98d728ae22, 0x7137449123ef65cd, 0xb5c0fbcfec4d3b2f, 0xe9b5dba58189dbbc,
    0x3956c25bf348b538, 0x59f111f1b605d019, 0x923f82a4af194f9b, 0xab1c5ed5da6d8118,
    0xd807aa98a3030242, 0x12835b0145706fbe, 0x243185be4ee4b28c, 0x550c7dc3d5ffb4e2,
    0x72be5d74f27b896f, 0x80deb1fe3b1696b1, 0x9bdc06a725c71235, 0xc19bf174cf692694,
    0xe49b69c19ef14ad2, 0xefbe4786384f25e3, 0x0fc19dc68b8cd5b5, 0x240ca1cc77ac9c65,
    0x2de92c6f592b0275, 0x4a7484aa6ea6e483, 0x5cb0a9dcbd41fbd4, 0x76f988da831153b5,
    0x983e5152ee66dfab, 0xa831c66d2db43210, 0xb00327c898fb213f, 0xbf597fc7beef0ee4,
    0xc6e00bf33da88fc2, 0xd5a79147930aa725, 0x06ca6351e003826f, 0x142929670a0e6e70,
    0x27b70a8546d22ffc, 0x2e1b21385c26c926, 0x4d2c6dfc5ac42aed, 0x53380d139d95b3df,
    0x650a73548baf63de, 0x766a0abb3c77b2a8, 0x81c2c92e47edaee6, 0x92722c851482353b,
    0xa2bfe8a14cf10364, 0xa81a664bbc423001, 0xc24b8b70d0f89791, 0xc76c51a30654be30,
    0xd192e819d6ef5218, 0xd69906245565a910, 0xf40e35855771202a, 0x106aa07032bbd1b8,
    0x19a4c116b8d2d0c8, 0x1e376c085141ab53, 0x2748774cdf8eeb99, 0x34b0bcb5e19b48a8,
    0x391c0cb3c5c95a63, 0x4ed8aa4ae3418acb, 0x5b9cca4f7763e373, 0x682e6ff3d6b2b8a3,
    0x748f82ee5defb2fc, 0x78a5636f43172f60, 0x84c87814a1f0ab72, 0x8cc702081a6439ec,
    0x90befffa23631e28, 0xa4506cebde82bde9, 0xbef9a3f7b2c67915, 0xc67178f2e372532b,
    0xca273eceea26619c, 0xd186b8c721c0c207, 0xeada7dd6cde0eb1e, 0xf57d4f7fee6ed178,
    0x06f067aa72176fba, 0x0a637dc5a2c898a6, 0x113f9804bef90dae, 0x1b710b35131c471b,
    0x28db77f523047d84, 0x32caab7b40c72493, 0x3c9ebe0a15c9bebc, 0x431d67c49c100d4c,
    0x4cc5d4becb3e42b6, 0x597f299cfc657e2a, 0x5fcb6fab3ad6faec, 0x6c44198c4a475817,
]
IV512 = [0x6a09e667f3bcc908, 0xbb67ae8584caa73b, 0x3c6ef372fe94f82b, 0xa54ff53a5f1d36f1,
         0x510e527fade682d1, 0x9b05688c2b3e6c1f, 0x1f83d9abfb41bd6b, 0x5be0cd19137e2179]


def _rotr64(x, n):
    return ((x >> n) | (x << (64 - n))) & MASK64


def _sigma0_64(x):
    return _rotr64(x, 28) ^ _rotr64(x, 34) ^ _rotr64(x, 39)


def _sigma1_64(x):
    return _rotr64(x, 14) ^ _rotr64(x, 18) ^ _rotr64(x, 41)


def _small_sigma0_64(x):
    return _rotr64(x, 1) ^ _rotr64(x, 8) ^ (x >> 7)


def _small_sigma1_64(x):
    return _rotr64(x, 19) ^ _rotr64(x, 61) ^ (x >> 6)


def expand_block_512(block_words, rounds=80):
    W = list(block_words)
    for t in range(16, rounds):
        W.append((W[t - 16] + _small_sigma0_64(W[t - 15]) + W[t - 7]
                  + _small_sigma1_64(W[t - 2])) & MASK64)
    return W


def compress_512(state, block_words, rounds=80, return_states=False):
    a, b, c, d, e, f, g, h = state
    W = expand_block_512(block_words, rounds)
    states = [(a, b, c, d, e, f, g, h)] if return_states else None
    for t in range(rounds):
        S1 = _sigma1_64(e)
        ch = (e & f) ^ (~e & g)
        t1 = (h + S1 + ch + K512[t] + W[t]) & MASK64
        S0 = _sigma0_64(a)
        maj = (a & b) ^ (a & c) ^ (b & c)
        t2 = (S0 + maj) & MASK64
        h, g, f, e, d, c, b, a = g, f, e, (d + t1) & MASK64, c, b, a, (t1 + t2) & MASK64
        if return_states:
            states.append((a, b, c, d, e, f, g, h))
    out = [(state[i] + v) & MASK64 for i, v in enumerate((a, b, c, d, e, f, g, h))]
    if return_states:
        return out, states, W
    return out


def sha512(data: bytes, rounds: int = 80) -> bytes:
    if rounds < 1 or rounds > 80:
        raise ValueError("rounds trebuie in [1, 80]")
    bitlen = len(data) * 8
    data = data + b"\x80"
    data += b"\x00" * ((112 - len(data) % 128) % 128)
    data += struct.pack(">Q", 0) + struct.pack(">Q", bitlen)
    state = list(IV512)
    for i in range(0, len(data), 128):
        block = struct.unpack(">16Q", data[i:i + 128])
        state = compress_512(state, list(block), rounds)
    return struct.pack(">8Q", *state)


def sha512_states(data: bytes, rounds: int = 80):
    """Stari intermediare (comparatie structurala SHA-256 vs SHA-512)."""
    bitlen = len(data) * 8
    padded = data + b"\x80"
    padded += b"\x00" * ((112 - len(padded) % 128) % 128)
    padded += struct.pack(">Q", 0) + struct.pack(">Q", bitlen)
    state = list(IV512)
    out = []
    for i in range(0, len(padded), 128):
        block = list(struct.unpack(">16Q", padded[i:i + 128]))
        state, states, W = compress_512(state, block, rounds, return_states=True)
        out.append({"block": block, "states": states, "W": W, "final": state})
    return out


def reference_sha512(data: bytes) -> bytes:
    return hashlib.sha512(data).digest()


# ---------------------------------------------------------------------------
# Analiza structurala comparativa SHA-256 vs SHA-512 (fapte, nu speculatii)
# ---------------------------------------------------------------------------

STRUCTURAL_COMPARISON = {
    "sha256": {
        "word_bits": 32, "rounds": 64, "block_bytes": 64, "sigma0_rots": [2, 13, 22],
        "sigma1_rots": [6, 11, 25], "small_sigma0": [7, 18, 3], "small_sigma1": [17, 19, 10],
        "expansion": "W[t] = W[t-16] + s0(W[t-15]) + W[t-7] + s1(W[t-2]) (mod 2^32)",
    },
    "sha512": {
        "word_bits": 64, "rounds": 80, "block_bytes": 128, "sigma0_rots": [28, 34, 39],
        "sigma1_rots": [14, 18, 41], "small_sigma0": [1, 8, 7], "small_sigma1": [19, 61, 6],
        "expansion": "W[t] = W[t-16] + s0(W[t-15]) + W[t-7] + s1(W[t-2]) (mod 2^64)",
    },
}


def avalanche_comparison(data: bytes, seed: int = 1234, samples: int = 200):
    """Compara numarul mediu de biti care se schimba in starea interna,
    per runda, intre SHA-256 si SHA-512 (aceeasi structura ARX)."""
    import random
    from .sha256_advanced import sha256_states
    random.seed(seed)
    res = {"sha256": {}, "sha512": {}}
    base = data if data else bytes(random.getrandbits(8) for _ in range(64))
    for name, fn, nrounds, wordbits in (
        ("sha256", sha256_states, 64, 32), ("sha512", sha512_states, 80, 64)):
        s0 = fn(base, nrounds)[0]["states"]
        totals = [0] * (nrounds + 1)
        for _ in range(samples):
            flipped = bytearray(base)
            i = random.randrange(len(flipped))
            flipped[i] ^= 1 << random.randrange(8)
            s1 = fn(bytes(flipped), nrounds)[0]["states"]
            for r in range(nrounds + 1):
                x = sum(bin(x0 ^ x1).count("1") for x0, x1 in zip(s0[r], s1[r]))
                totals[r] += x
        res[name] = {
            "expected_bits_full_state": 8 * wordbits,
            "avg_flipped_bits_per_round": [round(t / samples, 2) for t in totals],
            "rounds_to_full_avalanche": next(
                (r for r in range(nrounds + 1)
                 if totals[r] / samples >= 0.5 * 8 * wordbits), None),
        }
    return res
