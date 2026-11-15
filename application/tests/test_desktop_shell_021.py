import importlib.machinery
import importlib.util
import socket
import sys
import types
from pathlib import Path


def _load_launcher(monkeypatch):
    fake_webview = types.ModuleType('webview')
    fake_webview.create_window = lambda *a, **k: None
    fake_webview.start = lambda *a, **k: None
    monkeypatch.setitem(sys.modules, 'webview', fake_webview)
    root = Path(__file__).resolve().parents[1]
    path = root / 'START_NEXUS_DESKTOP.pyw'
    loader = importlib.machinery.SourceFileLoader('nexus_desktop_launcher_test', str(path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def test_desktop_shell_uses_loopback_and_finds_alternate_port_when_default_busy(monkeypatch):
    module = _load_launcher(monkeypatch)
    assert module.HOST == '127.0.0.1'
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as occupied:
        occupied.bind((module.HOST, 0))
        occupied.listen(1)
        busy_port = occupied.getsockname()[1]
        monkeypatch.setattr(module, 'DEFAULT_PORT', busy_port)
        monkeypatch.setattr(module, 'nexus_is_running', lambda port: False)
        port, already_running = module.choose_port()
        assert already_running is False
        assert port != busy_port
        assert 1 <= port <= 65535


def test_desktop_shell_reuses_existing_nexus_on_default_port(monkeypatch):
    module = _load_launcher(monkeypatch)
    monkeypatch.setattr(module, 'nexus_is_running', lambda port: port == module.DEFAULT_PORT)
    port, already_running = module.choose_port()
    assert port == module.DEFAULT_PORT and already_running is True
