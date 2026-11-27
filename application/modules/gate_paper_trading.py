"""Gate public spot research and strictly simulated RON paper trading.

No account credentials, private endpoints, real orders, wallet signing or transfers.
"""
from __future__ import annotations

import math
import sqlite3
import statistics
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from modules.data_paths import data_path
from modules.market_data import (
    DEFAULT_GATE_BASE_URL, GATE_PAPER_ASSETS as ASSETS,
    GATE_PUBLIC_PROVIDER, GatePublicMarketDataProvider, MarketDataError,
)

router = APIRouter(tags=["Gate Info · Research & Paper Trading"])

QUOTE = "USDT"
INITIAL_CAPITAL_RON = 100.0
GATE_API = DEFAULT_GATE_BASE_URL
PAPER_DB_PATH = data_path("db", "gate_paper_trading.sqlite3")


# Backward-compatible names for the existing Gate paper-trading surface.
GateAPIError = MarketDataError
GatePublicClient = GatePublicMarketDataProvider
GATE_CLIENT = GATE_PUBLIC_PROVIDER


def _db_path() -> Path:
    return Path(PAPER_DB_PATH)


class PaperTradingStore:
    """SQLite ledger. Cash and cost basis are denominated in RON."""

    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path is not None else _db_path()

    @contextmanager
    def _connect(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path, timeout=5, isolation_level="IMMEDIATE")
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def initialize(self):
        with self._connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS paper_portfolio (
                    id INTEGER PRIMARY KEY CHECK(id=1),
                    cash_ron REAL NOT NULL,
                    initial_capital_ron REAL NOT NULL,
                    created_utc TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS paper_positions (
                    symbol TEXT PRIMARY KEY,
                    quantity REAL NOT NULL CHECK(quantity >= 0),
                    average_cost_ron REAL NOT NULL CHECK(average_cost_ron >= 0)
                );
                CREATE TABLE IF NOT EXISTS paper_trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_utc TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL CHECK(side IN ('buy','sell')),
                    quantity REAL NOT NULL,
                    market_price_usdt REAL NOT NULL,
                    execution_price_usdt REAL NOT NULL,
                    ron_per_usdt REAL NOT NULL,
                    gross_ron REAL NOT NULL,
                    fee_ron REAL NOT NULL,
                    realized_pnl_ron REAL NOT NULL,
                    cash_after_ron REAL NOT NULL,
                    simulated_only INTEGER NOT NULL DEFAULT 1 CHECK(simulated_only=1)
                );
            """)
            conn.execute(
                """INSERT OR IGNORE INTO paper_portfolio
                   (id,cash_ron,initial_capital_ron,created_utc) VALUES(1,?,?,?)""",
                (INITIAL_CAPITAL_RON, INITIAL_CAPITAL_RON,
                 datetime.now(timezone.utc).isoformat())
            )

    def portfolio(self) -> dict:
        self.initialize()
        with self._connect() as conn:
            cash = conn.execute("SELECT * FROM paper_portfolio WHERE id=1").fetchone()
            positions = [dict(row) for row in conn.execute(
                "SELECT symbol,quantity,average_cost_ron FROM paper_positions WHERE quantity>0 ORDER BY symbol"
            )]
            trades = [dict(row) for row in conn.execute(
                "SELECT * FROM paper_trades ORDER BY id DESC LIMIT 100"
            )]
            realized_pnl = conn.execute(
                "SELECT COALESCE(SUM(realized_pnl_ron),0) FROM paper_trades"
            ).fetchone()[0]
        return {
            "currency": "RON", "cash_ron": round(cash["cash_ron"], 8),
            "initial_capital_ron": cash["initial_capital_ron"],
            "realized_pnl_ron": round(realized_pnl, 8),
            "positions": positions, "recent_trades": trades,
            "execution_mode": "paper_only", "real_orders_enabled": False,
            "wallet_signing_enabled": False, "transfers_enabled": False,
        }

    def execute(self, *, symbol: str, side: str, quantity: float,
                market_price_usdt: float, execution_price_usdt: float,
                ron_per_usdt: float, fee_bps: float) -> dict:
        self.initialize()
        if symbol not in ASSETS:
            raise ValueError("unsupported_asset")
        if side not in ("buy", "sell"):
            raise ValueError("invalid_side")
        values = (quantity, market_price_usdt, execution_price_usdt, ron_per_usdt, fee_bps)
        if any(
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            for value in values
        ):
            raise ValueError("numeric_values_must_be_finite")
        if any(value <= 0 for value in values[:4]):
            raise ValueError("numeric_values_must_be_positive")
        if not 0 <= fee_bps <= 1000:
            raise ValueError("fee_bps_out_of_range")

        gross = quantity * execution_price_usdt * ron_per_usdt
        fee = gross * fee_bps / 10000.0
        now = datetime.now(timezone.utc).isoformat()

        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            portfolio = conn.execute("SELECT cash_ron FROM paper_portfolio WHERE id=1").fetchone()
            cash = float(portfolio["cash_ron"])
            pos = conn.execute(
                "SELECT quantity,average_cost_ron FROM paper_positions WHERE symbol=?",
                (symbol,)
            ).fetchone()
            held = float(pos["quantity"]) if pos else 0.0
            avg_cost = float(pos["average_cost_ron"]) if pos else 0.0
            realized = 0.0

            if side == "buy":
                debit = gross + fee
                if debit > cash + 1e-8:
                    raise ValueError("insufficient_virtual_cash")
                new_qty = held + quantity
                new_avg = ((held * avg_cost) + debit) / new_qty
                conn.execute(
                    """INSERT INTO paper_positions(symbol,quantity,average_cost_ron)
                       VALUES(?,?,?) ON CONFLICT(symbol) DO UPDATE SET
                       quantity=excluded.quantity,average_cost_ron=excluded.average_cost_ron""",
                    (symbol, new_qty, new_avg)
                )
                cash -= debit
            else:
                if quantity > held + 1e-10:
                    raise ValueError("insufficient_virtual_position")
                proceeds = gross - fee
                realized = proceeds - quantity * avg_cost
                new_qty = max(0.0, held - quantity)
                if new_qty <= 1e-10:
                    conn.execute("DELETE FROM paper_positions WHERE symbol=?", (symbol,))
                else:
                    conn.execute(
                        "UPDATE paper_positions SET quantity=? WHERE symbol=?",
                        (new_qty, symbol)
                    )
                cash += proceeds

            conn.execute("UPDATE paper_portfolio SET cash_ron=? WHERE id=1", (cash,))
            cursor = conn.execute(
                """INSERT INTO paper_trades
                   (created_utc,symbol,side,quantity,market_price_usdt,execution_price_usdt,
                    ron_per_usdt,gross_ron,fee_ron,realized_pnl_ron,cash_after_ron,simulated_only)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,1)""",
                (now, symbol, side, quantity, market_price_usdt, execution_price_usdt,
                 ron_per_usdt, gross, fee, realized, cash)
            )
            trade_id = cursor.lastrowid

        return {
            "trade_id": trade_id, "symbol": symbol, "side": side,
            "quantity": quantity, "market_price_usdt": market_price_usdt,
            "execution_price_usdt": execution_price_usdt,
            "ron_per_usdt": ron_per_usdt, "gross_ron": round(gross, 8),
            "fee_ron": round(fee, 8), "realized_pnl_ron": round(realized, 8),
            "cash_after_ron": round(cash, 8), "simulated_only": True,
            "real_order_submitted": False,
        }


class PaperOrder(BaseModel):
    symbol: str
    side: Literal["buy", "sell"]
    quantity: float = Field(gt=0, le=1e12)
    # Explicit input prevents NEXUS from silently assuming an FX conversion rate.
    ron_per_usdt: float = Field(gt=0, le=1000)
    fee_bps: float = Field(default=10, ge=0, le=1000)
    slippage_bps: float = Field(default=5, ge=0, le=500)


def _symbol(value: str) -> str:
    symbol = value.strip().upper()
    if symbol not in ASSETS:
        raise HTTPException(status_code=404, detail="Asset not in the configured Gate watchlist")
    return symbol


def analyze_candles(candles: list) -> dict:
    """Compute transparent indicators from Gate OHLCV candles; no prediction claims."""
    parsed = []
    for row in candles:
        try:
            if isinstance(row, dict):
                timestamp = int(row.get("t", row.get("time")))
                close = float(row.get("c", row.get("close")))
            else:
                timestamp = int(float(row[0]))
                close = float(row[2])
            if close > 0:
                parsed.append((timestamp, close))
        except (TypeError, ValueError, IndexError):
            continue
    parsed.sort(key=lambda item: item[0])
    closes = [item[1] for item in parsed]
    if len(closes) < 2:
        return {"status": "insufficient_data", "candles_used": len(closes)}
    changes = [(closes[i] / closes[i - 1]) - 1 for i in range(1, len(closes))]
    gains = [max(change, 0.0) for change in changes[-14:]]
    losses = [max(-change, 0.0) for change in changes[-14:]]
    avg_gain = sum(gains) / len(gains) if gains else 0.0
    avg_loss = sum(losses) / len(losses) if losses else 0.0
    if avg_loss == 0:
        rsi14 = 100.0 if avg_gain > 0 else 50.0
    else:
        rsi14 = 100.0 - (100.0 / (1.0 + avg_gain / avg_loss))
    trend = ((closes[-1] / closes[-21]) - 1.0) * 100 if len(closes) >= 21 else None
    return {
        "status": "ok", "candles_used": len(closes), "last_close_usdt": closes[-1],
        "sma20_usdt": statistics.fmean(closes[-20:]) if len(closes) >= 20 else None,
        "sma50_usdt": statistics.fmean(closes[-50:]) if len(closes) >= 50 else None,
        "rsi14": round(rsi14, 4) if len(changes) >= 14 else None,
        "return_20_candles_pct": round(trend, 4) if trend is not None else None,
        "realized_volatility_20_returns_pct": (
            round(statistics.pstdev(changes[-20:]) * 100, 4) if len(changes) >= 20 else None
        ),
        "method": "SMA20/SMA50; simple RSI14; standard deviation of last 20 close-to-close returns",
        "interpretation": "Descriptive indicators only; not a price forecast or trading recommendation.",
    }


def _book_vwap(book: dict, side: str, quantity: float) -> float:
    """Walk the visible book and return VWAP; reject orders beyond visible depth."""
    levels = book.get("asks" if side == "buy" else "bids") or []
    if not levels:
        raise GateAPIError("empty_order_book")
    remaining = quantity
    notional = 0.0
    for level in levels:
        try:
            if isinstance(level, dict):
                price = float(level.get("p", level.get("price")))
                available = float(level.get("s", level.get("size", level.get("amount"))))
            else:
                price, available = float(level[0]), float(level[1])
        except (TypeError, ValueError, IndexError):
            raise GateAPIError("invalid_order_book_level")
        if price <= 0 or available <= 0:
            continue
        filled = min(remaining, available)
        notional += filled * price
        remaining -= filled
        if remaining <= max(quantity * 1e-12, 1e-15):
            break
    if remaining > max(quantity * 1e-12, 1e-15):
        raise GateAPIError("insufficient_visible_order_book_depth")
    return notional / quantity


@router.get("/api/gate/config")
def gate_config():
    return {
        "provider": "Gate.io public spot API v4", "quote": QUOTE,
        "assets": list(ASSETS), "research_enabled": True,
        "paper_trading_enabled": True, "initial_capital_ron": INITIAL_CAPITAL_RON,
        "real_orders_enabled": False, "private_api_credentials_required": False,
        "wallet_signing_enabled": False, "transfers_enabled": False,
    }


@router.get("/api/gate/markets")
def gate_markets():
    try:
        rows = GATE_CLIENT.tickers()
    except GateAPIError as exc:
        raise HTTPException(status_code=502, detail=f"Gate public market data unavailable: {exc}") from exc
    by_pair = {row.get("currency_pair"): row for row in rows}
    result = []
    for asset in ASSETS:
        pair = f"{asset}_{QUOTE}"
        row = by_pair.get(pair)
        if row is None:
            result.append({"symbol": asset, "pair": pair, "status": "not_available"})
            continue
        try:
            result.append({
                "symbol": asset, "pair": pair, "status": "live",
                "last_usdt": float(row["last"]),
                "bid_usdt": float(row.get("highest_bid") or 0),
                "ask_usdt": float(row.get("lowest_ask") or 0),
                "change_24h_pct": float(row.get("change_utc0", row.get("change_percentage")) or 0),
                "high_24h_usdt": float(row.get("high_24h") or 0),
                "low_24h_usdt": float(row.get("low_24h") or 0),
                "base_volume_24h": float(row.get("base_volume") or 0),
                "quote_volume_24h": float(row.get("quote_volume") or 0),
                "source": "Gate spot REST API v4",
                "observed_at_utc": datetime.now(timezone.utc).isoformat(),
            })
        except (KeyError, TypeError, ValueError):
            result.append({"symbol": asset, "pair": pair, "status": "invalid_upstream_payload"})
    return {"provider": "Gate.io", "quote": QUOTE, "count": len(result),
            "live_count": sum(x["status"] == "live" for x in result),
            "items": result}


@router.get("/api/gate/market/{symbol}")
def gate_market_detail(symbol: str, interval: str = Query(default="15m", pattern="^(15m|1h|4h|1d)$")):
    asset = _symbol(symbol)
    try:
        ticker_rows = GATE_CLIENT.tickers()
        ticker = next((x for x in ticker_rows if x.get("currency_pair") == f"{asset}_{QUOTE}"), None)
        if ticker is None:
            raise HTTPException(status_code=404, detail="Gate spot pair not available")
        book = GATE_CLIENT.orderbook(asset, limit=10)
        candles = GATE_CLIENT.candles(asset, interval=interval, limit=100)
    except GateAPIError as exc:
        raise HTTPException(status_code=502, detail=f"Gate market detail unavailable: {exc}") from exc
    return {"symbol": asset, "pair": f"{asset}_{QUOTE}", "ticker": ticker,
            "order_book": book, "candles": candles, "interval": interval,
            "source": "Gate spot REST API v4"}


@router.get("/api/gate/research/{symbol}")
def gate_research(symbol: str, interval: str = Query(default="15m", pattern="^(15m|1h|4h|1d)$")):
    asset = _symbol(symbol)
    try:
        candles = GATE_CLIENT.candles(asset, interval=interval, limit=100)
    except GateAPIError as exc:
        raise HTTPException(status_code=502, detail=f"Gate research data unavailable: {exc}") from exc
    return {
        "symbol": asset, "pair": f"{asset}_{QUOTE}", "interval": interval,
        "source": "Gate spot REST API v4", "indicators": analyze_candles(candles),
    }


@router.get("/api/gate/paper/portfolio")
def gate_paper_portfolio():
    return PaperTradingStore().portfolio()


@router.post("/api/gate/paper/orders")
def gate_paper_order(order: PaperOrder):
    asset = _symbol(order.symbol)
    try:
        book = GATE_CLIENT.orderbook(asset, limit=5)
        market_price = _book_vwap(book, order.side, order.quantity)
        adjustment = order.slippage_bps / 10000.0
        execution_price = market_price * (1 + adjustment if order.side == "buy" else 1 - adjustment)
        return PaperTradingStore().execute(
            symbol=asset, side=order.side, quantity=order.quantity,
            market_price_usdt=market_price, execution_price_usdt=execution_price,
            ron_per_usdt=order.ron_per_usdt, fee_bps=order.fee_bps
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except GateAPIError as exc:
        raise HTTPException(status_code=502, detail=f"Cannot price simulated order: {exc}") from exc


@router.get("/gate-paper", response_class=HTMLResponse)
def gate_paper_dashboard():
    return HTMLResponse(PANEL)


PANEL = r"""<!doctype html>
<html lang="ro"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>NEXUS · Gate Research & Paper Trading</title>
<style>
body{margin:0;background:#0b1220;color:#e8eef8;font:15px/1.5 Segoe UI,Arial,sans-serif}main{max-width:1200px;margin:auto;padding:22px}
h1{margin-bottom:4px}.muted{color:#9aabc4}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:12px}
.card{background:#121d30;border:1px solid #263752;border-radius:12px;padding:16px;margin:12px 0}
table{width:100%;border-collapse:collapse;font-size:13px}td,th{text-align:left;padding:9px;border-bottom:1px solid #263752;white-space:nowrap}
.wrap{overflow:auto}input,select{background:#0b1525;color:#e8eef8;border:1px solid #40516a;padding:10px;border-radius:8px;width:100%;box-sizing:border-box}
label{display:block;font-size:12px;color:#9aabc4;margin:8px 0 4px}button{background:#62a5ff;color:#061222;border:0;padding:10px 15px;border-radius:8px;font-weight:bold;cursor:pointer;margin-top:12px}
pre{white-space:pre-wrap;overflow-wrap:anywhere;color:#cbd8ea}.good{color:#38c99a}.bad{color:#f3bf62}
</style></head><body><main>
<h1>NEXUS · Gate Research & Paper Trading</h1><div class="muted">Gate public spot data · 10 configured assets · simulated portfolio only</div>
<div class="grid">
<div class="card"><div class="muted">Capital inițial</div><h2>100 RON</h2></div>
<div class="card"><div class="muted">Execuție reală</div><h2 class="good">DEZACTIVATĂ</h2></div>
<div class="card"><div class="muted">Provider</div><h2>Gate API v4</h2></div>
</div>
<div class="card"><h2>Piață live</h2><button id="refresh">Actualizează datele</button><div id="marketStatus" class="muted">Se încarcă…</div>
<div class="wrap"><table><thead><tr><th>Asset</th><th>Last USDT</th><th>Bid</th><th>Ask</th><th>24h %</th><th>Volum USDT</th><th>Status</th></tr></thead><tbody id="markets"></tbody></table></div></div>
<div class="card"><h2>Research tehnic</h2><p class="muted">SMA20/SMA50, RSI14, randament și volatilitate descriptivă pe lumânări Gate.</p><div class="grid"><div><label>Asset pentru analiză</label><select id="researchSymbol"></select></div><div><label>Interval</label><select id="interval"><option>15m</option><option>1h</option><option>4h</option><option>1d</option></select></div></div><button id="researchRun">Rulează analiza</button><pre id="researchResult">Selectează un activ și rulează analiza.</pre></div>
<div class="card"><h2>Paper Trading</h2><p class="muted">Introduceți cursul RON/USDT observat. Acesta nu este presupus automat. Costurile de simulare sunt ipoteze configurabile.</p>
<div class="grid">
<div><label>Asset</label><select id="symbol"></select></div><div><label>Operațiune</label><select id="side"><option value="buy">BUY</option><option value="sell">SELL</option></select></div>
<div><label>Cantitate (unități asset)</label><input id="quantity" type="number" min="0.00000001" step="any" value="0.001"></div>
<div><label>Curs RON pentru 1 USDT</label><input id="fx" type="number" min="0.0001" step="any" placeholder="Introdu cursul curent"></div>
<div><label>Comision simulat (bps)</label><input id="fee" type="number" min="0" max="1000" value="10"></div>
<div><label>Slippage simulat (bps)</label><input id="slippage" type="number" min="0" max="500" value="5"></div>
</div><button id="submit">Execută simularea</button><pre id="orderResult">Nicio simulare efectuată.</pre></div>
<div class="card"><h2>Portofoliu virtual</h2><button id="portfolioRefresh">Actualizează portofoliu</button><pre id="portfolio">Se încarcă…</pre></div>
<p class="muted">Limitări: datele pieței sunt publice și read-only. Ordinele se înregistrează exclusiv în ledger-ul SQLite local. Nu există endpoint de ordine reale, chei API private, semnare sau transferuri.</p>
</main><script>
const $=id=>document.getElementById(id);const api=async(url,opts)=>{const r=await fetch(url,opts);const d=await r.json();if(!r.ok)throw Error(d.detail||r.statusText);return d};
async function markets(){const d=await api('/api/gate/markets');$('markets').innerHTML=d.items.map(x=>'<tr><td>'+x.symbol+'</td><td>'+(x.last_usdt??'—')+'</td><td>'+(x.bid_usdt??'—')+'</td><td>'+(x.ask_usdt??'—')+'</td><td>'+(x.change_24h_pct??'—')+'</td><td>'+(x.quote_volume_24h??'—')+'</td><td>'+x.status+'</td></tr>').join('');$('symbol').innerHTML=d.items.filter(x=>x.status==='live').map(x=>'<option>'+x.symbol+'</option>').join('');$('researchSymbol').innerHTML=$('symbol').innerHTML;$('marketStatus').textContent=d.live_count+' / '+d.count+' pairs returned by Gate; quote '+d.quote;}
async function portfolio(){$('portfolio').textContent=JSON.stringify(await api('/api/gate/paper/portfolio'),null,2);}
$('refresh').onclick=()=>markets().catch(e=>$('marketStatus').textContent=e.message);
$('researchRun').onclick=async()=>{try{$('researchResult').textContent=JSON.stringify(await api('/api/gate/research/'+$('researchSymbol').value+'?interval='+$('interval').value),null,2);}catch(e){$('researchResult').textContent=e.message;}};
$('portfolioRefresh').onclick=()=>portfolio().catch(e=>$('portfolio').textContent=e.message);
$('submit').onclick=async()=>{try{const fx=Number($('fx').value);if(!(fx>0))throw Error('Introdu cursul RON/USDT înainte de simulare.');const body={symbol:$('symbol').value,side:$('side').value,quantity:Number($('quantity').value),ron_per_usdt:fx,fee_bps:Number($('fee').value),slippage_bps:Number($('slippage').value)};const d=await api('/api/gate/paper/orders',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});$('orderResult').textContent=JSON.stringify(d,null,2);await portfolio();}catch(e){$('orderResult').textContent=e.message;}};
markets().then(portfolio).catch(e=>$('marketStatus').textContent=e.message);
</script></body></html>"""
