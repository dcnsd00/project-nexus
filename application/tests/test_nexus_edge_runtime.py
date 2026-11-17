import json
from nexus_edge.runtime import EdgeTransportRuntime

class _Config:
    pass

class _Bridge:
    def __init__(self, config, callback):
        self.callback=callback; self.started=False; self.stops=0
    def start(self): self.started=True
    def stop(self): self.started=False; self.stops+=1

def test_edge_runtime_is_disabled_without_explicit_opt_in():
    calls=[]
    runtime=EdgeTransportRuntime(env={},manager_factory=lambda: calls.append("manager"),bridge_factory=_Bridge)
    runtime.start()
    assert calls == []
    assert runtime.status()["mqtts"] == "disabled_by_default"

def test_edge_runtime_starts_only_after_explicit_opt_in(monkeypatch):
    from nexus_edge import runtime as module
    from nexus_edge.transports import MQTTConfig
    env={"NEXUS_EDGE_MQTT_ENABLED":"true","NEXUS_EDGE_MQTT_HOST":"broker.example","NEXUS_EDGE_MQTT_CLIENT_ID":"nexus-runtime-test"}
    created=[]
    runtime=EdgeTransportRuntime(env=env,manager_factory=lambda: object(),bridge_factory=lambda cfg,cb: created.append(_Bridge(cfg,cb)) or created[-1])
    # Exercise lifecycle without a live broker; replace only the bridge configuration reader.
    monkeypatch.setattr("nexus_edge.transports.mqtt_config_from_env",lambda values: MQTTConfig(host="broker.example",client_id="nexus-runtime-test"))
    runtime.start()
    assert len(created)==1 and created[0].started
    assert runtime.status()["connected"] is True
    runtime.stop()
    assert created[0].started is False and created[0].stops==1
