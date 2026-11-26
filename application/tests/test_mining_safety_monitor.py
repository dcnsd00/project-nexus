from mining.safety_monitor import MiningSafetyMonitor


class FakeSupervisor:
    def __init__(self, lanes):
        self.lanes = set(lanes)
        self.stopped = []

    def status(self, read_only=False):
        return {"engines": {
            lane: {"state": "running" if lane in self.lanes else "stopped"}
            for lane in ("cpu", "gpu")
        }}

    def stop(self, engine):
        self.stopped.append(engine)
        self.lanes.discard(engine)
        return {"stopped": True, "engine": engine}


class FakeController:
    MINERS = {"xmrig": {"device": ["CPU"]}, "srbminer": {"device": ["CPU", "GPU"]}}

    def __init__(self, status=None):
        self._status = status or {"status": "stopped"}
        self.stop_calls = 0

    def status(self):
        return dict(self._status)

    def stop(self):
        self.stop_calls += 1
        self._status = {"status": "stopped"}
        return {"status": "stopped"}


class FakeTelemetry:
    def __init__(self, snapshot):
        self.snapshot_data = snapshot
        self.calls = 0

    def sample(self):
        self.calls += 1
        return self.snapshot_data


def _snapshot(cpu=62, gpu=70, gpu_memory=4096):
    return {
        "temperatures": {"available": True, "sensors": [
            {"name": "CPU Package", "temperature_c": cpu}
        ]},
        "gpu": {"available": True, "devices": [{
            "name": "NVIDIA test GPU", "temperature_c": gpu,
            "memory_total_mib": gpu_memory,
        }]},
    }


def test_idle_monitor_does_not_sample_sensors_without_miners():
    telemetry = FakeTelemetry(_snapshot())
    monitor = MiningSafetyMonitor(FakeSupervisor([]), FakeController(), telemetry)
    result = monitor.check_once()
    assert result["active"] is False
    assert result["telemetry_sampled"] is False
    assert telemetry.calls == 0


def test_monitor_keeps_healthy_hybrid_cpu_and_gpu_running():
    supervisor = FakeSupervisor({"cpu", "gpu"})
    monitor = MiningSafetyMonitor(supervisor, FakeController(), FakeTelemetry(_snapshot()))
    result = monitor.check_once()
    assert result["active_lanes"] == ["cpu", "gpu"]
    assert result["events"] == []
    assert supervisor.stopped == []


def test_monitor_stops_only_overheated_hybrid_cpu_lane():
    supervisor = FakeSupervisor({"cpu", "gpu"})
    monitor = MiningSafetyMonitor(
        supervisor, FakeController(), FakeTelemetry(_snapshot(cpu=91, gpu=70))
    )
    result = monitor.check_once()
    assert [event["engine"] for event in result["events"]] == ["cpu"]
    assert supervisor.stopped == ["cpu"]
    assert supervisor.lanes == {"gpu"}


def test_monitor_stops_gpu_when_temperature_telemetry_disappears():
    snapshot = _snapshot()
    snapshot["gpu"]["devices"][0]["temperature_c"] = None
    supervisor = FakeSupervisor({"gpu"})
    monitor = MiningSafetyMonitor(supervisor, FakeController(), FakeTelemetry(snapshot))
    result = monitor.check_once()
    assert result["events"][0]["engine"] == "gpu"
    assert "temperature_telemetry_missing" in result["events"][0]["reason"]
    assert supervisor.stopped == ["gpu"]


def test_monitor_stops_direct_cpu_worker_when_cpu_sensor_is_missing():
    controller = FakeController({"status": "running", "miner_id": "xmrig", "device": "CPU"})
    snapshot = {"temperatures": {"available": False, "sensors": []},
                "gpu": {"available": False, "devices": []}}
    monitor = MiningSafetyMonitor(FakeSupervisor([]), controller, FakeTelemetry(snapshot))
    result = monitor.check_once()
    assert result["events"][0]["targets"] == ["direct_controller"]
    assert controller.stop_calls == 1


def test_monitor_stops_direct_both_device_worker_only_once_for_missing_cpu_sensor():
    controller = FakeController({"status": "running", "miner_id": "srbminer", "device": "BOTH"})
    snapshot = {"temperatures": {"available": False, "sensors": []},
                "gpu": {"available": False, "devices": []}}
    monitor = MiningSafetyMonitor(FakeSupervisor([]), controller, FakeTelemetry(snapshot))
    result = monitor.check_once()
    assert controller.stop_calls == 1
    assert result["events"][0]["targets"] == ["direct_controller"]


def test_monitor_stops_active_lane_when_telemetry_probe_raises():
    class BrokenTelemetry:
        def sample(self):
            raise OSError("sensor provider unavailable")

    supervisor = FakeSupervisor({"cpu"})
    monitor = MiningSafetyMonitor(supervisor, FakeController(), BrokenTelemetry())
    result = monitor.check_once()
    assert result["telemetry_error"] == "OSError"
    assert supervisor.stopped == ["cpu"]
    assert "telemetry_probe_failed" in result["events"][0]["reason"]


def test_reference_benchmark_is_external_and_never_claimed_as_local():
    import json
    from pathlib import Path

    path = Path(__file__).resolve().parents[1] / "mining" / "reference_benchmarks.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    record = payload["records"][0]
    assert record["algorithm"] == "RandomX"
    assert record["hashrate_hs"] == 1747.75
    assert record["measured_on_this_nexus_installation"] is False
    assert record["local_reproduction_required"] is True
    assert record["source_url"] == "https://xmrig.com/benchmark/5dq62x"



def test_reference_benchmark_is_external_and_not_local_measurement():
    import json
    from pathlib import Path

    path = Path(__file__).resolve().parents[1] / "mining" / "reference_benchmarks.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    record = payload["records"][0]
    assert record["algorithm"] == "RandomX"
    assert record["hashrate_hs"] == 1747.75
    assert record["measured_on_this_nexus_installation"] is False
    assert record["local_reproduction_required"] is True
    assert record["source_url"] == "https://xmrig.com/benchmark/5dq62x"
