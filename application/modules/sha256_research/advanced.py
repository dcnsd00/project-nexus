"""Resource-bounded advanced SHA-256 reduced-round research.

This module integrates two supplied research ideas:
1) deterministic multi-bit differential hill-climbing with independent holdout;
2) a SAT encoding of reduced-round SHA-256 compression collisions.

The module is research-only. It does not alter SHA-256, Bitcoin consensus, or miners.
"""
from __future__ import annotations

import json
import math
import random
import threading
import time
from collections import Counter
from pathlib import Path
from typing import Iterable, Sequence

from .sha256_core import IV, K, MASK32, compress, expand_schedule, validate_rounds

MAX_SEARCH_STEPS = 120
MAX_SEARCH_SAMPLES = 96
MAX_SEARCH_RESTARTS = 3
MAX_SEARCH_WORK = 1_000_000
MAX_TRACK_SAMPLES = 4096
MAX_SAT_ROUNDS = 24
MAX_SAT_VARIABLES = 60_000
MAX_SAT_CLAUSES = 300_000


def _validate_delta(delta_words: Sequence[int]) -> list[int]:
    if not isinstance(delta_words, (list, tuple)) or len(delta_words) != 16:
        raise ValueError("delta_words trebuie să conțină exact 16 cuvinte.")
    if any(isinstance(x, bool) or not isinstance(x, int) or not 0 <= x <= MASK32 for x in delta_words):
        raise ValueError("Fiecare cuvânt delta trebuie să fie unsigned pe 32 de biți.")
    result = list(delta_words)
    if not any(result):
        raise ValueError("Diferența XOR nu poate fi zero.")
    return result


def _trace_internal_states(block_words: Sequence[int], rounds: int) -> list[tuple[int, ...]]:
    """Return initial state and internal states after each round, without feed-forward."""
    validate_rounds(rounds)
    schedule = expand_schedule(block_words)
    a, b, c, d, e, f, g, h = IV
    states: list[tuple[int, ...]] = [(a, b, c, d, e, f, g, h)]
    for t in range(rounds):
        big1 = (((e >> 6) | (e << 26)) & MASK32) ^ (((e >> 11) | (e << 21)) & MASK32) ^ (((e >> 25) | (e << 7)) & MASK32)
        ch = (e & f) ^ ((~e) & g)
        t1 = (h + big1 + ch + K[t] + schedule[t]) & MASK32
        big0 = (((a >> 2) | (a << 30)) & MASK32) ^ (((a >> 13) | (a << 19)) & MASK32) ^ (((a >> 22) | (a << 10)) & MASK32)
        maj = (a & b) ^ (a & c) ^ (b & c)
        t2 = (big0 + maj) & MASK32
        h, g, f, e, d, c, b, a = g, f, e, (d + t1) & MASK32, c, b, a, (t1 + t2) & MASK32
        states.append((a, b, c, d, e, f, g, h))
    return states


def _state_difference_words(left: Sequence[int], right: Sequence[int]) -> tuple[int, ...]:
    return tuple((a ^ b) & MASK32 for a, b in zip(left, right))


def _hamming_words(words: Sequence[int]) -> int:
    return sum(int(x).bit_count() for x in words)


def _build_blocks(samples: int, seed: int) -> list[list[int]]:
    rng = random.Random(seed)
    return [[rng.getrandbits(32) for _ in range(16)] for _ in range(samples)]


def _per_round_profile(delta: Sequence[int], rounds: int, blocks: Sequence[Sequence[int]]) -> list[dict]:
    weights = [0] * (rounds + 1)
    top_differences = [Counter() for _ in range(rounds + 1)]
    for block in blocks:
        altered = [word ^ mask for word, mask in zip(block, delta)]
        base_trace = _trace_internal_states(block, rounds)
        alt_trace = _trace_internal_states(altered, rounds)
        for r, (base_state, alt_state) in enumerate(zip(base_trace, alt_trace)):
            diff = _state_difference_words(base_state, alt_state)
            weights[r] += _hamming_words(diff)
            top_differences[r][diff] += 1
    n = len(blocks)
    out = []
    for r in range(rounds + 1):
        mode_count = top_differences[r].most_common(1)[0][1]
        out.append({
            "round": r,
            "mean_state_difference_bits": weights[r] / n,
            "modal_full_state_difference_count": mode_count,
            "modal_full_state_difference_frequency": mode_count / n,
            "distinct_full_state_differences": len(top_differences[r]),
        })
    return out


