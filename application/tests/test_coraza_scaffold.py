from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def test_coraza_pilot_is_loopback_only_and_detection_only():
    caddyfile = (_repo_root() / "deployment/security/coraza/Caddyfile").read_text(
        encoding="utf-8"
    )
    assert "http://127.0.0.1:8780" in caddyfile
    assert "bind 127.0.0.1" in caddyfile
    assert "reverse_proxy 127.0.0.1:8765" in caddyfile
    assert "SecRuleEngine DetectionOnly" in caddyfile


def test_coraza_audit_parts_omit_request_data_and_matched_rules():
    caddyfile = (_repo_root() / "deployment/security/coraza/Caddyfile").read_text(
        encoding="utf-8"
    )
    assert "SecAuditLogParts AHZ" in caddyfile
    assert "SecAuditLogParts AB" not in caddyfile
    assert "SecAuditLogParts K" not in caddyfile


def test_caddy_access_logs_redact_common_query_secrets_and_keep_json():
    caddyfile = (_repo_root() / "deployment/security/coraza/Caddyfile").read_text(
        encoding="utf-8"
    )
    assert "format filter {" in caddyfile
    assert "request>uri query {" in caddyfile
    assert "wrap json" in caddyfile
    for key in ("access_token", "refresh_token", "id_token", "api_key", "client_secret", "password"):
        assert f"replace {key} REDACTED" in caddyfile


def test_caddy_rolled_access_logs_are_uncompressed_and_crowdsec_matches_them():
    caddyfile = (_repo_root() / "deployment/security/coraza/Caddyfile").read_text(
        encoding="utf-8"
    )
    acquisition = (
        _repo_root() / "deployment/security/crowdsec/acquis-windows.yaml.example"
    ).read_text(encoding="utf-8")
    assert "roll_uncompressed" in caddyfile
    assert "access*.log" in acquisition
    assert "access.log*" not in acquisition
