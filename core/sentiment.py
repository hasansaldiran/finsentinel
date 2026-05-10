"""
FinSentinel — Topluluk & Haber Sentiment Motoru
core/sentiment.py

Kaynaklar (tümü yasal / RSS / açık API):
  • Mevcut RSS feed'leri (config/settings.py → NEWS_RSS_FEEDS)
  • Google News RSS (sembol bazlı dinamik sorgu)
  • Investing.com TR RSS (genel / hisse bazlı)
  • CoinTelegraph / CryptoSlate (kripto)
  • TradingView: Kamuya açık RSS feed'i yok → Google News ile ikame edildi

Sentiment Yöntemi:
  Kural tabanlı Türkçe + İngilizce anahtar kelime skoru.
  ML modeli gerektirmez, bağımlılık eklenmez.

Kullanım:
    from core.sentiment import SentimentFeed
    feed = SentimentFeed()
    result = feed.analyze_symbol("GARAN", limit=20)
    # result.score      → -1.0 .. +1.0
    # result.label      → "güçlü_pozitif" | "pozitif" | "nötr" | "negatif" | "güçlü_negatif"
    # result.headlines  → list[dict]  (başlık, kaynak, url, skor, ts)
    # result.summary    → str
"""

from __future__ import annotations

import re
import time
import feedparser
import requests
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import quote_plus

from loguru import logger
from config.settings import NEWS_RSS_FEEDS, BIST_SYMBOLS


# ─────────────────────────────────────────────────────────────────────────────
# Anahtar Kelime Sözlükleri
# ─────────────────────────────────────────────────────────────────────────────

_POZITIF_TR = [
    "artış", "yükseliş", "rekor", "büyüme", "kar", "kâr", "kazanç", "güçlü",
    "rallisi", "rally", "atlaması", "toparlanma", "başarı", "pozitif",
    "yatırım", "temettü", "ihracat", "satın alma", "birleşme", "anlaşma",
    "genişleme", "büyüyor", "artıyor", "yükseliyor", "güçleniyor",
    "beklentilerin üzerinde", "olumlu", "ivme", "patlama", "zirve",
]
_NEGATIF_TR = [
    "düşüş", "gerileme", "kayıp", "zarar", "kriz", "endişe", "risk",
    "çöküş", "çakılma", "alarm", "tehlike", "sorun", "problem", "olumsuz",
    "daralma", "baskı", "sert satış", "iflas", "yaptırım", "dava",
    "manipülasyon", "manipüle", "soruşturma", "borç", "erteleme", "temerrüt",
    "beklentilerin altında", "zayıf", "endişe verici", "kritik",
]
_POZITIF_EN = [
    "surge", "rally", "record", "growth", "profit", "gain", "strong",
    "beat", "bullish", "outperform", "upgrade", "buy", "acquisition",
    "merger", "expansion", "above expectations", "positive", "recovery",
]
_NEGATIF_EN = [
    "drop", "fall", "decline", "loss", "crisis", "risk", "crash", "collapse",
    "warning", "miss", "bearish", "downgrade", "sell", "bankruptcy", "lawsuit",
    "investigation", "fraud", "debt", "default", "below expectations", "weak",
]

# Güçlendirici ifadeler — skor çarpanı
_GUCLENDIRICILER = ["%", "rekor", "tüm zamanların", "tarihsel", "sert", "ani", "büyük", "record", "historic"]


def _score_text(text: str) -> float:
    """
    Metin bazlı sentiment skoru: -1.0 .. +1.0
    Basit kelime frekansı ağırlıklı.
    """
    if not text:
        return 0.0
    low = text.lower()
    pos = sum(1 for w in _POZITIF_TR + _POZITIF_EN if w in low)
    neg = sum(1 for w in _NEGATIF_TR + _NEGATIF_EN if w in low)
    amp = 1 + 0.3 * sum(1 for w in _GUCLENDIRICILER if w in low)

    total = pos + neg
    if total == 0:
        return 0.0

    raw = (pos - neg) / total
    return max(-1.0, min(1.0, raw * amp))


def _label(score: float) -> str:
    if score >= 0.5:
        return "güçlü_pozitif"
    elif score >= 0.15:
        return "pozitif"
    elif score <= -0.5:
        return "güçlü_negatif"
    elif score <= -0.15:
        return "negatif"
    return "nötr"


def _label_en(score: float) -> str:
    """İngilizce etiket (AI prompt'larında kullanılır)."""
    if score >= 0.5:   return "strongly bullish"
    if score >= 0.15:  return "bullish"
    if score <= -0.5:  return "strongly bearish"
    if score <= -0.15: return "bearish"
    return "neutral"


