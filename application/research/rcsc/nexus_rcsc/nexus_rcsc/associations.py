"""Reward-conditioned nonce association tests using within-stratum permutations.

This is an exploratory screen, not a causal model. It controls for halving era
and nBits, but does not yet control for miner/pool/software attribution.
"""
from __future__ import annotations

import random
from collections import Counter, defaultdict
from typing import Any


def _chi_square_independence(x_values: list[int], y_values: list[int],
                             x_categories: int, y_categories: int) -> float:
    n = len(x_values)
    if n == 0:
        return 0.0
    table = [[0 for _ in range(y_categories)] for _ in range(x_categories)]
    row_totals = [0] * x_categories
    col_totals = [0] * y_categories
    for x, y in zip(x_values, y_values):
        table[x][y] += 1
        row_totals[x] += 1
        col_totals[y] += 1
    statistic = 0.0
    for i in range(x_categories):
        for j in range(y_categories):
            expected = row_totals[i] * col_totals[j] / n
            if expected > 0:
                statistic += (table[i][j] - expected) ** 2 / expected
    return statistic


def _tertile_labels(values: list[int]) -> list[int] | None:
    """Make low/mid/high reward groups without splitting ties arbitrarily."""
    n = len(values)
    ordered = sorted(values)
    q1, q2 = ordered[n // 3], ordered[(2 * n) // 3]
    if q1 >= q2:
        return None
    labels = [0 if value < q1 else 1 if value < q2 else 2 for value in values]
    if len(set(labels)) < 3:
        return None
    return labels


def reward_conditioned_nonce_tests(records: list[dict[str, Any]],
                                   permutations: int = 1999,
                                   min_stratum_size: int = 60,
                                   seed: int = 20261111) -> dict[str, Any]:
    """Test coinbase payout groups vs displayed nonce nibble groups.

    Blocks are stratified by halving era and nBits. Within each stratum, payout
    ranks are permuted relative to nonce features, preserving payout-group
    counts and the stratum's nonce distribution. Each nonce nibble is collapsed
    into four predeclared groups: 0-3, 4-7, 8-b, c-f.

    The coinbase output total is the miner's claimed payout, not necessarily
    subsidy plus all fees: a miner may underclaim. Pool/software attribution
    remains an important omitted confounder.
    """
    grouped: dict[tuple[int, int], list[dict[str, Any]]] = defaultdict(list)
    for row in records:
        if not all([
            row.get("reported_hash_matches_header") is True,
            row.get("reported_fields_match_header") is True,
            row.get("pow_valid") is True,
            row.get("in_best_chain") is True,
            isinstance(row.get("coinbase_total_sats"), int),
            isinstance(row.get("nonce"), int),
            isinstance(row.get("bits"), int),
        ]):
            continue
        era = int(row["height"]) // 210_000
        grouped[(era, int(row["bits"]))].append(row)

    strata: list[dict[str, Any]] = []
    for (era, bits), rows in grouped.items():
        if len(rows) < min_stratum_size:
            continue
        rewards = [int(r["coinbase_total_sats"]) for r in rows]
        reward_labels = _tertile_labels(rewards)
        if reward_labels is None:
            continue
        nonce_hexes = [f"{int(r['nonce']):08x}" for r in rows]
        strata.append({
            "era": era,
            "bits": bits,
            "reward_labels": reward_labels,
            "nibble_features": [
                [int(nonce_hex[pos], 16) // 4 for nonce_hex in nonce_hexes]
                for pos in range(8)
            ],
        })

    if not strata:
        return {
            "status": "insufficient_data",
            "reason": "No halving-era/nBits stratum met the minimum size and had at least two distinct payout cut points.",
            "minimum_stratum_size": min_stratum_size,
            "eligible_block_count": sum(len(v) for v in grouped.values()),
            "tests": [],
        }

    observed = [0.0] * 8
    for stratum in strata:
        labels = stratum["reward_labels"]
        for pos in range(8):
            observed[pos] += _chi_square_independence(labels,
                                                       stratum["nibble_features"][pos],
                                                       3, 4)

    rng = random.Random(seed)
    exceed = [0] * 8
    for _ in range(permutations):
        perm_stats = [0.0] * 8
        for stratum in strata:
            shuffled_labels = list(stratum["reward_labels"])
            rng.shuffle(shuffled_labels)
            for pos in range(8):
                perm_stats[pos] += _chi_square_independence(
                    shuffled_labels, stratum["nibble_features"][pos], 3, 4
                )
        for pos in range(8):
            if perm_stats[pos] >= observed[pos]:
                exceed[pos] += 1

    total_n = sum(len(s["reward_labels"]) for s in strata)
    tests = []
    for pos in range(8):
        p = (exceed[pos] + 1) / (permutations + 1)
        tests.append({
            "nonce_hex_position_from_left": pos,
            "feature_bins": ["0-3", "4-7", "8-b", "c-f"],
            "reward_groups": ["low_third", "middle_third", "high_third"],
            "stratified_chi_square_sum": observed[pos],
            "permutation_p_value": p,
            "bonferroni_p_value_8_tests": min(1.0, p * 8),
        })

    return {
        "status": "exploratory_result",
        "sample_size": total_n,
        "stratum_count": len(strata),
        "strata": [{"halving_era": s["era"], "bits": s["bits"],
                    "block_count": len(s["reward_labels"])} for s in strata],
        "permutations": permutations,
        "random_seed": seed,
        "reward_variable": "coinbase_total_sats (claimed output total)",
        "confounders_controlled": ["halving era", "nBits target/difficulty epoch"],
        "confounders_not_yet_controlled": ["mining pool", "miner software", "ASIC/firmware", "coinbase tag", "timestamp subperiod", "version"],
        "tests": tests,
        "interpretation": "A low corrected p-value is only a candidate association. Require holdout replication and miner/process controls; it does not imply SHA-256 weakness or future nonce predictability.",
    }