def _first_affected_round(delta: Sequence[int]) -> int:
    active = [i for i, mask in enumerate(delta) if mask]
    return min(active) + 1 if active else 1


def _objective(delta: Sequence[int], rounds: int, blocks: Sequence[Sequence[int]]) -> float:
    """Average state-difference weight only after the earliest input word is consumed.

    This prevents the search from winning trivially by moving a difference to a later
    input word and counting the preceding zero-effect rounds as a low-diffusion path.
    """
    first_round = _first_affected_round(delta)
    if first_round > rounds:
        return math.inf
    total = 0
    count = 0
    for block in blocks:
        altered = [word ^ mask for word, mask in zip(block, delta)]
        base_trace = _trace_internal_states(block, rounds)
        alt_trace = _trace_internal_states(altered, rounds)
        for r in range(first_round, rounds + 1):
            total += _hamming_words(_state_difference_words(base_trace[r], alt_trace[r]))
            count += 1
    return total / max(1, count)


def _sparse_delta(rng: random.Random, allowed_words: Sequence[int]) -> list[int]:
    delta = [0] * 16
    delta[rng.choice(list(allowed_words))] = 1 << rng.randrange(32)
    return delta


def _mutate_delta(delta: Sequence[int], rng: random.Random, allowed_words: Sequence[int]) -> list[int]:
    candidate = list(delta)
    flips = 1 + (1 if rng.random() < 0.30 else 0) + (1 if rng.random() < 0.08 else 0)
    for _ in range(flips):
        candidate[rng.choice(list(allowed_words))] ^= 1 << rng.randrange(32)
    if not any(candidate):
        candidate[rng.choice(list(allowed_words))] = 1 << rng.randrange(32)
    return candidate


def track_differential(delta_words: Sequence[int], rounds: int = 20,
                       samples: int = 256, seed: int = 1) -> dict:
    validate_rounds(rounds)
    delta = _validate_delta(delta_words)
    if isinstance(samples, bool) or not isinstance(samples, int) or not 16 <= samples <= MAX_TRACK_SAMPLES:
        raise ValueError(f"samples trebuie să fie între 16 și {MAX_TRACK_SAMPLES}.")
    if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed < 2**64:
        raise ValueError("seed trebuie să fie unsigned pe 64 de biți.")
    t0 = time.perf_counter()
    profile = _per_round_profile(delta, rounds, _build_blocks(samples, seed))
    return {
        "experiment": "reduced_round_sha256_internal_state_differential_track",
        "rounds": rounds,
        "first_affected_round": _first_affected_round(delta),
        "samples": samples,
        "seed": seed,
        "delta_words_hex": [f"0x{x:08x}" for x in delta],
        "active_words": [i for i, x in enumerate(delta) if x],
        "active_bit_count": sum(x.bit_count() for x in delta),
        "per_round": profile,
        "elapsed_seconds": time.perf_counter() - t0,
        "interpretation": (
            "Frecvența modului este doar frecvența empirică a celei mai comune diferențe complete "
            "în eșantion; NU este probabilitatea unei căi diferențiale și NU se înmulțesc frecvențele pe runde."
        ),
        "consensus_compatible": False,
    }