# ─────────────────────────────────────────────────────────────────────────────
# Veri Yapıları
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class Headline:
    title:   str
    source:  str
    url:     str
    score:   float          # -1..+1
    ts:      str            # ISO timestamp
    snippet: str = ""


@dataclass
class SentimentResult:
    symbol:     str
    score:      float       # Ağırlıklı ortalama
    label:      str         # Türkçe etiket
    label_en:   str         # İngilizce etiket (AI için)
    headlines:  list[Headline] = field(default_factory=list)
    pos_count:  int = 0
    neg_count:  int = 0
    neu_count:  int = 0
    summary:    str = ""    # En yüksek skorlu başlıkların özeti
    fetched_at: str = ""


# ─────────────────────────────────────────────────────────────────────────────
# RSS Yardımcısı
# ─────────────────────────────────────────────────────────────────────────────

_FEEDPARSER_TIMEOUT = 10
_MAX_AGE_HOURS      = 48


def _parse_feed(url: str, source_name: str, keyword: str = "") -> list[Headline]:
    """Tek RSS feed'ini parse eder, keyword filtresi uygular."""
    headlines = []
    try:
        feed = feedparser.parse(url, agent="FinSentinel/1.0", request_headers={"timeout": _FEEDPARSER_TIMEOUT})
        cutoff = datetime.utcnow() - timedelta(hours=_MAX_AGE_HOURS)

        for entry in feed.entries[:40]:
            title   = entry.get("title", "")
            snippet = entry.get("summary", entry.get("description", ""))[:200]
            url_e   = entry.get("link", "")

            # Tarih
            ts = ""
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                try:
                    pub_dt = datetime(*entry.published_parsed[:6])
                    if pub_dt < cutoff:
                        continue
                    ts = pub_dt.isoformat()
                except Exception:
                    ts = datetime.utcnow().isoformat()
            else:
                ts = datetime.utcnow().isoformat()

            # Keyword filtresi
            combined = (title + " " + snippet).lower()
            if keyword and keyword.lower() not in combined:
                # Türkçe karakter normalizasyonlu ikinci deneme
                norm = combined.replace("ğ","g").replace("ş","s").replace("ı","i") \
                               .replace("ö","o").replace("ü","u").replace("ç","c")
                kw_norm = keyword.lower().replace("ğ","g").replace("ş","s").replace("ı","i") \
                                         .replace("ö","o").replace("ü","u").replace("ç","c")
                if kw_norm not in norm:
                    continue

            score = _score_text(title + " " + snippet)
            headlines.append(Headline(
                title=title, source=source_name,
                url=url_e, score=score, ts=ts, snippet=snippet,
            ))
    except Exception as e:
        logger.debug(f"RSS parse [{source_name}]: {e}")

    return headlines


# ─────────────────────────────────────────────────────────────────────────────
# Ana Sentiment Feed Sınıfı
# ─────────────────────────────────────────────────────────────────────────────

