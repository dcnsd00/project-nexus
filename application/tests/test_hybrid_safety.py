from mining.hybrid_safety import (
    cpu_temperature_from_telemetry,
    validate_engine_resources,
    validate_telemetry_snapshot,
)


def test_gpu_requires_vram_margin_and_thermal_headroom():
    result = validate_engine_resources(
        "gpu",
        {"available": True, "memory_total_mb": 4000, "temperature_c": 88},
        {"required_vram_mb": 3800, "vram_margin_mb": 256, "max_temperature_c": 85},
    )
    assert result["allowed"] is False
    assert "vram_insufficient" in result["reasons"]
    assert "temperature_limit" in result["reasons"]


def test_gpu_missing_telemetry_fails_closed():
    result = validate_engine_resources("gpu", {}, {})
    assert result["allowed"] is False
    assert "gpu_telemetry_missing" in result["reasons"]
    assert "temperature_telemetry_missing" in result["reasons"]


def test_cpu_requires_measured_temperature_but_not_gpu_vram():
    assert validate_engine_resources("cpu", {}, {})["allowed"] is False
    result = validate_engine_resources(
        "cpu", {"available": True, "temperature_c": 62}, {"max_temperature_c": 85}
    )
    assert result["allowed"] is True
    assert result["telemetry"] == "measured"


def test_cpu_over_temperature_and_invalid_limit_fail_closed():
    hot = validate_engine_resources(
        "cpu", {"available": True, "temperature_c": 87}, {"max_temperature_c": 85}
    )
    invalid = validate_engine_resources(
        "cpu", {"available": True, "temperature_c": 50}, {"max_temperature_c": 200}
    )
    assert hot["allowed"] is False
    assert "temperature_limit" in hot["reasons"]
    assert invalid["allowed"] is False
    assert invalid["reasons"] == ["invalid_temperature_limit"]


def test_cpu_sensor_adapter_uses_hottest_cpu_sensor_and_excludes_gpu():
    report = {"available": True, "sensors": [
        {"name": "CPU Package", "temperature_c": 66},
        {"name": "CPU Core #2", "temperature_c": 73},
        {"name": "NVIDIA GPU", "temperature_c": 82},
    ]}
    assert cpu_temperature_from_telemetry(report) == 73


def test_snapshot_adapter_fails_closed_when_cpu_temperature_is_unavailable():
    result = validate_telemetry_snapshot(
        "cpu", {"temperatures": {"available": True, "sensors": [
            {"name": "NVIDIA GPU", "temperature_c": 65}
        ]}}
    )
    assert result["allowed"] is False
    assert "temperature_telemetry_missing" in result["reasons"]


def test_unknown_engine_is_rejected():
    assert validate_engine_resources("asic", {}, {})["allowed"] is False
