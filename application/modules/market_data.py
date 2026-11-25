"""Public, read-only market data adapters for NEXUS MASTER.

No credentials, private endpoints, orders, wallet access or transfers are supported.
All providers return source-attributed snapshots with explicit freshness metadata.
"""
from __future__ import annotations

import math
import os
import re
import time
from datetime import datetime, timezone
from typing import Any, Protocol

import httpx
from fastapi import APIRouter, HTTPException, Query

DEFAULT_BINANCE_BASE_URL = "https://data-api.binance.vision"
DEFAULT_GATE_BASE_URL = "https://api.gateio.ws/api/v4"
QUOTE = "USDT"
GATE_PAPER_ASSETS = ("BTC", "ETH", "SOL", "BNB", "XRP", "AIOZ", "GRASS", "TAO", "NEAR", "FIL")
WATCHLIST_ASSETS = ("BTC", "ETH", "SOL", "BNB", "XRP", "ZEC", "DOGE", "LINK")
SUPPORTED_ASSETS = tuple(dict.fromkeys((*GATE_PAPER_ASSETS, *WATCHLIST_ASSETS)))
INTERVALS = ("1m", "5m", "15m", "30m", "1h", "4h", "8h", "1d")

router = APIRouter(tags=["Public Market Data · Read Only"])


class MarketDataError(RuntimeError):
    """A normalized, provider-safe public market data failure."""

    def __init__(self, code: str, retry_after_s: float | None = None):
        super().__init__(code)
        self.code = code
        self.retry_after_s = retry_after_s


class ReadOnlyMarketDataProvider(Protocol):
    provider_id: str
    base_url: str

    def ticker(self, symbol: str) -> dict[str, Any]: ...
    def ticker_24h(self, symbol: str) -> dict[str, Any]: ...
    def klines(self, symbol: str, interval: str = "1h", limit: int = 100) -> dict[str, Any]: ...
    def order_book(self, symbol: str, limit: int = 20) -> dict[str, Any]: ...
    def recent_trades(self, symbol: str, limit: int = 50) -> dict[str, Any]: ...


def _asset(symbol: str) -> str:
    value = str(symbol or "").strip().upper()
    if not re.fullmatch(r"[A-Z0-9]{2,12}", value):
        raise MarketDataError("invalid_symbol")
    if value not in SUPPORTED_ASSETS:
        raise MarketDataError("symbol_not_supported")
    return value