class SentimentFeed:
    """
    Çoklu RSS kaynağından belirli bir sembol/konu için sentiment analizi.

    Kaynaklar:
      1. config/settings.py → NEWS_RSS_FEEDS (Dünya, Bloomberg HT, Ekonomim vb.)
      2. Google News RSS (Türkçe, sembol bazlı)
      3. Investing.com TR RSS (genel)
      4. CoinTelegraph / CryptoSlate (kripto)
    """

    _GOOGLE_NEWS_URL = (
        "https://news.google.com/rss/search"
        "?q={query}&hl=tr&gl=TR&ceid=TR:tr"
    )
    _INVESTING_TR = "https://tr.investing.com/rss/news.rss"

    def __init__(self):
        # Mevcut RSS feed'lerini settings'ten al
        self._feeds: dict[str, str] = NEWS_RSS_FEEDS.copy()

    # ── Sembol Bazlı Analiz ───────────────────────────────────────────────

    def analyze_symbol(
        self,
        symbol: str,
        limit: int = 25,
        include_google: bool = True,
    ) -> SentimentResult:
        """
        BIST sembolü için haber sentiment analizi.

        symbol: "GARAN" veya "GARAN.IS" — ".IS" otomatik kaldırılır.
        """
        clean_sym = symbol.replace(".IS", "").upper()
        headlines: list[Headline] = []

        # 1. Mevcut RSS kaynaklarını tara
        for source_name, url in self._feeds.items():
            fetched = _parse_feed(url, source_name, keyword=clean_sym)
            headlines.extend(fetched)

        # 2. Google News RSS — sembol adıyla
        if include_google:
            gn_url  = self._GOOGLE_NEWS_URL.format(query=quote_plus(f"{clean_sym} hisse borsa"))
            gn_hits = _parse_feed(gn_url, "Google Haberler", keyword="")
            headlines.extend(gn_hits[:15])

            # Şirket tam adıyla da ara (varsa)
            from config.settings import KATILIM_30_HISSELER
            sirket_adi = (KATILIM_30_HISSELER.get(clean_sym) or {}).get("ad", "")
            if sirket_adi:
                gn2_url  = self._GOOGLE_NEWS_URL.format(query=quote_plus(sirket_adi))
                gn2_hits = _parse_feed(gn2_url, "Google Haberler (Şirket)", keyword="")
                headlines.extend(gn2_hits[:10])

        # 3. Tekrar / duplikat temizle
        seen: set[str] = set()
        unique: list[Headline] = []
        for h in headlines:
            key = h.title[:60].lower()
            if key not in seen:
                seen.add(key)
                unique.append(h)

        # 4. Sırala + sınırla
        unique.sort(key=lambda h: (abs(h.score), h.ts), reverse=True)
        unique = unique[:limit]

        return self._build_result(clean_sym, unique)

    # ── Kripto Analizi ────────────────────────────────────────────────────

    def analyze_crypto(self, symbol: str, limit: int = 20) -> SentimentResult:
        """
        BTC, ETH vb. için kripto haber sentiment analizi.
        symbol: "BTCUSDT" → "BTC" olarak aranır.
        """
        clean = symbol.replace("USDT", "").replace("BTC", "Bitcoin") \
                      .replace("ETH", "Ethereum").replace("BNB", "Binance Coin")

        crypto_feeds = {
            "CoinTelegraph": "https://cointelegraph.com/rss",
            "CryptoSlate":   "https://cryptoslate.com/feed/",
            "Decrypt":       "https://decrypt.co/feed",
        }
        headlines: list[Headline] = []
        for src, url in crypto_feeds.items():
            headlines.extend(_parse_feed(url, src, keyword=clean[:3]))

        # Google News kripto
        gn_url = self._GOOGLE_NEWS_URL.format(query=quote_plus(f"{clean} kripto fiyat"))
        headlines.extend(_parse_feed(gn_url, "Google Kripto", keyword="")[:10])

        seen: set[str] = set()
        unique = []
        for h in headlines:
            k = h.title[:60].lower()
            if k not in seen:
                seen.add(k)
                unique.append(h)

        unique.sort(key=lambda h: (abs(h.score), h.ts), reverse=True)
        return self._build_result(symbol.replace("USDT",""), unique[:limit])

    # ── Genel Piyasa Sentimenti ───────────────────────────────────────────

    def analyze_market(self, limit: int = 30) -> SentimentResult:
        """
        Genel BIST / Türkiye ekonomi sentiment analizi.
        Tüm RSS kaynaklarını toplar.
        """
        headlines: list[Headline] = []
        for src, url in self._feeds.items():
            headlines.extend(_parse_feed(url, src, keyword=""))

        gn_url = self._GOOGLE_NEWS_URL.format(query=quote_plus("borsa istanbul bist hisse"))
        headlines.extend(_parse_feed(gn_url, "Google Borsa", keyword="")[:15])

        seen: set[str] = set()
        unique = []
        for h in headlines:
            k = h.title[:60].lower()
            if k not in seen:
                seen.add(k)
                unique.append(h)

        unique.sort(key=lambda h: (abs(h.score), h.ts), reverse=True)
        return self._build_result("MARKET", unique[:limit])

    # ── İç Yardımcı ──────────────────────────────────────────────────────

    @staticmethod
    def _build_result(symbol: str, headlines: list[Headline]) -> SentimentResult:
        if not headlines:
            return SentimentResult(
                symbol=symbol, score=0.0,
                label="nötr", label_en="neutral",
                fetched_at=datetime.utcnow().isoformat(),
            )

        # Ağırlıklı ortalama (|score| büyükse daha fazla ağırlık)
        weights = [max(abs(h.score), 0.1) for h in headlines]
        w_total = sum(weights)
        w_score = sum(h.score * w for h, w in zip(headlines, weights)) / w_total

        pos = sum(1 for h in headlines if h.score > 0.1)
        neg = sum(1 for h in headlines if h.score < -0.1)
        neu = len(headlines) - pos - neg

        # Özet: en yüksek mutlak skorlu 5 başlık
        top5 = sorted(headlines, key=lambda h: abs(h.score), reverse=True)[:5]
        summary = " | ".join(h.title[:80] for h in top5)

        return SentimentResult(
            symbol=symbol,
            score=round(w_score, 3),
            label=_label(w_score),
            label_en=_label_en(w_score),
            headlines=headlines,
            pos_count=pos,
            neg_count=neg,
            neu_count=neu,
            summary=summary,
            fetched_at=datetime.utcnow().isoformat(),
        )
