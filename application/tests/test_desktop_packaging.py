from pathlib import Path
import json
import runpy
import socket
import sys
import types

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


def _load_desktop_launcher(monkeypatch):
    uvicorn = types.ModuleType("uvicorn")
    uvicorn.Config = lambda *args, **kwargs: object()
    uvicorn.Server = type("Server", (), {})
    webview = types.ModuleType("webview")
    webview.create_window = lambda *args, **kwargs: None
    webview.start = lambda *args, **kwargs: None
    nexus_master = types.ModuleType("nexus_master")
    nexus_master.app = object()
    monkeypatch.setitem(sys.modules, "uvicorn", uvicorn)
    monkeypatch.setitem(sys.modules, "webview", webview)
    monkeypatch.setitem(sys.modules, "nexus_master", nexus_master)
    return runpy.run_path(str(ROOT / "START_NEXUS_DESKTOP.pyw"))


def test_desktop_launcher_never_attaches_to_an_unverified_loopback_service(monkeypatch):
    launcher = _load_desktop_launcher(monkeypatch)
    assert "nexus_is_running" not in launcher
    occupied = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    occupied.bind(("127.0.0.1", 0))
    occupied.listen(socket.SOMAXCONN)
    occupied_port = occupied.getsockname()[1]
    launcher["DEFAULT_PORT"] = occupied_port
    try:
        port, listener = launcher["choose_listener"]()
        try:
            assert port != occupied_port
            assert listener.getsockname() == ("127.0.0.1", port)
        finally:
            listener.close()
    finally:
        occupied.close()


def test_desktop_launcher_readiness_uses_its_own_server_state(monkeypatch):
    launcher = _load_desktop_launcher(monkeypatch)

    class Server:
        started = True

    class Thread:
        def is_alive(self):
            return True

    assert launcher["wait_ready"](Server(), Thread(), timeout=0.01) is True

    class StoppedServer:
        started = False

    class StoppedThread:
        def is_alive(self):
            return False

    assert launcher["wait_ready"](StoppedServer(), StoppedThread(), timeout=1.0) is False

