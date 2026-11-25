import json
from pathlib import Path


def test_headscale_example_policy_is_valid_json_and_explicit_deny_all():
    policy_path = (
        Path(__file__).resolve().parents[2]
        / "deployment"
        / "security"
        / "headscale"
        / "policy.example.hujson"
    )
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    assert policy == {"grants": []}


def test_headscale_policy_template_contains_no_private_key_material():
    policy_path = (
        Path(__file__).resolve().parents[2]
        / "deployment"
        / "security"
        / "headscale"
        / "policy.example.hujson"
    )
    text = policy_path.read_text(encoding="utf-8").lower()
    assert "privatekey" not in text
    assert "private_key" not in text
    assert "authkey" not in text
    assert "preauthkey" not in text
