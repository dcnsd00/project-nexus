"""Evidence-gated, recommendation-only mining configuration analysis."""
from __future__ import annotations
import statistics


def score_configuration(metrics: dict, policy: dict | None = None) -> dict:
    policy = policy or {}
    rate = metrics.get('hashrate_hs')
    accepted = metrics.get('accepted_shares')
    rejected = metrics.get('rejected_shares')
    power = metrics.get('power_w')
    violations = list(metrics.get('safety_violations') or [])
    temperature = metrics.get('temperature_c')
    if temperature is not None and float(temperature) >= float(policy.get('max_temperature_c', 85)) and 'temperature_limit' not in violations:
        violations.append('temperature_limit')
    if metrics.get('process_stable') is False and 'process_unstable' not in violations:
        violations.append('process_unstable')
    if metrics.get('vram_headroom_mb') is not None and float(metrics['vram_headroom_mb']) < float(policy.get('minimum_vram_headroom_mb', 256)) and 'vram_headroom_low' not in violations:
        violations.append('vram_headroom_low')
    duration = float(metrics.get('duration_seconds') or 0)
    reject_ratio = None
    if isinstance(accepted, (int, float)) and isinstance(rejected, (int, float)) and accepted + rejected > 0:
        reject_ratio = rejected / (accepted + rejected)
    accepted_rate = (float(accepted) / duration) if isinstance(accepted, (int, float)) and accepted >= 0 and duration > 0 else None
    energy = (accepted_rate / float(power)) if accepted_rate is not None and isinstance(power, (int, float)) and power > 0 else None
    eligible = (isinstance(rate, (int, float)) and rate > 0 and isinstance(accepted, (int, float)) and accepted > 0
                and duration >= float(policy.get('minimum_duration_seconds', 300)) and not violations
                and reject_ratio is not None and reject_ratio <= float(policy.get('max_reject_ratio', .05)))
    return {'window_id': metrics.get('window_id'), 'pool_id': metrics.get('pool_id'),
            'share_difficulty': metrics.get('share_difficulty'), 'hashrate_hs': rate,
            'accepted_shares': accepted, 'rejected_shares': rejected, 'accepted_shares_per_second': accepted_rate, 'reject_ratio': reject_ratio,
            'energy_efficiency': energy, 'energy_efficiency_status': 'measured' if energy is not None else 'unknown',
            'duration_seconds': duration, 'safety_violations': violations,
            'classification': 'candidate' if eligible else 'research_only'}


def _windows_valid(windows, policy):
    if not isinstance(windows, list) or len(windows) < 3:
        return False, 'insufficient_windows'
    ids = [w.get('window_id') for w in windows]
    if any(not x for x in ids) or len(set(ids)) != len(ids):
        return False, 'duplicate_or_missing_window_id'
    pool = {w.get('pool_id') for w in windows}
    difficulty = {w.get('share_difficulty') for w in windows}
    if len(pool) != 1 or None in pool or len(difficulty) != 1 or None in difficulty:
        return False, 'incomparable_pool_or_difficulty'
    scores = [score_configuration(w, policy) for w in windows]
    if any(s['classification'] != 'candidate' for s in scores):
        return False, 'incomplete_or_unsafe_measurements'
    return True, scores


def rank_candidates(baseline: dict, candidates: list[dict], policy: dict | None = None) -> dict:
    policy = policy or {}
    base_ok, base_result = _windows_valid(baseline.get('windows'), policy)
    output = []
    for candidate in candidates:
        windows = candidate.get('windows') or []
        ok, result = _windows_valid(windows, policy)
        reason = result if not ok else None
        baseline_ids = {w.get('window_id') for w in baseline.get('windows', [])}
        candidate_ids = {w.get('window_id') for w in windows}
        if baseline_ids & candidate_ids:
            ok, reason = False, 'window_id_reused_across_comparison'
        if not base_ok:
            ok, reason = False, f'baseline_{base_result}'
        if ok:
            bpool = baseline['windows'][0].get('pool_id')
            bdiff = baseline['windows'][0].get('share_difficulty')
            if windows[0].get('pool_id') != bpool or windows[0].get('share_difficulty') != bdiff:
                ok, reason = False, 'baseline_candidate_scope_mismatch'
        if candidate.get('consensus_equivalent') is not True or candidate.get('algorithm_variant') in {'reduced_rounds', 'non_equivalent'}:
            ok, reason = False, 'non_consensus_algorithm'
        if ok:
            base_scores = [score_configuration(w, policy) for w in baseline['windows']]
            candidate_scores = [score_configuration(w, policy) for w in windows]
            base_rates = [float(w['hashrate_hs']) for w in baseline['windows']]
            rates = [float(w['hashrate_hs']) for w in windows]
            baseline_median, candidate_median = statistics.median(base_rates), statistics.median(rates)
            dispersion = statistics.median([abs(x - candidate_median) for x in rates])
            energy_measured = all(x['energy_efficiency'] is not None for x in base_scores + candidate_scores)
            if energy_measured:
                objective = 'accepted_shares_per_second_per_watt'
                base_values = [x['energy_efficiency'] for x in base_scores]
                candidate_values = [x['energy_efficiency'] for x in candidate_scores]
            else:
                objective = 'accepted_shares_per_second'
                base_values = [x['accepted_shares_per_second'] for x in base_scores]
                candidate_values = [x['accepted_shares_per_second'] for x in candidate_scores]
            baseline_metric = statistics.median(base_values)
            candidate_metric = statistics.median(candidate_values)
            improvement = ((candidate_metric / baseline_metric) - 1) * 100 if baseline_metric > 0 else None
            classification = 'manual_review'
        else:
            baseline_median = candidate_median = dispersion = None
            objective = baseline_metric = candidate_metric = improvement = None
            classification = 'research_only'
        output.append({'classification': classification, 'reason': reason,
                       'objective': objective, 'baseline_objective_median': baseline_metric,
                       'candidate_objective_median': candidate_metric, 'improvement_percent': improvement,
                       'baseline_median_hashrate_hs': baseline_median,
                       'candidate_median_hashrate_hs': candidate_median,
                       'candidate_mad_hashrate_hs': dispersion,
                       'automatic_application': False})
    return {'baseline_valid': base_ok, 'candidates': output, 'automatic_application': False}


def recommend_parameters(engine: str, telemetry: dict, benchmark_results: list[dict], constraints: dict | None = None) -> dict:
    return {'engine': engine, 'classification': 'research_only', 'recommendations': [],
            'reason': 'No candidate can be recommended without three comparable measured windows.',
            'automatic_application': False}
