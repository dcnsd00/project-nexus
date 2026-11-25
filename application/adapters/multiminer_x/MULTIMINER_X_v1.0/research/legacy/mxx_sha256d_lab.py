#!/usr/bin/env python3
"""MULTIMINER X — SHA-256d Bitcoin research lab.

This is a transparent correctness/research prototype, NOT a high-speed miner.
It demonstrates the Bitcoin 80-byte header layout, standard midstate reuse,
and a job-level precomputation of the first three rounds plus W[16], W[17]
for the nonce-dependent second block.

No pool/network code, wallet handling, or payout functionality is included.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
import time
from dataclasses import dataclass
from typing import Iterable

MASK = 0xFFFFFFFF
IV = (
    0x6A09E667, 0xBB67AE85, 0x3C6EF372, 0xA54FF53A,
    0x510E527F, 0x9B05688C, 0x1F83D9AB, 0x5BE0CD19,
)
K = (
    0x428A2F98, 0x71374491, 0xB5C0FBCF, 0xE9B5DBA5, 0x3956C25B, 0x59F111F1, 0x923F82A4, 0xAB1C5ED5,
    0xD807AA98, 0x12835B01, 0x243185BE, 0x550C7DC3, 0x72BE5D74, 0x80DEB1FE, 0x9BDC06A7, 0xC19BF174,
    0xE49B69C1, 0xEFBE4786, 0x0FC19DC6, 0x240CA1CC, 0x2DE92C6F, 0x4A7484AA, 0x5CB0A9DC, 0x76F988DA,
    0x983E5152, 0xA831C66D, 0xB00327C8, 0xBF597FC7, 0xC6E00BF3, 0xD5A79147, 0x06CA6351, 0x14292967,
    0x27B70A85, 0x2E1B2138, 0x4D2C6DFC, 0x53380D13, 0x650A7354, 0x766A0ABB, 0x81C2C92E, 0x92722C85,
    0xA2BFE8A1, 0xA81A664B, 0xC24B8B70, 0xC76C51A3, 0xD192E819, 0xD6990624, 0xF40E3585, 0x106AA070,
    0x19A4C116, 0x1E376C08, 0x2748774C, 0x34B0BCB5, 0x391C0CB3, 0x4ED8AA4A, 0x5B9CCA4F, 0x682E6FF3,
    0x748F82EE, 0x78A5636F, 0x84C87814, 0x8CC70208, 0x90BEFFFA, 0xA4506CEB, 0xBEF9A3F7, 0xC67178F2,
)


def rotr(x: int, n: int) -> int:
    return ((x >> n) | (x << (32 - n))) & MASK


def small_sigma0(x: int) -> int:
    return rotr(x, 7) ^ rotr(x, 18) ^ (x >> 3)


def small_sigma1(x: int) -> int:
    return rotr(x, 17) ^ rotr(x, 19) ^ (x >> 10)


def big_sigma0(x: int) -> int:
    return rotr(x, 2) ^ rotr(x, 13) ^ rotr(x, 22)


def big_sigma1(x: int) -> int:
    return rotr(x, 6) ^ rotr(x, 11) ^ rotr(x, 25)


def sha256_round(state: tuple[int, ...], word: int, round_index: int) -> tuple[int, ...]:
    a, b, c, d, e, f, g, h = state
    ch = (e & f) ^ ((~e) & g)
    maj = (a & b) ^ (a & c) ^ (b & c)
    t1 = (h + big_sigma1(e) + ch + K[round_index] + word) & MASK
    t2 = (big_sigma0(a) + maj) & MASK
    return (
        (t1 + t2) & MASK,
        a,
        b,
        c,
        (d + t1) & MASK,
        e,
        f,
        g,
    )


def words_from_block(block: bytes) -> list[int]:
    if len(block) != 64:
        raise ValueError("SHA-256 compression input must be exactly 64 bytes")
    return [int.from_bytes(block[i:i + 4], "big") for i in range(0, 64, 4)]


def expand_schedule(words16: Iterable[int]) -> list[int]:
    w = list(words16)
    if len(w) != 16:
        raise ValueError("Need exactly 16 initial schedule words")
    for i in range(16, 64):
        value = small_sigma1(w[i - 2]) + w[i - 7] + small_sigma0(w[i - 15]) + w[i - 16]
        w.append(value & MASK)
    return w


def compress(state: tuple[int, ...], block: bytes) -> tuple[int, ...]:
    w = expand_schedule(words_from_block(block))
    work = state
    for i in range(64):
        work = sha256_round(work, w[i], i)
    return tuple((state[i] + work[i]) & MASK for i in range(8))


def state_bytes(state: tuple[int, ...]) -> bytes:
    return b"".join(x.to_bytes(4, "big") for x in state)


def sha256d_reference(header80: bytes) -> bytes:
    if len(header80) != 80:
        raise ValueError("Bitcoin block header must be exactly 80 bytes")
    return hashlib.sha256(hashlib.sha256(header80).digest()).digest()


def bitcoin_header_with_nonce(header80: bytes, nonce: int) -> bytes:
    """Insert nonce in serialized Bitcoin header form (4-byte little-endian)."""
    if len(header80) != 80:
        raise ValueError("Bitcoin block header must be exactly 80 bytes")
    if not 0 <= nonce <= 0xFFFFFFFF:
        raise ValueError("nonce must fit in uint32")
    return header80[:76] + nonce.to_bytes(4, "little")


@dataclass(frozen=True)
class PreparedJob:
    original_header: bytes
    midstate: tuple[int, ...]
    second_block_words: tuple[int, ...]  # template with W[3] cleared
    prefix_state_after_round2: tuple[int, ...]
    w16: int
    w17: int


def prepare_job(header80: bytes) -> PreparedJob:
    """Prepare everything independent of nonce for one fixed Bitcoin job."""
    if len(header80) != 80:
        raise ValueError("Bitcoin block header must be exactly 80 bytes")

    # SHA-256(header80): compression of first 64 bytes is the midstate.
    midstate = compress(IV, header80[:64])

    # The second 64-byte SHA-256 block is header[64:80] plus padding.
    second = bytearray(64)
    second[:16] = header80[64:80]
    second[16] = 0x80
    second[56:64] = (80 * 8).to_bytes(8, "big")
    words = words_from_block(bytes(second))

    # Bitcoin nonce lives at header bytes 76..79, i.e. schedule word W[3].
    # Clear it in the job template; the per-nonce path will replace W[3].
    words[3] = 0

    # W[16], W[17] do not depend on W[3]. Precompute them per job.
    w16 = (words[0] + small_sigma0(words[1]) + words[9] + small_sigma1(words[14])) & MASK
    w17 = (words[1] + small_sigma0(words[2]) + words[10] + small_sigma1(words[15])) & MASK

    # Rounds 0, 1, 2 consume only W[0], W[1], W[2], all fixed for this job.
    prefix = midstate
    for r in range(3):
        prefix = sha256_round(prefix, words[r], r)

    return PreparedJob(
        original_header=header80,
        midstate=midstate,
        second_block_words=tuple(words),
        prefix_state_after_round2=prefix,
        w16=w16,
        w17=w17,
    )


def sha256d_precomputed_nonce(job: PreparedJob, nonce: int) -> bytes:
    """Compute standard SHA-256d using job-level precomputation.

    The returned 32 bytes must be identical to hashlib SHA256d. The nonce is
    serialized little-endian in the Bitcoin header, then interpreted as W[3]
    in SHA-256's big-endian word representation.
    """
    if not 0 <= nonce <= 0xFFFFFFFF:
        raise ValueError("nonce must fit in uint32")

    nonce_bytes = nonce.to_bytes(4, "little")
    nonce_word = int.from_bytes(nonce_bytes, "big")

    w = list(job.second_block_words) + [0] * 48
    w[3] = nonce_word
    w[16] = job.w16
    w[17] = job.w17
    for i in range(18, 64):
        value = small_sigma1(w[i - 2]) + w[i - 7] + small_sigma0(w[i - 15]) + w[i - 16]
        w[i] = value & MASK

    # Continue from the precomputed working state after rounds 0..2.
    work = job.prefix_state_after_round2
    for r in range(3, 64):
        work = sha256_round(work, w[r], r)

    inner_state = tuple((job.midstate[i] + work[i]) & MASK for i in range(8))
    inner_digest = state_bytes(inner_state)

    # Outer SHA-256 over the 32-byte inner digest. Its input is nonce-dependent.
    outer_digest = hashlib.sha256(inner_digest).digest()
    return outer_digest


def selftest(random_cases: int = 250, seed: int = 20261102) -> dict:
    rng = random.Random(seed)
    checked = 0

    # Bitcoin genesis block header (serialized 80-byte header).
    genesis_hex = (
        "01000000" + "00" * 32 +
        "3ba3edfd7a7b12b27ac72c3e67768f617fc81bc3888a51323a9fb8aa4b1e5e4a" +
        "29ab5f49ffff001d1dac2b7c"
    )
    genesis = bytes.fromhex(genesis_hex)
    if len(genesis) != 80:
        raise AssertionError(f"Genesis test vector malformed: {len(genesis)} bytes")
    genesis_hash = sha256d_reference(genesis)[::-1].hex()
    expected_genesis_hash = "000000000019d6689c085ae165831e934ff763ae46a2a6c172b3f1b60a8ce26f"
    if genesis_hash != expected_genesis_hash:
        raise AssertionError(f"Genesis vector failed: {genesis_hash}")
    genesis_job = prepare_job(genesis)
    got_genesis = sha256d_precomputed_nonce(genesis_job, 2083236893)[::-1].hex()
    if got_genesis != expected_genesis_hash:
        raise AssertionError(f"Precomputed genesis failed: {got_genesis}")
    checked += 1

    for _ in range(random_cases):
        # Generate a random 76-byte fixed prefix, then test a random nonce.
        header = rng.randbytes(76) + rng.randbytes(4)
        nonce = rng.randrange(0, 1 << 32)
        job = prepare_job(header)
        reference = sha256d_reference(bitcoin_header_with_nonce(header, nonce))
        optimized = sha256d_precomputed_nonce(job, nonce)
        if reference != optimized:
            raise AssertionError(
                f"Mismatch at case {_}: nonce={nonce}, ref={reference.hex()}, opt={optimized.hex()}"
            )
        checked += 1

    return {
        "status": "PASS",
        "vectors_checked": checked,
        "genesis_block_hash": genesis_hash,
        "random_cases": random_cases,
        "seed": seed,
        "comparison": "custom midstate + 3-round prefix + W16/W17 precompute vs hashlib SHA256d",
    }


def analyze() -> dict:
    rounds_per_nonce_baseline = 128  # 64 inner tail + 64 outer
    rounds_precomputed_per_nonce = 3
    remaining_rounds_per_nonce = rounds_per_nonce_baseline - rounds_precomputed_per_nonce
    return {
        "bitcoin_header_bytes": 80,
        "sha256_block_bytes": 64,
        "sha256d_compressions_naive_per_nonce": 3,
        "sha256d_compressions_after_midstate_per_nonce": 2,
        "nonce_location": "header bytes 76..79 -> SHA-256 schedule word W[3] in inner second block",
        "nonce_independent_schedule_words": "W[0..2], W[4..17]",
        "nonce_dependent_schedule_words": "W[3], W[18..63]",
        "nonce_independent_round_prefix": "rounds 0..2 (3 rounds)",
        "extra_static_schedule_precompute": ["W[16]", "W[17]"],
        "compression_rounds_per_nonce_before_prefix_precompute": rounds_per_nonce_baseline,
        "rounds_amortized_per_nonce": rounds_precomputed_per_nonce,
        "compression_rounds_per_nonce_after_prefix_precompute": remaining_rounds_per_nonce,
        "maximum_round-count_reduction": rounds_precomputed_per_nonce / rounds_per_nonce_baseline,
        "idealized_round-count_speedup_ceiling": rounds_per_nonce_baseline / remaining_rounds_per_nonce,
        "warning": "This is an operation-count ceiling, not a measured speedup. Instruction scheduling, SHA-NI mapping, message scheduling, memory traffic and job churn can erase some or all of the gain.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="MULTIMINER X SHA-256d research lab")
    sub = parser.add_subparsers(dest="command", required=True)
    p_test = sub.add_parser("selftest", help="compare precomputed implementation against hashlib")
    p_test.add_argument("--cases", type=int, default=250)
    p_test.add_argument("--seed", type=int, default=20261102)
    sub.add_parser("analyze", help="print the derived operation/dependency model")
    args = parser.parse_args()

    try:
        if args.command == "selftest":
            result = selftest(args.cases, args.seed)
        else:
            result = analyze()
        print(json.dumps(result, indent=2))
        return 0
    except Exception as exc:  # make failures visible and nonzero for scripts/CI
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
