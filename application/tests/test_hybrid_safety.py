from mining.hybrid_safety import validate_engine_resources


def test_gpu_requires_vram_margin_and_thermal_headroom():
    result = validate_engine_resources('gpu', {'available': True, 'memory_total_mb': 4000, 'temperature_c': 88},
                                       {'required_vram_mb': 3800, 'vram_margin_mb': 256, 'max_temperature_c': 85})
    assert result['allowed'] is False
    assert 'vram_insufficient' in result['reasons']
    assert 'temperature_limit' in result['reasons']


def test_gpu_missing_telemetry_fails_closed():
    result = validate_engine_resources('gpu', {}, {})
    assert result['allowed'] is False
    assert 'gpu_telemetry_missing' in result['reasons']


def test_cpu_does_not_require_gpu_telemetry():
    assert validate_engine_resources('cpu', {}, {})['allowed'] is True
