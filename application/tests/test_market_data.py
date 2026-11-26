import time

import pytest

from modules import market_data


class FakeResponse:
    def __init__(self, payload, status_code=200, headers=None):
        self.payload = payload
        self.status_code = status_code
        self.headers = headers or {}

    def json(self):
        return self.payload

    def raise_for_status(self):
        return None


def test_binance_ticker_and_24h_snapshot_include_source_and_freshness(monkeypatch):
    now_ms = int(time.time() * 1000)
    calls = []

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        if url.endswith("/api/v3/ticker/price"):
            return FakeResponse({"symbol": "BTCUSDT", "price": "65000.5"})
        if url.endswith("/api/v3/ticker/24hr"):
            return FakeResponse({
                "symbol": "BTCUSDT", "lastPrice": "65000.5",
                "priceChange": "100", "priceChangePercent": "0.15",
                "weightedAvgPrice": "64900", "openPrice": "64900",
                "highPrice": "66000", "lowPrice": "64000",
                "volume": "12", "quoteVolume": "780000",
                "count": 123, "bidPrice": "65000", "askPrice": "65001",
                "closeTime": now_ms,
            })
        raise AssertionError(url)

    monkeypatch.setattr(market_data.httpx, "get", fake_get)
    client = market_data.BinancePublicMarketDataProvider(max_retries=0)

    ticker = client.ticker("BTC")
    stats = client.ticker_24h("BTC")

    assert ticker["data"]["last_price"] == 65000.5
    assert ticker["freshness"] == "unknown"
    assert stats["data"]["price_change_pct"] == 0.15
    assert stats["freshness"] == "fresh"
    assert stats["source"]["provider"] == "binance"
    assert stats["auth_required"] is False
    assert stats["read_only"] is True
    assert all("Authorization" not in call[1]["headers"] for call in calls)


def test_gate_ticker_uses_public_ticker_and_reports_upstream_timestamp(monkeypatch):
    now_s = int(time.time())

    def fake_get(url, **kwargs):
        assert url.endswith("/spot/tickers")
        assert kwargs["params"]["currency_pair"] == "BTC_USDT"
        return FakeResponse([{
            "currency_pair": "BTC_USDT", "last": "65000",
            "highest_bid": "64999", "lowest_ask": "65001",
            "change_percentage": "1.2", "high_24h": "66000",
            "low_24h": "64000", "base_volume": "12",
            "quote_volume": "780000", "update": str(now_s),
        }])

    monkeypatch.setattr(market_data.httpx, "get", fake_get)
    client = market_data.GatePublicMarketDataProvider(max_retries=0)
    snapshot = client.ticker("BTC")

    assert snapshot["data"]["last_price"] == 65000
    assert snapshot["data"]["bid_price"] == 64999
    assert snapshot["freshness"] == "fresh"
    assert snapshot["source_timestamp"] is not None


def test_binance_klines_order_book_and_recent_trades_are_normalized(monkeypatch):
    now_ms = int(time.time() * 1000)
    payloads = [
        [[now_ms - 3_600_000, "10", "12", "9", "11", "100", now_ms, "1100", 20]],
        {"lastUpdateId": 123, "bids": [["10", "2"]], "asks": [["11", "3"]]},
        [{"id": 1, "price": "10.5", "qty": "2", "time": now_ms, "isBuyerMaker": False}],
    ]

    def fake_get(url, **kwargs):
        return FakeResponse(payloads.pop(0))

    monkeypatch.setattr(market_data.httpx, "get", fake_get)
    client = market_data.BinancePublicMarketDataProvider(max_retries=0)

    candles = client.klines("BTC", interval="1h", limit=1)
    book = client.order_book("BTC", limit=20)
    trades = client.recent_trades("BTC", limit=1)

    assert candles["data"]["candles"][0]["close"] == 11
    assert candles["data"]["candles"][0]["trade_count"] == 20
    assert book["data"]["last_update_id"] == 123
    assert book["data"]["bids"] == [["10", "2"]]
    assert trades["data"]["trades"][0]["price"] == "10.5"
    assert trades["freshness"] == "fresh"


