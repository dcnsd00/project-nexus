import os
from fastapi.testclient import TestClient
import pytest
import nexus_master

client = TestClient(nexus_master.app)

def test_hybrid_capabilities_reports_native_and_optional_backends():
    d = client.get('/api/math/hybrid/capabilities').json()
    assert d['router'] == 'NEXUS Hybrid Solver Router'
    assert d['backends']['native_exact']['available'] is True
    assert 'sympy' in d['backends'] and 'z3_smt' in d['backends'] and 'pysat' in d['backends']

def test_hybrid_modular_solver_exact_solution_and_verification():
    r = client.post('/api/math/hybrid/solve', json={'kind':'modular_congruence','a':14,'b':30,'modulus':100})
    assert r.status_code == 200
    d = r.json()
    assert d['verified'] is True
    assert d['one_solution'] == 45
    assert d['solution_count'] == 2
    assert d['private_local'] is True and d['auto_apply'] is False

def test_hybrid_linear_solver_exact_rational_system():
    r = client.post('/api/math/hybrid/solve', json={
        'kind':'linear_system','matrix':[[2,1],[1,-1]],'rhs':[5,1]
    })
    assert r.status_code == 200
    d = r.json()
    assert d['verified'] is True
    assert d['solution'] == ['2', '1']

def test_hybrid_solver_rejects_bad_matrix_without_crash():
    r = client.post('/api/math/hybrid/solve', json={
        'kind':'linear_system','matrix':[[1,2],[3]],'rhs':[1,2]
    })
    assert r.status_code == 400

def test_hybrid_bitvector_solver_has_exact_native_fallback():
    r = client.post('/api/math/hybrid/solve', json={
        'kind':'bitvector_xor','variables':['a','b','c'],'target':173,'width':8
    })
    assert r.status_code == 200
    d = r.json()
    assert d['verified'] is True and d['solvable'] is True
    assert d['backend'] == 'native_exact_xor'
    value = 0
    for part in d['solution'].values():
        value ^= part
    assert value == 173
    assert d['private_local'] is True and d['auto_apply'] is False


def test_hybrid_bitvector_solver_rejects_target_outside_width():
    r = client.post('/api/math/hybrid/solve', json={
        'kind':'bitvector_xor','variables':['a','b'],'target':256,'width':8
    })
    assert r.status_code == 400
