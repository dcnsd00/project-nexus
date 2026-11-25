"""
SHA-256 avansat pentru NEXUS.
- Numar configurabil de runde (rounds=64 -> SHA-256 standard).
- intoarce toate starile intermediare (pentru criptanaliza).
- Midstate pentru mining Bitcoin (antet de 80 de octeti).
- Verificat contra hashlib in tests.py / verify_results.py.

NOTA: implementare de referinta, prioritizand corectitudinea si
instrumentarea, nu viteza bruta.
"""

import struct
import hashlib

MASK32 = 0xFFFFFFFF
K256 = [
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1,
    0x923f82a4, 0xab1c5ed5, 0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3,
    0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174, 0xe49b69c1, 0xefbe4786,
    0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147,
    0x06ca6351, 0x14292967, 0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13,
    0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85, 0xa2bfe8a1, 0xa81a664b,
    0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a,
    0x5b9cca4f, 0x682e6ff3, 0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208,
    0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2,
]
IV256 = [0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a,
         0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19]


def _rotr(x, n):
    return ((x >> n) | (x << (32 - n))) & MASK32


def _sigma0(x):
    return _rotr(x, 2) ^ _rotr(x, 13) ^ _rotr(x, 22)


def _sigma1(x):
    return _rotr(x, 6) ^ _rotr(x, 11) ^ _rotr(x, 25)


def _small_sigma0(x):
    return _rotr(x, 7) ^ _rotr(x, 18) ^ (x >> 3)


def _small_sigma1(x):
    return _rotr(x, 17) ^ _rotr(x, 19) ^ (x >> 10)


def expand_block(block_words, rounds=64):
    """Schedule-ul mesajului: W[0..15] din bloc, apoi expansiunea pana la `rounds`."""
    W = list(block_words)
    for t in range(16, rounds):
        W.append((W[t - 16] + _small_sigma0(W[t - 15]) + W[t - 7]
                  + _small_sigma1(W[t - 2])) & MASK32)
    return W


def compress(state, block_words, rounds=64, return_states=False):
    """O compresie SHA-256 cu `rounds` runde (feedforward inclus).

    rounds=64 -> SHA-256 standard. rounds<64 -> varianta redusa (doar pentru
    cercetare; NU este SHA-256).
    """
    a, b, c, d, e, f, g, h = state
    W = expand_block(block_words, rounds)
    states = [(a, b, c, d, e, f, g, h)] if return_states else None
    for t in range(rounds):
        S1 = _sigma1(e)
        ch = (e & f) ^ (~e & g)
        t1 = (h + S1 + ch + K256[t] + W[t]) & MASK32
        S0 = _sigma0(a)
        maj = (a & b) ^ (a & c) ^ (b & c)
        t2 = (S0 + maj) & MASK32
        h, g, f, e, d, c, b, a = g, f, e, (d + t1) & MASK32, c, b, a, (t1 + t2) & MASK32
        if return_states:
            states.append((a, b, c, d, e, f, g, h))
    out = [(state[i] + v) & MASK32 for i, v in enumerate((a, b, c, d, e, f, g, h))]
    if return_states:
        return out, states, W
    return out


def sha256(data: bytes, rounds: int = 64) -> bytes:
    """SHA-256 (sau varianta cu runde reduse) pe date arbitrar de lungi."""
    if rounds < 1 or rounds > 64:
        raise ValueError("rounds trebuie in [1, 64]")
    bitlen = len(data) * 8
    data = data + b"\x80"
    data += b"\x00" * ((56 - len(data) % 64) % 64)
    data += struct.pack(">Q", bitlen)
    state = list(IV256)
    for i in range(0, len(data), 64):
        block = struct.unpack(">16I", data[i:i + 64])
        state = compress(state, list(block), rounds)
    return struct.pack(">8I", *state)


def double_sha256(data: bytes, rounds: int = 64) -> bytes:
    return sha256(sha256(data, rounds), rounds)


def sha256_states(data: bytes, rounds: int = 64):
    """Toate starile intermediare ale fiecarei compresii (instrumentare)."""
    bitlen = len(data) * 8
    padded = data + b"\x80"
    padded += b"\x00" * ((56 - len(padded) % 64) % 64)
    padded += struct.pack(">Q", bitlen)
    state = list(IV256)
    all_states = []
    for i in range(0, len(padded), 64):
        block = list(struct.unpack(">16I", padded[i:i + 64]))
        state, states, W = compress(state, block, rounds, return_states=True)
        all_states.append({"block": block, "states": states, "W": W, "final": state})
    return all_states


# ---------------------------------------------------------------------------
# Midstate mining (antet Bitcoin de 80 de octeti, nonce in bytes 76..79)
# ---------------------------------------------------------------------------

