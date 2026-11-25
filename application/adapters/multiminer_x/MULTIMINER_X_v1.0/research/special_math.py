"""Statistical cryptographic diagnostics for public hash functions.
These tests characterize outputs; they do not invert, decrypt, or weaken hashes.
"""
from __future__ import annotations
import hashlib, math, random
HASHES={'SHA-256':hashlib.sha256,'SHA-512':hashlib.sha512,'SHA3-256':hashlib.sha3_256}

def hamming_distance(a: bytes,b: bytes) -> int:
    if len(a)!=len(b): raise ValueError('Inputs must have equal length')
    return sum((x^y).bit_count() for x,y in zip(a,b))

def avalanche_experiment(algorithm: str='SHA-256', input_bytes: int=32,
                         trials: int=1000, seed: int=20261107) -> dict:
    if algorithm not in HASHES: raise ValueError('Unsupported algorithm')
    if not 1<=input_bytes<=4096 or not 10<=trials<=100_000: raise ValueError('Invalid experiment size')
    rng=random.Random(seed); fn=HASHES[algorithm]; digest_bits=fn().digest_size*8
    distances=[]
    for _ in range(trials):
        src=bytes(rng.getrandbits(8) for _ in range(input_bytes))
        bit=rng.randrange(input_bytes*8)
        changed=bytearray(src); changed[bit//8]^=1<<(bit%8)
        distances.append(hamming_distance(fn(src).digest(),fn(bytes(changed)).digest()))
    mean=sum(distances)/trials
    expected=digest_bits/2
    # A one-bit input perturbation should flip roughly half the digest bits.
    # Binomial approximation to aggregate changed output bits.
    z=(mean-expected)/math.sqrt(digest_bits/(4*trials))
    return {'algorithm':algorithm,'input_bytes':input_bytes,'trials':trials,'seed':seed,
            'digest_bits':digest_bits,'mean_changed_bits':mean,'expected_mean':expected,
            'z_score_vs_half_bits':z,'min_changed_bits':min(distances),
            'max_changed_bits':max(distances),
            'interpretation':'Avalanche diagnostic only; finite sample, not a proof of security or a preimage/collision attack.'}

# Research directions: each remains a hypothesis until formalized and independently reviewed.
HYPOTHESES = {
 'chaotic_nonce_ordering': 'May alter search order but cannot improve expected success probability for uniform independent nonce space.',
 'spectral_bias_scan': 'Search output bit sequences for statistically significant bias; correct for multiple testing.',
 'reduced_round_sat_smt': 'Use SAT/SMT only on reduced-round toy instances to study constraints; no claim about full SHA.',
 'modular_differential_trails': 'Analyze modular-addition differential propagation; must be checked against exact round equations.',
 'gpu_occupancy_autotuning': 'Empirically optimize batch size/register pressure; hardware-specific, benchmark only.',
 'p_adic_or_non_archimedean_models': 'Exploratory mathematical representation; no known route to invert standard SHA-256/512.'
}
