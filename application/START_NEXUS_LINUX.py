"""Linux browser launcher for the NEXUS local-first desktop runtime."""
from __future__ import annotations

import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path

import uvicorn
from nexus_master import app as nexus_app

HOST = "127.0.0.1"
DEFAULT_PORT = 8765


def choose_listener() -> tuple[int, socket.socket]:
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


def self_test() -> int:
    from fastapi.testclient import TestClient

    with TestClient(nexus_app) as client:
        manifest = client.get("/api/nexus/master")
        dashboard = client.get("/api/nexus/dashboard")
        if manifest.status_code != 200 or dashboard.status_code != 200:
            raise RuntimeError("NEXUS API/dashboard self-test failed")
        data = manifest.json()
        if data.get("product") != "NEXUS" or not data.get("version"):
            raise RuntimeError("NEXUS manifest invalid")
        if "NEXUS Control Center" not in dashboard.text:
            raise RuntimeError("NEXUS dashboard content missing")
    print("NEXUS_LINUX_SELF_TEST_OK")
    return 0


def main() -> int:
    if "--self-test" in sys.argv[1:]:
        return self_test()

    port, listener = choose_listener()
    url = f"http://{HOST}:{port}/api/nexus/dashboard"
    config = uvicorn.Config(nexus_app, host=HOST, port=port, log_level="warning", access_log=False)
    server = uvicorn.Server(config)
    thread = threading.Thread(
        target=server.run, kwargs={"sockets": [listener]},
        name="NEXUS-API", daemon=True,
    )
    thread.start()
    deadline = time.monotonic() + 25
    while time.monotonic() < deadline and thread.is_alive() and not server.started:
        time.sleep(0.05)
    if not server.started:
        server.should_exit = True
        listener.close()
        raise RuntimeError("NEXUS local API did not start within 25 seconds")
    print(f"NEXUS dashboard: {url}", flush=True)
    webbrowser.open(url)
    try:
        while thread.is_alive():
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        server.should_exit = True
        listener.close()
        thread.join(timeout=10)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