def search_differential(rounds: int = 20, steps: int = 80, samples: int = 24,
                        restarts: int = 2, validation_samples: int = 128,
                        seed: int = 20261109, allowed_words: Sequence[int] = (14, 15)) -> dict:
    """Deterministic common-sample hill-climb + independent holdout validation."""
    validate_rounds(rounds)
    for name, value, low, high in (
        ("steps", steps, 1, MAX_SEARCH_STEPS),
        ("samples", samples, 8, MAX_SEARCH_SAMPLES),
        ("restarts", restarts, 1, MAX_SEARCH_RESTARTS),
        ("validation_samples", validation_samples, 16, 1024),
    ):
        if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
            raise ValueError(f"{name} trebuie să fie între {low} și {high}.")
    if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed < 2**64:
        raise ValueError("seed trebuie să fie unsigned pe 64 de biți.")
    if not isinstance(allowed_words, (list, tuple)) or not allowed_words:
        raise ValueError("allowed_words trebuie să conțină cel puțin un index W0–W15.")
    normalized_words = sorted(set(allowed_words))
    if any(isinstance(w, bool) or not isinstance(w, int) or not 0 <= w < 16 for w in normalized_words):
        raise ValueError("allowed_words acceptă numai indecși între 0 și 15.")
    if rounds < max(normalized_words) + 1:
        raise ValueError("Numărul de runde trebuie să includă consumarea tuturor cuvintelor permise.")
    work_units = steps * samples * rounds * restarts * 2
    if work_units > MAX_SEARCH_WORK:
        raise ValueError(f"Bugetul depășește limita locală ({work_units:,} > {MAX_SEARCH_WORK:,} unități). Redu pașii, probele sau rundele.")

    t0 = time.perf_counter()
    rng = random.Random(seed)
    training_blocks = _build_blocks(samples, seed ^ 0x4E45585553)
    global_best: list[int] | None = None
    global_cost = math.inf
    restart_summaries = []
    accepted_improvements = 0

    for restart in range(restarts):
        current = _sparse_delta(rng, normalized_words)
        current_cost = _objective(current, rounds, training_blocks)
        restart_start = current_cost
        for _ in range(steps):
            candidate = _mutate_delta(current, rng, normalized_words)
            candidate_cost = _objective(candidate, rounds, training_blocks)
            if candidate_cost < current_cost:
                current, current_cost = candidate, candidate_cost
                accepted_improvements += 1
        restart_summaries.append({
            "restart": restart + 1,
            "starting_objective": restart_start,
            "best_training_objective": current_cost,
            "active_bit_count": sum(x.bit_count() for x in current),
        })
        if current_cost < global_cost:
            global_best, global_cost = list(current), current_cost

    assert global_best is not None
    validation_seed = (seed + 0x9E3779B97F4A7C15) % (2**64)
    validation_blocks = _build_blocks(validation_samples, validation_seed)
    validation_profile = _per_round_profile(global_best, rounds, validation_blocks)
    first_active_round = _first_affected_round(global_best)
    validation_cost = sum(x["mean_state_difference_bits"] for x in validation_profile[first_active_round:]) / (rounds - first_active_round + 1)
    baseline_rng = random.Random(seed ^ 0xB45311E)
    first_word = min(i for i, mask in enumerate(global_best) if mask)
    baseline_delta = [0] * 16
    baseline_delta[first_word] = 1 << baseline_rng.randrange(32)
    baseline_profile = _per_round_profile(baseline_delta, rounds, validation_blocks)
    active_start = _first_affected_round(global_best)
    baseline_validation_cost = sum(x["mean_state_difference_bits"] for x in baseline_profile[active_start:]) / (rounds - active_start + 1)
    improvement = baseline_validation_cost - validation_cost
    return {
        "experiment": "reduced_round_sha256_multibit_differential_hill_climb",
        "rounds": rounds,
        "search_steps_per_restart": steps,
        "search_samples": samples,
        "restarts": restarts,
        "validation_samples": validation_samples,
        "seed": seed,
        "validation_seed": validation_seed,
        "work_units": work_units,
        "candidate_delta_words_hex": [f"0x{x:08x}" for x in global_best],
        "candidate_active_words": [i for i, x in enumerate(global_best) if x],
        "candidate_active_bit_count": sum(x.bit_count() for x in global_best),
        "allowed_input_words": normalized_words,
        "first_affected_round": first_active_round,
        "objective_scope": "mean internal-state difference from first affected round onward; zero-effect prefix rounds excluded",
        "training_objective_mean_internal_state_difference_bits": global_cost,
        "validation_objective_mean_internal_state_difference_bits": validation_cost,
        "random_single_bit_baseline_validation_objective": baseline_validation_cost,
        "holdout_improvement_vs_random_single_bit": improvement,
        "holdout_improved": improvement > 0,
        "accepted_improvements": accepted_improvements,
        "restart_summaries": restart_summaries,
        "validation_profile": validation_profile,
        "baseline_validation_profile": baseline_profile,
        "elapsed_seconds": time.perf_counter() - t0,
        "methodology": "Toți candidații din căutare sunt evaluați pe aceleași blocuri (common random numbers); candidatul final este evaluat pe un set independent cu seed separat.",
        "limitations": [
            "Hill-climbing este euristic și nu garantează optimul global.",
            "Căutarea este limitată la cuvintele de intrare permise; runda de activare este raportată, iar prefixul fără efect este exclus din obiectiv.",
            "Obiectivul măsoară greutatea Hamming a stării interne fără feed-forward, nu o scurtătură pentru SHA-256 standard.",
            "Frecvența diferenței modale este descriptivă și nu este probabilitate de cale.",
            "Variantele reduse la 1–63 runde nu sunt compatibile cu consensul sau mining-ul real.",
        ],
        "consensus_compatible": False,
    }


