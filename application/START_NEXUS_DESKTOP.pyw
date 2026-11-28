"""NEXUS desktop shell with a resilient embedded/browser UI fallback."""
from __future__ import annotations

import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path

import uvicorn
from nexus_master import app as nexus_app

ROOT = Path(__file__).resolve().parent
HOST = "127.0.0.1"
DEFAULT_PORT = 8765


def write_launcher_log(message: str) -> None:
    log = ROOT / "logs" / "desktop-launcher.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a", encoding="utf-8") as stream:
        stream.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} | {message}\n")


def run_packaged_self_test() -> int:
    """Exercise the frozen app's real API, dashboard, and version manifest."""
    from fastapi.testclient import TestClient

    with TestClient(nexus_app) as client:
        manifest = client.get("/api/nexus/master")
        if manifest.status_code != 200:
            raise RuntimeError(f"master manifest HTTP {manifest.status_code}")
        metadata = manifest.json()
        if metadata.get("product") != "NEXUS" or not metadata.get("version"):
            raise RuntimeError("NEXUS master manifest is invalid")
        dashboard = client.get("/api/nexus/dashboard")
        if dashboard.status_code != 200:
            raise RuntimeError(f"desktop dashboard HTTP {dashboard.status_code}")
        html = dashboard.text
        required_ui = (
            "NEXUS Control Center",
            'data-tab="mining"',
            'data-tab="research"',
            'id="apiStatus"',
        )
        missing = [item for item in required_ui if item not in html]
        if missing:
            raise RuntimeError("Desktop UI resources missing: " + ", ".join(missing))
        if metadata.get("modules", {}).get("desktop_shell", {}).get("present") is not True:
            raise RuntimeError("Desktop shell is not present in the packaged app")
        print("NEXUS_PACKAGED_SELF_TEST_OK")
        print(f"version={metadata['version']}; dashboard_bytes={len(html.encode('utf-8'))}")
    return 0


def choose_listener() -> tuple[int, socket.socket]:
    """Reserve a loopback listener; never attach to an unverified process."""
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        listener.bind((HOST, DEFAULT_PORT))
    except OSError:
        listener.close()
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.bind((HOST, 0))
    listener.listen(socket.SOMAXCONN)
    listener.setblocking(False)
    return int(listener.getsockname()[1]), listener


def wait_ready(server: uvicorn.Server, thread: threading.Thread,
               timeout: float = 25.0) -> bool:
    """Wait for this process's Uvicorn server, not an unauthenticated HTTP banner."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if server.started:
            return True
        if not thread.is_alive():
            return False
        time.sleep(0.05)
    return bool(server.started)


def launch_desktop_ui(server: uvicorn.Server, url: str) -> str:
    """Prefer the embedded window; fall back to the system browser on GUI/CLR failure."""
    try:
        # Import lazily: pythonnet/CLR initialization occurs in the Windows GUI backend.
        import webview

        window = webview.create_window(
            "NEXUS Control Center",
            url,
            width=1500,
            height=960,
            min_size=(1050, 700),
            background_color="#0b1220",
        )
        window.events.closed += lambda: setattr(server, "should_exit", True)
        webview.start(gui="edgechromium", debug=False)
        return "embedded"
    except Exception as exc:
        write_launcher_log(
            f"Embedded WebView unavailable ({type(exc).__name__}: {exc}); "
            "opening NEXUS in the default browser."
        )
        if not webbrowser.open(url, new=1, autoraise=True):
            raise RuntimeError(
                "Nici fereastra integrată, nici browserul implicit nu au putut fi pornite. "
                "Verifică logs/desktop-launcher.log."
            ) from exc
        return "browser"


def main():
    if "--self-test" in sys.argv[1:]:
        return run_packaged_self_test()

    port, listener = choose_listener()
    url = f"http://{HOST}:{port}/api/nexus/dashboard"
    config = uvicorn.Config(
        nexus_app, host=HOST, port=port, log_level="warning", access_log=False
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(
        target=server.run,
        kwargs={"sockets": [listener]},
        name="NEXUS-API",
        daemon=True,
    )
    thread.start()
    if not wait_ready(server, thread):
        server.should_exit = True
        listener.close()
        raise RuntimeError(
            f"Motorul local NEXUS nu a pornit pe 127.0.0.1:{port} în 25 secunde."
        )

    mode = launch_desktop_ui(server, url)
    if mode == "browser":
        # The browser does not expose a portable window-closed event. Keep the
        # loopback API alive while the fallback dashboard is in use.
        while thread.is_alive():
            thread.join(timeout=1.0)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        write_launcher_log(f"FATAL {type(exc).__name__}: {exc}")
        raise
