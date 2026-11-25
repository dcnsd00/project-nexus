import json
from modules import coin_catalog


def test_coin_catalog_normalizes_remote_metadata():
    rows = coin_catalog._normalize_remote([
        {"id": "btc-bitcoin", "name": "Bitcoin", "symbol": "BTC", "rank": 1,
         "type": "coin", "is_active": True, "is_new": False},
        {"id": None, "symbol": None},
    ])
    assert len(rows) == 1
    assert rows[0]["symbol"] == "BTC"


def test_coin_catalog_cache_write_is_atomic_and_readable(tmp_path, monkeypatch):
    cache = tmp_path / "nested" / "coins.json"
    monkeypatch.setattr(coin_catalog, "CACHE", cache)
    rows = [{"id": "btc-bitcoin", "name": "Bitcoin", "symbol": "BTC",
             "rank": 1, "type": "coin", "is_active": True, "is_new": False}]
    coin_catalog._write_cache(rows, 123456.0)
    assert cache.is_file()
    assert not cache.with_suffix(".json.tmp").exists()
    loaded, fetched_at, source = coin_catalog._read_cache()
    assert loaded[0]["symbol"] == "BTC"
    assert fetched_at == 123456.0
    assert source == "CoinPaprika API"


def test_coin_catalog_bundled_fallback_keeps_pow_classification():
    rows = coin_catalog._bundled_fallback()
    btc = next(row for row in rows if row["symbol"] == "BTC")
    eth = next(row for row in rows if row["symbol"] == "ETH")
    assert btc["pow_mineable"] is True
    assert eth["pow_mineable"] is False
