"""
FinSentinel — Kalıcı Bot Portföyü
core/bot_portfolio.py

Program yeniden başlatılsa dahi veriler korunur (data/bot_portfolio.json).
Streamlit portföy sayfası da bu dosyayı okuyabilir.
"""

import json
from datetime import datetime
from pathlib import Path
from loguru import logger

_FILE = Path("data/bot_portfolio.json")
_ALARMS_FILE = Path("data/bot_alarms.json")


# ─── Portföy ──────────────────────────────────────────────────────────────────

def _load_portfolio() -> dict:
    try:
        if _FILE.exists():
            return json.loads(_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _save_portfolio(data: dict):
    _FILE.parent.mkdir(parents=True, exist_ok=True)
    _FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def add_stock(symbol: str, qty: float, avg_price: float, chat_id: str = "") -> dict:
    p = _load_portfolio()
    sym = symbol.upper().strip()
    if sym in p:
        # Maliyet ortalaması güncelle
        old_qty   = p[sym]["qty"]
        old_price = p[sym]["avg_price"]
        new_qty   = old_qty + qty
        new_avg   = (old_qty * old_price + qty * avg_price) / new_qty
        p[sym].update({"qty": new_qty, "avg_price": round(new_avg, 4),
                        "updated_at": datetime.now().isoformat()})
    else:
        p[sym] = {
            "symbol":    sym,
            "qty":       qty,
            "avg_price": avg_price,
            "chat_id":   chat_id,
            "added_at":  datetime.now().isoformat(),
        }
    _save_portfolio(p)
    return p[sym]


def remove_stock(symbol: str) -> bool:
    p = _load_portfolio()
    sym = symbol.upper().strip()
    if sym not in p:
        return False
    del p[sym]
    _save_portfolio(p)
    return True


def get_portfolio() -> list[dict]:
    return list(_load_portfolio().values())


def get_portfolio_with_prices() -> list[dict]:
    items = get_portfolio()
    if not items:
        return []
    try:
        from core.fetcher import PriceFetcher
        syms  = [f"{i['symbol']}.IS" for i in items]
        prices = PriceFetcher.get_bulk_quotes(syms)
        for item in items:
            q     = prices.get(f"{item['symbol']}.IS", {})
            price = q.get("price", 0) if q else 0
            item["current_price"] = price
            if price > 0 and item["avg_price"] > 0:
                item["pnl_pct"]  = round((price - item["avg_price"]) / item["avg_price"] * 100, 2)
                item["pnl_try"]  = round((price - item["avg_price"]) * item["qty"], 2)
                item["mkt_val"]  = round(price * item["qty"], 2)
            else:
                item["pnl_pct"] = 0.0
                item["pnl_try"] = 0.0
                item["mkt_val"] = round(item["avg_price"] * item["qty"], 2)
    except Exception as e:
        logger.debug(f"get_portfolio_with_prices hatası: {e}")
        for item in items:
            item.setdefault("current_price", 0)
            item.setdefault("pnl_pct", 0.0)
            item.setdefault("pnl_try", 0.0)
            item.setdefault("mkt_val", round(item["avg_price"] * item["qty"], 2))
    return items


# ─── Alarmlar ──────────────────────────────────────────────────────────────────

def _load_alarms() -> dict:
    try:
        if _ALARMS_FILE.exists():
            return json.loads(_ALARMS_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _save_alarms(data: dict):
    _ALARMS_FILE.parent.mkdir(parents=True, exist_ok=True)
    _ALARMS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def add_alarm(symbol: str, threshold: float, direction: str,
              chat_id: str = "", note: str = "") -> dict:
    alarms = _load_alarms()
    sym = symbol.upper().strip()
    key = f"{sym}_{threshold}_{direction}"
    alarms[key] = {
        "key":       key,
        "symbol":    sym,
        "threshold": threshold,
        "direction": direction,   # "above" | "below"
        "chat_id":   chat_id,
        "note":      note,
        "active":    True,
        "created_at": datetime.now().isoformat(),
    }
    _save_alarms(alarms)
    return alarms[key]


def remove_alarm(symbol: str) -> int:
    """Sembolün tüm aktif alarmlarını siler. Silinen alarm sayısını döner."""
    alarms = _load_alarms()
    sym    = symbol.upper().strip()
    keys   = [k for k, v in alarms.items() if v["symbol"] == sym]
    for k in keys:
        del alarms[k]
    _save_alarms(alarms)
    return len(keys)


def get_active_alarms() -> list[dict]:
    return [v for v in _load_alarms().values() if v.get("active")]


def deactivate_alarm(key: str):
    alarms = _load_alarms()
    if key in alarms:
        alarms[key]["active"] = False
        alarms[key]["triggered_at"] = datetime.now().isoformat()
        _save_alarms(alarms)


def check_alarms() -> list[dict]:
    """
    Aktif alarmları fiyatla karşılaştırır.
    Tetiklenen alarmları döner ve deactivate eder.
    """
    active = get_active_alarms()
    if not active:
        return []
    try:
        from core.fetcher import PriceFetcher
        syms   = list({f"{a['symbol']}.IS" for a in active})
        prices = PriceFetcher.get_bulk_quotes(syms)
    except Exception:
        return []

    triggered = []
    for alarm in active:
        sym_yf = f"{alarm['symbol']}.IS"
        q = prices.get(sym_yf, {})
        if not q or "price" not in q:
            continue
        price = q["price"]
        hit   = (alarm["direction"] == "above" and price >= alarm["threshold"]) or \
                (alarm["direction"] == "below" and price <= alarm["threshold"])
        if hit:
            alarm["current_price"] = price
            triggered.append(alarm)
            deactivate_alarm(alarm["key"])
    return triggered
