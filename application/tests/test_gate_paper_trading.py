from modules import gate_paper_trading as gate


class FakeGate:
    def tickers(self):
        return [
            {"currency_pair": f"{asset}_USDT", "last": "10", "highest_bid": "9.9",
             "lowest_ask": "10.1", "change_percentage": "1.2",
             "high_24h": "11", "low_24h": "9", "base_volume": "100",
             "quote_volume": "1000"}
            for asset in gate.ASSETS
        ]

    def orderbook(self, symbol, limit=5):
        return {"bids": [["9.9", "100"]], "asks": [["10.1", "100"]]}

    def candles(self, symbol, interval="15m", limit=100):
        return [["1700000000", "100", "10", "11", "9", "9.5", "950", "5"]]


def test_config_declares_all_assets_and_disables_real_execution():
    config = gate.gate_config()
    assert config["assets"] == list(gate.ASSETS)
    assert len(config["assets"]) == 10
    assert config["initial_capital_ron"] == 100.0
    assert config["real_orders_enabled"] is False
    assert config["wallet_signing_enabled"] is False


def test_public_market_snapshot_normalizes_all_ten_assets(monkeypatch):
    monkeypatch.setattr(gate, "GATE_CLIENT", FakeGate())
    result = gate.gate_markets()
    assert result["count"] == 10
    assert result["live_count"] == 10
    assert {row["symbol"] for row in result["items"]} == set(gate.ASSETS)
    assert all(row["status"] == "live" for row in result["items"])


def test_paper_buy_and_sell_ledger_never_submits_real_order(tmp_path):
    store = gate.PaperTradingStore(tmp_path / "paper.sqlite3")
    store.initialize()
    buy = store.execute(
        symbol="BTC", side="buy", quantity=0.5, market_price_usdt=10,
        execution_price_usdt=10.1, ron_per_usdt=5, fee_bps=10
    )
    assert buy["simulated_only"] is True
    assert buy["real_order_submitted"] is False
    assert buy["cash_after_ron"] < 100
    sell = store.execute(
        symbol="BTC", side="sell", quantity=0.5, market_price_usdt=11,
        execution_price_usdt=10.9, ron_per_usdt=5, fee_bps=10
    )
    assert sell["simulated_only"] is True
    assert sell["real_order_submitted"] is False
    portfolio = store.portfolio()
    assert portfolio["positions"] == []
    assert portfolio["cash_ron"] > 100
    assert portfolio["realized_pnl_ron"] != 0
    assert portfolio["real_orders_enabled"] is False


def test_paper_buy_rejects_insufficient_cash(tmp_path):
    store = gate.PaperTradingStore(tmp_path / "paper.sqlite3")
    try:
        store.execute(
            symbol="BTC", side="buy", quantity=100, market_price_usdt=100,
            execution_price_usdt=100, ron_per_usdt=5, fee_bps=10
        )
    except ValueError as exc:
        assert str(exc) == "insufficient_virtual_cash"
    else:
        raise AssertionError("Expected insufficient virtual cash error")


def test_paper_sell_rejects_unowned_quantity(tmp_path):
    store = gate.PaperTradingStore(tmp_path / "paper.sqlite3")
    try:
        store.execute(
            symbol="ETH", side="sell", quantity=1, market_price_usdt=10,
            execution_price_usdt=10, ron_per_usdt=5, fee_bps=10
        )
    except ValueError as exc:
        assert str(exc) == "insufficient_virtual_position"
    else:
        raise AssertionError("Expected insufficient virtual position error")


def test_market_detail_rejects_unconfigured_symbol():
    try:
        gate.gate_market_detail("NOTREAL")
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 404
    else:
        raise AssertionError("Expected unconfigured asset rejection")


def test_initial_portfolio_is_persisted_at_100_ron(tmp_path):
    store = gate.PaperTradingStore(tmp_path / "paper.sqlite3")
    portfolio = store.portfolio()
    assert portfolio["initial_capital_ron"] == 100.0
    assert portfolio["cash_ron"] == 100.0
    assert portfolio["execution_mode"] == "paper_only"
    assert portfolio["transfers_enabled"] is False


def test_paper_order_uses_gate_ask_and_never_calls_real_execution(monkeypatch, tmp_path):
    monkeypatch.setattr(gate, "GATE_CLIENT", FakeGate())
    monkeypatch.setattr(gate, "PAPER_DB_PATH", tmp_path / "paper.sqlite3")
    order = gate.PaperOrder(
        symbol="BTC", side="buy", quantity=0.001, ron_per_usdt=5,
        fee_bps=10, slippage_bps=5
    )
    result = gate.gate_paper_order(order)
    assert result["market_price_usdt"] == 10.1
    assert result["execution_price_usdt"] > result["market_price_usdt"]
    assert result["simulated_only"] is True
    assert result["real_order_submitted"] is False


def test_candle_research_indicators_are_bounded_and_descriptive():
    candles = []
    for i in range(60):
        # Gate candle format: timestamp, volume, close, high, low, open, quote volume, trades.
        close = 100.0 + i
        candles.append([str(1700000000 + i * 900), "10", str(close),
                        str(close + 1), str(close - 1), str(close - 0.5), "1000", "12"])
    result = gate.analyze_candles(candles)
    assert result["status"] == "ok"
    assert result["candles_used"] == 60
    assert result["sma20_usdt"] is not None
    assert result["sma50_usdt"] is not None
    assert result["rsi14"] == 100.0
    assert result["interpretation"].startswith("Descriptive indicators")
