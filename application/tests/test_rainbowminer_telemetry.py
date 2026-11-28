import json
from urllib.parse import urlencode

import pytest
from fastapi.testclient import TestClient

from modules import rainbowminer_telemetry as telemetry
from nexus_master import app


def _test_data_path(tmp_path):
    db = tmp_path / "nexus-data" / "mining" / "rainbowminer_telemetry.sqlite3"

    def path(*parts, create_parent=False):
        if create_parent:
            db.parent.mkdir(parents=True, exist_ok=True)
        return db

    return db, path


def test_report_requires_operator_provisioned_key(monkeypatch):
    monkeypatch.delenv("NEXUS_RAINBOWMINER_REPORT_KEY", raising=False)
    with TestClient(app, base_url="http://127.0.0.1",
                    client=("127.0.0.1", 51234)) as client:
        response = client.post(
            "/api/mining/rainbowminer/report",
            data={"user": "any-key", "worker": "test-rig"},
        )
    assert response.status_code == 503
    assert response.json()["detail"] == "rainbowminer_ingest_not_configured"


def test_authenticated_form_report_is_sanitized_and_persisted(monkeypatch, tmp_path):
    db, path = _test_data_path(tmp_path)
    monkeypatch.setattr(telemetry, "data_path", path)
    monkeypatch.setenv("NEXUS_RAINBOWMINER_REPORT_KEY", "test-report-secret")
    report = {
        "user": "test-report-secret",
        "worker": "rig-one",
        "machinename": "private-machine-name",
        "machineip": "192.0.2.11",
        "email": "private@example.invalid",
        "pushoverkey": "private-pushover-key",
        "console": "private console output",
        "profit": "0.0001",
        "powerdraw": "120",
        "cputemp": "64.5",
        "status": "Running",
        "data": json.dumps([{
            "Name": "test-miner",
            "Algorithm": ["RandomX"],
            "CurrentSpeed": [1000],
            "Accepted": [12],
            "Rejected": [1],
            "Path": "C:/private/path/miner.exe",
        }]),
        "devices": json.dumps([{
            "Name": "GPU 0",
            "Temperature": 62,
            "PowerDraw": 75,
            "SerialNumber": "private-serial",
        }]),
        "pool_totals": json.dumps([{"Pool": ["pool.example"], "Accepted": [12]}]),
        "rates": json.dumps({"BTC": 1.0, "RON": 100000.0}),
        "crashdata": json.dumps([{"Name": "miner", "Path": "C:/private/path"}]),
    }
    with TestClient(app, base_url="http://127.0.0.1",
                    client=("127.0.0.1", 51235)) as client:
        response = client.post(
            "/api/mining/rainbowminer/report",
            content=urlencode(report),
            headers={"content-type": "application/x-www-form-urlencoded"},
        )
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["accepted"] is True
    assert result["miner_records"] == 1
    assert result["device_records"] == 1
    assert result["credentials_persisted"] is False
    assert db.is_file()

    import sqlite3
    with sqlite3.connect(str(db)) as connection:
        stored = connection.execute(
            "SELECT payload_json FROM rainbowminer_reports"
        ).fetchone()[0]
    assert "test-report-secret" not in stored
    assert "private@example.invalid" not in stored
    assert "private-pushover-key" not in stored
    assert "private console output" not in stored
    assert "private-machine-name" not in stored
    assert "192.0.2.11" not in stored
    assert "C:/private/path" not in stored
    assert "private-serial" not in stored
    assert '"worker":"rig-one"' in stored


def test_bad_key_and_non_loopback_client_are_rejected(monkeypatch):
    monkeypatch.setenv("NEXUS_RAINBOWMINER_REPORT_KEY", "correct-secret")
    with TestClient(app, base_url="http://127.0.0.1",
                    client=("127.0.0.1", 51236)) as client:
        bad_key = client.post(
            "/api/mining/rainbowminer/report",
            data={"user": "wrong-secret", "worker": "rig"},
        )
    assert bad_key.status_code == 401

    with TestClient(app, base_url="http://127.0.0.1",
                    client=("192.0.2.8", 51237)) as client:
        remote = client.post(
            "/api/mining/rainbowminer/report",
            data={"user": "correct-secret", "worker": "rig"},
        )
    assert remote.status_code == 403


def test_json_report_normalization_drops_sensitive_fields():
    normalized = telemetry.normalize_report({
        "worker": "safe-worker",
        "user": "must-not-persist",
        "console": "must-not-persist",
        "data": [{
            "Name": "miner-a",
            "Accepted": [20],
            "Path": "private/path",
            "Password": "secret",
        }],
    })
    encoded = json.dumps(normalized)
    assert "must-not-persist" not in encoded
    assert "private/path" not in encoded
    assert "secret" not in encoded
    assert normalized["data"][0] == {"Name": "miner-a", "Accepted": [20]}


def test_report_body_size_limit_is_enforced():
    with pytest.raises(telemetry.RainbowMinerReportError, match="report_too_large"):
        telemetry._parse_request_body(
            b"x" * (telemetry.MAX_REPORT_BYTES + 1),
            "application/x-www-form-urlencoded",
        )


