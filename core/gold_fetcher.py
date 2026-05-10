"""
FinSentinel — Türk Altın Fiyatları
core/gold_fetcher.py

Kaynak önceliği:
  1. haremaltin.com  — HTML tablo parse (td bazlı, kolon sıralı)
  2. canlidoviz.com  — HTML tablo parse
  3. Fallback        — yfinance ONS × USD/TRY kuru hesaplama
"""

import re
import time
import requests
from datetime import datetime
from loguru import logger

_CACHE: dict = {}
_CACHE_TTL = 90   # saniye

# ── Beklenen fiyat aralıkları (doğrulama için, TL) ───────────────────────────
# Gram altın ~3000-20000, çeyrek ~5500-35000, vs.
_VALID_RANGES = {
    "gram_altin":       (1_000,  30_000),
    "bilezik_22":       (900,    29_000),
    "has_altin":        (1_000,  30_000),
    "gumus_gram":       (30,     1_500),
    "ceyrek_altin":     (1_750,  55_000),
    "yarim_altin":      (3_500,  110_000),
    "tam_altin":        (7_000,  220_000),
    "cumhuriyet_altin": (7_000,  220_000),
    "ata_altin":        (7_000,  220_000),
}

# ── Ürün adı eşleşme kuralları ────────────────────────────────────────────────
_NAME_MAP = [
    ("gram_altin",       ["gram altın", "gram altin", "gram"]),
    ("ceyrek_altin",     ["çeyrek altın", "ceyrek altin", "çeyrek", "ceyrek"]),
    ("yarim_altin",      ["yarım altın", "yarim altin", "yarım", "yarim"]),
    ("tam_altin",        ["tam altın", "tam altin", "tam "]),
    ("cumhuriyet_altin", ["cumhuriyet altın", "cumhuriyet altin", "cumhuriyet"]),
    ("ata_altin",        ["ata altın", "ata altin", "ata "]),
    ("bilezik_22",       ["22 ayar", "bilezik 22", "22ayar", "bilezik"]),
    ("has_altin",        ["has altın", "has altin", "24 ayar", "995", "has"]),
    ("gumus_gram",       ["gram gümüş", "gümüş gram", "gram gumus", "gümüş", "gumus"]),
]

GOLD_LABELS = {
    "gram_altin":       ("💛 Gram Altın",           "g"),
    "ceyrek_altin":     ("🪙 Çeyrek Altın",         "adet"),
    "yarim_altin":      ("🪙 Yarım Altın",           "adet"),
    "tam_altin":        ("🥇 Tam Altın",             "adet"),
    "cumhuriyet_altin": ("🏛️ Cumhuriyet Altını",    "adet"),
    "ata_altin":        ("🏛️ Ata Altın",            "adet"),
    "bilezik_22":       ("📿 Bilezik (22 Ayar)",    "g"),
    "has_altin":        ("✨ Has Altın (24 Ayar)",   "g"),
    "gumus_gram":       ("🥈 Gram Gümüş",           "g"),
}

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "tr-TR,tr;q=0.9",
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
}


# ─── Ana giriş noktası ────────────────────────────────────────────────────────

def get_gold_prices(force: bool = False) -> dict:
    if not force and _CACHE.get("_ts") and (time.time() - _CACHE["_ts"]) < _CACHE_TTL:
        return _CACHE

    data = _fetch_haremaltin() or _fetch_canlidoviz() or _calc_from_yfinance()
    if data:
        _CACHE.clear()
        _CACHE.update(data)
        _CACHE["_ts"] = time.time()
    return _CACHE


# ─── Sayı dönüştürücü ─────────────────────────────────────────────────────────

def _parse_tr_number(s: str) -> float | None:
    """
    Türkçe/İngilizce format sayıyı float'a çevirir.
    "4.328,50" → 4328.50
    "4,328.50" → 4328.50
    "4328"     → 4328.0
    """
    s = s.strip()
    # Hem nokta hem virgül varsa Türkçe format
    if "." in s and "," in s:
        if s.index(".") < s.index(","):   # 4.328,50
            s = s.replace(".", "").replace(",", ".")
        else:                              # 4,328.50
            s = s.replace(",", "")
    elif "," in s:
        # Sadece virgül: ondalık mı yoksa binlik mi?
        parts = s.split(",")
        if len(parts) == 2 and len(parts[1]) <= 2:
            s = s.replace(",", ".")        # 4328,50 → 4328.50
        else:
            s = s.replace(",", "")         # 4,328 → 4328
    try:
        return float(s)
    except Exception:
        return None


def _valid(val: float, key: str) -> bool:
    lo, hi = _VALID_RANGES.get(key, (0, 999_999_999))
    return lo <= val <= hi


def _match_key(text: str) -> str | None:
    t = text.lower().strip()
    for key, aliases in _NAME_MAP:
        for alias in aliases:
            if alias in t:
                return key
    return None


# ─── TD bazlı tablo parser (her iki site için) ───────────────────────────────