def _number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _timestamp(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    try:
        number = float(value)
        if not math.isfinite(number) or number < 0:
            return None
        if number > 100_000_000_000:
            number /= 1000.0
        return datetime.fromtimestamp(number, tz=timezone.utc)
    except (TypeError, ValueError, OverflowError, OSError):
        return None


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


class _PublicProvider:
    provider_id = "public"
    default_base_url = ""

    def __init__(
        self,
        base_url: str | None = None,
        *,
        timeout: float = 8.0,
        max_retries: int = 2,
        stale_after_s: int = 180,
    ):
        if timeout <= 0 or max_retries < 0 or stale_after_s < 1:
            raise ValueError("invalid_market_data_client_limits")
        self.base_url = (base_url or self.default_base_url).rstrip("/")
        self.timeout = float(timeout)
        self.max_retries = int(max_retries)
        self.stale_after_s = int(stale_after_s)

    def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        headers = {
            "Accept": "application/json",
            "User-Agent": "NEXUS-MASTER-market-data/1.0",
        }
        for attempt in range(self.max_retries + 1):
            try:
                response = httpx.get(
                    self.base_url + path,
                    params=params,
                    timeout=self.timeout,
                    headers=headers,
                )
            except httpx.HTTPError as exc:
                if attempt < self.max_retries:
                    time.sleep(min(0.25 * (2 ** attempt), 2.0))
                    continue
                raise MarketDataError("network_error") from exc

            status = int(getattr(response, "status_code", 0) or 0)
            if status == 429 or 500 <= status <= 599:
                retry_after = _number(getattr(response, "headers", {}).get("Retry-After"))
                if attempt < self.max_retries:
                    delay = retry_after if retry_after is not None else 0.25 * (2 ** attempt)
                    time.sleep(min(max(delay, 0.0), 2.0))
                    continue
                raise MarketDataError(
                    "rate_limited" if status == 429 else "upstream_unavailable",
                    retry_after_s=retry_after,
                )
            if status >= 400:
                raise MarketDataError("upstream_rejected_request")
            try:
                response.raise_for_status()
                return response.json()
            except (httpx.HTTPError, ValueError, TypeError) as exc:
                raise MarketDataError("invalid_upstream_response") from exc
        raise MarketDataError("upstream_unavailable")

    def _snapshot(
        self,
        symbol: str,
        pair: str,
        endpoint: str,
        data: Any,
        source_timestamp: Any = None,
    ) -> dict[str, Any]:
        retrieved = datetime.now(timezone.utc)
        source_time = _timestamp(source_timestamp)
        if source_time is None:
            freshness = "unknown"
            stale = None
        else:
            age = (retrieved - source_time).total_seconds()
            freshness = "stale" if age > self.stale_after_s else "fresh"
            stale = freshness == "stale"
        return {
            "provider": self.provider_id,
            "symbol": symbol,
            "pair": pair,
            "quote": QUOTE,
            "data": data,
            "source": {
                "provider": self.provider_id,
                "base_url": self.base_url,
                "endpoint": endpoint,
            },
            "retrieved_at": retrieved.isoformat(),
            "source_timestamp": _iso(source_time),
            "freshness": freshness,
            "stale": stale,
            "stale_after_seconds": self.stale_after_s,
            "auth_required": False,
            "read_only": True,
        }


class BinancePublicMarketDataProvider(_PublicProvider):
    """Unauthenticated Binance Spot public market-data API."""

    provider_id = "binance"
    default_base_url = DEFAULT_BINANCE_BASE_URL

    @staticmethod
    def _pair(symbol: str) -> str:
        return f"{_asset(symbol)}_{QUOTE}".replace("_", "")

    def ticker(self, symbol: str) -> dict[str, Any]:
        asset = _asset(symbol)
        pair = self._pair(asset)
        endpoint = "/api/v3/ticker/price"
        row = self._get(endpoint, {"symbol": pair})
        if not isinstance(row, dict) or _number(row.get("price")) is None:
            raise MarketDataError("invalid_ticker_payload")
        return self._snapshot(asset, pair, endpoint, {
            "last_price": _number(row.get("price")),
            "exchange_symbol": row.get("symbol", pair),
        })

    def ticker_24h(self, symbol: str) -> dict[str, Any]:
        asset = _asset(symbol)
        pair = self._pair(asset)
        endpoint = "/api/v3/ticker/24hr"
        row = self._get(endpoint, {"symbol": pair})
        if not isinstance(row, dict) or _number(row.get("lastPrice")) is None:
            raise MarketDataError("invalid_ticker_payload")
        data = {
            "last_price": _number(row.get("lastPrice")),
            "price_change": _number(row.get("priceChange")),
            "price_change_pct": _number(row.get("priceChangePercent")),
            "weighted_avg_price": _number(row.get("weightedAvgPrice")),
            "open_price": _number(row.get("openPrice")),
            "high_price": _number(row.get("highPrice")),
            "low_price": _number(row.get("lowPrice")),
            "volume": _number(row.get("volume")),
            "quote_volume": _number(row.get("quoteVolume")),
            "trade_count": row.get("count"),
            "bid_price": _number(row.get("bidPrice")),
            "ask_price": _number(row.get("askPrice")),
        }
        return self._snapshot(asset, pair, endpoint, data, row.get("closeTime"))

    def klines(self, symbol: str, interval: str = "1h", limit: int = 100) -> dict[str, Any]:
        asset = _asset(symbol)
        if interval not in INTERVALS or not 1 <= int(limit) <= 1000:
            raise MarketDataError("invalid_kline_request")
        pair = self._pair(asset)
        endpoint = "/api/v3/klines"
        rows = self._get(endpoint, {"symbol": pair, "interval": interval, "limit": int(limit)})
        if not isinstance(rows, list):
            raise MarketDataError("invalid_kline_payload")
        candles = []
        for row in rows:
            if not isinstance(row, list) or len(row) < 8:
                raise MarketDataError("invalid_kline_payload")
            candles.append({
                "open_time": _iso(_timestamp(row[0])),
                "open": _number(row[1]), "high": _number(row[2]),
                "low": _number(row[3]), "close": _number(row[4]),
                "volume": _number(row[5]), "close_time": _iso(_timestamp(row[6])),
                "quote_volume": _number(row[7]),
                "trade_count": row[8] if len(row) > 8 else None,
            })
        source_time = rows[-1][6] if rows else None
        return self._snapshot(asset, pair, endpoint, {"interval": interval, "candles": candles}, source_time)

    def order_book(self, symbol: str, limit: int = 20) -> dict[str, Any]:
        asset = _asset(symbol)
        if not 5 <= int(limit) <= 1000:
            raise MarketDataError("invalid_order_book_limit")
        pair = self._pair(asset)
        endpoint = "/api/v3/depth"
        row = self._get(endpoint, {"symbol": pair, "limit": int(limit)})
        if not isinstance(row, dict) or not isinstance(row.get("bids"), list) or not isinstance(row.get("asks"), list):
            raise MarketDataError("invalid_order_book_payload")
        return self._snapshot(asset, pair, endpoint, {
            "last_update_id": row.get("lastUpdateId"),
            "bids": row["bids"], "asks": row["asks"],
        })

    def recent_trades(self, symbol: str, limit: int = 50) -> dict[str, Any]:
        asset = _asset(symbol)
        if not 1 <= int(limit) <= 1000:
            raise MarketDataError("invalid_trade_limit")
        pair = self._pair(asset)
        endpoint = "/api/v3/trades"
        rows = self._get(endpoint, {"symbol": pair, "limit": int(limit)})
        if not isinstance(rows, list):
            raise MarketDataError("invalid_trade_payload")
        source_time = rows[-1].get("time") if rows and isinstance(rows[-1], dict) else None
        return self._snapshot(asset, pair, endpoint, {"trades": rows}, source_time)


class GatePublicMarketDataProvider(_PublicProvider):
    """Unauthenticated Gate API v4 public spot market-data adapter."""

    provider_id = "gate"
    default_base_url = DEFAULT_GATE_BASE_URL

    @staticmethod
    def _pair(symbol: str) -> str:
        return f"{_asset(symbol)}_{QUOTE}"

    def tickers(self) -> list[dict[str, Any]]:
        rows = self._get("/spot/tickers", {"timezone": "utc0"})
        if not isinstance(rows, list):
            raise MarketDataError("invalid_ticker_payload")
        wanted = {f"{asset}_{QUOTE}" for asset in GATE_PAPER_ASSETS}
        return [row for row in rows if isinstance(row, dict) and row.get("currency_pair") in wanted]

    def orderbook(self, symbol: str, limit: int = 5) -> dict[str, Any]:
        return self._get("/spot/order_book", {
            "currency_pair": self._pair(symbol), "limit": int(limit)
        })

    def candles(self, symbol: str, interval: str = "15m", limit: int = 100) -> list:
        return self._get("/spot/candlesticks", {
            "currency_pair": self._pair(symbol), "interval": interval, "limit": int(limit)
        })

    def ticker(self, symbol: str) -> dict[str, Any]:
        asset = _asset(symbol)
        pair = self._pair(asset)
        endpoint = "/spot/tickers"
        rows = self._get(endpoint, {"currency_pair": pair})
        if not isinstance(rows, list) or not rows:
            raise MarketDataError("symbol_not_available")
        row = rows[0]
        data = {
            "last_price": _number(row.get("last")),
            "bid_price": _number(row.get("highest_bid")),
            "ask_price": _number(row.get("lowest_ask")),
            "change_24h_pct": _number(row.get("change_percentage")),
            "high_24h": _number(row.get("high_24h")),
            "low_24h": _number(row.get("low_24h")),
            "base_volume_24h": _number(row.get("base_volume")),
            "quote_volume_24h": _number(row.get("quote_volume")),
        }
        if data["last_price"] is None:
            raise MarketDataError("invalid_ticker_payload")
        return self._snapshot(asset, pair, endpoint, data, row.get("update"))

    def ticker_24h(self, symbol: str) -> dict[str, Any]:
        return self.ticker(symbol)

    def klines(self, symbol: str, interval: str = "1h", limit: int = 100) -> dict[str, Any]:
        asset = _asset(symbol)
        if interval not in INTERVALS or not 1 <= int(limit) <= 1000:
            raise MarketDataError("invalid_kline_request")
        pair = self._pair(asset)
        endpoint = "/spot/candlesticks"
        rows = self._get(endpoint, {"currency_pair": pair, "interval": interval, "limit": int(limit)})
        if not isinstance(rows, list):
            raise MarketDataError("invalid_kline_payload")
        candles = []
        for row in rows:
            if not isinstance(row, list) or len(row) < 6:
                raise MarketDataError("invalid_kline_payload")
            candles.append({
                "open_time": _iso(_timestamp(row[0])),
                "volume": _number(row[1]), "close": _number(row[2]),
                "high": _number(row[3]), "low": _number(row[4]),
                "open": _number(row[5]),
                "quote_volume": _number(row[6]) if len(row) > 6 else None,
                "trade_count": row[7] if len(row) > 7 else None,
            })
        source_time = rows[-1][0] if rows else None
        return self._snapshot(asset, pair, endpoint, {"interval": interval, "candles": candles}, source_time)

    def order_book(self, symbol: str, limit: int = 20) -> dict[str, Any]:
        asset = _asset(symbol)
        if not 1 <= int(limit) <= 100:
            raise MarketDataError("invalid_order_book_limit")
        pair = self._pair(asset)
        endpoint = "/spot/order_book"
        row = self._get(endpoint, {"currency_pair": pair, "limit": int(limit)})
        if not isinstance(row, dict) or not isinstance(row.get("bids"), list) or not isinstance(row.get("asks"), list):
            raise MarketDataError("invalid_order_book_payload")
        return self._snapshot(asset, pair, endpoint, {
            "current": row.get("current"), "update": row.get("update"),
            "bids": row["bids"], "asks": row["asks"],
        }, row.get("current"))

    def recent_trades(self, symbol: str, limit: int = 50) -> dict[str, Any]:
        asset = _asset(symbol)
        if not 1 <= int(limit) <= 1000:
            raise MarketDataError("invalid_trade_limit")
        pair = self._pair(asset)
        endpoint = "/spot/trades"
        rows = self._get(endpoint, {"currency_pair": pair, "limit": int(limit)})
        if not isinstance(rows, list):
            raise MarketDataError("invalid_trade_payload")
        latest = rows[-1] if rows and isinstance(rows[-1], dict) else {}
        source_time = latest.get("create_time_ms") or latest.get("create_time")
        return self._snapshot(asset, pair, endpoint, {"trades": rows}, source_time)


BINANCE_PUBLIC_PROVIDER = BinancePublicMarketDataProvider(
    base_url=os.environ.get("NEXUS_BINANCE_BASE_URL", DEFAULT_BINANCE_BASE_URL)
)
GATE_PUBLIC_PROVIDER = GatePublicMarketDataProvider(
    base_url=os.environ.get("NEXUS_GATE_BASE_URL", DEFAULT_GATE_BASE_URL)
)
PROVIDERS: dict[str, ReadOnlyMarketDataProvider] = {
    "binance": BINANCE_PUBLIC_PROVIDER,
    "gate": GATE_PUBLIC_PROVIDER,
}


def provider_status() -> dict[str, Any]:
    return {
        "providers": [
            {
                "id": provider.provider_id,
                "base_url": provider.base_url,
                "auth_required": False,
                "read_only": True,
                "write_capabilities": False,
                "supported_assets": list(SUPPORTED_ASSETS),
            }
            for provider in PROVIDERS.values()
        ],
        "network_calls_by_status_probe": False,
        "real_orders_enabled": False,
        "wallet_signing_enabled": False,
        "transfers_enabled": False,
    }


def _provider(name: str) -> ReadOnlyMarketDataProvider:
    provider = PROVIDERS.get(str(name or "").lower())
    if provider is None:
        raise HTTPException(status_code=404, detail="unknown_market_data_provider")
    return provider


def _call_provider(name: str, method: str, *args: Any, **kwargs: Any) -> dict[str, Any]:
    provider = _provider(name)
    try:
        return getattr(provider, method)(*args, **kwargs)
    except MarketDataError as exc:
        if exc.code == "symbol_not_supported":
            raise HTTPException(status_code=404, detail=exc.code) from exc
        if exc.code == "invalid_symbol":
            raise HTTPException(status_code=400, detail=exc.code) from exc
        if exc.code == "rate_limited":
            retry_after = max(1, int(math.ceil(exc.retry_after_s or 1)))
            raise HTTPException(
                status_code=429, detail=exc.code,
                headers={"Retry-After": str(retry_after)},
            ) from exc
        raise HTTPException(status_code=502, detail=exc.code) from exc


@router.get("/api/market-data/providers")
def market_data_providers():
    return provider_status()


@router.get("/api/market-data/{provider}/ticker/{symbol}")
def market_data_ticker(provider: str, symbol: str):
    return _call_provider(provider, "ticker", symbol)


@router.get("/api/market-data/{provider}/24h/{symbol}")
def market_data_24h(provider: str, symbol: str):
    return _call_provider(provider, "ticker_24h", symbol)


@router.get("/api/market-data/{provider}/klines/{symbol}")
def market_data_klines(
    provider: str,
    symbol: str,
    interval: str = Query(default="1h", pattern="^(1m|5m|15m|30m|1h|4h|8h|1d)$"),
    limit: int = Query(default=100, ge=1, le=1000),
):
    return _call_provider(provider, "klines", symbol, interval=interval, limit=limit)


@router.get("/api/market-data/{provider}/order-book/{symbol}")
def market_data_order_book(
    provider: str,
    symbol: str,
    limit: int = Query(default=20, ge=1, le=100),
):
    return _call_provider(provider, "order_book", symbol, limit=limit)


@router.get("/api/market-data/{provider}/trades/{symbol}")
def market_data_trades(
    provider: str,
    symbol: str,
    limit: int = Query(default=50, ge=1, le=1000),
):
    return _call_provider(provider, "recent_trades", symbol, limit=limit)