# -------------------- SAT encoding --------------------

class CNFBuilder:
    """Tseitin CNF builder; bit vectors are stored LSB-first."""
    def __init__(self) -> None:
        self.nvars = 0
        self.clauses: list[list[int]] = []
        self.true_lit = self.new_var()
        self.clauses.append([self.true_lit])
        self.false_lit = -self.true_lit

    def new_var(self) -> int:
        self.nvars += 1
        return self.nvars

    def const_word(self, value: int) -> list[int]:
        if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= MASK32:
            raise ValueError("constant word must be unsigned 32-bit")
        return [self.true_lit if (value >> bit) & 1 else self.false_lit for bit in range(32)]

    def xor2(self, a: int, b: int) -> int:
        c = self.new_var()
        self.clauses.extend(([-a, -b, -c], [a, b, -c], [a, -b, c], [-a, b, c]))
        return c

    def xor3(self, a: int, b: int, c: int) -> int:
        return self.xor2(self.xor2(a, b), c)

    def ch(self, e: int, f: int, g: int) -> int:
        out = self.new_var()
        # out = e ? f : g
        self.clauses.extend(([-e, -f, out], [-e, f, -out], [e, -g, out], [e, g, -out]))
        return out

    def maj(self, a: int, b: int, c: int) -> int:
        out = self.new_var()
        self.clauses.extend(([-a, -b, out], [-a, -c, out], [-b, -c, out],
                             [a, b, -out], [a, c, -out], [b, c, -out]))
        return out

    def add32(self, x: Sequence[int], y: Sequence[int]) -> list[int]:
        carry = self.false_lit
        out = []
        for i in range(32):
            out.append(self.xor3(x[i], y[i], carry))
            if i < 31:
                carry = self.maj(x[i], y[i], carry)
        return out

    def xor_vectors(self, *vectors: Sequence[int]) -> list[int]:
        result = list(vectors[0])
        for vector in vectors[1:]:
            result = [self.xor2(a, b) for a, b in zip(result, vector)]
        return result

    def xor3_vectors(self, a: Sequence[int], b: Sequence[int], c: Sequence[int]) -> list[int]:
        return [self.xor3(x, y, z) for x, y, z in zip(a, b, c)]

    def equal(self, a: int, b: int) -> None:
        self.clauses.extend(([-a, b], [a, -b]))


def _rot_right_vector(vector: Sequence[int], amount: int) -> list[int]:
    return [vector[(i + amount) % 32] for i in range(32)]


def _shift_right_vector(vector: Sequence[int], amount: int, fill: int) -> list[int]:
    return [vector[i + amount] if i + amount < 32 else fill for i in range(32)]


