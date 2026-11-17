import json
import time
import pytest
from nexus_edge.transports import MQTTBridge, MQTTConfig, NetworkPath, TransportKind, transport_matrix
from nexus_edge.topology import DeploymentMode, DeploymentTopology

class FakeResult:
    rc = 0

class FakeMessage:
    topic = "nexus/v1/nodes/esp32-node-01/up"
    payload = b'{"sequence":1}'

class FakeClient:
    def __init__(self, **kwargs):
        self.kwargs=kwargs; self.calls=[]; self.on_message=None
    def username_pw_set(self,*args): self.calls.append(("auth",args))
    def tls_set(self,**kwargs): self.calls.append(("tls",kwargs))
    def tls_insecure_set(self,value): self.calls.append(("tls_insecure",value))
    def connect(self,*args): self.calls.append(("connect",args))
    def loop_start(self): self.calls.append(("loop_start",))
    def subscribe(self,*args,**kwargs): self.calls.append(("subscribe",args,kwargs))
    def publish(self,*args,**kwargs): self.calls.append(("publish",args,kwargs)); return FakeResult()
    def disconnect(self): self.calls.append(("disconnect",))
    def loop_stop(self): self.calls.append(("loop_stop",))

def test_network_paths_map_to_explicit_transport_types():
    matrix=transport_matrix()
    assert matrix[NetworkPath.LAN.value] == [TransportKind.HTTPS.value,TransportKind.MQTTS.value]
    assert matrix[NetworkPath.WAN.value] == matrix[NetworkPath.MOBILE_DATA.value]
    assert matrix[NetworkPath.LORAWAN.value] == [TransportKind.LORAWAN_WEBHOOK.value]

def test_mqtt_bridge_uses_tls_and_subscribes_to_node_uplink():
    client=FakeClient(); received=[]
    bridge=MQTTBridge(MQTTConfig(host="broker.example",client_id="nexus-test"),
                      lambda topic,body: received.append((topic,body)),
                      client_factory=lambda **kwargs: client)
    bridge.start()
    assert ("tls_insecure",False) in client.calls
    assert any(call[0]=="subscribe" for call in client.calls)
    bridge._handle_message(client,None,FakeMessage())
    assert received[0][1] == {"sequence":1}
    bridge.publish_downlink("esp32-node-01",{"task":"telemetry"})
    assert any(call[0]=="publish" for call in client.calls)
    bridge.stop()
    assert bridge.started is False

def test_mqtt_bridge_rejects_invalid_tls_client_cert_pair():
    with pytest.raises(ValueError,match="supplied together"):
        MQTTConfig(host="broker.example",client_id="nexus-test",
                   client_cert="client.crt").validate()

def test_active_active_rejects_local_sqlite():
    topology=DeploymentTopology(DeploymentMode.ACTIVE_ACTIVE,2,"sqlite",True,True)
    with pytest.raises(ValueError,match="not local SQLite"):
        topology.validate()

def test_two_server_primary_standby_requires_shared_or_replicated_backend():
    topology=DeploymentTopology(DeploymentMode.PRIMARY_STANDBY,2,"postgresql",True,False)
    topology.validate()
    bad=DeploymentTopology(DeploymentMode.PRIMARY_STANDBY,2,"sqlite")
    with pytest.raises(ValueError,match="replicated/shared"):
        bad.validate()

def test_mqtt_uplink_requires_node_hmac_and_monotonic_sequence():
    from nexus_edge.transports import authenticate_mqtt_uplink
    from nexus_edge.manager import EdgeManager, sign_message
    from nexus_edge.replay_guard import MemoryReplayGuard
    manager=EdgeManager(replay_guard=MemoryReplayGuard())
    secret=b"n"*32
    manager.register_node("esp32-node-09",["telemetry"],secret)
    timestamp=int(time.time())
    payload={"temperature_c":23.5}
    message={"kind":"node_request","action":"mqtt.uplink","node_id":"esp32-node-09",
             "timestamp":timestamp,"sequence":1,"payload":payload}
    body={"timestamp":timestamp,"sequence":1,"payload":payload,
          "signature":sign_message(secret,message)}
    topic="nexus/v1/nodes/esp32-node-09/up"
    assert authenticate_mqtt_uplink(manager,topic,body)["accepted"] is True
    with pytest.raises(ValueError,match="replayed|out-of-order"):
        authenticate_mqtt_uplink(manager,topic,body)

def test_mqtt_uplink_rejects_unexpected_topic():
    from nexus_edge.transports import authenticate_mqtt_uplink
    with pytest.raises(ValueError,match="topic"):
        authenticate_mqtt_uplink(object(),"other/topic",{})
