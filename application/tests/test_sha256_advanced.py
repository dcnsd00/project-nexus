import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault('NEXUS_WALLET_DB', '/tmp/nexus-advanced-sha-wallet.db')
os.environ.setdefault('NEXUS_DB', '/tmp/nexus-advanced-sha-core.db')
sys.path.insert(0, str(ROOT))

from modules.sha256_research.advanced import (  # noqa: E402
    advanced_research_info,
    build_collision_cnf,
    output_prefix_msb_first,
    sat_selfcheck,
    search_differential,
    track_differential,
)
from nexus_master import app  # noqa: E402


def test_advanced_search_is_reproducible_and_has_independent_holdout():
    a = search_differential(8, 8, 8, 1, 24, 123, [6, 7])
    b = search_differential(8, 8, 8, 1, 24, 123, [6, 7])
    assert a['candidate_delta_words_hex'] == b['candidate_delta_words_hex']
    assert a['validation_seed'] == b['validation_seed']
    assert a['validation_samples'] == 24
    assert a['consensus_compatible'] is False
    assert a['methodology'].find('aceleași blocuri') >= 0
    assert set(a['candidate_active_words']).issubset({6, 7})
    assert a['first_affected_round'] in (7, 8)


def test_search_rejects_excessive_work_budget():
    with pytest.raises(ValueError, match='Bugetul depășește'):
        search_differential(64, 120, 96, 3, 64, 1)


def test_search_rejects_word_indices_not_consumed_by_requested_rounds():
    with pytest.raises(ValueError, match='trebuie să includă consumarea'):
        search_differential(15, 5, 8, 1, 16, 3, [14, 15])


def test_track_rejects_zero_or_malformed_delta():
    with pytest.raises(ValueError, match='zero'):
        track_differential([0] * 16, 12, 16, 1)
    with pytest.raises(ValueError, match='exact 16'):
        track_differential([1, 0], 12, 16, 1)


def test_track_reports_empirical_modal_frequency_without_path_probability_claim():
    delta = [0] * 16
    delta[15] = 0x80000000
    result = track_differential(delta, 16, 32, 44)
    assert len(result['per_round']) == 17
    assert result['first_affected_round'] == 16
    assert result['per_round'][15]['mean_state_difference_bits'] == 0
    assert 0 <= result['per_round'][16]['modal_full_state_difference_frequency'] <= 1
    assert 'NU este probabilitatea' in result['interpretation']


def test_sat_cnf_prefix_order_is_big_endian():
    vectors = [[1000 + i for i in range(32)], [2000 + i for i in range(32)]]
    assert output_prefix_msb_first(vectors, 3) == [1031, 1030, 1029]
    assert output_prefix_msb_first(vectors, 33)[32] == 2031


def test_sat_selfcheck_matches_reference_for_multiple_reduced_rounds():
    for rounds in (1, 4, 12, 20):
        result = sat_selfcheck(rounds, 987)
        assert result['encoding_matches_reference'] is True
        assert result['consensus_compatible'] is False
        assert result['variables'] > 0 and result['clauses'] > 0


def test_sat_collision_builder_enforces_nonzero_delta_and_prefix():
    builder, _, _ = build_collision_cnf(2, 8, None)
    # A nonzero-delta clause is present, and the requested prefix has two clauses per bit.
    assert builder.nvars > 0
    assert len(builder.clauses) > 2 * 8


def test_advanced_info_exposes_resource_guards():
    info = advanced_research_info()
    assert info['differential_search']['max_work_units'] == 1_000_000
    assert info['sat_solver']['max_rounds'] == 24
    assert info['guardrails']


def test_advanced_sha_api_info_search_track_and_selfcheck():
    with TestClient(app) as client:
        info = client.get('/api/research/sha256/advanced/info')
        assert info.status_code == 200
        search = client.post('/api/research/sha256/advanced/search', json={
            'rounds': 8, 'steps': 6, 'samples': 8, 'restarts': 1,
            'validation_samples': 16, 'seed': 11, 'allowed_words': [6, 7]
        })
        assert search.status_code == 200
        assert search.json()['result']['rounds'] == 8
        delta = [0] * 16
        delta[15] = 0x80000000
        track = client.post('/api/research/sha256/advanced/track', json={
            'rounds': 8, 'samples': 16, 'delta_words': delta, 'seed': 12
        })
        assert track.status_code == 200
        assert len(track.json()['result']['per_round']) == 9
        selfcheck = client.post('/api/research/sha256/sat/selfcheck', json={'rounds': 4, 'seed': 13})
        assert selfcheck.status_code == 200
        assert selfcheck.json()['result']['encoding_matches_reference'] is True


def test_sat_api_solver_missing_is_explicit_and_dimacs_is_exported():
    with TestClient(app) as client:
        info = client.get('/api/research/sha256/advanced/info').json()
        solve = client.post('/api/research/sha256/sat/solve', json={
            'rounds': 2, 'bits': 4, 'timeout_seconds': 1
        })
        if info['sat_solver']['available']:
            assert solve.status_code == 200
        else:
            assert solve.status_code == 501
            assert 'Solverul opțional lipsește' in solve.json()['detail']
        dimacs = client.post('/api/research/sha256/sat/dimacs', json={'rounds': 2, 'bits': 4})
        assert dimacs.status_code == 200
        target = Path(dimacs.json()['result']['path'])
        assert target.exists()
        content = target.read_text(encoding='ascii').splitlines()[0]
        assert content.startswith('p cnf ')
        target.unlink()
