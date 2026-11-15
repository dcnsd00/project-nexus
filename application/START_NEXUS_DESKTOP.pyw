"""NEXUS desktop shell with loopback-only dynamic port selection."""
from __future__ import annotations
import json, socket, threading, time, urllib.request
from pathlib import Path
import uvicorn
import webview
from nexus_master import app as nexus_app

ROOT = Path(__file__).resolve().parent
HOST = "127.0.0.1"
DEFAULT_PORT = 8765


def nexus_is_running(port: int = DEFAULT_PORT) -> bool:
    try:
        with urllib.request.urlopen(f"http://{HOST}:{port}/api/nexus/master", timeout=1.2) as r:
            data = json.loads(r.read().decode("utf-8"))
            return data.get("product") == "NEXUS"
    except Exception:
        return False


def choose_port() -> tuple[int, bool]:
    """Return (port, already_running); never bind to a non-loopback interface."""
    if nexus_is_running(DEFAULT_PORT):
        return DEFAULT_PORT, True
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind((HOST, DEFAULT_PORT))
            return DEFAULT_PORT, False
        except OSError:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as ephemeral:
                ephemeral.bind((HOST, 0))
                return int(ephemeral.getsockname()[1]), False


def wait_ready(port: int, timeout: float = 25.0) -> bool:
    end = time.time() + timeout
    while time.time() < end:
        if nexus_is_running(port):
            return True
        time.sleep(0.25)
    return False


def main():
    port, already_running = choose_port()
    url = f"http://{HOST}:{port}/api/nexus/dashboard"
    server = None
    if not already_running:
        config = uvicorn.Config(nexus_app, host=HOST, port=port, log_level="warning", access_log=False)
        server = uvicorn.Server(config)
        thread = threading.Thread(target=server.run, name="NEXUS-API", daemon=True)
        thread.start()
        if not wait_ready(port):
            raise RuntimeError(f"Motorul local NEXUS nu a pornit pe 127.0.0.1:{port} în 25 secunde. Verifică logs/desktop-launcher.log.")
    window = webview.create_window("NEXUS Control Center", url, width=1500, height=960,
                                   min_size=(1050, 700), background_color="#0b1220")
    if server is not None:
        window.events.closed += lambda: setattr(server, "should_exit", True)
    webview.start(gui="edgechromium", debug=False)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        log = ROOT / "logs" / "desktop-launcher.log"
        log.parent.mkdir(parents=True, exist_ok=True)
        with log.open("a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} | {type(exc).__name__}: {exc}\n")
