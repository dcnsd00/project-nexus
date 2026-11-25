"""Reproducible paired-difference experiments for reduced-round SHA-256."""
from __future__ import annotations
import math
import secrets
import time
from collections import Counter
from random import Random
from typing import Iterable

from .sha256_core import compress_schedule, compress_schedule_with_round_carries, expand_schedule_with_carries, verify_against_hashlib

OUTPUT_BITS = 256
MAX_SAMPLES = 20_000
MAX_SWEEP_ROUNDS = 29


def research_info() -> dict:
    return {
        "module": "NEXUS SHA-256 Differential Research Lab",
        "standard_sha256_rounds": 64,
        "allowed_research_rounds": [1, 64],
        "default_samples": 2000,
        "max_samples_per_request": MAX_SAMPLES,
        "output_bits_tested_per_delta": OUTPUT_BITS,
        "method": "paired random 512-bit message blocks; XOR input delta; compare 256-bit compression outputs; inspect W0-W63 schedule and schedule expansion carries",
        "multi_bit_presets": ["single bit", "adjacent pair", "separated pair", "four-bit mask", "cross-word pair", "cross-word triplet"],
        "statistical_control": "exact two-sided binomial p-value for maximum-deviation output bit; Bonferroni correction across all tested output bits and sweep configurations",
        "important_limit": "Reduced-round outputs are non-standard research variants; findings do not imply a weakness in full 64-round SHA-256 or a pool-compatible mining optimization.",
        "hashlib_validation": verify_against_hashlib(),
    }


def _wilson_interval(successes: int, n: int, z: float = 1.959963984540054) -> list[float]:
    phat = successes / n
    den = 1 + z * z / n
    center = (phat + z * z / (2 * n)) / den
    margin = z * math.sqrt((phat * (1 - phat) / n) + (z * z / (4 * n * n))) / den
    return [max(0.0, center - margin), min(1.0, center + margin)]


def _binomial_two_sided_log10(successes: int, n: int) -> float:
    """Exact symmetric two-sided binomial p-value in log10 space.

    Uses doubled lower tail for p=0.5, avoiding floating-point underflow.
    """
    k = min(successes, n - successes)
    log_term = -n * math.log(2.0)  # P(X=0)
    max_log = log_term
    scaled_sum = 1.0
    for j in range(1, k + 1):
        log_term += math.log(n - j + 1) - math.log(j)
        if log_term > max_log:
            scaled_sum = scaled_sum * math.exp(max_log - log_term) + 1.0
            max_log = log_term
        else:
            scaled_sum += math.exp(log_term - max_log)
    log_tail = max_log + math.log(scaled_sum)
    log_p = min(0.0, math.log(2.0) + log_tail)
    return log_p / math.log(10.0)


def _p_two_sided_normal(z: float) -> float:
    return math.erfc(abs(z) / math.sqrt(2.0))


def _p_from_log10(log10_p: float) -> float:
    return 0.0 if log10_p < -323.0 else min(1.0, 10.0 ** log10_p)


