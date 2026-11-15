"""Bounded Stratum V1 subscribe/authorize diagnostic; does not request mining work."""
from __future__ import annotations
import json, re, socket, ssl, time
from typing import Any

class StratumProbeError(RuntimeError):
    pass

_HOST = re.compile(r"^[A-Za-z0-9.-]{1,253}$")

def _read_response(sock: socket.socket, expected_id: int, deadline: float) -> dict[str, Any]:
    buf = b""
    while time.monotonic() < deadline:
        try:
            chunk = sock.recv(4096)
        except socket.timeout:
            continue
        if not chunk:
            break
        buf += chunk
        while b"\n" in buf:
            line, buf = buf.split(b"\n", 1)
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line.decode("utf-8"))
            except Exception:
                continue
            if isinstance(obj, dict) and obj.get("id") == expected_id:
                return obj
    raise StratumProbeError(f"Timeout/închidere înainte de răspunsul Stratum pentru id={expected_id}.")

def probe_stratum(host: str, port: int, username: str, password: str = "x", use_tls: bool = False, timeout: float = 5.0) -> dict[str, Any]:
    if not isinstance(host, str) or not _HOST.fullmatch(host) or ".." in host:
        raise ValueError("Host Stratum invalid.")
    if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535:
        raise ValueError("Port Stratum invalid.")
    if not isinstance(username, str) or not 3 <= len(username) <= 256 or any(c.isspace() for c in username):
        raise ValueError("Username/worker invalid.")
    if not isinstance(password, str) or len(password) > 128:
        raise ValueError("Password pool invalid.")
    timeout = max(1.0, min(float(timeout), 8.0))
    started = time.perf_counter()
    context = ssl.create_default_context() if use_tls else None
    try:
        raw = socket.create_connection((host, port), timeout=timeout)
        raw.settimeout(0.5)
        conn = context.wrap_socket(raw, server_hostname=host) if context else raw
        with conn:
            conn.sendall((json.dumps({"id": 1, "method": "mining.subscribe", "params": ["NEXUS/0.10.6"]}) + "\n").encode())
            subscribe = _read_response(conn, 1, time.monotonic() + timeout)
            if subscribe.get("error"):
                return {"ok": False, "tcp_reachable": True, "tls": bool(use_tls), "subscribed": False,
                        "authorized": False, "stage": "subscribe", "error": str(subscribe.get("error"))[:300],
                        "latency_ms": round((time.perf_counter()-started)*1000, 2), "no_work_requested": True}
            conn.sendall((json.dumps({"id": 2, "method": "mining.authorize", "params": [username, password]}) + "\n").encode())
            auth = _read_response(conn, 2, time.monotonic() + timeout)
            authorized = auth.get("result") is True and not auth.get("error")
            return {"ok": authorized, "tcp_reachable": True, "tls": bool(use_tls), "subscribed": True,
                    "authorized": authorized, "stage": "authorized" if authorized else "authorize_rejected",
                    "server_extranonce": (subscribe.get("result") or [None, None])[1] if isinstance(subscribe.get("result"), list) and len(subscribe.get("result")) > 1 else None,
                    "error": auth.get("error"), "latency_ms": round((time.perf_counter()-started)*1000, 2),
                    "no_work_requested": True, "scope": "Stratum subscribe + authorize only; no mining.notify job processing and no share submitted."}
    except Exception as exc:
        return {"ok": False, "tcp_reachable": False, "tls": bool(use_tls), "subscribed": False,
                "authorized": False, "stage": "connect_or_protocol_error", "error": f"{type(exc).__name__}: {str(exc)[:220]}",
                "latency_ms": round((time.perf_counter()-started)*1000, 2), "no_work_requested": True}
