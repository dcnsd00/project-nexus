import pytest
from modules import math_intelligence as mi

def test_exact_benchmark_sha512_and_sha3():
    r=mi.hash_benchmark(["sha512","sha3_256"],128,20)
    assert len(r['results'])==2
    assert all(x['hashes_per_second']>0 for x in r['results'])
    assert all(len(x['output_hex']) in (64,128) for x in r['results'])

def test_modular_solver_multiple_solutions():
    r=mi.solve_modular_congruence(14,30,100)
    assert r['solvable'] and r['verification'] and r['solution_count']==2

def test_modular_solver_no_solution():
    r=mi.solve_modular_congruence(14,31,100)
    assert not r['solvable']

def test_candidate_triage_does_not_auto_apply():
    r=mi.triage_candidate({'baseline_hashrate':100,'candidate_hashrate':105,'duration_seconds':240,'accepted_shares':20,'rejected_shares':0,'exact_equivalence_verified':True,'independent_runs':3})
    assert r['verdict']=='PROMISING_MEASURED_GAIN'
    assert r['eligible_for_manual_review'] and not r['auto_apply']

def test_candidate_research_only_without_equivalence():
    r=mi.triage_candidate({'baseline_hashrate':100,'candidate_hashrate':150,'duration_seconds':600,'accepted_shares':30,'rejected_shares':0,'exact_equivalence_verified':False,'independent_runs':10})
    assert r['verdict']=='RESEARCH_ONLY' and not r['eligible_for_manual_review']

def test_bounds():
    with pytest.raises(ValueError): mi.hash_benchmark(['sha256'],1024,1)
    with pytest.raises(ValueError): mi.solve_modular_congruence(1,2,1)