class MidstateMiner:
    """Optimizare exacta (fara aproximare) pentru double-SHA256 pe antet Bitcoin.

    - midstate: starea dupa compresia primului bloc (bytes 0..63) - constanta.
    - block2 precalculat: doar wordul 3 (nonce) variaza; W[16], W[17] si
      runda 0..2 ale compresiei 1 sunt constante -> precalculate.
    - early-exit: compara doar primul cuvant al hash-ului final cu target.
    Toate rezultatele sunt identice cu double_sha256(header) (verificat in teste).
    """

    def __init__(self, header_80: bytes):
        if len(header_80) != 80:
            raise ValueError("antetul trebuie sa aiba exact 80 de octeti")
        self.header = bytearray(header_80)
        block1 = list(struct.unpack(">16I", bytes(header_80[:64])))
        self.midstate = compress(list(IV256), block1, 64)
        # blocul 2 al primei hash: bytes 64..79 + padding (64 de octeti)
        b2 = bytearray(64)
        b2[0:16] = header_80[64:80]
        b2[16] = 0x80  # byte 80 al mesajului
        # lungimea totala 640 biti -> bytes 120..127
        b2[56:64] = struct.pack(">Q", 640)
        self._block2_template = b2
        w2 = list(struct.unpack(">16I", bytes(b2)))
        self._W2_const = expand_block(w2, 64)
        # runde 0..2 nu depind de W[3] (nonce) -> stare dupa runda 2 constanta
        a, b, c, d, e, f, g, h = self.midstate
        W = self._W2_const
        for t in range(3):
            t1 = (h + _sigma1(e) + ((e & f) ^ (~e & g)) + K256[t] + W[t]) & MASK32
            t2 = (_sigma0(a) + ((a & b) ^ (a & c) ^ (b & c))) & MASK32
            h, g, f, e, d, c, b, a = g, f, e, (d + t1) & MASK32, c, b, a, (t1 + t2) & MASK32
        self._state_after_round2 = (a, b, c, d, e, f, g, h)
        # W[16] si W[17] nu depind de W[3]
        self._W16 = self._W2_const[16]
        self._W17 = self._W2_const[17]

    def hash_header(self, nonce: int) -> bytes:
        """double-SHA256(antet cu nonce) - cale optimizata, rezultat identic."""
        b2 = bytearray(self._block2_template)
        b2[12:16] = struct.pack("<I", nonce)  # nonce little-endian in serialized Bitcoin header
        w2 = list(struct.unpack(">16I", bytes(b2)))
        W = list(w2)
        W.extend(self._W2_const[16:18])
        for t in range(18, 64):
            W.append((W[t - 16] + _small_sigma0(W[t - 15]) + W[t - 7]
                      + _small_sigma1(W[t - 2])) & MASK32)
        a, b, c, d, e, f, g, h = self._state_after_round2
        for t in range(3, 64):
            t1 = (h + _sigma1(e) + ((e & f) ^ (~e & g)) + K256[t] + W[t]) & MASK32
            t2 = (_sigma0(a) + ((a & b) ^ (a & c) ^ (b & c))) & MASK32
            h, g, f, e, d, c, b, a = g, f, e, (d + t1) & MASK32, c, b, a, (t1 + t2) & MASK32
        h1 = [(self.midstate[i] + v) & MASK32
              for i, v in enumerate((a, b, c, d, e, f, g, h))]
        # a doua hash: un singur bloc, W[9..15] sunt constante
        W3 = list(h1)
        W3.append(0x80000000)
        W3.extend([0, 0, 0, 0, 0, 0])  # W[9..14] = 0
        W3.append(0x100)  # W[15] = 256 biti (big-endian)
        W3 = expand_block(W3, 64)
        a, b, c, d, e, f, g, h = IV256
        for t in range(64):
            t1 = (h + _sigma1(e) + ((e & f) ^ (~e & g)) + K256[t] + W3[t]) & MASK32
            t2 = (_sigma0(a) + ((a & b) ^ (a & c) ^ (b & c))) & MASK32
            h, g, f, e, d, c, b, a = g, f, e, (d + t1) & MASK32, c, b, a, (t1 + t2) & MASK32
        out = [(IV256[i] + v) & MASK32
               for i, v in enumerate((a, b, c, d, e, f, g, h))]
        return struct.pack(">8I", *out)

    def first_output_word(self, nonce: int) -> int:
        """Primul cuvant (32 biti) al hash-ului final - pentru early-exit."""
        return struct.unpack(">I", self.hash_header(nonce)[:4])[0]


def reference_double_sha256(data: bytes) -> bytes:
    """Referinta independenta (hashlib) pentru validare."""
    return hashlib.sha256(hashlib.sha256(data).digest()).digest()
