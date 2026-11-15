import json, subprocess, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def test_local_chain_benchmark_runs():
    p=subprocess.run([sys.executable,str(ROOT/'nexus_local_chain_benchmark.py')],capture_output=True,text=True)
    assert p.returncode==0, p.stdout+'\n'+p.stderr
    r=json.loads((ROOT/'results/local_chain_lifecycle_v0.4.json').read_text())
    assert r['totals']['signed_transactions']==40
    assert r['totals']['source_to_receiver_transfers']==31
    assert r['totals']['receiver_to_external_transfers']==9
    assert r['wallet_deletion_semantics']['account_erased_from_chain'] is False
    assert r['real_funds_moved'] is False
    assert r['totals']['source_and_receiver_balances_zero'] is True
    assert all(s['all_source_and_receiver_balances_zero'] for s in r['network_summaries'].values())
    assert all(c['hash_chain_valid'] for c in r['chains'].values())
