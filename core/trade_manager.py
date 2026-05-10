"""
FinSentinel — Trade Tracker & Active Trade Manager
core/trade_manager.py

/izle  THYAO 300.50 280 340  → giriş + stop + hedef ile takip başlat
/kapat THYAO                 → pozisyonu kapat, itibar puanı hesapla
check_all_trades()           → scheduler tarafından her 5 dk çağrılır
"""

import json
from datetime import datetime
from pathlib import Path
from loguru import logger

_TRADES_FILE = Path("data/active_trades.json")


# ─── Persistence ──────────────────────────────────────────────────────────────

def _load() -> dict:
    try:
        if _TRADES_FILE.exists():
            return json.loads(_TRADES_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _save(trades: dict):
    try:
        _TRADES_FILE.parent.mkdir(parents=True, exist_ok=True)
        _TRADES_FILE.write_text(json.dumps(trades, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        logger.error(f"Trade kayıt hatası: {e}")


# ─── CRUD ─────────────────────────────────────────────────────────────────────

def add_trade(symbol: str, entry: float, stop: float, target: float,
              adet: int = 1, chat_id: str = "") -> dict:
    trades = _load()
    sym = symbol.upper().strip()
    trades[sym] = {
        "symbol":    sym,
        "entry":     entry,
        "stop":      stop,
        "target":    target,
        "adet":      adet,
        "chat_id":   chat_id,
        "opened_at": datetime.now().isoformat(),
        "status":    "open",
        "last_price": entry,
        "peak_price": entry,
    }
    _save(trades)
    return trades[sym]


def close_trade(symbol: str, close_price: float | None = None) -> dict | None:
    trades = _load()
    sym = symbol.upper().strip()
    if sym not in trades:
        return None
    t = trades[sym]
    price = close_price or t.get("last_price", t["entry"])
    pct   = (price - t["entry"]) / t["entry"] * 100
    t.update({
        "status":     "closed",
        "close_price": price,
        "pnl_pct":    round(pct, 2),
        "closed_at":  datetime.now().isoformat(),
    })
    _save(trades)
    return t


def get_open_trades() -> list[dict]:
    return [t for t in _load().values() if t.get("status") == "open"]


def get_all_trades() -> list[dict]:
    return list(_load().values())


def update_last_price(symbol: str, price: float):
    trades = _load()
    sym = symbol.upper().strip()
    if sym in trades:
        trades[sym]["last_price"] = price
        if price > trades[sym].get("peak_price", 0):
            trades[sym]["peak_price"] = price
        _save(trades)


# ─── Price Check (Scheduler çağırır) ──────────────────────────────────────────

def check_all_trades() -> list[dict]:
    """
    Açık işlemlerin fiyatlarını kontrol eder.
    Stop veya hedef kırılırsa uyarı objesi döner.
    Çağıran (scheduler) Telegram mesajı gönderir.
    """
    open_trades = get_open_trades()
    if not open_trades:
        return []

    alerts = []
    try:
        from core.fetcher import PriceFetcher
        syms = [f"{t['symbol']}.IS" for t in open_trades]
        prices = PriceFetcher.get_bulk_quotes(syms)
    except Exception as e:
        logger.debug(f"Trade fiyat çekme hatası: {e}")
        return []

    for t in open_trades:
        sym_yf = f"{t['symbol']}.IS"
        q = prices.get(sym_yf, {})
        if not q or "price" not in q:
            continue
        price = q["price"]
        update_last_price(t["symbol"], price)
        pct   = (price - t["entry"]) / t["entry"] * 100

        if price <= t["stop"]:
            alerts.append({
                "symbol":  t["symbol"],
                "type":    "STOP",
                "price":   price,
                "pct":     round(pct, 2),
                "chat_id": t.get("chat_id", ""),
                "trade":   t,
            })
        elif price >= t["target"]:
            alerts.append({
                "symbol":  t["symbol"],
                "type":    "TARGET",
                "price":   price,
                "pct":     round(pct, 2),
                "chat_id": t.get("chat_id", ""),
                "trade":   t,
            })

    return alerts


# ─── Performans Raporu ─────────────────────────────────────────────────────────

def performance_report() -> dict:
    trades = [t for t in get_all_trades() if t.get("status") == "closed"]
    if not trades:
        return {"total": 0}
    wins   = [t for t in trades if t.get("pnl_pct", 0) > 0]
    losses = [t for t in trades if t.get("pnl_pct", 0) <= 0]
    avg_win  = sum(t["pnl_pct"] for t in wins)  / max(len(wins), 1)
    avg_loss = sum(t["pnl_pct"] for t in losses) / max(len(losses), 1)
    return {
        "total":    len(trades),
        "wins":     len(wins),
        "losses":   len(losses),
        "win_rate": round(len(wins) / len(trades) * 100, 1),
        "avg_win":  round(avg_win, 2),
        "avg_loss": round(avg_loss, 2),
        "bot_pnl":  round(sum(t.get("pnl_pct", 0) for t in trades) / len(trades), 2),
    }
