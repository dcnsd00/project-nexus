from mining.development_pow import define_experiment, verify_sha256d_header


def test_only_regtest_or_testnet_experiments_are_accepted():
    assert define_experiment('regtest', 'sha256d') ['research_only'] is False
    try:
        define_experiment('mainnet', 'sha256d')
    except ValueError:
        pass
    else:
        assert False, 'mainnet must not be accepted by research harness'


def test_non_equivalent_hash_variant_cannot_claim_consensus():
    exp = define_experiment('testnet', 'sha256d-reduced-rounds')
    assert exp['research_only'] is True
    assert exp['consensus_equivalent'] is False


def test_sha256d_header_verification_checks_target():
    header = bytes(80)
    assert verify_sha256d_header(header.hex(), 'ff' * 32)['valid'] is True
    assert verify_sha256d_header(header.hex(), '00' * 32)['valid'] is False


def test_development_cpu_worker_is_local_and_reports_no_pool_submission(tmp_path):
    import json
    from mining.development_pow import run_development_worker
    status = tmp_path / 'dev' / 'status.json'
    rc = run_development_worker('cpu', {'network': 'regtest', 'algorithm': 'sha256d', 'attempts': 2000},
                                str(status), str(tmp_path / 'dev' / 'stop'))
    data = json.loads(status.read_text())
    assert rc == 0
    assert data['state'] == 'stopped'
    assert data['pool_connected'] is False
    assert data['authorized'] is False
    assert data['experiment']['consensus_verified'] is False


def test_development_gpu_fails_truthfully_without_verified_backend(tmp_path):
    import json
    from mining.development_pow import run_development_worker
    status = tmp_path / 'devgpu' / 'status.json'
    rc = run_development_worker('gpu', {'network': 'regtest', 'algorithm': 'sha256d'},
                                str(status), str(tmp_path / 'devgpu' / 'stop'))
    assert rc != 0
    assert json.loads(status.read_text())['last_error'] == 'backend_unavailable'


def test_development_worker_reports_invalid_network_without_traceback_state(tmp_path):
    import json
    from mining.development_pow import run_development_worker
    status = tmp_path / 'invalid' / 'status.json'
    rc = run_development_worker('cpu', {'network': 'mainnet', 'algorithm': 'sha256d'},
                                str(status), str(tmp_path / 'invalid' / 'stop'))
    assert rc != 0
    assert json.loads(status.read_text())['last_error'] == 'invalid_network'