def _build_cnf_compression(builder: CNFBuilder, block: Sequence[Sequence[int]], rounds: int) -> list[list[int]]:
    validate_rounds(rounds)
    words = list(block)
    for t in range(16, rounds):
        s0 = builder.xor3_vectors(
            _rot_right_vector(words[t - 15], 7),
            _rot_right_vector(words[t - 15], 18),
            _shift_right_vector(words[t - 15], 3, builder.false_lit),
        )
        s1 = builder.xor3_vectors(
            _rot_right_vector(words[t - 2], 17),
            _rot_right_vector(words[t - 2], 19),
            _shift_right_vector(words[t - 2], 10, builder.false_lit),
        )
        value = builder.add32(words[t - 16], s0)
        value = builder.add32(value, words[t - 7])
        value = builder.add32(value, s1)
        words.append(value)

    a, b, c, d, e, f, g, h = [builder.const_word(value) for value in IV]
    for t in range(rounds):
        big1 = builder.xor3_vectors(_rot_right_vector(e, 6), _rot_right_vector(e, 11), _rot_right_vector(e, 25))
        choose = [builder.ch(e[i], f[i], g[i]) for i in range(32)]
        t1 = builder.add32(h, big1)
        t1 = builder.add32(t1, choose)
        t1 = builder.add32(t1, builder.const_word(K[t]))
        t1 = builder.add32(t1, words[t])
        big0 = builder.xor3_vectors(_rot_right_vector(a, 2), _rot_right_vector(a, 13), _rot_right_vector(a, 22))
        majority = [builder.maj(a[i], b[i], c[i]) for i in range(32)]
        t2 = builder.add32(big0, majority)
        h, g, f, e, d, c, b, a = g, f, e, builder.add32(d, t1), c, b, a, builder.add32(t1, t2)
    return [builder.add32(builder.const_word(iv), state) for iv, state in zip(IV, (a, b, c, d, e, f, g, h))]


def output_prefix_msb_first(words: Sequence[Sequence[int]], bits: int) -> list[int]:
    """Flatten SHA output in byte/word order, MSB first, for prefix-bit equality."""
    if isinstance(bits, bool) or not isinstance(bits, int) or not 1 <= bits <= 256:
        raise ValueError("bits trebuie să fie între 1 și 256.")
    flattened = [literal for word in words for literal in reversed(word)]
    return flattened[:bits]


def build_collision_cnf(rounds: int, bits: int, delta_words: Sequence[int] | None = None):
    if isinstance(rounds, bool) or not isinstance(rounds, int) or not 1 <= rounds <= MAX_SAT_ROUNDS:
        raise ValueError(f"SAT este limitat local la 1–{MAX_SAT_ROUNDS} runde reduse.")
    if isinstance(bits, bool) or not isinstance(bits, int) or not 1 <= bits <= 256:
        raise ValueError("bits trebuie să fie între 1 și 256.")
    fixed_delta = _validate_delta(delta_words) if delta_words is not None else None
    builder = CNFBuilder()
    message_a = [[builder.new_var() for _ in range(32)] for _ in range(16)]
    if fixed_delta is None:
        delta = [[builder.new_var() for _ in range(32)] for _ in range(16)]
        builder.clauses.append([literal for word in delta for literal in word])  # delta != 0
    else:
        delta = [builder.const_word(value) for value in fixed_delta]
    message_b = [[builder.xor2(a, d) for a, d in zip(wa, wd)] for wa, wd in zip(message_a, delta)]
    out_a = _build_cnf_compression(builder, message_a, rounds)
    out_b = _build_cnf_compression(builder, message_b, rounds)
    flat_a = output_prefix_msb_first(out_a, bits)
    flat_b = output_prefix_msb_first(out_b, bits)
    for a, b in zip(flat_a, flat_b):
        builder.equal(a, b)
    return builder, message_a, delta


def _assign_once(assign: dict[int, bool], queue: list[int], variable: int, value: bool) -> None:
    previous = assign.get(variable)
    if previous is not None:
        if previous != value:
            raise RuntimeError("conflict in SAT circuit unit propagation")
        return
    assign[variable] = value
    queue.append(variable)


def unit_propagate(builder: CNFBuilder, assign: dict[int, bool]) -> dict[int, bool]:
    occurrences: dict[int, list[int]] = {}
    for clause_index, clause in enumerate(builder.clauses):
        for literal in clause:
            occurrences.setdefault(abs(literal), []).append(clause_index)
    queue = list(assign)
    for clause in builder.clauses:
        if len(clause) == 1:
            literal = clause[0]
            _assign_once(assign, queue, abs(literal), literal > 0)
    while queue:
        variable = queue.pop()
        for clause_index in occurrences.get(variable, []):
            clause = builder.clauses[clause_index]
            satisfied = False
            free: list[int] = []
            for literal in clause:
                value = assign.get(abs(literal))
                if value is None:
                    free.append(literal)
                elif value == (literal > 0):
                    satisfied = True
                    break
            if satisfied:
                continue
            if not free:
                raise RuntimeError("conflict in SAT circuit unit propagation")
            if len(free) == 1:
                literal = free[0]
                _assign_once(assign, queue, abs(literal), literal > 0)
    return assign


