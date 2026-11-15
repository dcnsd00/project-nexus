import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from nexus_consolidation_benchmark import build_benchmark


def test_19_sources_5_destinations_and_conservation(tmp_path):
    r = build_benchmark(tmp_path)
    assert r['wallet_counts'] == {'source_test_wallets': 19, 'destination_test_wallets': 5, 'total_wallets': 24}
    assert r['key_open_tests']['passed'] == 24
    assert r['key_open_tests']['failed'] == 0
    assert r['synthetic_ledger']['broadcast_transactions'] == 0
    assert r['all_invariants_passed']
    assert all(x['difference'] == 0 for x in r['balance_conservation'])
    assert (tmp_path / 'simulated_transfers.json').exists()