def test_report_normalizes_documented_nested_devices_and_pool_totals():
    normalized = telemetry.normalize_report({
        "worker": "device-rig",
        "uncleanalert": "0",
        "data": [{
            "Name": "miner-a",
            "Algorithm": ["KawPow"],
            "CurrentSpeed": [12.5],
            "Devices": [{"Id": 0, "Name": "GPU 0", "Watt": 100, "Temp": 65,
                         "Mem": 8, "Fan": 55, "Core": 1700, "MemC": 7000,
                         "MaxTemp": 70, "PrivatePath": "must-drop"}],
        }],
        "devices": {
            "GPU#0": {"Name": "GPU 0", "Watt": 100, "Temp": 65,
                      "Mem": 8, "Fan": 55, "Core": 1700, "MemC": 7000,
                      "MaxTemp": 70, "SerialNumber": "must-drop"},
        },
        "pool_totals": {
            "pool.example": {"Accepted": 12, "Rejected": 1,
                             "Profit": 0.0001, "ApiKey": "must-drop"},
        },
    })
    assert normalized["uncleanalert"] is False
    assert normalized["data"][0]["Devices"][0]["Id"] == 0
    assert normalized["devices"][0]["Id"] == "GPU#0"
    assert normalized["pool_totals"][0]["Pool"] == "pool.example"
    encoded = json.dumps(normalized)
    assert "must-drop" not in encoded
    assert "SerialNumber" not in encoded
    assert "ApiKey" not in encoded


def test_rainbowminer_minerdata_and_poolsdata_multipart_uploads(monkeypatch, tmp_path):
    db, path = _test_data_path(tmp_path)
    monkeypatch.setattr(telemetry, "data_path", path)
    monkeypatch.setenv("NEXUS_RAINBOWMINER_REPORT_KEY", "extra-report-secret")

    minerdata = {
        "Miners": [{
            "Name": "miner-a",
            "Version": "1.2.3",
            "Algorithm": "KawPow",
            "DeviceName": "GPU#0",
            "DeviceModel": "NVIDIA GTX 1650",
            "HashRate": 12.5,
            "PowerDraw": 75,
            "OCProfile": "profile-1",
            "Path": "private/miner.exe",
        }],
        "OCprofiles": {"profile-1": {"private_setting": "must-not-persist"}},
        "CPU": "Test CPU Model",
    }
    poolsdata = [
        {
            "Name": "pool.example",
            "Algorithm": "SHA256",
            "CoinSymbol": "BTC",
            "Price": 100.0,
            "StablePrice": 95.0,
            "PenaltyFactor": 1.02,
            "ErrorRatio": 0.01,
            "ApiKey": "must-not-persist",
        }
    ]

    with TestClient(app, base_url="http://127.0.0.1",
                    client=("127.0.0.1", 51240)) as client:
        miner_response = client.post(
            "/api/mining/rainbowminer/report",
            data={"user": "extra-report-secret", "worker": "rig-extra", "version": "1.0"},
            files={"minerdata": ("minerdata.json", json.dumps(minerdata).encode(), "application/json")},
        )
        pool_response = client.post(
            "/api/mining/rainbowminer/report",
            data={"user": "extra-report-secret", "worker": "rig-extra", "version": "1.0"},
            files={"poolsdata": ("poolsdata.json", json.dumps(poolsdata).encode(), "application/json")},
        )
        latest_miners = client.get("/api/mining/rainbowminer/miners/latest?worker=rig-extra")
        latest_pools = client.get("/api/mining/rainbowminer/pools/latest?worker=rig-extra")
        status = client.get("/api/mining/rainbowminer/status")

    assert miner_response.status_code == 200, miner_response.text
    assert pool_response.status_code == 200, pool_response.text
    assert miner_response.json()["payload_type"] == "minerdata"
    assert pool_response.json()["payload_type"] == "poolsdata"
    assert miner_response.json()["Status"] == "OK"
    assert miner_response.json()["Actions"] == []
    assert latest_miners.status_code == 200
    assert latest_pools.status_code == 200
    miner_payload = latest_miners.json()["payload"]
    pool_payload = latest_pools.json()["payload"]
    assert miner_payload["miners"][0]["HashRate"] == 12.5
    assert miner_payload["cpu_model"] == "Test CPU Model"
    assert "OCProfile" not in miner_payload["miners"][0]
    assert pool_payload["pools"][0]["Price"] == 100.0
    assert pool_payload["pools"][0]["StablePrice"] == 95.0
    assert status.json()["extra_reports_stored"] == {"minerdata": 1, "poolsdata": 1}

    stored = db.read_text() if False else None
    import sqlite3
    with sqlite3.connect(str(db)) as connection:
        contents = connection.execute(
            "SELECT payload_json FROM rainbowminer_extra_reports"
        ).fetchall()
    encoded = json.dumps([row[0] for row in contents])
    assert "extra-report-secret" not in encoded
    assert "private/miner.exe" not in encoded
    assert "must-not-persist" not in encoded
    assert "ApiKey" not in encoded


def test_rainbowminer_extra_upload_rejects_invalid_json_and_oversized_files():
    with pytest.raises(telemetry.RainbowMinerReportError, match="invalid_extra_payload_json"):
        telemetry.normalize_extra_payload("poolsdata", b"not-json", worker="rig")
    with pytest.raises(telemetry.RainbowMinerReportError, match="extra_payload_too_large"):
        telemetry.normalize_extra_payload(
            "minerdata",
            b"x" * (telemetry.MAX_EXTRA_PAYLOAD_BYTES + 1),
            worker="rig",
        )
