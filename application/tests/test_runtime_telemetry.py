from types import SimpleNamespace
import json

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


def test_runtime_telemetry_reads_real_psutil_temperature_sensors(monkeypatch):
    monkeypatch.setattr(
        "modules.runtime_telemetry.platform.system", lambda: "Linux"
    )
    monkeypatch.setattr(
        "modules.runtime_telemetry.psutil.sensors_temperatures",
        lambda: {
            "coretemp": [
                SimpleNamespace(
                    label="Package id 0", current=62.5, high=90.0, critical=100.0
                )
            ]
        },
    )

    result = RuntimeTelemetry()._temperatures()
    assert result["available"] is True
    assert result["source"] == "psutil"
    assert result["sensors"][0]["temperature_c"] == 62.5
    assert result["sensors"][0]["high_c"] == 90.0
    assert result["sensors"][0]["thermal_state"] == "below_reported_sensor_thresholds"


def test_runtime_telemetry_reads_librehardwaremonitor_wmi_on_windows(monkeypatch):
    monkeypatch.setattr(
        "modules.runtime_telemetry.platform.system", lambda: "Windows"
    )
    monkeypatch.setattr(
        "modules.runtime_telemetry.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(
            stdout=json.dumps([{
                "Name": "CPU Package",
                "SensorType": "Temperature",
                "Value": 67.25,
                "Identifier": "/intelcpu/0/temperature/0",
            }])
        ),
    )

    result = RuntimeTelemetry()._temperatures()
    assert result["available"] is True
    assert result["source"] == "LibreHardwareMonitor WMI"
    assert result["sensors"][0]["temperature_c"] == 67.2


def test_runtime_telemetry_never_invents_temperature_when_sensors_unavailable(monkeypatch):
    monkeypatch.setattr(
        "modules.runtime_telemetry.platform.system", lambda: "Linux"
    )
    monkeypatch.setattr(
        "modules.runtime_telemetry.psutil.sensors_temperatures", lambda: {}
    )

    result = RuntimeTelemetry()._temperatures()
    assert result["available"] is False
    assert result["sensors"] == []
    assert result["reason"] == "OS or hardware does not expose temperature sensors"


def test_runtime_telemetry_reports_nvidia_gpu_clocks_power_limit_and_throttle(monkeypatch):
    responses = iter([
        SimpleNamespace(
            stdout="NVIDIA GeForce GTX 1650, 24, 1024, 4096, 63, 42.5\n"
        ),
        SimpleNamespace(stdout="1500, 1350, 4000, 75, Not Active\n"),
    ])
    monkeypatch.setattr("shutil.which", lambda name: "nvidia-smi")
    monkeypatch.setattr(
        "modules.runtime_telemetry.subprocess.run",
        lambda *args, **kwargs: next(responses),
    )

    result = RuntimeTelemetry()._gpu()
    assert result["available"] is True
    assert result["devices"][0]["temperature_c"] == 63.0
    assert result["devices"][0]["graphics_clock_mhz"] == 1500.0
    assert result["devices"][0]["power_limit_w"] == 75.0
    assert result["devices"][0]["throttle_reasons_active"] == "Not Active"