def _parse_table_html(html: str, source: str) -> dict | None:
    """
    HTML içindeki <tr>…</tr> satırlarını tek tek okur.
    Her satır için:
      - İlk <td> ürün adını içerir
      - Sonraki td'lerden ilk geçerli alış/satış çifti alınır
    """
    result = {}

    # Tüm tr bloklarını al
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.DOTALL | re.IGNORECASE)

    for row in rows:
        # td içeriklerini temizle
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.DOTALL | re.IGNORECASE)
        cells = [re.sub(r"<[^>]+>", "", c).strip() for c in cells]
        cells = [c for c in cells if c]

        if len(cells) < 2:
            continue

        key = _match_key(cells[0])
        if not key:
            continue

        # Alış ve satış sayılarını bul (kolon sırasıyla)
        prices = []
        for cell in cells[1:]:
            val = _parse_tr_number(cell)
            if val and _valid(val, key):
                prices.append(round(val, 2))
            if len(prices) == 2:
                break

        if len(prices) >= 2:
            # Alış her zaman satıştan küçük olmalı; ters geldiyse düzelt
            alis  = min(prices[0], prices[1])
            satis = max(prices[0], prices[1])
            result[key] = {
                "alis":        alis,
                "satis":       satis,
                "degisim_pct": 0.0,
            }
        elif len(prices) == 1:
            result[key] = {
                "alis":  prices[0],
                "satis": prices[0],
                "degisim_pct": 0.0,
            }

    if len(result) >= 3:
        result["source"]     = source
        result["updated_at"] = datetime.now().isoformat()
        return result
    return None


# ─── Kaynak 1: haremaltin.com ────────────────────────────────────────────────

def _fetch_haremaltin() -> dict | None:
    urls = [
        "https://www.haremaltin.com/altin-fiyatlari",
        "https://www.haremaltin.com/",
    ]
    for url in urls:
        try:
            r = requests.get(url, headers=_HEADERS, timeout=10)
            if not r.ok:
                continue
            r.encoding = "utf-8"
            data = _parse_table_html(r.text, "haremaltin.com")
            if data:
                logger.debug(f"haremaltin: {len(data)-2} ürün çekildi")
                return data
        except Exception as e:
            logger.debug(f"haremaltin {url} hatası: {e}")
    return None


# ─── Kaynak 2: canlidoviz.com ────────────────────────────────────────────────

def _fetch_canlidoviz() -> dict | None:
    urls = [
        "https://canlidoviz.com/altin-fiyatlari",
        "https://canlidoviz.com/doviz-kurlari",
        "https://canlidoviz.com/",
    ]
    for url in urls:
        try:
            r = requests.get(url, headers=_HEADERS, timeout=10)
            if not r.ok:
                continue
            r.encoding = "utf-8"
            data = _parse_table_html(r.text, "canlidoviz.com")
            if data:
                logger.debug(f"canlidoviz: {len(data)-2} ürün çekildi")
                return data
        except Exception as e:
            logger.debug(f"canlidoviz {url} hatası: {e}")
    return None


# ─── Kaynak 3: Hesaplama (yfinance fallback) ──────────────────────────────────

def _calc_from_yfinance() -> dict | None:
    """
    ONS (GC=F) × USD/TRY ÷ 31.1035 = gram altın TL
    Diğer ürünler katsayıyla türetilir.
    """
    try:
        import yfinance as yf

        tickers = yf.download(
            ["GC=F", "USDTRY=X", "SI=F"],
            period="2d", auto_adjust=True,
            progress=False, multi_level_index=False,
        )
        if tickers.empty:
            return None

        close   = tickers["Close"].iloc[-1]
        ons_usd = float(close.get("GC=F",     0) or 0)
        usd_try = float(close.get("USDTRY=X", 0) or 0)
        si_usd  = float(close.get("SI=F",     0) or 0)

        if not ons_usd or not usd_try:
            return None

        gram_try = ons_usd * usd_try / 31.1035

        def _pair(val):
            v = round(val, 2)
            return {"alis": v, "satis": round(v * 1.005, 2), "degisim_pct": 0.0}

        result = {
            "gram_altin":       _pair(gram_try),
            "bilezik_22":       _pair(gram_try * 0.916),
            "has_altin":        _pair(gram_try * 0.995),
            "ceyrek_altin":     _pair(gram_try * 1.75),
            "yarim_altin":      _pair(gram_try * 3.50),
            "tam_altin":        _pair(gram_try * 7.00),
            "cumhuriyet_altin": _pair(gram_try * 7.216),
            "ata_altin":        _pair(gram_try * 7.216),
        }
        if si_usd:
            result["gumus_gram"] = _pair(si_usd * usd_try / 31.1035)

        result["source"]     = f"hesaplama (ONS=${ons_usd:,.0f} × {usd_try:.2f}₺)"
        result["updated_at"] = datetime.now().isoformat()
        logger.info(f"Altın fallback: gram≈{gram_try:,.0f}₺")
        return result

    except Exception as e:
        logger.debug(f"_calc_from_yfinance hatası: {e}")
        return None
