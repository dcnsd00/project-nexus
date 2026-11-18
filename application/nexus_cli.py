"""Read-only operator CLI for the local NEXUS MASTER control plane.

Examples:
  python nexus_cli.py status
  python nexus_cli.py modules
  python nexus_cli.py telemetry --history 30
  python nexus_cli.py mining
  python nexus_cli.py edge
  python nexus_cli.py all

This CLI issues GET requests only. It never starts/stops miners, unlocks
wallets, submits transactions, or changes security configuration.
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


DEFAULT_BASE_URL = "http://127.0.0.1:8765"
COMMAND_ENDPOINTS: dict[str, tuple[str, ...]] = {
    "status": (
        "/api/nexus/master",
        "/api/nexus/runtime",
        "/api/nexus/readiness",
    ),
    "modules": (
        "/api/nexus/module-registry",
        "/api/nexus/module-registry/health",
    ),
    "mining": (
        "/api/mining/status",
        "/api/mining/hardware",
        "/api/mining/processes",
        "/api/mining/diagnostics",
    ),
    "edge": (
        "/api/nexus/runtime",
        "/api/edge/transports",
        "/api/edge/gateway",
        "/api/edge/topology",
    ),
    "operator": ("/api/nexus/operator",),
    "blockchain": ("/api/blockchain/nodes/bitcoin", "/api/blockchain/nodes/evm"),
}


def _read_json(base_url: str, path: str, timeout: float) -> dict[str, Any]:
    url = base_url.rstrip("/") + path
    request = Request(url, headers={
        "Accept": "application/json",
        "User-Agent": "NEXUS-Operator-CLI/1.0",
    }, method="GET")
    try:
        with urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
            return {
                "ok": True,
                "http_status": getattr(response, "status", 200),
                "data": payload,
            }
    except HTTPError as exc:
        try:
            detail = exc.read().decode("utf-8", errors="replace")[:2000]
        except Exception:
            detail = str(exc)
        return {"ok": False, "http_status": exc.code, "error": detail}
    except (URLError, TimeoutError, OSError) as exc:
        reason = getattr(exc, "reason", exc)
        return {
            "ok": False,
            "error": f"{type(exc).__name__}: {reason}",
            "hint": "Verifică dacă NEXUS MASTER rulează pe adresa configurată.",
        }
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return {"ok": False, "error": f"Invalid JSON response: {exc}"}


def _endpoints(command: str, history: int) -> tuple[str, ...]:
    if command == "operator":
        return COMMAND_ENDPOINTS["operator"]
    if command == "telemetry":
        return (f"/api/nexus/telemetry?history={history}",)
    if command == "all":
        return tuple(dict.fromkeys(
            path
            for group in ("status", "modules", "mining", "edge", "blockchain", "operator")
            for path in COMMAND_ENDPOINTS[group]
        )) + (f"/api/nexus/telemetry?history={history}",)
    return COMMAND_ENDPOINTS[command]


def collect(command: str, *, base_url: str = DEFAULT_BASE_URL,
            timeout: float = 5.0, history: int = 30) -> dict[str, Any]:
    """Collect read-only status data from the local NEXUS MASTER API."""
    if command not in {*COMMAND_ENDPOINTS, "telemetry", "all"}:
        raise ValueError(f"unsupported command: {command}")
    if not 1 <= history <= 300:
        raise ValueError("history must be between 1 and 300")
    results = {
        path: _read_json(base_url, path, timeout)
        for path in _endpoints(command, history)
    }
    return {
        "product": "NEXUS",
        "command": command,
        "base_url": base_url.rstrip("/"),
        "read_only": True,
        "successful_endpoints": sum(item["ok"] for item in results.values()),
        "failed_endpoints": sum(not item["ok"] for item in results.values()),
        "results": results,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="NEXUS operator CLI — read-only status and telemetry"
    )
    parser.add_argument(
        "command", choices=("status", "modules", "telemetry", "mining", "edge", "blockchain", "operator", "all")
    )
    parser.add_argument("--url", default=DEFAULT_BASE_URL,
                        help=f"MASTER API base URL (default: {DEFAULT_BASE_URL})")
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument("--history", type=int, default=30,
                        help="telemetry history samples, 1-300")
    args = parser.parse_args(argv)

    if args.timeout <= 0:
        parser.error("--timeout must be positive")
    try:
        report = collect(args.command, base_url=args.url,
                         timeout=args.timeout, history=args.history)
    except ValueError as exc:
        parser.error(str(exc))
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    return 0 if report["failed_endpoints"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
