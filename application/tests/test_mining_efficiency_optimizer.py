from modules.mining_efficiency_optimizer import score_configuration, rank_candidates


def _window(window_id, rate=100, accepted=10, power=50):
    return {'window_id': window_id, 'pool_id': 'pool-a', 'share_difficulty': 2,
            'duration_seconds': 600, 'hashrate_hs': rate, 'accepted_shares': accepted,
            'rejected_shares': 0, 'power_w': power, 'temperature_c': 60,
            'safety_violations': []}


def test_score_marks_energy_unknown_without_power_and_zero_shares_ineligible():
    result = score_configuration({**_window('a', accepted=0), 'power_w': None}, {})
    assert result['energy_efficiency'] is None
    assert result['classification'] == 'research_only'


def test_manual_review_requires_three_unique_comparable_windows():
    baseline = {'windows': [_window('b1'), _window('b2'), _window('b3')]}
    candidate = {'windows': [_window('c1', rate=120), _window('c2', rate=121), _window('c3', rate=119)]}
    result = rank_candidates(baseline, [{**candidate, 'consensus_equivalent': True}], {})
    assert result['candidates'][0]['classification'] == 'manual_review'


def test_cross_pool_or_duplicate_windows_are_rejected():
    baseline = {'windows': [_window('b1'), _window('b2'), _window('b3')]}
    bad = {'windows': [_window('c1'), _window('c1'), {**_window('c3'), 'pool_id': 'other'}]}
    result = rank_candidates(baseline, [bad], {})
    assert result['candidates'][0]['classification'] == 'research_only'


def test_non_consensus_candidate_is_never_manual_review():
    baseline = {'windows': [_window('b1'), _window('b2'), _window('b3')]}
    candidate = {'windows': [_window('c1', 120), _window('c2', 121), _window('c3', 119)],
                 'consensus_equivalent': False}
    result = rank_candidates(baseline, [candidate], {})
    assert result['candidates'][0]['classification'] == 'research_only'
    assert result['candidates'][0]['reason'] == 'non_consensus_algorithm'


def test_optimizer_uses_accepted_shares_per_watt_when_power_is_measured():
    baseline = {'windows': [_window('b1', 100, 10, 100), _window('b2', 100, 10, 100), _window('b3', 100, 10, 100)]}
    candidate = {'consensus_equivalent': True, 'windows': [_window('c1', 105, 12, 50), _window('c2', 105, 12, 50), _window('c3', 105, 12, 50)]}
    result = rank_candidates(baseline, [candidate], {})['candidates'][0]
    assert result['objective'] == 'accepted_shares_per_second_per_watt'
    assert result['improvement_percent'] > 100


def test_optimizer_rejects_window_id_reuse_across_baseline_and_candidate():
    baseline = {'windows': [_window('a'), _window('b'), _window('c')]}
    candidate = {'consensus_equivalent': True, 'windows': [_window('a'), _window('d'), _window('e')]}
    result = rank_candidates(baseline, [candidate], {})['candidates'][0]
    assert result['classification'] == 'research_only'
    assert result['reason'] == 'window_id_reused_across_comparison'


def test_optimizer_derives_temperature_and_stability_guardrails():
    result = score_configuration({**_window('hot'), 'temperature_c': 90, 'process_stable': False},
                                 {'max_temperature_c': 85})
    assert result['classification'] == 'research_only'
    assert 'temperature_limit' in result['safety_violations']
    assert 'process_unstable' in result['safety_violations']
