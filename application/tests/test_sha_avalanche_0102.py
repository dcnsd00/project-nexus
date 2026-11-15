import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault('NEXUS_WALLET_DB', '/tmp/nexus-0102-wallet.db')
os.environ.setdefault('NEXUS_DB', '/tmp/nexus-0102-core.db')
sys.path.insert(0, str(ROOT))

from modules.sha_avalanche import avalanche_catalog, avalanche_experiment  # noqa: E402
from nexus_master import app  # noqa: E402


def test_sha512_avalanche_is_deterministic_and_full_standard():
    a = avalanche_experiment('sha512', 32, 64, 123)
    b = avalanche_experiment('sha512', 32, 64, 123)
    assert a['mean_changed_output_bits'] == b['mean_changed_output_bits']
    assert a['standard_digest_bits'] == 512
    assert a['expected_mean_for_ideal_random_mapping'] == 256
    assert a['consensus_compatible'] is True
    assert a['not_a_pow_benchmark'] is True


def test_supported_hash_families_run():
    for name, bits in [('sha256', 256), ('sha3_256', 256), ('sha3_512', 512), ('blake2b_256', 256)]:
        result = avalanche_experiment(name, 16, 8, 44)
        assert result['standard_digest_bits'] == bits
        assert 0 <= result['min_distance'] <= bits
        assert 0 <= result['max_distance'] <= bits


def test_avalanche_rejects_invalid_inputs():
    with pytest.raises(ValueError):
        avalanche_experiment('sha999', 16, 64, 1)
    with pytest.raises(ValueError):
        avalanche_experiment('sha512', 15, 64, 1)
    with pytest.raises(ValueError):
        avalanche_experiment('sha512', 16, 0, 1)


def test_avalanche_api_catalog_and_run():
    with TestClient(app) as client:
        catalog = client.get('/api/math-intelligence/avalanche/catalog')
        assert catalog.status_code == 200
        assert catalog.json()['algorithms']['sha512'] == 512
        response = client.post('/api/math-intelligence/avalanche/run', json={
            'algorithm': 'sha512', 'samples': 16, 'payload_bytes': 32, 'seed': 7
        })
        assert response.status_code == 200
        assert response.json()['result']['standard_digest_bits'] == 512


def test_avalanche_catalog_warns_not_a_security_proof():
    catalog = avalanche_catalog()
    assert catalog['max_samples'] == 4096
    assert any('not a proof' in item.lower() for item in catalog['limits'])
