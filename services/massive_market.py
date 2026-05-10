"""
FinSentinel — Massive Market Data Servisi
services/massive_market.py

Massive Market Data API üzerinden hisse, forex, kripto ve emtia verisi çeker.
Mevcut fetcher.py ile entegre çalışır; cache-first yaklaşım uygulanır.
API Dökümantasyonu: https://docs.massivemarkets.io
"""

import requests
from typing import Optional
from loguru import logger
from config.settings import MASSIVE_MARKET_API_KEY, CACHE_TTL
from core.db import db

_BASE_URL = "https://api.massivemarkets.io/v1"

_HEADERS = {
    "x-api-key": MASSIVE_MARKET_API_KEY,
    "Accept": "application/json",
    "Content-Type": "application/json",
}


# ─── Yardımcı ─────────────────────────────────────────────────────────────────

def _get(endpoint: str, params: dict = None) -> Optional[dict]:
    """Genel GET isteği. Hataları yutar, None döner."""
    if not MASSIVE_MARKET_API_KEY:
        logger.warning("MASSIVE_MARKET_API_KEY tanımlı değil — bu servis devre dışı.")
        return None
    try:
        resp = requests.get(
            f"{_BASE_URL}{endpoint}",
            headers=_HEADERS,
            params=params or {},
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.HTTPError as e:
        logger.error(f"MassiveMarket HTTP {e.response.status_code}: {endpoint} — {e}")
    except requests.exceptions.RequestException as e:
        logger.error(f"MassiveMarket bağlantı hatası: {endpoint} — {e}")
    return None


# ─── Hisse / ETF ──────────────────────────────────────────────────────────────

def get_quote(symbol: str, use_cache: bool = True) -> Optional[dict]:
    """
    Tek sembol için anlık fiyat.
    Örnek: get_quote("AAPL"), get_quote("THYAO")
    """
    cache_key = f"massive:quote:{symbol}"
    if use_cache:
        cached = db.cache_get(cache_key)
        if cached:
            return cached

    data = _get(f"/quote/{symbol}")
    if data:
        result = {
            "symbol":     symbol,
            "price":      data.get("price"),
            "open":       data.get("open"),
            "high":       data.get("high"),
            "low":        data.get("low"),
            "prev_close": data.get("previousClose"),
            "change":     data.get("change"),
            "change_pct": data.get("changePercent"),
            "volume":     data.get("volume"),
            "market_cap": data.get("marketCap"),
            "currency":   data.get("currency"),
            "source":     "massive_market",
        }
        db.cache_set(cache_key, result, CACHE_TTL["tick"])
        return result
    return None


def get_bulk_quotes(symbols: list[str]) -> dict[str, Optional[dict]]:
    """Birden fazla sembol için toplu fiyat çekimi."""
    cache_key = f"massive:bulk:{','.join(sorted(symbols))}"
    cached = db.cache_get(cache_key)
    if cached:
        return cached

    data = _get("/quotes", params={"symbols": ",".join(symbols)})
    results = {}
    if data and isinstance(data, list):
        for item in data:
            sym = item.get("symbol", "")
            results[sym] = {
                "symbol":     sym,
                "price":      item.get("price"),
                "change_pct": item.get("changePercent"),
                "volume":     item.get("volume"),
                "source":     "massive_market",
            }
    db.cache_set(cache_key, results, CACHE_TTL["tick"])
    return results


def get_historical(
    symbol: str,
    period: str = "1mo",
    interval: str = "1d",
) -> Optional[list[dict]]:
    """
    Tarihsel OHLCV verisi.
    period: 1d, 5d, 1mo, 3mo, 6mo, 1y, 5y, max
    interval: 1m, 5m, 15m, 1h, 1d, 1wk, 1mo
    """
    cache_key = f"massive:hist:{symbol}:{period}:{interval}"
    cached = db.cache_get(cache_key)
    if cached:
        return cached

    data = _get(f"/historical/{symbol}", params={"period": period, "interval": interval})
    if data and "candles" in data:
        result = data["candles"]
        db.cache_set(cache_key, result, CACHE_TTL["hourly"])
        return result
    return None


# ─── Forex ────────────────────────────────────────────────────────────────────

def get_forex_rate(base: str, quote: str) -> Optional[dict]:
    """
    Anlık forex kuru.
    Örnek: get_forex_rate("USD", "TRY")
    """
    cache_key = f"massive:fx:{base}{quote}"
    cached = db.cache_get(cache_key)
    if cached:
        return cached

    data = _get("/forex/rate", params={"base": base, "quote": quote})
    if data:
        result = {
            "pair":   f"{base}/{quote}",
            "rate":   data.get("rate"),
            "bid":    data.get("bid"),
            "ask":    data.get("ask"),
            "spread": data.get("spread"),
            "source": "massive_market",
        }
        db.cache_set(cache_key, result, CACHE_TTL["tick"])
        return result
    return None


def get_forex_bulk(pairs: list[tuple[str, str]]) -> dict[str, Optional[dict]]:
    """
    Çoklu forex kuru.
    pairs: [("USD","TRY"), ("EUR","TRY"), ...]
    """
    pair_str = ",".join(f"{b}{q}" for b, q in pairs)
    cache_key = f"massive:fx_bulk:{pair_str}"
    cached = db.cache_get(cache_key)
    if cached:
        return cached

    data = _get("/forex/rates", params={"pairs": pair_str})
    results = {}
    if data and isinstance(data, list):
        for item in data:
            key = item.get("pair", "")
            results[key] = {
                "pair":   key,
                "rate":   item.get("rate"),
                "bid":    item.get("bid"),
                "ask":    item.get("ask"),
                "source": "massive_market",
            }
    db.cache_set(cache_key, results, CACHE_TTL["tick"])
    return results


# ─── Kripto ───────────────────────────────────────────────────────────────────

def get_crypto_price(symbol: str, vs_currency: str = "usd") -> Optional[dict]:
    """
    Anlık kripto fiyatı.
    Örnek: get_crypto_price("BTC"), get_crypto_price("ETH", "try")
    """
    cache_key = f"massive:crypto:{symbol}:{vs_currency}"
    cached = db.cache_get(cache_key)
    if cached:
        return cached

    data = _get(f"/crypto/{symbol.lower()}", params={"vs_currency": vs_currency})
    if data:
        result = {
            "symbol":         symbol.upper(),
            "price":          data.get("price"),
            "market_cap":     data.get("marketCap"),
            "volume_24h":     data.get("volume24h"),
            "change_24h":     data.get("change24h"),
            "change_pct_24h": data.get("changePercent24h"),
            "ath":            data.get("ath"),
            "source":         "massive_market",
        }
        db.cache_set(cache_key, result, CACHE_TTL["tick"])
        return result
    return None


def get_crypto_bulk(symbols: list[str], vs_currency: str = "usd") -> dict[str, Optional[dict]]:
    """Birden fazla kripto sembolü için toplu fiyat."""
    sym_str = ",".join(s.lower() for s in symbols)
    cache_key = f"massive:crypto_bulk:{sym_str}:{vs_currency}"
    cached = db.cache_get(cache_key)
    if cached:
        return cached

    data = _get("/crypto/prices", params={"symbols": sym_str, "vs_currency": vs_currency})
    results = {}
    if data and isinstance(data, list):
        for item in data:
            sym = item.get("symbol", "").upper()
            results[sym] = {
                "symbol":         sym,
                "price":          item.get("price"),
                "change_pct_24h": item.get("changePercent24h"),
                "volume_24h":     item.get("volume24h"),
                "source":         "massive_market",
            }
    db.cache_set(cache_key, results, CACHE_TTL["tick"])
    return results


# ─── Emtia ────────────────────────────────────────────────────────────────────

def get_commodity(symbol: str) -> Optional[dict]:
    """
    Emtia fiyatı.
    Örnek: get_commodity("GOLD"), get_commodity("SILVER"), get_commodity("CRUDE_OIL")
    """
    cache_key = f"massive:commodity:{symbol}"
    cached = db.cache_get(cache_key)
    if cached:
        return cached

    data = _get(f"/commodities/{symbol.lower()}")
    if data:
        result = {
            "symbol":     symbol.upper(),
            "price":      data.get("price"),
            "unit":       data.get("unit"),
            "change_pct": data.get("changePercent"),
            "source":     "massive_market",
        }
        db.cache_set(cache_key, result, CACHE_TTL["tick"])
        return result
    return None


# ─── Piyasa Özeti ─────────────────────────────────────────────────────────────

def get_market_summary() -> Optional[dict]:
    """
    Küresel piyasa özeti: toplam market cap, kripto dominans, korku/açgözlülük endeksi.
    """
    cache_key = "massive:market_summary"
    cached = db.cache_get(cache_key)
    if cached:
        return cached

    data = _get("/market/summary")
    if data:
        db.cache_set(cache_key, data, CACHE_TTL["hourly"])
    return data


def get_movers(market: str = "us", direction: str = "gainers", limit: int = 10) -> Optional[list]:
    """
    Günün en çok kazanan / kaybeden hisseleri.
    market: us, tr, eu, crypto
    direction: gainers, losers
    """
    cache_key = f"massive:movers:{market}:{direction}:{limit}"
    cached = db.cache_get(cache_key)
    if cached:
        return cached

    data = _get("/market/movers", params={"market": market, "direction": direction, "limit": limit})
    if data and isinstance(data, list):
        db.cache_set(cache_key, data, CACHE_TTL["hourly"])
        return data
    return None


def get_news(symbol: str = None, limit: int = 20) -> Optional[list]:
    """
    Finansal haberler. symbol belirtilirse o hisseye ait haberler.
    """
    cache_key = f"massive:news:{symbol or 'global'}:{limit}"
    cached = db.cache_get(cache_key)
    if cached:
        return cached

    params = {"limit": limit}
    if symbol:
        params["symbol"] = symbol
    data = _get("/news", params=params)
    if data and isinstance(data, list):
        db.cache_set(cache_key, data, CACHE_TTL["hourly"])
        return data
    return None


# ─── Sağlık Kontrolü ──────────────────────────────────────────────────────────

def health_check() -> dict:
    """API bağlantısını test et. settings sayfasından çağrılabilir."""
    if not MASSIVE_MARKET_API_KEY:
        return {"status": "error", "message": "API key tanımlı değil"}
    data = _get("/status")
    if data:
        return {"status": "ok", "response": data}
    return {"status": "error", "message": "API'ye ulaşılamadı"}