def run_differential(rounds: int, samples: int = 2000, word: int = 14,
                     input_bit: int = 0, seed: int | None = None,
                     family_size: int = OUTPUT_BITS,
                     delta_words: list[int] | None = None,
                     delta_name: str | None = None) -> dict:
    if isinstance(rounds, bool) or not isinstance(rounds, int) or not 1 <= rounds <= 64:
        raise ValueError("Runda trebuie să fie între 1 și 64.")
    if isinstance(samples, bool) or not isinstance(samples, int) or not 100 <= samples <= MAX_SAMPLES:
        raise ValueError(f"Numărul de probe trebuie să fie între 100 și {MAX_SAMPLES}.")
    if isinstance(word, bool) or not isinstance(word, int) or not 0 <= word < 16:
        raise ValueError("Cuvântul de intrare trebuie să fie între 0 și 15.")
    if isinstance(input_bit, bool) or not isinstance(input_bit, int) or not 0 <= input_bit < 32:
        raise ValueError("Bitul de intrare trebuie să fie între 0 și 31.")
    if isinstance(family_size, bool) or not isinstance(family_size, int) or family_size < OUTPUT_BITS:
        raise ValueError("family_size must be at least 256")

    actual_seed = seed if seed is not None else secrets.randbits(64)
    if isinstance(actual_seed, bool) or not isinstance(actual_seed, int) or not 0 <= actual_seed < 2**64:
        raise ValueError("Seed-ul trebuie să fie un întreg pe 64 de biți.")
    rng = Random(actual_seed)
    if delta_words is None:
        delta = [0] * 16
        delta[word] = 1 << input_bit
        delta_name = delta_name or f"W{word}_bit{input_bit}"
    else:
        if not isinstance(delta_words, (list, tuple)) or len(delta_words) != 16:
            raise ValueError("delta_words trebuie să conțină exact 16 măști XOR.")
        if any(isinstance(x, bool) or not isinstance(x, int) or not 0 <= x <= 0xFFFFFFFF for x in delta_words):
            raise ValueError("Fiecare mască XOR trebuie să fie un întreg unsigned pe 32 de biți.")
        delta = list(delta_words)
        if not any(delta):
            raise ValueError("Diferența XOR nu poate fi zero.")
        delta_name = delta_name or "custom_multi_bit_delta"
    active_words = [i for i, mask in enumerate(delta) if mask]
    flips = [0] * OUTPUT_BITS
    full_diffs: Counter[int] = Counter()
    total_hamming = 0
    zero_diffs = 0
    schedule_changed_counts = [0] * 64
    schedule_hamming_totals = [0] * 64
    carry_stage_mismatches = [0, 0, 0]
    start = time.perf_counter()

    for _ in range(samples):
        block = [rng.getrandbits(32) for _ in range(16)]
        altered_block = [x ^ d for x, d in zip(block, delta)]
        base_schedule, base_carries = expand_schedule_with_carries(block)
        alt_schedule, alt_carries = expand_schedule_with_carries(altered_block)
        baseline = compress_schedule(base_schedule, rounds)
        altered = compress_schedule(alt_schedule, rounds)
        for t, (base_word, alt_word) in enumerate(zip(base_schedule, alt_schedule)):
            word_diff = base_word ^ alt_word
            schedule_hamming_totals[t] += word_diff.bit_count()
            if word_diff:
                schedule_changed_counts[t] += 1
            if t >= 16:
                for stage in range(3):
                    carry_stage_mismatches[stage] += base_carries[t][stage] != alt_carries[t][stage]
        diff = 0
        for x, y in zip(baseline, altered):
            word_diff = x ^ y
            diff = (diff << 32) | word_diff
            total_hamming += word_diff.bit_count()
        if diff == 0:
            zero_diffs += 1
        full_diffs[diff] += 1
        for i in range(OUTPUT_BITS):
            flips[i] += (diff >> i) & 1

    elapsed = max(time.perf_counter() - start, 1e-9)
    ranked = []
    for i, successes in enumerate(flips):
        rate = successes / samples
        z = abs(rate - 0.5) / (0.5 / math.sqrt(samples))
        p_raw = _p_two_sided_normal(z)
        ranked.append({
            "output_bit_lsb_index": i,
            "flips": successes,
            "flip_rate": rate,
            "z_score": z,
            "p_raw_normal_approx": p_raw,
            "p_bonferroni": min(1.0, p_raw * family_size),
            "wilson_95_ci": _wilson_interval(successes, samples),
        })
    ranked.sort(key=lambda x: x["z_score"], reverse=True)
    no_effect = zero_diffs == samples
    if no_effect:
        # The chosen input word has not affected any output in the tested rounds.
        # A 0% bit-flip rate here is structural, not evidence of a random-output bias.
        for item in ranked:
            item["z_score"] = None
            item["p_raw_normal_approx"] = None
        top = ranked[0]
        for item in ranked[:10]:
            item["log10_p_raw_exact_binomial"] = None
            item["p_raw_exact_binomial"] = None
            item["log10_p_bonferroni"] = None
            item["p_bonferroni_exact"] = None
    else:
        item = ranked[0]
        logp = _binomial_two_sided_log10(item["flips"], samples)
        item["log10_p_raw_exact_binomial"] = logp
        item["p_raw_exact_binomial"] = _p_from_log10(logp)
        item["log10_p_bonferroni"] = min(0.0, logp + math.log10(family_size))
        item["p_bonferroni_exact"] = _p_from_log10(item["log10_p_bonferroni"])
        top = ranked[0]
    mean_hamming = total_hamming / samples
    schedule_profile = [
        {"word": t, "changed_samples": schedule_changed_counts[t],
         "change_frequency": schedule_changed_counts[t] / samples,
         "mean_changed_bits": schedule_hamming_totals[t] / samples}
        for t in range(64)
    ]
    return {
        "experiment": "reduced_round_sha256_compression_xor_differential",
        "rounds": rounds,
        "samples": samples,
        "input_delta": {
            "name": delta_name,
            "active_words": active_words,
            "active_bit_count": sum(mask.bit_count() for mask in delta),
            "xor_masks_hex": [f"0x{mask:08x}" for mask in delta],
        },
        "seed": actual_seed,
        "output_bits": OUTPUT_BITS,
        "mean_changed_output_bits": mean_hamming,
        "mean_output_bit_flip_rate": mean_hamming / OUTPUT_BITS,
        "zero_output_difference_samples": zero_diffs,
        "zero_output_difference_fraction": zero_diffs / samples,
        "max_exact_difference_multiplicity": max(full_diffs.values()),
        "distinct_output_differences": len(full_diffs),
        "message_schedule_profile": schedule_profile,
        "schedule_carry_out_mismatches_by_stage": carry_stage_mismatches,
        "schedule_carry_out_mismatch_rate_by_stage": [x / (48 * samples) for x in carry_stage_mismatches],
        "best_output_bit": top,
        "top_10_output_bits": ranked[:10],
        "input_delta_effect": "no_observed_effect_in_any_sample" if no_effect else "output_difference_observed",
        "family_size_for_bonferroni": family_size,
        "elapsed_seconds": elapsed,
        "paired_samples_per_second": samples / elapsed,
        "interpretation": "Descriptive reduced-round evidence only. An exact binomial p-value is calculated for the maximum-deviation output bit; Bonferroni correction covers 256 output-bit tests (and all sweep configurations when run as a sweep). Statistical bias is not a full-round SHA-256 break, not a preimage/collision result, and not a consensus-compatible mining shortcut.",
        "consensus_compatible": False,
    }