def _literal_value(assign: dict[int, bool], literal: int) -> bool:
    value = assign.get(abs(literal))
    if value is None:
        raise RuntimeError(f"unassigned literal {literal} after unit propagation")
    return value == (literal > 0)


def _vector_value(assign: dict[int, bool], vector: Sequence[int]) -> int:
    return sum(1 << bit for bit, literal in enumerate(vector) if _literal_value(assign, literal))


def sat_selfcheck(rounds: int = 12, seed: int = 1234) -> dict:
    if isinstance(rounds, bool) or not isinstance(rounds, int) or not 1 <= rounds <= MAX_SAT_ROUNDS:
        raise ValueError(f"Self-check SAT limitat la 1–{MAX_SAT_ROUNDS} runde.")
    rng = random.Random(seed)
    builder = CNFBuilder()
    block = [[builder.new_var() for _ in range(32)] for _ in range(16)]
    outputs = _build_cnf_compression(builder, block, rounds)
    message = [rng.getrandbits(32) for _ in range(16)]
    assignment = {builder.true_lit: True}
    for vector, value in zip(block, message):
        for bit, literal in enumerate(vector):
            assignment[literal] = bool((value >> bit) & 1)
    unit_propagate(builder, assignment)
    observed = [_vector_value(assignment, vector) for vector in outputs]
    expected = compress(message, rounds)
    passed = observed == expected
    return {
        "rounds": rounds,
        "seed": seed,
        "variables": builder.nvars,
        "clauses": len(builder.clauses),
        "encoding_matches_reference": passed,
        "digest_hex": "".join(f"{word:08x}" for word in observed),
        "reference_digest_hex": "".join(f"{word:08x}" for word in expected),
        "consensus_compatible": False,
    }


def solve_reduced_collision(rounds: int = 12, bits: int = 32, timeout_seconds: int = 15,
                            delta_words: Sequence[int] | None = None) -> dict:
    if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, int) or not 1 <= timeout_seconds <= 30:
        raise ValueError("timeout_seconds trebuie să fie între 1 și 30.")
    try:
        from pysat.solvers import Glucose4
    except ImportError as exc:
        raise RuntimeError("Solverul opțional lipsește. Instalează requirements-research.txt sau exportă DIMACS.") from exc

    t0 = time.perf_counter()
    builder, message_a_vars, delta_vars = build_collision_cnf(rounds, bits, delta_words)
    if builder.nvars > MAX_SAT_VARIABLES or len(builder.clauses) > MAX_SAT_CLAUSES:
        raise ValueError("Formula depășește limita locală de resurse NEXUS.")
    solver = Glucose4(bootstrap_with=builder.clauses)
    timer = threading.Timer(timeout_seconds, solver.interrupt)
    timer.daemon = True
    timer.start()
    try:
        status = solver.solve_limited(expect_interrupt=True)
    finally:
        timer.cancel()
    elapsed = time.perf_counter() - t0
    if status is None:
        solver.delete()
        return {"status": "timeout", "rounds": rounds, "output_prefix_bits": bits,
                "variables": builder.nvars, "clauses": len(builder.clauses),
                "elapsed_seconds": elapsed, "interpretation": "Nedecis în timpul alocat; nu este dovadă de nesatisfiabilitate."}
    if status is False:
        solver.delete()
        return {"status": "unsat", "rounds": rounds, "output_prefix_bits": bits,
                "variables": builder.nvars, "clauses": len(builder.clauses),
                "elapsed_seconds": elapsed, "interpretation": "Solverul a demonstrat că formula cu aceste limite este nesatisfiabilă."}

    positive_model = {literal for literal in solver.get_model() if literal > 0}
    assignment = {variable: variable in positive_model for variable in range(1, builder.nvars + 1)}
    message_a = [_vector_value(assignment, vector) for vector in message_a_vars]
    if delta_words is None:
        delta = [_vector_value(assignment, vector) for vector in delta_vars]
    else:
        delta = list(delta_words)
    message_b = [a ^ d for a, d in zip(message_a, delta)]
    out_a = compress(message_a, rounds)
    out_b = compress(message_b, rounds)
    diff = 0
    for a, b in zip(out_a, out_b):
        diff = (diff << 32) | (a ^ b)
    prefix_matches = (diff >> (256 - bits)) == 0
    delta_nonzero = any(delta)
    verified = prefix_matches and delta_nonzero
    solver.delete()
    return {
        "status": "sat_verified" if verified else "verification_failed",
        "rounds": rounds,
        "output_prefix_bits": bits,
        "variables": builder.nvars,
        "clauses": len(builder.clauses),
        "elapsed_seconds": elapsed,
        "message_a_words_hex": [f"0x{x:08x}" for x in message_a],
        "delta_words_hex": [f"0x{x:08x}" for x in delta],
        "message_b_words_hex": [f"0x{x:08x}" for x in message_b],
        "output_a_hex": "".join(f"{x:08x}" for x in out_a),
        "output_b_hex": "".join(f"{x:08x}" for x in out_b),
        "output_xor_hex": f"{diff:064x}",
        "independent_reference_verification": verified,
        "consensus_compatible": False,
        "interpretation": "Soluție verificată independent pentru funcția de compresie cu runde reduse; nu este coliziune SHA-256 standard și nu este un rezultat de mining.",
    }


