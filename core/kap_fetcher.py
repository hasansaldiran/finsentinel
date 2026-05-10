"""
FinSentinel — KAP (Kamuyu Aydınlatma Platformu) Veri Çekici
core/kap_fetcher.py

KAP'ın açık JSON API'sini kullanarak duyuru çeker.
API: https://www.kap.org.tr/tr/api/...
"""
import requests
import pandas as pd
from datetime import datetime, timedelta
from loguru import logger

KAP_BASE = "https://www.kap.org.tr/tr/api"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.kap.org.tr/",
}

# Duyuru tip etiketleri
DISCLOSURE_TYPES = {
    "FR": "Finansal Rapor",
    "DD": "Özel Durum",
    "GM": "Genel Kurul",
    "BF": "Bağımsız Denetim",
    "YK": "Yönetim Kurulu",
    "SR": "Sürdürülebilirlik",
    "FD": "Fon Duyurusu",
    "PAY": "Pay Alım Satım",
    "MDV": "Maddi Duran Varlık",
}

IMPORTANCE_KEYWORDS = [
    "kâr", "zarar", "temettü", "birleşme", "satın alma",
    "halka arz", "sermaye", "borç", "ihraç", "ortaklık",
    "sözleşme", "anlaşma", "iştirak", "devir", "lisans",
    "yeni iş ilişkisi", "pay alım satım", "fiyat istikrarı",
]

SMART_MONEY_KEYWORDS = [
    "pay alım satım", "maddi duran varlık alımı", "yeni iş ilişkisi", 
    "ihaleye girilmesi", "ihale kazanılması", "teşvik belgesi",
    "geri alınan paylar", "özel durum açıklaması (genel)"
]


def _get_member_oid(sym: str) -> str | None:
    """KAP üye arama: sembol → OID (örnek: GARAN → '1234567890')"""
    try:
        url = f"https://www.kap.org.tr/tr/api/member/search?keyword={sym}"
        resp = requests.get(url, headers=HEADERS, timeout=6)
        if resp.status_code == 200:
            data = resp.json()
            items = data if isinstance(data, list) else data.get("data", [])
            for item in items:
                code = (item.get("stockCode") or item.get("memberCode") or "").upper()
                if code == sym:
                    oid = item.get("memberOid") or item.get("oid") or item.get("id")
                    if oid:
                        return str(oid)
    except Exception:
        pass
    return None