def run_multi_delta_sweep(rounds: int = 20, samples: int = 2000, seed: int | None = None) -> dict:
    """Compare curated one-/multi-bit input XOR differences on a reduced-round variant."""
    if isinstance(rounds, bool) or not isinstance(rounds, int) or not 1 <= rounds <= 64:
        raise ValueError("Runda trebuie să fie între 1 și 64.")
    if isinstance(samples, bool) or not isinstance(samples, int) or not 100 <= samples <= MAX_SAMPLES:
        raise ValueError(f"Numărul de probe trebuie să fie între 100 și {MAX_SAMPLES}.")
    patterns = []
    def pat(name: str, masks: dict[int, int]) -> None:
        words = [0] * 16
        for idx, mask in masks.items():
            words[idx] = mask
        patterns.append((name, words))
    pat("W14_single_bit0", {14: 1 << 0})
    pat("W14_adjacent_bits_0_1", {14: (1 << 0) | (1 << 1)})
    pat("W14_spread_bits_0_16", {14: (1 << 0) | (1 << 16)})
    pat("W14_four_bits_0_8_16_24", {14: sum(1 << b for b in (0, 8, 16, 24))})
    pat("W15_single_bit0", {15: 1 << 0})
    pat("W14_W15_bit0_pair", {14: 1 << 0, 15: 1 << 0})
    pat("W13_W14_W15_bit0_triplet", {13: 1 << 0, 14: 1 << 0, 15: 1 << 0})
    pat("W13_single_bit0", {13: 1 << 0})
    base_seed = seed if seed is not None else secrets.randbits(64)
    family_size = len(patterns) * OUTPUT_BITS
    results = []
    for i, (name, words) in enumerate(patterns):
        result = run_differential(rounds, samples, word=14, input_bit=0,
                                  seed=(base_seed + i) % (2**64),
                                  family_size=family_size,
                                  delta_words=words, delta_name=name)
        exact_logp = result["best_output_bit"].get("log10_p_raw_exact_binomial")
        if exact_logp is None:
            result["best_output_bit"]["p_familywise_bonferroni"] = None
        else:
            adjusted_logp = min(0.0, exact_logp + math.log10(family_size))
            result["best_output_bit"]["log10_p_familywise_bonferroni"] = adjusted_logp
            result["best_output_bit"]["p_familywise_bonferroni"] = _p_from_log10(adjusted_logp)
        results.append(result)
    return {
        "experiment": "reduced_round_sha256_curated_multi_delta_sweep",
        "rounds": rounds,
        "samples_per_pattern": samples,
        "patterns_tested": [name for name, _ in patterns],
        "base_seed": base_seed,
        "family_size_for_multiple_testing_correction": family_size,
        "results": results,
        "consensus_compatible": False,
    }


