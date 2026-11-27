from pathlib import Path
import json
import runpy
import socket
import sys
import types

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_one_click_installer_and_frozen_desktop_entrypoint_exist():
    assert (ROOT / "INSTALL_NEXUS.bat").is_file()
    assert (ROOT / "INSTALL_NEXUS_ONECLICK.ps1").is_file()
    launcher = (ROOT / "START_NEXUS_DESKTOP.pyw").read_text(encoding="utf-8")
    assert "--self-test" in launcher
    assert "TestClient(nexus_app)" in launcher
    assert "127.0.0.1" in launcher
    assert "opening NEXUS in the default browser" in launcher


def test_frozen_spec_bundles_runtime_resources():
    spec = (ROOT / "packaging" / "NEXUS_DESKTOP.spec").read_text(encoding="utf-8")
    for package in ("nexus_edge", "research", "tools", "core", "modules", "mining"):
        assert f"ROOT/'{package}'" in spec or f"ROOT/'{package}'" in spec.replace(" ", "")
    assert "START_NEXUS_DESKTOP.pyw" in spec


def test_dashboard_version_matches_package_manifest():
    version = json.loads((ROOT / "VERSION.json").read_text(encoding="utf-8"))["version"]
    html = (ROOT / "dashboard.html").read_text(encoding="utf-8")
    assert version == "0.10.27"
    assert f"CONTROL CENTER · {version}" in html
    assert f">{version}<" in html


def _load_desktop_launcher(monkeypatch, *, webview_error=None, browser_result=True):
    uvicorn = types.ModuleType("uvicorn")
    uvicorn.Config = lambda *args, **kwargs: object()
    uvicorn.Server = type("Server", (), {})
    webview = types.ModuleType("webview")
    webview.create_window = lambda *args, **kwargs: types.SimpleNamespace(
        events=types.SimpleNamespace(closed=types.SimpleNamespace(__iadd__=lambda self, cb: self))
    )
    if webview_error:
        def fail_start(*args, **kwargs):
            raise webview_error
        webview.start = fail_start
    else:
        webview.start = lambda *args, **kwargs: None
    browser = types.ModuleType("webbrowser")
    browser.open = lambda *args, **kwargs: browser_result
    nexus_master = types.ModuleType("nexus_master")
    nexus_master.app = object()
    monkeypatch.setitem(sys.modules, "uvicorn", uvicorn)
    monkeypatch.setitem(sys.modules, "webview", webview)
    monkeypatch.setitem(sys.modules, "webbrowser", browser)
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


def test_pythonnet_or_webview_failure_falls_back_to_default_browser(monkeypatch, tmp_path):
    launcher = _load_desktop_launcher(
        monkeypatch, webview_error=RuntimeError("Python.Runtime.Loader.Initialize failed")
    )
    launcher["ROOT"] = tmp_path

    class Server:
        should_exit = False

    assert launcher["launch_desktop_ui"](Server(), "http://127.0.0.1:8765/api/nexus/dashboard") == "browser"
    log = (tmp_path / "logs" / "desktop-launcher.log").read_text(encoding="utf-8")
    assert "Python.Runtime.Loader.Initialize failed" in log
    assert "default browser" in log


def test_browser_fallback_failure_is_reported(monkeypatch, tmp_path):
    launcher = _load_desktop_launcher(
        monkeypatch, webview_error=RuntimeError("pythonnet failure"), browser_result=False
    )
    launcher["ROOT"] = tmp_path

    class Server:
        should_exit = False

    with pytest.raises(RuntimeError, match="browserul implicit"):
        launcher["launch_desktop_ui"](Server(), "http://127.0.0.1:8765/api/nexus/dashboard")


def test_windows_desktop_package_runs_on_main_and_preserves_existing_triggers():
    workflow_path = ROOT.parent / ".github" / "workflows" / "nexus-desktop-package.yml"
    if not workflow_path.is_file():
        pytest.skip("GitHub workflow definitions are not included in the Windows runtime artifact")
    workflow = workflow_path.read_text(encoding="utf-8")
    assert 'branches: ["main", "feature/edge-replay-protection-sqlite-v1", "feature/nexus-ai-worker-mining-safety-v1"]' in workflow
    assert "pull_request:" in workflow
    assert "workflow_dispatch:" in workflow