def fetch_disclosures(symbol: str = None, limit: int = 20) -> list[dict]:
    """KAP'tan son duyuruları çek — birden fazla endpoint dene"""
    endpoints_to_try = []

    if symbol:
        sym = symbol.replace(".IS", "").upper()
        # OID üzerinden erişim dene (daha güvenilir)
        oid = _get_member_oid(sym)

        endpoints_to_try = []
        if oid:
            endpoints_to_try += [
                f"https://www.kap.org.tr/tr/api/memberDisclosures/{oid}?page=1&pageSize={limit}",
                f"https://www.kap.org.tr/tr/api/disclosure/member/{oid}?size={limit}",
            ]
        # Stock code bazlı endpoint'ler
        endpoints_to_try += [
            f"{KAP_BASE}/disclosures?memberCode={sym}&page=1&pageSize={limit}",
            f"https://www.kap.org.tr/tr/api/memberDisclosures/{sym}?page=1&pageSize={limit}",
            f"https://www.kap.org.tr/tr/api/disclosure/company/{sym}?size={limit}",
            f"https://www.kap.org.tr/tr/api/disclosure?stockCode={sym}&pageSize={limit}",
        ]
    else:
        endpoints_to_try = [
            f"{KAP_BASE}/disclosures?page=1&pageSize={limit}",
            f"https://www.kap.org.tr/tr/api/latestDisclosures?size={limit}",
            f"https://www.kap.org.tr/tr/api/disclosure/latest?size={limit}",
            f"https://www.kap.org.tr/tr/api/disclosure?page=1&pageSize={limit}",
        ]

    for url in endpoints_to_try:
        try:
            resp = requests.get(url, headers=HEADERS, timeout=8)
            if resp.status_code == 200 and resp.content:
                try:
                    data = resp.json()
                except Exception:
                    continue

                items = data if isinstance(data, list) else data.get("data", data.get("items", data.get("content", [])))

                if not items:
                    continue

                result = []
                for item in items:
                    try:
                        published = (item.get("publishDate") or item.get("disclosureDate")
                                   or item.get("publishDatetime") or item.get("date", ""))
                        title = (item.get("title") or item.get("summary")
                               or item.get("subject") or item.get("disclosureTitle", "Başlık yok"))
                        company = (item.get("memberTitle") or item.get("companyName")
                                 or item.get("stockCode") or item.get("company", ""))
                        disc_type = item.get("disclosureClass") or item.get("type", "")
                        url_path = (item.get("url") or item.get("disclosureUrl")
                                   or item.get("path") or item.get("link", ""))

                        importance = "normal"
                        title_lower = str(title).lower()
                        if any(kw in title_lower for kw in IMPORTANCE_KEYWORDS):
                            importance = "high"

                        full_url = ""
                        if url_path:
                            if url_path.startswith("http"):
                                full_url = url_path
                            else:
                                full_url = f"https://www.kap.org.tr{url_path}"

                        result.append({
                            "company":    company,
                            "title":      str(title)[:200],
                            "type":       disc_type,
                            "type_label": DISCLOSURE_TYPES.get(disc_type, disc_type or "Diğer"),
                            "published":  str(published)[:16] if published else "",
                            "importance": importance,
                            "url":        full_url or "https://www.kap.org.tr/tr/duyurular",
                        })
                    except Exception:
                        continue

                if result:
                    return result[:limit]
        except Exception:
            continue

    return []


def fetch_smart_money(limit: int = 20) -> list[dict]:
    """
    Smart Money sinyalleri: KAP API (bloklu) → yfinance insider → Google News RSS fallback.
    KAP API 666 bot-bloğu nedeniyle erişilemez; alternatif yasal kaynaklar kullanılır.
    """
    results = []

    # ── 1. yfinance: portföy sembollerinde insider işlemleri ─────────────────
    try:
        from config.settings import BIST_SYMBOLS
        check_syms = (BIST_SYMBOLS or [])[:15]  # İlk 15 sembol — performans
        for sym in check_syms:
            try:
                ticker = __import__("yfinance").Ticker(sym)
                ins = ticker.insider_transactions
                if ins is not None and not ins.empty:
                    for _, row in ins.head(3).iterrows():
                        try:
                            name  = str(row.get("Insider", row.get("insider", "Insider")))
                            ttype = str(row.get("Transaction", row.get("transaction", "")))
                            val   = row.get("Value", row.get("value", 0)) or 0
                            date  = str(row.get("Start Date", row.get("startDate", "")))[:10]
                            if not ttype:
                                continue
                            is_buy = "purchase" in ttype.lower() or "buy" in ttype.lower() or "alım" in ttype.lower()
                            label  = "👔 Insider Alım" if is_buy else "📤 Insider Satım"
                            results.append({
                                "company":    sym.replace(".IS", ""),
                                "title":      f"{name} — {ttype} ({val:,.0f} USD)" if val else f"{name} — {ttype}",
                                "type":       "PAY",
                                "type_label": label,
                                "published":  date,
                                "importance": "smart_money",
                                "url":        f"https://finance.yahoo.com/quote/{sym}/insider-transactions",
                            })
                        except Exception:
                            continue
            except Exception:
                continue
        if results:
            return results[:limit]
    except Exception as e:
        logger.debug(f"yfinance insider hatası: {e}")

    # ── 2. Google News RSS: insider/temettü/anlaşma haberleri ─────────────────
    try:
        import feedparser, urllib.parse
        queries = [
            "BIST hisse insider alım satım",
            "borsa temettü anlaşma sözleşme türkiye",
            "BIST pay alım satım büyük yatırımcı",
        ]
        seen = set()
        for q in queries:
            url = f"https://news.google.com/rss/search?q={urllib.parse.quote(q)}&hl=tr&gl=TR&ceid=TR:tr"
            feed = feedparser.parse(url)
            for entry in feed.entries[:5]:
                t = entry.get("title", "")
                if t in seen:
                    continue
                seen.add(t)
                published = entry.get("published", "")[:16] if entry.get("published") else ""
                # Keyword filtresi
                t_lower = t.lower()
                if not any(kw in t_lower for kw in ["alım", "satım", "temettü", "anlaşma", "sözleşme", "insider", "büyük", "fon"]):
                    continue
                results.append({
                    "company":    "",
                    "title":      t[:100],
                    "type":       "NEWS",
                    "type_label": "📰 Haber",
                    "published":  published,
                    "importance": "smart_money",
                    "url":        entry.get("link", "https://news.google.com"),
                })
            if len(results) >= limit:
                break
    except Exception as e:
        logger.debug(f"Google News RSS insider hatası: {e}")

    return results[:limit]


