from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]


def test_one_click_installer_and_frozen_desktop_entrypoint_exist():
    assert (ROOT / "INSTALL_NEXUS.bat").is_file()
    assert (ROOT / "INSTALL_NEXUS_ONECLICK.ps1").is_file()
    launcher = (ROOT / "START_NEXUS_DESKTOP.pyw").read_text(encoding="utf-8")
    assert "--self-test" in launcher
    assert "TestClient(nexus_app)" in launcher
    assert "127.0.0.1" in launcher


def test_frozen_spec_bundles_runtime_resources():
    spec = (ROOT / "packaging" / "NEXUS_DESKTOP.spec").read_text(encoding="utf-8")
    for package in ("nexus_edge", "research", "tools", "core", "modules", "mining"):
        assert f"ROOT/'{package}'" in spec or f"ROOT/'{package}'" in spec.replace(" ", "")
    assert "START_NEXUS_DESKTOP.pyw" in spec


def test_dashboard_version_matches_package_manifest():
    version = json.loads((ROOT / "VERSION.json").read_text(encoding="utf-8"))["version"]
    html = (ROOT / "dashboard.html").read_text(encoding="utf-8")
    assert version == "0.10.26"
    assert f"CONTROL CENTER · {version}" in html
    assert f">{version}<" in html
