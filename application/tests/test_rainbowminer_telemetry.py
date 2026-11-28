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
