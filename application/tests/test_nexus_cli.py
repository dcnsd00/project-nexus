import json
from urllib.error import URLError

import nexus_cli


class FakeResponse:
    status = 200

    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return json.dumps(self.body).encode("utf-8")


def test_cli_status_collects_master_runtime_and_readiness(monkeypatch):
    requested = []

    def fake_urlopen(request, timeout):
        requested.append((request.full_url, request.get_method(), timeout))
        return FakeResponse({"ready": True})

    monkeypatch.setattr(nexus_cli, "urlopen", fake_urlopen)
    result = nexus_cli.collect("status", base_url="http://127.0.0.1:9000")

    assert result["successful_endpoints"] == 3
    assert result["failed_endpoints"] == 0
    assert all(method == "GET" for _, method, _ in requested)
    assert [url.rsplit(":", 1)[-1] for url, _, _ in requested] == [
        "9000/api/nexus/master", "9000/api/nexus/runtime",
        "9000/api/nexus/readiness",
    ]


def test_cli_telemetry_respects_bounded_history(monkeypatch):
    requested = []

    def fake_urlopen(request, timeout):
        requested.append(request.full_url)
        return FakeResponse({"snapshot": {}, "history": []})

    monkeypatch.setattr(nexus_cli, "urlopen", fake_urlopen)
    result = nexus_cli.collect("telemetry", history=120)

    assert result["successful_endpoints"] == 1
    assert requested == ["http://127.0.0.1:8765/api/nexus/telemetry?history=120"]


def test_cli_reports_master_unavailable_without_crashing(monkeypatch):
    def fake_urlopen(request, timeout):
        raise URLError("connection refused")

    monkeypatch.setattr(nexus_cli, "urlopen", fake_urlopen)
    result = nexus_cli.collect("edge")

    assert result["failed_endpoints"] == 3
    assert result["successful_endpoints"] == 0
    assert all("hint" in row for row in result["results"].values())


def test_cli_rejects_out_of_range_history():
    import pytest

    with pytest.raises(ValueError, match="history must be between 1 and 300"):
        nexus_cli.collect("telemetry", history=301)


def test_cli_all_uses_only_read_only_get_endpoints(monkeypatch):
    requested = []

    def fake_urlopen(request, timeout):
        requested.append(request.get_method())
        return FakeResponse({})

    monkeypatch.setattr(nexus_cli, "urlopen", fake_urlopen)
    result = nexus_cli.collect("all")

    assert result["failed_endpoints"] == 0
    assert len(requested) >= 10
    assert set(requested) == {"GET"}