def test_gate_klines_order_book_and_recent_trades_are_normalized(monkeypatch):
    now_s = int(time.time())
    payloads = [
        [[str(now_s), "100", "11", "12", "9", "10", "1100", "true"]],
        {"current": now_s, "update": 1, "bids": [["10", "2"]], "asks": [["11", "3"]]},
        [{"id": 1, "price": "10.5", "amount": "2", "create_time": str(now_s), "side": "buy"}],
    ]

    def fake_get(url, **kwargs):
        return FakeResponse(payloads.pop(0))

    monkeypatch.setattr(market_data.httpx, "get", fake_get)
    client = market_data.GatePublicMarketDataProvider(max_retries=0)

    candles = client.klines("BTC", interval="1h", limit=1)
    book = client.order_book("BTC", limit=20)
    trades = client.recent_trades("BTC", limit=1)

    assert candles["data"]["candles"][0]["close"] == 11
    assert candles["data"]["candles"][0]["quote_volume"] == 100
    assert candles["data"]["candles"][0]["volume"] == 1100
    assert candles["data"]["candles"][0]["window_closed"] is True
    assert book["data"]["bids"] == [["10", "2"]]
    assert book["freshness"] == "fresh"
    assert trades["data"]["trades"][0]["side"] == "buy"
    assert trades["freshness"] == "fresh"


def test_public_provider_retries_429_and_respects_retry_after(monkeypatch):
    responses = [
        FakeResponse({}, status_code=429, headers={"Retry-After": "0"}),
        FakeResponse({"symbol": "BTCUSDT", "price": "65000"}),
    ]
    sleeps = []

    def fake_get(url, **kwargs):
        return responses.pop(0)

    monkeypatch.setattr(market_data.httpx, "get", fake_get)
    monkeypatch.setattr(market_data.time, "sleep", sleeps.append)
    client = market_data.BinancePublicMarketDataProvider(max_retries=1)

    result = client.ticker("BTC")

    assert result["data"]["last_price"] == 65000
    assert len(sleeps) == 1
    assert sleeps[0] == 0


def test_stale_data_is_explicit_and_unsupported_symbols_are_rejected(monkeypatch):
    old_time = int(time.time()) - 3600

    def fake_get(url, **kwargs):
        return FakeResponse([{
            "currency_pair": "BTC_USDT", "last": "65000",
            "update": str(old_time),
        }])

    monkeypatch.setattr(market_data.httpx, "get", fake_get)
    client = market_data.GatePublicMarketDataProvider(max_retries=0, stale_after_s=60)

    assert client.ticker("BTC")["stale"] is True
    with pytest.raises(market_data.MarketDataError, match="symbol_not_supported"):
        client.ticker("NOTREAL")


def test_provider_status_is_read_only_and_does_not_fetch():
    status = market_data.provider_status()
    assert {row["id"] for row in status["providers"]} == {"binance", "gate"}
    assert all(row["auth_required"] is False for row in status["providers"])
    assert all(row["write_capabilities"] is False for row in status["providers"])
    assert status["network_calls_by_status_probe"] is False
    assert status["real_orders_enabled"] is False
    assert status["wallet_signing_enabled"] is False
    assert status["transfers_enabled"] is False


def test_market_data_api_route_uses_provider_contract_and_maps_rate_limits(monkeypatch):
    from fastapi import HTTPException

    class FakeProvider:
        provider_id = "binance"
        base_url = "https://example.invalid"

        def ticker(self, symbol):
            raise market_data.MarketDataError("rate_limited", retry_after_s=2)

    monkeypatch.setitem(market_data.PROVIDERS, "binance", FakeProvider())
    with pytest.raises(HTTPException) as caught:
        market_data.market_data_ticker("binance", "BTC")

    assert caught.value.status_code == 429
    assert caught.value.headers["Retry-After"] == "2"


def test_market_data_api_route_rejects_unknown_provider():
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as caught:
        market_data.market_data_ticker("unknown", "BTC")
    assert caught.value.status_code == 404


@pytest.mark.parametrize(
    "base_url",
    (
        "http://127.0.0.1:8080",
        "https://user:password@data-api.binance.vision",
        "https://example.invalid",
        "https://api.gateio.ws/other-path",
    ),
)
def test_provider_rejects_non_official_or_non_https_base_urls(base_url):
    with pytest.raises(ValueError, match="unsupported_public_market_data_base_url"):
        market_data.BinancePublicMarketDataProvider(base_url=base_url)
