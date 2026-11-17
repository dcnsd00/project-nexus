from modules.runtime_telemetry import RuntimeTelemetry


def test_runtime_telemetry_returns_measured_host_fields_and_three_decimal_percentages():
    telemetry = RuntimeTelemetry(history_size=4)
    first = telemetry.sample()
    second = telemetry.sample()

    assert first["host"]["logical_cpus"] >= 1
    assert 0 <= first["memory"]["utilization_percent"] <= 100
    assert len(first["cpu"]["per_core_percent"]) >= 1
    assert second["network"]["tx_mbps"] is not None
    assert second["network"]["rx_mbps"] is not None
    assert telemetry.history(2)[-1]["timestamp_utc"] == second["timestamp_utc"]
    assert len(telemetry.history(99)) == 2
    assert first["data_quality"]["cpu"] == "measured_local"


def test_runtime_telemetry_history_is_bounded():
    telemetry = RuntimeTelemetry(history_size=2)
    telemetry.sample()
    telemetry.sample()
    telemetry.sample()
    assert len(telemetry.history(10)) == 2
