import base64
import time
import pytest
from fastapi.testclient import TestClient
from nexus_edge.gateway import create_edge_app
from nexus_edge.manager import EdgeManager, sign_message
from nexus_edge.replay_guard import MemoryReplayGuard

def _envelope(secret, node_id, action, seq, payload=None, timestamp=None):
    timestamp = int(time.time()) if timestamp is None else timestamp
    payload = payload or {}
    message = {"kind":"node_request","action":action,"node_id":node_id,
               "timestamp":timestamp,"sequence":seq,"payload":payload}
    return {"timestamp":timestamp,"sequence":seq,"payload":payload,
            "signature":sign_message(secret,message)}

def test_gateway_requires_strong_operator_token():
    with pytest.raises(RuntimeError):
        create_edge_app(EdgeManager(), provisioning_token="short")

def test_gateway_provisions_node_and_requires_operator_token():
    manager=EdgeManager(replay_guard=MemoryReplayGuard())
    client=TestClient(create_edge_app(manager, provisioning_token="p"*40))
    denied=client.post("/v1/edge/nodes/provision",json={"node_id":"esp32-node-01","capabilities":["telemetry"]})
    assert denied.status_code==401
    ok=client.post("/v1/edge/nodes/provision",headers={"Authorization":"Bearer "+"p"*40},
                   json={"node_id":"esp32-node-01","capabilities":["telemetry"]})
    assert ok.status_code==200
    secret=base64.urlsafe_b64decode(ok.json()["node_secret_b64url"])
    assert len(secret)==32
    assert ok.json()["secret_delivery"].startswith("one_time_response")

def test_gateway_rejects_replayed_or_invalid_node_requests():
    manager=EdgeManager(replay_guard=MemoryReplayGuard())
    client=TestClient(create_edge_app(manager, provisioning_token="p"*40))
    secret=b"s"*32
    manager.register_node("esp32-node-02",["telemetry"],secret)
    heartbeat=_envelope(secret,"esp32-node-02","heartbeat",1)
    assert client.post("/v1/edge/nodes/esp32-node-02/heartbeat",json=heartbeat).status_code==200
    body=_envelope(secret,"esp32-node-02","claim_task",2)
    first=client.post("/v1/edge/nodes/esp32-node-02/claim",json=body)
    assert first.status_code==200
    replay=client.post("/v1/edge/nodes/esp32-node-02/claim",json=body)
    assert replay.status_code==401

def test_gateway_signed_payload_is_bound_to_requested_task():
    manager=EdgeManager(replay_guard=MemoryReplayGuard())
    client=TestClient(create_edge_app(manager, provisioning_token="p"*40))
    secret=b"s"*32
    manager.register_node("esp32-node-03",["telemetry"],secret)
    body=_envelope(secret,"esp32-node-03","start_task",1,{"task_id":"different"})
    response=client.post("/v1/edge/nodes/esp32-node-03/tasks/task-123/start",json=body)
    assert response.status_code==400

def test_gateway_reports_transport_matrix_without_claiming_external_connectivity():
    client=TestClient(create_edge_app(EdgeManager(), provisioning_token="p"*40))
    response=client.get("/v1/edge/transports")
    assert response.status_code==200
    body=response.json()
    assert body["https_gateway"]=="active_in_this_process"
    assert body["mqtts"]=="adapter_available_opt_in_not_started"
    assert body["lorawan_webhook"].endswith("network_server_not_configured")
    assert body["lan_wan_mobile_data"].startswith("same_https_api")
