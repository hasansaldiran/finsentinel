"""
FinSentinel — Halka Arz (IPO) Verileri
core/ipo_fetcher.py

KAP halka arz sayfasından yaklaşan/son halka arzları çeker,
yfinance ile ilk gün + 1 hafta + 1 ay + güncel getiri performansını hesaplar.

Veri kaynakları (öncelik sırasıyla):
  1. KAP resmi halka arz sayfası (scraping)
  2. data/ipo_calendar.json (fallback)

Tüm fonksiyonlar TTL cache'li — aynı veri dakikalarca tekrar çekilmez.
"""
from __future__ import annotations

import json
import os
import time
import logging
from datetime import datetime, timedelta
from typing import Optional

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

_KAP_IPO_URLS = [
    "https://www.kap.org.tr/tr/halka-arz-bilgileri",
    "https://www.kap.org.tr/tr/HalkaArz",
    "https://www.borsaistanbul.com/tr/sayfa/165/halka-arzlar",
]
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
_HEADERS = {"User-Agent": _USER_AGENT, "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8"}

# Basit modül-seviyesi TTL cache
_CACHE: dict = {}
_CACHE_TTL = 3600  # 1 saat


def _cache_get(key: str):
    item = _CACHE.get(key)
    if not item:
        return None
    if time.time() - item["ts"] > _CACHE_TTL:
        _CACHE.pop(key, None)
        return None
    return item["value"]


def _cache_set(key: str, value) -> None:
    _CACHE[key] = {"ts": time.time(), "value": value}


def _fallback_path() -> str:
    """data/ipo_calendar.json yolunu döner (proje kök tabanlı)."""
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.dirname(here)
    return os.path.join(root, "data", "ipo_calendar.json")


def _load_fallback() -> dict:
    """Fallback JSON dosyasından halka arz verisini yükler."""
    path = _fallback_path()
    if not os.path.exists(path):
        return {"upcoming": [], "recent": []}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f) or {"upcoming": [], "recent": []}
    except Exception as e:
        logger.warning(f"ipo_fetcher fallback yüklenemedi: {e}")
        return {"upcoming": [], "recent": []}


def _scrape_kap_ipos() -> dict:
    """KAP halka arz sayfasını scraping ile dener. Başarısızsa boş dict döner."""
    resp = None
    last_err = None
    for url in _KAP_IPO_URLS:
        try:
            r = requests.get(url, headers=_HEADERS, timeout=15)
            r.raise_for_status()
            resp = r
            break
        except Exception as e:
            last_err = e
            continue
    if resp is None:
        logger.warning(f"Halka arz sayfası hiçbir kaynaktan çekilemedi: {last_err}")
        return {}

    try:
        soup = BeautifulSoup(resp.text, "html.parser")
        upcoming: list[dict] = []
        recent: list[dict] = []

        # KAP sayfasında halka arzlar genelde tablolar halinde gelir.
        tables = soup.find_all("table")
        for table in tables:
            rows = table.find_all("tr")
            for tr in rows[1:]:  # başlık satırını atla
                cells = [c.get_text(strip=True) for c in tr.find_all(["td", "th"])]
                if len(cells) < 3:
                    continue
                # Heuristik: ilk hücre şirket ismi, sonra tarih/fiyat kolonları
                record = {
                    "sirket": cells[0],
                    "sektor": cells[1] if len(cells) > 1 else "-",
                    "arz_tarihi": cells[2] if len(cells) > 2 else "-",
                    "arz_fiyati": cells[3] if len(cells) > 3 else "-",
                    "arz_buyuklugu": cells[4] if len(cells) > 4 else "-",
                    "konsorsiyum": cells[5] if len(cells) > 5 else "-",
                }
                # Tarih parse denemesi — gelecekteyse upcoming, değilse recent
                try:
                    dt = _parse_tr_date(record["arz_tarihi"])
                    if dt and dt >= datetime.now().date():
                        upcoming.append(record)
                    else:
                        recent.append(record)
                except Exception:
                    upcoming.append(record)

        return {"upcoming": upcoming, "recent": recent}
    except Exception as e:
        logger.exception(f"KAP halka arz parse hatası: {e}")
        return {}


