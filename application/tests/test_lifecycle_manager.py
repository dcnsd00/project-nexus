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
