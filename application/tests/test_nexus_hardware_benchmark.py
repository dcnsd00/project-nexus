from __future__ import annotations

import json

import pytest

from tools import nexus_hardware_benchmark as benchmark


class FakeTelemetry:
    def __init__(self, snapshots):
        self.snapshots = list(snapshots)
        self.calls = 0

    def sample(self):
        self.calls += 1
        if self.snapshots:
            return self.snapshots.pop(0)
        return {
            "host": {"logical_cpus": 4, "physical_cpus": 2},
            "processes": {"top": [], "mining": []},
            "temperatures": {"available": False, "sensors": []},
            "gpu": {"available": False, "devices": []},
            "data_quality": {"temperatures": "unavailable", "gpu": "unavailable"},
        }


def snapshot(*, miner=None, temperature=None):
    return {
        "host": {
            "logical_cpus": 4,
            "physical_cpus": 2,
            "processor": "Test CPU",
            "architecture": "AMD64",
        },
        "cpu": {"utilization_percent": 3.0},
        "memory": {"used_percent": 40.0},
        "disk": {},
        "network": {},
        "processes": {"top": ([{"name": miner}] if miner else []), "mining": []},
        "temperatures": {
            "available": temperature is not None,
            "sensors": ([temperature] if temperature else []),
        },
        "gpu": {"available": False, "devices": []},
        "data_quality": {
            "temperatures": "measured_local" if temperature else "unavailable",
            "gpu": "unavailable",
        },
    }


def test_thread_parser_rejects_duplicates_and_invalid_values():
    assert benchmark._parse_threads("1,2,4", 8) == [1, 2, 4]
    with pytest.raises(ValueError):
        benchmark._parse_threads("1,1", 8)
    with pytest.raises(ValueError):
        benchmark._parse_threads("1,9", 8)
    with pytest.raises(ValueError):
        benchmark._parse_threads("x", 8)


def test_benchmark_blocks_when_miner_is_active(monkeypatch, tmp_path):
    monkeypatch.setattr(
        benchmark, "RuntimeTelemetry",
        lambda history_size=32: FakeTelemetry([snapshot(miner="xmrig.exe")]),
    )
    monkeypatch.setattr(
        benchmark, "native_status",
        lambda: pytest.fail("native backend must not be called when miners are active"),
    )
    target = tmp_path / "blocked.json"
    result = benchmark.run_hardware_benchmark(output=str(target))
    assert result["state"] == "blocked_active_miner_detected"
    assert result["active_miner_processes"] == ["xmrig.exe"]
    assert json.loads(target.read_text(encoding="utf-8"))["state"] == result["state"]


def test_benchmark_reports_backend_unavailable_without_fake_throughput(monkeypatch, tmp_path):
    telemetry = FakeTelemetry([snapshot(), snapshot()])
    monkeypatch.setattr(benchmark, "RuntimeTelemetry", lambda history_size=32: telemetry)
    monkeypatch.setattr(
        benchmark, "native_status",
        lambda: {"available": False, "variants": [], "error": "MSVC unavailable"},
    )
    target = tmp_path / "unavailable.json"
    result = benchmark.run_hardware_benchmark(
        seconds_per_profile=0.25, batch_hashes=1000, threads="1", output=str(target)
    )
    assert result["state"] == "native_backend_unavailable"
    assert result["profiles"] == []
    assert result["best_sha256d_profile"] is None
    assert any("No native" in item for item in result["limitations"])
    stored = json.loads(target.read_text(encoding="utf-8"))
    assert stored["native_sha256d"]["error"] == "MSVC unavailable"


def test_profile_aggregates_exact_work_and_stops_at_sensor_limit(monkeypatch):
    before = snapshot(temperature={
        "temperature_c": 70.0, "high_c": 90.0, "critical_c": 100.0,
        "thermal_state": "below_reported_sensor_thresholds",
    })
    after = snapshot(temperature={
        "temperature_c": 90.0, "high_c": 90.0, "critical_c": 100.0,
        "thermal_state": "at_or_above_sensor_high_threshold",
    })
    telemetry = FakeTelemetry([before, after])
    clock = iter([0.0, 0.1, 0.3, 0.31])
    monkeypatch.setattr(benchmark.time, "perf_counter", lambda: next(clock))
    calls = []

    def fake_scan(header, start, count, target, block_target, *, variant, threads):
        calls.append((start, count, variant, threads))
        return {
            "status": "range_exhausted",
            "checked": count,
            "native_hashrate_mhs": 5.0,
        }

    monkeypatch.setattr(benchmark, "scan_nonce_range_native", fake_scan)
    result = benchmark._profile(
        variant=1, threads=2, seconds=0.25,
        batch_hashes=1000, telemetry=telemetry,
    )
    assert result["state"] == "stopped_thermal_threshold"
    assert result["thermal_stop"] is True
    assert result["hashes_checked"] == 1000
    assert result["throughput_hashes_per_second"] > 0
    assert result["native_rate_median_mh_s"] == 5.0
    assert result["variant"] == "scalar_midstate"
    assert result["telemetry_after"]["temperatures"]["sensors"][0]["temperature_c"] == 90.0
    assert calls == [(100_000, 1000, 1, 2)]