def run_round_sweep(rounds: Iterable[int], samples: int = 2000, word: int = 14,
                    input_bit: int = 0, seed: int | None = None) -> dict:
    round_list = list(rounds)
    if not round_list or len(round_list) > MAX_SWEEP_ROUNDS:
        raise ValueError(f"Sweep-ul trebuie să conțină 1–{MAX_SWEEP_ROUNDS} configurații.")
    if len(set(round_list)) != len(round_list):
        raise ValueError("Sweep-ul nu poate conține runde duplicate.")
    if any(isinstance(r, bool) or not isinstance(r, int) or not 1 <= r <= 64 for r in round_list):
        raise ValueError("Fiecare configurație trebuie să aibă între 1 și 64 de runde.")
    base_seed = seed if seed is not None else secrets.randbits(64)
    # Correct across all output-bit tests in the complete sweep, not round by round.
    family_size = len(round_list) * OUTPUT_BITS
    results = []
    for i, r in enumerate(round_list):
        results.append(run_differential(r, samples, word, input_bit,
                                        (base_seed + i) % (2**64), family_size))
    for row in results:
        row["family_size_for_bonferroni"] = family_size
        exact_logp = row["best_output_bit"].get("log10_p_raw_exact_binomial")
        if exact_logp is None:
            row["best_output_bit"]["log10_p_familywise_bonferroni"] = None
            row["p_familywise_bonferroni_exact"] = None
            row["best_output_bit"]["p_familywise_bonferroni"] = None
        else:
            adjusted_logp = min(0.0, exact_logp + math.log10(family_size))
            row["best_output_bit"]["log10_p_familywise_bonferroni"] = adjusted_logp
            row["p_familywise_bonferroni_exact"] = _p_from_log10(adjusted_logp)
            row["best_output_bit"]["p_familywise_bonferroni"] = _p_from_log10(adjusted_logp)
    return {
        "experiment": "reduced_round_sha256_round_sweep",
        "samples_per_round": samples,
        "input_delta": {"word_index": word, "bit_index_lsb": input_bit},
        "base_seed": base_seed,
        "rounds_tested": round_list,
        "family_size_for_multiple_testing_correction": family_size,
        "results": results,
        "consensus_compatible": False,
    }


def run_compression_carry_differential(rounds: int = 20, samples: int = 2000,
                                      word: int = 14, input_bit: int = 0,
                                      seed: int | None = None) -> dict:
    """Compare round-level carry decisions in T1/T2/state updates for paired inputs."""
    if isinstance(rounds, bool) or not isinstance(rounds, int) or not 1 <= rounds <= 64:
        raise ValueError("Runda trebuie să fie între 1 și 64.")
    if isinstance(samples, bool) or not isinstance(samples, int) or not 100 <= samples <= MAX_SAMPLES:
        raise ValueError(f"Numărul de probe trebuie să fie între 100 și {MAX_SAMPLES}.")
    if isinstance(word, bool) or not isinstance(word, int) or not 0 <= word < 16:
        raise ValueError("Cuvântul de intrare trebuie să fie între 0 și 15.")
    if isinstance(input_bit, bool) or not isinstance(input_bit, int) or not 0 <= input_bit < 32:
        raise ValueError("Bitul de intrare trebuie să fie între 0 și 31.")
    actual_seed = seed if seed is not None else secrets.randbits(64)
    rng = Random(actual_seed)
    delta = [0] * 16
    delta[word] = 1 << input_bit
    labels = ["T1:add1", "T1:add2", "T1:add3", "T1:add4", "T2:add", "state:e=d+T1", "state:a=T1+T2"]
    mismatches = [[0] * len(labels) for _ in range(rounds)]
    base_carry_ones = [[0] * len(labels) for _ in range(rounds)]
    alt_carry_ones = [[0] * len(labels) for _ in range(rounds)]
    start = time.perf_counter()
    for _ in range(samples):
        block = [rng.getrandbits(32) for _ in range(16)]
        altered = [x ^ d for x, d in zip(block, delta)]
        base_schedule = expand_schedule_with_carries(block)[0]
        alt_schedule = expand_schedule_with_carries(altered)[0]
        _, base_trace = compress_schedule_with_round_carries(base_schedule, rounds)
        _, alt_trace = compress_schedule_with_round_carries(alt_schedule, rounds)
        for r in range(rounds):
            for j in range(len(labels)):
                x, y = base_trace[r][j], alt_trace[r][j]
                mismatches[r][j] += x != y
                base_carry_ones[r][j] += x
                alt_carry_ones[r][j] += y
    elapsed = max(time.perf_counter() - start, 1e-9)
    rows = []
    for r in range(rounds):
        for j, label in enumerate(labels):
            rows.append({
                "round": r + 1, "operation": label,
                "carry_decision_mismatch_count": mismatches[r][j],
                "carry_decision_mismatch_rate": mismatches[r][j] / samples,
                "baseline_carry_rate": base_carry_ones[r][j] / samples,
                "altered_carry_rate": alt_carry_ones[r][j] / samples,
            })
    return {
        "experiment": "sha256_reduced_round_compression_carry_differential",
        "rounds": rounds, "samples": samples,
        "input_delta": {"word_index": word, "bit_index_lsb": input_bit},
        "seed": actual_seed, "operations_per_round": labels,
        "per_round_operation_results": rows,
        "elapsed_seconds": elapsed,
        "paired_samples_per_second": samples / elapsed,
        "interpretation": "Carry-decision correlation telemetry for exact SHA-256 round arithmetic. This is descriptive and does not imply a shortcut or weakness in full SHA-256.",
        "consensus_compatible": False,
    }