def fetch_disclosures_fallback(symbol: str = None, limit: int = 15) -> list[dict]:
    """
    KAP API çalışmazsa RSS/HTML tabanlı fallback.
    Çalışmayan API endpoint'i için demo verisi döner.
    """
    # Gerçek API çalışmazsa örnek yapıyı döndür (hiç veri yoktan iyi)
    now = datetime.now()
    sample = [
        {
            "company":    "KAP Duyuruları",
            "title":      "KAP API bağlantısı kurulamadı. Duyurular için kap.org.tr'yi ziyaret edin.",
            "type":       "INFO",
            "type_label": "Bilgi",
            "published":  now.strftime("%Y-%m-%d %H:%M"),
            "importance": "normal",
            "url":        "https://www.kap.org.tr/tr/duyurular",
        }
    ]
    return sample


def get_kap_disclosures(symbol: str = None, limit: int = 20) -> list[dict]:
    """Ana giriş noktası — API başarısız olursa fallback kullan"""
    result = fetch_disclosures(symbol=symbol, limit=limit)
    if not result:
        result = fetch_disclosures_fallback(symbol=symbol, limit=limit)
    return result


def render_kap_card(disclosure: dict, theme: dict) -> str:
    """KAP duyurusu için HTML kart"""
    imp = disclosure.get("importance", "normal")
    border_color = theme["yellow"] if imp == "high" else theme["border"]
    type_color = theme["blue"]

    title = disclosure.get("title", "")
    company = disclosure.get("company", "")
    published = disclosure.get("published", "")
    type_label = disclosure.get("type_label", "Diğer")
    url = disclosure.get("url", "https://www.kap.org.tr")

    high_badge = f'<span style="background:{theme["yellow"]}22;color:{theme["yellow"]};font-size:10px;padding:2px 6px;border-radius:10px;margin-left:6px">⭐ Önemli</span>' if imp == "high" else ""

    return (
        f'<div style="background:{theme["bg_card"]};border:1px solid {border_color};'
        f'border-left:3px solid {border_color};border-radius:8px;padding:12px 14px;margin:6px 0">'
        f'<div style="display:flex;justify-content:space-between;align-items:flex-start">'
        f'<div style="flex:1">'
        f'<div style="color:{theme["text_muted"]};font-size:11px;margin-bottom:4px">'
        f'<span style="color:{type_color}">{type_label}</span>'
        f' • {company} • {published}'
        f'{high_badge}</div>'
        f'<div style="color:{theme["text_primary"]};font-size:13px;line-height:1.4">{title}</div>'
        f'</div>'
        f'</div>'
        f'<div style="margin-top:8px">'
        f'<a href="{url}" target="_blank" style="color:{theme["blue"]};font-size:11px;text-decoration:none">'
        f'→ KAP\'ta görüntüle</a>'
        f'</div>'
        f'</div>'
    )
