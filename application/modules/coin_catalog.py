from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

CACHE = Path(__file__).resolve().parents[1] / "data" / "coinpaprika_coins.json"
BUNDLED = Path(__file__).resolve().parents[1] / "mining" / "coins.json"
URL = "https://api.coinpaprika.com/v1/coins"
CACHE_TTL_SECONDS = 6 * 3600
REQUEST_TIMEOUT_SECONDS = 12
USER_AGENT = "NEXUS-Crypto-Catalog/0.10.21"


def _normalize_remote(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, list):
        raise ValueError("Unexpected CoinPaprika response: expected a list")
    compact = []
    for item in payload:
        if not isinstance(item, dict) or not item.get("id") or not item.get("symbol"):
            continue
        compact.append({
            "id": item.get("id"), "name": item.get("name"),
            "symbol": item.get("symbol"), "rank": item.get("rank"),
            "type": item.get("type"), "is_active": item.get("is_active"),
            "is_new": item.get("is_new"),
        })
    if not compact:
        raise ValueError("CoinPaprika response contains no valid coin records")
    return compact


def _read_cache() -> tuple[list[dict[str, Any]] | None, float | None, str | None]:
    if not CACHE.is_file():
        return None, None, None
    try:
        raw = json.loads(CACHE.read_text(encoding="utf-8"))
        if isinstance(raw, dict) and isinstance(raw.get("coins"), list):
            coins = _normalize_remote(raw["coins"])
            fetched_at = raw.get("fetched_at")
            fetched_at = float(fetched_at) if isinstance(fetched_at, (int, float)) else CACHE.stat().st_mtime
            source = str(raw.get("source") or "CoinPaprika cached catalog")
            return coins, fetched_at, source
        # Backward compatibility with the previous format (plain list).
        coins = _normalize_remote(raw)
        return coins, CACHE.stat().st_mtime, "CoinPaprika legacy cache"
    except Exception:
        return None, None, "cache_invalid"


def _write_cache(coins: list[dict[str, Any]], fetched_at: float) -> None:
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    payload = {"schema_version": 2, "source": "CoinPaprika API", "fetched_at": fetched_at, "coins": coins}
    temp = CACHE.with_suffix(CACHE.suffix + ".tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    os.replace(temp, CACHE)


def _bundled_fallback() -> list[dict[str, Any]]:
    if not BUNDLED.is_file():
        return []
    raw = json.loads(BUNDLED.read_text(encoding="utf-8"))
    rows = raw.get("coins", []) if isinstance(raw, dict) else raw
    if not isinstance(rows, list):
        return []
    result = []
    for item in rows:
        if not isinstance(item, dict) or not item.get("symbol") or not item.get("name"):
            continue
        result.append({
            "id": None, "name": item.get("name"), "symbol": item.get("symbol"),
            "rank": None, "type": "coin", "is_active": None, "is_new": None,
            "algorithm": item.get("algorithm"), "pow_mineable": item.get("pow_mineable"),
            "device_classes": item.get("device_classes", []),
            "preferred_hardware": item.get("preferred_hardware"),
            "catalog_source": "NEXUS bundled mining catalogue",
        })
    return result


def get_coins(force: bool = False) -> dict[str, Any]:
    """Fetch CoinPaprika; on network failure serve stale cache, then NEXUS bundled data.

    A stale/fallback response is always explicitly marked so clients cannot mistake
    it for fresh CoinPaprika data. Cache writes are atomic and only happen after a
    complete, validated response.
    """
    now = time.time()
    cached, fetched_at, cache_source = _read_cache()
    if cached is not None and fetched_at is not None and not force and now - fetched_at < CACHE_TTL_SECONDS:
        return {
            "source": "CoinPaprika cached catalog", "cached": True, "stale": False,
            "fallback": False, "age_seconds": max(0, int(now - fetched_at)), "coins": cached,
        }

    req = urllib.request.Request(URL, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            if response.status != 200:
                raise RuntimeError(f"CoinPaprika HTTP {response.status}")
            payload = json.loads(response.read().decode("utf-8"))
        compact = _normalize_remote(payload)
        fetched_at = time.time()
        _write_cache(compact, fetched_at)
        return {
            "source": "CoinPaprika API", "cached": False, "stale": False,
            "fallback": False, "age_seconds": 0, "coins": compact,
        }
    except (OSError, TimeoutError, ValueError, RuntimeError, urllib.error.URLError, json.JSONDecodeError) as exc:
        error = f"{type(exc).__name__}: {str(exc)[:240]}"
        if cached is not None:
            age = max(0, int(now - (fetched_at or CACHE.stat().st_mtime)))
            return {
                "source": cache_source or "CoinPaprika stale cache", "cached": True,
                "stale": True, "fallback": True, "age_seconds": age,
                "warning": "CoinPaprika indisponibil; este servit ultimul cache valid.",
                "upstream_error": error, "coins": cached,
            }
        bundled = _bundled_fallback()
        if bundled:
            return {
                "source": "NEXUS bundled mining catalogue", "cached": True,
                "stale": True, "fallback": True, "age_seconds": None,
                "warning": "CoinPaprika indisponibil și nu există cache; sunt afișate doar intrările incluse în catalogul local NEXUS.",
                "upstream_error": error, "coins": bundled,
            }
        raise RuntimeError(f"CoinPaprika unavailable and no local fallback exists: {error}") from exc
