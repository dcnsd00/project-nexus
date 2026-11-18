import pytest
from modules.lifecycle_manager import LifecycleManager, ServiceSpec, LifecycleError

class Dummy:
    def __init__(self, events, name, healthy=True): self.events, self.name, self.healthy = events, name, healthy
    def initialize(self): self.events.append(self.name + ":init")
    def start(self): self.events.append(self.name + ":start")
    def health_check(self): return self.healthy
    def stop(self): self.events.append(self.name + ":stop")
    def shutdown(self): self.events.append(self.name + ":shutdown")

def test_dependency_order_and_reverse_shutdown():
    events=[]; m=LifecycleManager()
    m.register(ServiceSpec("api", lambda: Dummy(events,"api"), ("db",)))
    m.register(ServiceSpec("db", lambda: Dummy(events,"db")))
    snap=m.start_all()
    assert snap["system_ready"] is True
    assert snap["lifecycle_order"] == ["db","api"]
    m.stop_all()
    assert events.index("api:stop") < events.index("db:stop")

def test_startup_failure_rolls_back_started_services():
    events=[]; m=LifecycleManager()
    m.register(ServiceSpec("db", lambda: Dummy(events,"db")))
    m.register(ServiceSpec("api", lambda: Dummy(events,"api",False), ("db",)))
    with pytest.raises(LifecycleError): m.start_all()
    assert "db:stop" in events and "db:shutdown" in events
    assert m.snapshot()["system_ready"] is False

def test_dependency_cycle_rejected():
    m=LifecycleManager()
    m.register(ServiceSpec("a", lambda: Dummy([],"a"), ("b",)))
    m.register(ServiceSpec("b", lambda: Dummy([],"b"), ("a",)))
    with pytest.raises(LifecycleError): m.start_all()


def test_optional_service_failure_does_not_stop_independent_services():
    events = []
    m = LifecycleManager()
    m.register(ServiceSpec("core", lambda: Dummy(events, "core")))
    m.register(ServiceSpec(
        "optional_bad", lambda: Dummy(events, "optional_bad", False),
        ("core",), critical=False
    ))
    m.register(ServiceSpec(
        "optional_child", lambda: Dummy(events, "optional_child"),
        ("optional_bad",), critical=False
    ))
    m.register(ServiceSpec(
        "optional_independent", lambda: Dummy(events, "optional_independent"),
        critical=False
    ))

    snap = m.start_all()
    states = {row["name"]: row["state"] for row in snap["services"]}

    assert snap["system_ready"] is True
    assert states["core"] == "running"
    assert states["optional_bad"] == "failed"
    assert states["optional_child"] == "blocked"
    assert states["optional_independent"] == "running"
    assert "core:stop" not in events
    assert "optional_child:start" not in events
    assert "optional_bad:stop" in events
    assert "optional_bad:shutdown" in events


def test_optional_factory_exception_is_recorded_and_startup_continues():
    events = []
    m = LifecycleManager()
    m.register(ServiceSpec("core", lambda: Dummy(events, "core")))

    def broken_factory():
        raise RuntimeError("optional adapter unavailable")

    m.register(ServiceSpec("optional_broken", broken_factory, critical=False))
    m.register(ServiceSpec(
        "optional_independent", lambda: Dummy(events, "optional_independent"),
        critical=False
    ))

    snap = m.start_all()
    states = {row["name"]: row["state"] for row in snap["services"]}
    errors = {row["name"]: row["error"] for row in snap["services"]}

    assert snap["system_ready"] is True
    assert states["core"] == "running"
    assert states["optional_broken"] == "failed"
    assert "optional adapter unavailable" in errors["optional_broken"]
    assert states["optional_independent"] == "running"


def test_critical_service_blocked_by_failed_optional_dependency_aborts_startup():
    events = []
    m = LifecycleManager()
    m.register(ServiceSpec("core", lambda: Dummy(events, "core")))
    m.register(ServiceSpec(
        "optional_dependency", lambda: Dummy(events, "optional_dependency", False),
        ("core",), critical=False
    ))
    m.register(ServiceSpec(
        "critical_consumer", lambda: Dummy(events, "critical_consumer"),
        ("optional_dependency",), critical=True
    ))

    with pytest.raises(LifecycleError, match="critical service critical_consumer blocked"):
        m.start_all()

    states = {row["name"]: row["state"] for row in m.snapshot()["services"]}
    assert states["optional_dependency"] == "failed"
    assert states["critical_consumer"] == "blocked"
    assert states["core"] == "stopped"
    assert "core:stop" in events


def test_get_service_instance_requires_running_service():
    events = []
    instance = Dummy(events, "shared")
    manager = LifecycleManager()
    manager.register(ServiceSpec("shared", lambda: instance))

    with pytest.raises(LifecycleError, match="service is not running"):
        manager.get_service_instance("shared")

    manager.start_all()
    assert manager.get_service_instance("shared") is instance
    manager.stop_all()

    with pytest.raises(LifecycleError, match="service is not running"):
        manager.get_service_instance("shared")


def test_lifecycle_snapshot_reports_measured_startup_and_uptime():
    import os

    events = []
    manager = LifecycleManager()
    manager.register(ServiceSpec("measured", lambda: Dummy(events, "measured")))

    started = manager.start_all()
    row = started["services"][0]
    assert row["state"] == "running"
    assert row["started_at_utc"]
    assert row["startup_duration_seconds"] is not None
    assert row["startup_duration_seconds"] >= 0
    assert row["uptime_seconds"] is not None
    assert row["uptime_seconds"] >= 0
    assert row["shared_process_pid"] == os.getpid()
    assert row["individual_process_pid"] is None

    stopped = manager.stop_all()["services"][0]
    assert stopped["state"] == "stopped"
    assert stopped["stopped_at_utc"]
    assert stopped["uptime_seconds"] is not None
    assert stopped["uptime_seconds"] >= 0