def export_dimacs(rounds: int = 12, bits: int = 32,
                  results_dir: str | Path | None = None,
                  delta_words: Sequence[int] | None = None) -> dict:
    builder, _, _ = build_collision_cnf(rounds, bits, delta_words)
    if builder.nvars > MAX_SAT_VARIABLES or len(builder.clauses) > MAX_SAT_CLAUSES:
        raise ValueError("Formula depășește limita locală de resurse NEXUS.")
    target_dir = Path(results_dir) if results_dir else Path(__file__).with_name("results")
    target_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%dT%H%M%S", time.gmtime())
    path = target_dir / f"sha256_reduced_{rounds}r_{bits}b_{stamp}_{random.SystemRandom().randrange(1_000_000):06d}.cnf"
    with path.open("w", encoding="ascii", newline="\n") as handle:
        handle.write(f"p cnf {builder.nvars} {len(builder.clauses)}\n")
        for clause in builder.clauses:
            handle.write(" ".join(map(str, clause)) + " 0\n")
    return {"rounds": rounds, "output_prefix_bits": bits, "variables": builder.nvars,
            "clauses": len(builder.clauses), "path": str(path), "format": "DIMACS CNF",
            "consensus_compatible": False}


def advanced_research_info() -> dict:
    return {
        "module": "NEXUS Advanced SHA-256 Research",
        "differential_search": {
            "method": "bounded multi-bit hill-climbing with common random training blocks, allowed input-word range and independent holdout",
            "default_allowed_words": [14, 15],
            "objective": "mean state-difference Hamming weight after first affected round; zero-effect prefix excluded",
            "max_steps": MAX_SEARCH_STEPS,
            "max_samples": MAX_SEARCH_SAMPLES,
            "max_restarts": MAX_SEARCH_RESTARTS,
            "max_work_units": MAX_SEARCH_WORK,
            "meaning": "internal state Hamming-weight trajectory without feed-forward",
        },
        "sat_solver": {
            "method": "Tseitin CNF encoding of reduced-round compression with nonzero XOR delta",
            "max_rounds": MAX_SAT_ROUNDS,
            "max_variables": MAX_SAT_VARIABLES,
            "max_clauses": MAX_SAT_CLAUSES,
            "optional_dependency": "python-sat",
            "available": _pysat_available(),
            "dimacs_export_available": True,
            "output_prefix_order": "first N bits of the 256-bit digest in big-endian order",
        },
        "guardrails": [
            "Research-only reduced-round SHA-256; full SHA-256 remains 64 rounds.",
            "No reduced-round result is sent to miners or treated as consensus-compatible.",
            "No unbounded solver/search jobs; each operation has explicit CPU/work limits.",
            "SAT models are independently checked with the reference compressor before reporting success.",
        ],
    }


def _pysat_available() -> bool:
    try:
        import pysat  # noqa: F401
        return True
    except ImportError:
        return False
