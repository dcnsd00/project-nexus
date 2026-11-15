"""Feature extraction and first-pass, explicitly exploratory RCSC analysis."""
from __future__ import annotations

from collections import Counter, defaultdict
from statistics import mean, median
from typing import Any

from .bitcoin import subsidy_sats
from .statistics import conditioned_hash_bit_tests, nonce_nibble_tests
from .associations import reward_conditioned_nonce_tests


def halving_era(height: int) -> int:
    return height // 210_000


def analyze(records: list[dict[str, Any]]) -> dict[str, Any]:
    valid_header = [r for r in records if r.get("reported_hash_matches_header") is True
                    and r.get("reported_fields_match_header") is True
                    and r.get("pow_valid") is True
                    and r.get("in_best_chain") is True
                    and r.get("merkle_root_valid", True) is True]
    complete_reward = [r for r in valid_header if isinstance(r.get("coinbase_total_sats"), int)]
    nonce_rows = [r for r in valid_header if isinstance(r.get("nonce"), int)]

    era_counts = Counter(halving_era(int(r["height"])) for r in complete_reward)
    coinbase_excess_values = [r["claimed_above_subsidy_sats"] for r in complete_reward
                              if isinstance(r.get("claimed_above_subsidy_sats"), int)]
    reward_values = [r["coinbase_total_sats"] for r in complete_reward]

    era_summary = {}
    grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in complete_reward:
        grouped[halving_era(int(row["height"]))].append(row)
    for era, rows in sorted(grouped.items()):
        era_excess = [r["claimed_above_subsidy_sats"] for r in rows
                      if isinstance(r.get("claimed_above_subsidy_sats"), int)]
        era_summary[str(era)] = {
            "block_count": len(rows),
            "scheduled_subsidy_sats": subsidy_sats(era * 210_000),
            "mean_coinbase_excess_over_subsidy_sats": mean(era_excess) if era_excess else None,
            "median_coinbase_excess_over_subsidy_sats": median(era_excess) if era_excess else None,
        }

    return {
        "schema_version": "0.1.0",
        "research_label": "RCSC exploratory analysis; not a validated cryptanalytic attack",
        "input_record_count": len(records),
        "header_and_pow_verified_count": len(valid_header),
        "reward_complete_count": len(complete_reward),
        "records_with_errors": sum(1 for r in records if r.get("collection_error")),
        "halving_era_counts": dict(era_counts),
        "coinbase_total_sats_mean": mean(reward_values) if reward_values else None,
        "coinbase_total_sats_median": median(reward_values) if reward_values else None,
        "coinbase_excess_over_subsidy_sats_mean": mean(coinbase_excess_values) if coinbase_excess_values else None,
        "coinbase_excess_over_subsidy_sats_median": median(coinbase_excess_values) if coinbase_excess_values else None,
        "reward_by_halving_era": era_summary,
        "nonce_nibble_uniformity_tests": nonce_nibble_tests(r["nonce"] for r in nonce_rows),
        "reward_conditioned_nonce_permutation_tests": reward_conditioned_nonce_tests(records),
        "hash_bit_tests_conditioned_on_pow_target": conditioned_hash_bit_tests(valid_header),
        "interpretation_guardrails": [
            "A valid block hash is sampled conditionally on hash <= target; do not compare its 256 bits to an unconditional 50/50 null.",
            "Nonce patterns can fingerprint miner software, hardware, pool templates or search strategy; they do not by themselves show a SHA-256 weakness.",
            "Coinbase outputs minus scheduled subsidy are not necessarily exact transaction fees because miners may underclaim; use independently verified block fee totals for exact fees.",
            "Reward is confounded by halving era and fee-market conditions; analyze subsidy and actual fees separately.",
            "Do not infer predictability from in-sample correlation. Require chronological holdout and independent replication.",
            "A statistical anomaly is not a way to claim rewards from already-mined blocks or recover private keys."
        ],
    }
