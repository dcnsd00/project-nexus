import os

from mining.backend_adapters import (
    backend_catalog, discover_backends, evaluate_backend,
    normalize_telemetry, validate_launch_plan,
)


def test_backend_catalog_keeps_algorithm_specific_backend_profiles():
    rows = {x["backend_id"]: x for x in backend_catalog()}
    assert "RandomX" in rows["xmrig"]["algorithms"]
    assert "KawPoW" in rows["trex"]["algorithms"]
    assert rows["nerdminer"]["integration_kind"] == "device_protocol"


def test_backend_discovery_is_informational_and_does_not_claim_validation():
    rows = discover_backends(lambda name: "/opt/miners/xmrig" if name == "xmrig" else None)
    xmrig = next(x for x in rows if x["backend_id"] == "xmrig")
    assert xmrig["available"] is True
    assert xmrig["operationally_validated"] is False
    nerd = next(x for x in rows if x["backend_id"] == "nerdminer")
    assert nerd["discovery_status"] == "device_adapter_required"


def test_backend_algorithm_and_device_mismatch_are_blocked():
    assert evaluate_backend("xmrig", "RandomX", "CPU")["compatible"] is True
    result = evaluate_backend("xmrig", "RandomX", "GPU")
    assert result["compatible"] is False
    assert "device_class_not_supported_by_backend_profile" in result["reasons"]
    assert evaluate_backend("trex", "Etchash", "GPU")["compatible"] is False


def test_launch_plan_requires_absolute_allowlisted_executable_and_matching_argv(tmp_path):
    exe = tmp_path / "xmrig"
    exe.write_text("fake binary")
    valid = validate_launch_plan("xmrig", str(exe), [str(exe), "--version"])
    assert valid["valid"] is True
    assert valid["shell"] is False
    assert validate_launch_plan("xmrig", "xmrig", ["xmrig"])["valid"] is False
    other = tmp_path / "not-xmrig"
    other.write_text("fake")
    assert "executable_name_not_allowlisted" in validate_launch_plan(
        "xmrig", str(other), [str(other)]
    )["reasons"]


def test_launch_plan_rejects_argv_mismatch_and_nul_bytes(tmp_path):
    exe = tmp_path / "xmrig"
    exe.write_text("fake")
    assert "argv_executable_mismatch" in validate_launch_plan(
        "xmrig", str(exe), ["/tmp/other"]
    )["reasons"]
    assert "argv_must_be_nonempty_string_list" in validate_launch_plan(
        "xmrig", str(exe), [str(exe), "\x00"]
    )["reasons"]


def test_telemetry_normalizes_backend_aliases_without_inventing_values():
    data = normalize_telemetry("xmrig", {
        "hashrate": 1250, "accepted": 4, "rejected": 1,
        "temp": 62, "watts": 45, "authorized": True,
    })
    assert data["hashrate_hs"] == 1250.0
    assert data["accepted_shares"] == 4
    assert data["rejected_shares"] == 1
    assert data["power_w"] == 45.0
    assert data["pool_connected"] is None


def test_unknown_backend_telemetry_is_rejected():
    import pytest
    with pytest.raises(ValueError):
        normalize_telemetry("ghost", {})


def test_telemetry_rejects_non_finite_metrics_and_counts():
    data = normalize_telemetry("xmrig", {
        "hashrate_hs": float("inf"),
        "accepted_shares": float("nan"),
        "rejected_shares": float("inf"),
        "temperature_c": float("nan"),
        "power_w": 80,
    })
    assert data["hashrate_hs"] is None
    assert data["accepted_shares"] is None
    assert data["rejected_shares"] is None
    assert data["temperature_c"] is None
    assert data["power_w"] == 80.0