def _parse_tr_date(s: str):
    """'12.03.2026' veya '2026-03-12' gibi Türkçe tarih stringini date'e çevirir."""
    if not s or s == "-":
        return None
    s = s.strip()
    for fmt in ("%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def get_upcoming_ipos() -> list[dict]:
    """Yaklaşan halka arzların listesini döner.

    Dönüş öğeleri: {sirket, sektor, arz_tarihi, arz_fiyati, arz_buyuklugu, konsorsiyum}
    """
    cached = _cache_get("upcoming")
    if cached is not None:
        return cached

    data = _scrape_kap_ipos()
    upcoming = data.get("upcoming") if data else None

    if not upcoming:
        # Fallback: JSON dosyası
        fb = _load_fallback()
        upcoming = fb.get("upcoming", [])

    _cache_set("upcoming", upcoming)
    return upcoming


def calculate_ipo_performance(symbol: str, ipo_price: float, ipo_date: str) -> dict:
    """yfinance ile halka arz performansını hesaplar.

    Dönüş: {ilk_acilis, ilk_kapanis, hafta_getiri_pct, ay_getiri_pct,
            guncel_fiyat, toplam_getiri_pct}
    """
    result = {
        "ilk_acilis": None,
        "ilk_kapanis": None,
        "hafta_getiri_pct": None,
        "ay_getiri_pct": None,
        "guncel_fiyat": None,
        "toplam_getiri_pct": None,
    }
    try:
        import yfinance as yf
        # BIST sembolü ise .IS ekle
        sym = symbol.upper()
        if "." not in sym and not sym.endswith("=X"):
            sym = f"{sym}.IS"

        dt = _parse_tr_date(ipo_date)
        if not dt:
            return result

        start = dt.strftime("%Y-%m-%d")
        end = (datetime.now().date() + timedelta(days=1)).strftime("%Y-%m-%d")
        hist = yf.download(
            sym, start=start, end=end,
            auto_adjust=True, progress=False, multi_level_index=False,
        )
        if hist is None or hist.empty:
            return result

        # İlk gün
        first_row = hist.iloc[0]
        first_open = float(first_row.get("Open", 0) or 0)
        first_close = float(first_row.get("Close", 0) or 0)
        result["ilk_acilis"] = round(first_open, 2)
        result["ilk_kapanis"] = round(first_close, 2)

        # 1 hafta sonra
        if len(hist) >= 6:
            wk_close = float(hist.iloc[5].get("Close", 0) or 0)
            if ipo_price:
                result["hafta_getiri_pct"] = round((wk_close - ipo_price) / ipo_price * 100, 2)

        # 1 ay sonra (~22 iş günü)
        if len(hist) >= 22:
            mo_close = float(hist.iloc[21].get("Close", 0) or 0)
            if ipo_price:
                result["ay_getiri_pct"] = round((mo_close - ipo_price) / ipo_price * 100, 2)

        # Güncel
        last_close = float(hist.iloc[-1].get("Close", 0) or 0)
        result["guncel_fiyat"] = round(last_close, 2)
        if ipo_price:
            result["toplam_getiri_pct"] = round((last_close - ipo_price) / ipo_price * 100, 2)
    except Exception as e:
        logger.debug(f"calculate_ipo_performance {symbol} hatası: {e}")
    return result


def get_recent_ipos(days: int = 365) -> list[dict]:
    """Son `days` gündeki halka arzları getiri bilgisiyle birlikte döner."""
    cache_key = f"recent_{days}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    data = _scrape_kap_ipos()
    recent = data.get("recent") if data else None

    if not recent:
        fb = _load_fallback()
        recent = fb.get("recent", [])

    cutoff = datetime.now().date() - timedelta(days=days)
    enriched: list[dict] = []
    for rec in recent:
        dt = _parse_tr_date(rec.get("arz_tarihi", ""))
        if dt and dt < cutoff:
            continue
        sym = rec.get("sembol") or rec.get("kod") or rec.get("sirket", "").split()[0]
        try:
            price_str = str(rec.get("arz_fiyati", "0")).replace(",", ".").replace("TL", "").strip()
            ipo_price = float(price_str) if price_str and price_str != "-" else 0.0
        except ValueError:
            ipo_price = 0.0

        perf = calculate_ipo_performance(sym, ipo_price, rec.get("arz_tarihi", ""))
        merged = {**rec, **perf, "sembol": sym, "arz_fiyati_num": ipo_price}
        enriched.append(merged)

    _cache_set(cache_key, enriched)
    return enriched


def get_ipo_statistics(recent: Optional[list[dict]] = None) -> dict:
    """Son halka arzların özet istatistiklerini hesaplar."""
    if recent is None:
        recent = get_recent_ipos(365)
    total = len(recent)
    if total == 0:
        return {
            "toplam_adet": 0,
            "pozitif_oran": 0.0,
            "ort_ilk_gun_getiri": 0.0,
            "ort_ay_getiri": 0.0,
        }

    def _avg(key: str) -> float:
        vals = [r.get(key) for r in recent if isinstance(r.get(key), (int, float))]
        return round(sum(vals) / len(vals), 2) if vals else 0.0

    def _first_day_return(r: dict) -> Optional[float]:
        p = r.get("arz_fiyati_num") or 0
        c = r.get("ilk_kapanis") or 0
        if p and c:
            return (c - p) / p * 100
        return None

    fd_returns = [x for x in (_first_day_return(r) for r in recent) if x is not None]
    positive = sum(1 for r in recent if (r.get("toplam_getiri_pct") or 0) > 0)

    return {
        "toplam_adet": total,
        "pozitif_oran": round(positive / total * 100, 1),
        "ort_ilk_gun_getiri": round(sum(fd_returns) / len(fd_returns), 2) if fd_returns else 0.0,
        "ort_ay_getiri": _avg("ay_getiri_pct"),
    }
