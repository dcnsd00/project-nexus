import pytest
from mining import randomx_benchmark as rb


def test_randomx_benchmark_command_is_algorithm_specific_and_network_free():
    cmd = rb.build_xmrig_benchmark_command('/opt/nexus/xmrig', threads=4, dataset='1M')
    assert cmd == ['/opt/nexus/xmrig', '--bench=1M', '--threads=4', '--no-color']
    assert not any('pool' in item or 'url' in item for item in cmd)


def test_randomx_benchmark_rejects_invalid_thread_and_dataset_values():
    with pytest.raises(ValueError):
        rb.build_xmrig_benchmark_command('/opt/nexus/xmrig', threads=0)
    with pytest.raises(ValueError):
        rb.build_xmrig_benchmark_command('/opt/nexus/xmrig', threads=4, dataset='mainnet')


def test_randomx_parser_extracts_hashrate_and_keeps_algorithm_label():
    parsed = rb.parse_xmrig_benchmark_output('speed 10s/60s/15m 1.23k 1.20k 1.10k H/s')
    assert parsed['algorithm'] == 'RandomX'
    assert parsed['hashrate_hs'] == pytest.approx(1200.0)
    assert parsed['unit'] == 'H/s'


def test_randomx_benchmark_reports_backend_unavailable_without_any_backend(monkeypatch):
    monkeypatch.setattr(rb, '_resolve_xmrig', lambda: None)
    monkeypatch.setattr(rb, '_resolve_native_benchmark', lambda: None)
    result = rb.run_benchmark(threads=2, dataset='1M')
    assert result['state'] == 'backend_unavailable'
    assert result['algorithm'] == 'RandomX'


def test_randomx_benchmark_does_not_claim_success_when_output_has_no_rate(monkeypatch):
    class Result:
        returncode = 0
        stdout = 'XMRig benchmark started but no speed line'
        stderr = ''
    monkeypatch.setattr(rb, '_resolve_xmrig', lambda: '/fake/xmrig')
    monkeypatch.setattr(rb.subprocess, 'run', lambda *a, **k: Result())
    result = rb.run_benchmark(threads=2, dataset='1M')
    assert result['state'] == 'unparsed_output'
    assert result['hashrate_hs'] is None


def test_synthetic_blocks_command_is_offline_and_bounded():
    cmd = rb.build_synthetic_blocks_command('/opt/nexus/randomx-20block-benchmark',
                                            threads=4, hashes_per_block=1000)
    assert cmd == ['/opt/nexus/randomx-20block-benchmark', '4', '1000', 'fast']
    assert not any('pool' in item or 'wallet' in item or 'url' in item for item in cmd)
    with pytest.raises(ValueError):
        rb.build_synthetic_blocks_command('/opt/nexus/randomx-20block-benchmark', 0, 1000)
    with pytest.raises(ValueError):
        rb.build_synthetic_blocks_command('/opt/nexus/randomx-20block-benchmark', 4, 0)


def test_synthetic_blocks_parser_requires_twenty_blocks_and_real_rate():
    output = (
        'mode=fast flags=0x6e\n'
        'benchmark_seconds=10.0\nthreads=4 blocks=20 hashes_per_block=1000\n'
        'total_hashes=20000 total_hits=20\nhashrate_hs=2000.0\n'
        + ''.join(f'block={i} height={500000+i} target_zero_bits=8 hashes=1000 hits=1 first_nonce=1 first_hash='
                  + ('00' + '11' * 31) + '\n' for i in range(20))
    )
    parsed = rb.parse_synthetic_blocks_output(output)
    assert parsed['algorithm'] == 'RandomX'
    assert parsed['block_count'] == 20
    assert parsed['hashrate_hs'] == pytest.approx(2000.0)
    assert parsed['total_hashes'] == 20000
    assert parsed['pool_connected'] is False
    assert len(parsed['blocks']) == 20


def test_synthetic_blocks_parser_rejects_incomplete_output():
    parsed = rb.parse_synthetic_blocks_output('mode=fast\nhashrate_hs=12.0\n')
    assert parsed['state'] == 'unparsed_output'
    assert parsed['hashrate_hs'] is None


def test_synthetic_blocks_benchmark_reports_missing_binary_truthfully(monkeypatch):
    monkeypatch.setattr(rb, '_resolve_synthetic_blocks_binary', lambda: None)
    result = rb.run_synthetic_blocks_benchmark(threads=4, hashes_per_block=1000)
    assert result['state'] == 'backend_unavailable'
    assert result['hashrate_hs'] is None
    assert result['pool_connected'] is False


def test_native_reference_command_is_offline_and_validates_arguments():
    cmd = rb.build_native_benchmark_command('/opt/randomx-benchmark', 4, 'fast', 7, 500)
    assert '--mine' in cmd and '--threads' in cmd and '--seed' in cmd
    assert not any('pool' in item or 'wallet' in item or 'url' in item for item in cmd)
    with pytest.raises(ValueError):
        rb.build_native_benchmark_command('/opt/randomx-benchmark', 0)


def test_native_reference_parser_extracts_fast_mode_rate_and_hash():
    parsed = rb.parse_native_benchmark_output(
        'full memory mode (2080 MiB)\\nJIT compiled mode\\n'
        'Calculated result: ' + 'ab' * 32 + '\\nPerformance: 1234.5 hashes per second')
    assert parsed['algorithm'] == 'RandomX'
    assert parsed['hashrate_hs'] == pytest.approx(1234.5)
    assert parsed['mode'] == 'fast'
    assert parsed['calculated_result'] == 'ab' * 32


def test_native_reference_parser_converts_light_ms_per_hash():
    parsed = rb.parse_native_benchmark_output(
        'light memory mode (256 MiB)\\nCalculated result: ' + 'ef' * 32 +
        '\\nPerformance: 12.5 ms per hash')
    assert parsed['hashrate_hs'] == pytest.approx(80.0)
    assert parsed['mode'] == 'light'


def test_native_reference_reports_missing_binary_truthfully(monkeypatch):
    monkeypatch.setattr(rb, '_resolve_native_benchmark', lambda: None)
    result = rb.run_native_reference_benchmark(threads=2)
    assert result['state'] == 'backend_unavailable'
    assert result['hashrate_hs'] is None
    assert result['pool_connected'] is False
