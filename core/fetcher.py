"""
FinSentinel — Merkezi Veri Çekici
core/fetcher.py
yfinance, ccxt, TCMB EVDS, CoinGecko
"""
import time
import requests
import pandas as pd
import numpy as np
import yfinance as yf
import feedparser
from datetime import datetime, timedelta
from typing import Optional
from loguru import logger

from config.settings import (
    TCMB_API_KEY, ALPHA_VANTAGE_KEY, COINGECKO_API_KEY,
    BIST_SYMBOLS, BIST_INDEX, FOREX_PAIRS, CRYPTO_SYMBOLS,
    COMMODITY_SYMBOLS, WORLD_INDICES, TCMB_SERIES, NEWS_RSS_FEEDS,
    CACHE_TTL, TIMEZONE
)
from core.db import db


# ─── Yardımcı ─────────────────────────────────────────────────────────────────

def _now_istanbul():
    import pytz
    return datetime.now(pytz.timezone(TIMEZONE))


def _pct_change(current: float, previous: float) -> float:
    if previous and previous != 0:
        return round((current - previous) / abs(previous) * 100, 2)
    return 0.0


# ─── Anlık Fiyat Çekici ───────────────────────────────────────────────────────

class PriceFetcher:
    """
    Tüm varlık tipleri için anlık ve tarihsel fiyat çekimi.
    Cache-first yaklaşım: önce DB cache'e bak, yoksa API'ye git.
    """

    # ── Genel OHLCV (yfinance) ────────────────────────────────────────────

    # Bilinen delisted / 404 verecek semboller — atla, crash'i önle
    _SKIP_SYMBOLS = frozenset({
        "KOZAL.IS", "IIAG.IS", "THYAO",
        # 404 veren geçersiz semboller
        "ARMADA.IS", "BSVS.IS", "CENG.IS", "DEGYO.IS", "DOBUR.IS",
        "DURAN.IS", "EISAS.IS", "EMTAS.IS", "FINSN.IS", "GUBRE.IS",
        "HAVAS.IS", "IPEKE.IS", "LNGSN.IS", "LYKNS.IS", "METUR.IS",
        "MKTES.IS", "MLPYT.IS", "MNVLY.IS", "MRCOL.IS", "MTMTR.IS",
        "NXION.IS", "OFISE.IS", "OREN.IS", "PRKAR.IS", "RBIGS.IS",
        "RFET.IS",  "RNSAS.IS", "SILVER.IS","SMEN.IS",  "STONE.IS",
        "TBNK.IS",  "TMASM.IS", "TRABZ.IS", "UMAS.IS",  "URAS.IS",
        "WHTOB.IS", "WNDSL.IS", "YARHL.IS", "YGYO.IS",  "ALTIN.IS",
        # Türkçe karakterli — yfinance tanımıyor
        "NETAŞ.IS", "ÜLKER.IS",
    })

    @staticmethod
    def get_quote(symbol: str, use_cache: bool = True) -> dict:
        """Tek sembol için anlık fiyat bilgisi"""
        if symbol in PriceFetcher._SKIP_SYMBOLS:
            return {"symbol": symbol, "error": "Delisted/unavailable"}

        cache_key = f"quote:{symbol}"
        if use_cache:
            cached = db.cache_get(cache_key)
            if cached:
                return cached

        try:
            ticker = yf.Ticker(symbol)
            info   = ticker.fast_info
            hist   = ticker.history(period="5d", interval="1d")

            if hist is None or hist.empty:
                return {"symbol": symbol, "error": "Veri yok"}

            close   = float(hist["Close"].iloc[-1])
            prev    = float(hist["Close"].iloc[-2]) if len(hist) >= 2 else close
            change  = close - prev
            pct     = _pct_change(close, prev)

            result = {
                "symbol":       symbol,
                "price":        round(close, 4),
                "prev_close":   round(prev, 4),
                "change":       round(change, 4),
                "change_pct":   pct,
                "high_52w":     getattr(info, "fifty_two_week_high", None),
                "low_52w":      getattr(info, "fifty_two_week_low", None),
                "volume":       float(hist["Volume"].iloc[-1]) if "Volume" in hist else None,
                "updated_at":   _now_istanbul().isoformat(),
                "direction":    "up" if pct > 0 else ("down" if pct < 0 else "flat"),
            }
            db.cache_set(cache_key, result, CACHE_TTL["tick"])
            return result

        except Exception as e:
            logger.error(f"Quote hatası [{symbol}]: {e}")
            return {"symbol": symbol, "error": str(e)}

    @staticmethod
    def get_bulk_quotes(symbols: list[str]) -> dict[str, dict]:
        """Birden fazla sembol için toplu fiyat çekimi"""
        results = {}
        # Bilinen delisted sembolleri önceden filtrele
        valid_symbols = [s for s in symbols if s not in PriceFetcher._SKIP_SYMBOLS]
        for s in symbols:
            if s in PriceFetcher._SKIP_SYMBOLS:
                results[s] = {"symbol": s, "error": "Delisted/unavailable"}
        try:
            if not valid_symbols:
                return results
            # multi_level_index=False → düz kolon yapısı (yfinance 1.x uyumu)
            data = yf.download(
                valid_symbols, period="5d", interval="1d",
                group_by="column", auto_adjust=True,
                progress=False, threads=False,  # threads=True → 401 crumb sorununa yol açıyor
                multi_level_index=True,
                timeout=30,
            )
            if data is None or data.empty:
                for sym in valid_symbols:
                    results[sym] = {"symbol": sym, "error": "Veri yok"}
                return results
            for sym in valid_symbols:
                try:
                    # MultiIndex: ("Close", sym) veya tek sembol için ("Close", "")
                    if isinstance(data.columns, pd.MultiIndex):
                        if ("Close", sym) in data.columns:
                            close_col = data[("Close", sym)]
                        elif len(valid_symbols) == 1:
                            # Tek sembol — ikinci seviye boş veya ticker adı olabilir
                            close_key = [c for c in data.columns if c[0] == "Close"]
                            close_col = data[close_key[0]] if close_key else pd.Series(dtype=float)
                        else:
                            # Çok sembol ama bu sembol bulunamadı — hata olarak işaretle
                            results[sym] = {"symbol": sym, "error": "Sütun bulunamadı"}
                            continue
                    else:
                        if len(valid_symbols) == 1:
                            close_col = data["Close"] if "Close" in data.columns else pd.Series(dtype=float)
                        else:
                            results[sym] = {"symbol": sym, "error": "Beklenmedik kolon yapısı"}
                            continue

                    if close_col.dropna().empty:
                        results[sym] = {"symbol": sym, "error": "Veri yok"}
                        continue

                    closes = close_col.dropna()
                    close  = float(closes.iloc[-1])
                    prev   = float(closes.iloc[-2]) if len(closes) >= 2 else close
                    pct    = _pct_change(close, prev)

                    results[sym] = {
                        "symbol":     sym,
                        "price":      round(close, 4),
                        "prev_close": round(prev, 4),
                        "change":     round(close - prev, 4),
                        "change_pct": pct,
                        "direction":  "up" if pct > 0 else ("down" if pct < 0 else "flat"),
                        "updated_at": _now_istanbul().isoformat(),
                    }
                except Exception as e:
                    results[sym] = {"symbol": sym, "error": str(e)}
        except Exception as e:
            logger.error(f"Toplu fiyat hatası: {e}")
            for sym in symbols:
                results[sym] = {"symbol": sym, "error": str(e)}
        return results

    @staticmethod
    def get_history(
        symbol: str,
        period: str = "10y",
        interval: str = "1d"
    ) -> pd.DataFrame:
        """Tarihsel OHLCV verisi döndür"""
        cache_key = f"hist:{symbol}:{period}:{interval}"
        cached = db.cache_get(cache_key)
        if cached:
            return pd.DataFrame(cached)

        try:
            # multi_level_index=False → yfinance 1.x'te düz kolon yapısı
            df = yf.download(
                symbol, period=period, interval=interval,
                auto_adjust=True, progress=False,
                multi_level_index=False,
            )
            if df is None or df.empty:
                return pd.DataFrame()

            df.reset_index(inplace=True)
            # Kolon isimlerini düzleştir ve küçük harfe çevir
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = [col[0].lower() for col in df.columns]
            else:
                df.columns = [c.lower() if isinstance(c, str) else str(c).lower()
                              for c in df.columns]

            # Yinelenen kolon isimlerini kaldır (narwhals DuplicateError önlemi)
            seen, dedup = {}, []
            for c in df.columns:
                if c in seen:
                    seen[c] += 1
                    dedup.append(f"{c}_{seen[c]}")
                else:
                    seen[c] = 0
                    dedup.append(c)
            df.columns = dedup
            # Yinelenen OHLCV kolonlarını at (ilk occurrence tutulur)
            keep = []
            for c in df.columns:
                base = c.split("_")[0] if "_" in c and c.split("_")[-1].isdigit() else c
                if base not in keep:
                    keep.append(c)
            df = df[keep]
            df.columns = [c.split("_")[0] if "_" in c and c.split("_")[-1].isdigit() else c for c in df.columns]

            # Tarih kolonunu standartlaştır
            if "datetime" in df.columns and "date" not in df.columns:
                df.rename(columns={"datetime": "date"}, inplace=True)

            ttl = CACHE_TTL["tick"] if interval in ["1m","5m","15m"] else CACHE_TTL["hourly"]
            db.cache_set(cache_key, df.to_dict("records"), ttl)
            return df

        except Exception as e:
            logger.error(f"Geçmiş veri hatası [{symbol}/{period}]: {e}")
            return pd.DataFrame()

    # ── BIST Özel — yfinance (birincil kaynak) ───────────────────────────
    # NOT: TradingView Scanner API (scanner.tradingview.com/turkey/scan)
    # belgelenmemiş/özel bir endpoint olduğundan kaldırıldı.
    # Yasal alternatif: yfinance (Yahoo Finance — ~15dk gecikmeli)
    # Ticari gerçek zamanlı veri için: Borsa İstanbul DataStore lisansı gerekir.

    @staticmethod
    def get_tv_quotes(tickers: list) -> dict:
        """
        Eski TradingView Scanner çağrısıyla uyumlu arayüz.
        İçeride yfinance kullanır (yasal, belgelenmiş).
        tickers: ["GARAN", "XU100"] formatını kabul eder.
        """
        from core.live_feed import BistYFinanceFeed
        clean_symbols = [
            t.replace(".IS", "").replace("BIST:", "").strip().upper()
            for t in tickers
        ]
        data = BistYFinanceFeed.fetch_bulk(clean_symbols)
        # Eski format uyumu: key → "GARAN.IS"
        return {f"{k}.IS": v for k, v in data.items()}

    @staticmethod
    def get_bist_overview() -> pd.DataFrame:
        """
        Tüm BIST takip listesi için anlık özet.
        Veri kaynağı: TradingView Scanner (Yahoo Finance'den daha güvenilir BIST verisi)
        Fallback: Yahoo Finance (TV erişilemezse)
        """
        all_syms = BIST_INDEX + BIST_SYMBOLS

        # Önce TradingView'i dene
        tv_quotes = PriceFetcher.get_tv_quotes(all_syms)

        # TV başarısızsa Yahoo'ya düş
        if not tv_quotes:
            tv_quotes = PriceFetcher.get_bulk_quotes(all_syms)

        rows = []
        for sym, q in tv_quotes.items():
            if isinstance(q, dict) and "error" not in q and q.get("price"):
                rows.append({
                    "Sembol":      sym.replace(".IS", ""),
                    "Fiyat":       q["price"],
                    "Değişim":     q.get("change", 0),
                    "Değişim %":   q.get("change_pct", 0),
                    "Yön":         q.get("direction", "flat"),
                    "symbol_full": sym,
                })
        return pd.DataFrame(rows)

    # ── Kripto ────────────────────────────────────────────────────────────

    @staticmethod
    def get_crypto_overview() -> pd.DataFrame:
        """Kripto para anlık fiyatlar (CoinGecko)"""
        cache_key = "crypto:overview"
        cached    = db.cache_get(cache_key)
        if cached:
            return pd.DataFrame(cached)

        try:
            url    = "https://api.coingecko.com/api/v3/coins/markets"
            params = {
                "vs_currency":       "usd",
                "ids":               ",".join([
                    "bitcoin","ethereum","binancecoin","solana","ripple",
                    "cardano","avalanche-2","polkadot","matic-network",
                    "chainlink","dogecoin","litecoin","cosmos","uniswap","aave"
                ]),
                "order":             "market_cap_desc",
                "per_page":          20,
                "sparkline":         False,
                "price_change_percentage": "1h,24h,7d",
            }
            if COINGECKO_API_KEY:
                params["x_cg_demo_api_key"] = COINGECKO_API_KEY

            resp = requests.get(url, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()

            rows = []
            for c in data:
                rows.append({
                    "Sembol":         c["symbol"].upper(),
                    "İsim":           c["name"],
                    "Fiyat (USD)":    c["current_price"],
                    "1s %":           c.get("price_change_percentage_1h_in_currency", 0),
                    "24s %":          c.get("price_change_percentage_24h", 0),
                    "7g %":           c.get("price_change_percentage_7d_in_currency", 0),
                    "Piyasa Değeri":  c.get("market_cap", 0),
                    "Hacim 24s":      c.get("total_volume", 0),
                    "Rank":           c.get("market_cap_rank", 0),
                    "coin_id":        c["id"],
                })

            df = pd.DataFrame(rows)
            db.cache_set(cache_key, df.to_dict("records"), CACHE_TTL["tick"])
            return df

        except Exception as e:
            logger.error(f"Kripto veri hatası: {e}")
            # Fallback: yfinance
            quotes = PriceFetcher.get_bulk_quotes(CRYPTO_SYMBOLS)
            rows = []
            for sym, q in quotes.items():
                if "error" not in q:
                    rows.append({
                        "Sembol":      sym.replace("-USD",""),
                        "Fiyat (USD)": q["price"],
                        "24s %":       q["change_pct"],
                        "Yön":         q["direction"],
                    })
            return pd.DataFrame(rows)

    # ── Forex / Pariteler ─────────────────────────────────────────────────

    @staticmethod
    def get_forex_overview() -> pd.DataFrame:
        """Forex parite anlık fiyatları"""
        quotes = PriceFetcher.get_bulk_quotes(FOREX_PAIRS)
        rows   = []
        labels = {
            "USDTRY=X": "USD/TRY", "EURTRY=X": "EUR/TRY",
            "GBPTRY=X": "GBP/TRY", "JPYTRY=X": "JPY/TRY",
            "CHFTRY=X": "CHF/TRY", "CADTRY=X": "CAD/TRY",
            "AUDTRY=X": "AUD/TRY",
            "EURUSD=X": "EUR/USD", "GBPUSD=X": "GBP/USD",
            "USDJPY=X": "USD/JPY", "USDCHF=X": "USD/CHF",
            "AUDUSD=X": "AUD/USD", "USDCAD=X": "USD/CAD",
            "NZDUSD=X": "NZD/USD", "EURGBP=X": "EUR/GBP",
            "EURJPY=X": "EUR/JPY", "GBPJPY=X": "GBP/JPY",
        }
        for sym, q in quotes.items():
            if "error" not in q:
                rows.append({
                    "Parite":      labels.get(sym, sym),
                    "Fiyat":       q["price"],
                    "Değişim":     q["change"],
                    "Değişim %":   q["change_pct"],
                    "Yön":         q["direction"],
                    "symbol":      sym,
                })
        return pd.DataFrame(rows)

    # ── Emtia / Madenler ──────────────────────────────────────────────────

    @staticmethod
    def get_commodity_overview() -> pd.DataFrame:
        """Emtia ve maden anlık fiyatları"""
        sym_list = list(COMMODITY_SYMBOLS.values())
        quotes   = PriceFetcher.get_bulk_quotes(sym_list)

        rows = []
        sym_to_name = {v: k for k, v in COMMODITY_SYMBOLS.items()}
        for sym, q in quotes.items():
            if "error" not in q:
                rows.append({
                    "Emtia":       sym_to_name.get(sym, sym),
                    "Fiyat":       q["price"],
                    "Değişim %":   q["change_pct"],
                    "Yön":         q["direction"],
                    "symbol":      sym,
                })
        return pd.DataFrame(rows)

    # ── Dünya Borsaları ───────────────────────────────────────────────────

    @staticmethod
    def get_world_indices() -> pd.DataFrame:
        """Küresel borsa endeksleri — BIST için TradingView, diğerleri Yahoo Finance"""
        sym_list    = list(WORLD_INDICES.values())
        bist_syms   = [s for s in sym_list if s.endswith(".IS")]
        other_syms  = [s for s in sym_list if not s.endswith(".IS")]

        quotes = PriceFetcher.get_bulk_quotes(other_syms)

        # BIST sembolleri TradingView'den al (daha doğru değerler)
        if bist_syms:
            tv_q = PriceFetcher.get_tv_quotes(bist_syms)
            if tv_q:
                quotes.update(tv_q)
            else:
                quotes.update(PriceFetcher.get_bulk_quotes(bist_syms))

        rows = []
        sym_to_name = {v: k for k, v in WORLD_INDICES.items()}
        for sym, q in quotes.items():
            if "error" not in q and q.get("price", 0) > 0:
                rows.append({
                    "Borsa":       sym_to_name.get(sym, sym),
                    "Değer":       q["price"],
                    "Değişim %":   q["change_pct"],
                    "Yön":         q["direction"],
                    "symbol":      sym,
                })
        return pd.DataFrame(rows)


# ─── TCMB Veri Çekici ─────────────────────────────────────────────────────────

class TCMBFetcher:
    """TCMB EVDS (Elektronik Veri Dağıtım Sistemi) entegrasyonu"""

    BASE_URL = "https://evds2.tcmb.gov.tr/service/evds"

    @classmethod
    def get_series(
        cls,
        series_key: str,
        start_date: str = "01-01-2020",
        end_date: Optional[str] = None,
        freq: str = "DEFAULT"
    ) -> pd.DataFrame:
        """
        TCMB EVDS'den veri serisi çek.
        Freq: DEFAULT=doğal frekans, MONTHLY=aylık, QUARTERLY=çeyreklik
        """
        if not TCMB_API_KEY:
            logger.warning("TCMB API anahtarı eksik — örnek veri döndürülüyor")
            return cls._mock_data(series_key)

        if not end_date:
            end_date = datetime.now().strftime("%d-%m-%Y")

        params = {
            "series":    series_key,
            "startDate": start_date,
            "endDate":   end_date,
            "type":      "json",
            "key":       TCMB_API_KEY,
            "frequency": freq,
            "formulas":  "0",
        }

        try:
            resp = requests.get(
                f"{cls.BASE_URL}/series",
                params=params,
                timeout=20
            )
            resp.raise_for_status()
            # Boş yanıt kontrolü (TCMB bazen 200 OK + boş body döndürür)
            if not resp.content or not resp.content.strip():
                return cls._mock_data(series_key)
            try:
                raw = resp.json()
            except Exception:
                return cls._mock_data(series_key)
            items = raw.get("items", [])

            if not items:
                return pd.DataFrame()

            records = []
            for item in items:
                date_str = item.get("Tarih", "")
                val_str  = item.get(series_key, "")
                try:
                    date = pd.to_datetime(date_str, format="%d-%m-%Y")
                    val  = float(str(val_str).replace(",", "."))
                    records.append({"date": date, "value": val})
                except (ValueError, TypeError):
                    continue

            return pd.DataFrame(records).sort_values("date")

        except Exception as e:
            logger.error(f"TCMB hata [{series_key}]: {e}")
            return cls._mock_data(series_key)

    @classmethod
    def get_all_macro(cls) -> dict[str, pd.DataFrame]:
        """Tüm makro göstergeleri çek"""
        result = {}
        for name, key in TCMB_SERIES.items():
            result[name] = cls.get_series(key)
            time.sleep(0.3)  # Rate limit için ara ver
        return result

    @staticmethod
    def _mock_data(series_key: str) -> pd.DataFrame:
        """API anahtarı yokken demo veri üret"""
        dates  = pd.date_range(start="2020-01-01", end=datetime.now(), freq="MS")
        np.random.seed(42)

        if "TUFE" in series_key:
            values = np.cumsum(np.random.uniform(1, 3, len(dates))) + 10
        elif "FAIZ" in series_key or "AOFON" in series_key:
            values = np.random.uniform(8, 45, len(dates))
        elif "USD" in series_key or "EUR" in series_key:
            values = np.cumsum(np.random.uniform(0.1, 0.5, len(dates))) + 8
        else:
            values = np.random.uniform(50, 200, len(dates))

        return pd.DataFrame({"date": dates, "value": np.round(values, 2)})


# ─── Haber Çekici ─────────────────────────────────────────────────────────────

class NewsFetcher:
    """RSS/Atom feed'lerden haber çekimi"""

    @staticmethod
    def fetch_all(save_to_db: bool = True) -> list[dict]:
        """Tüm kaynaklardan haberleri çek"""
        all_news = []

        for source_name, feed_url in NEWS_RSS_FEEDS.items():
            try:
                feed  = feedparser.parse(feed_url)
                items = []

                for entry in feed.entries[:10]:  # Her kaynaktan max 10 haber
                    published = None
                    if hasattr(entry, "published_parsed") and entry.published_parsed:
                        published = datetime(*entry.published_parsed[:6])

                    items.append({
                        "source":       source_name,
                        "title":        getattr(entry, "title", "")[:500],
                        "summary":      getattr(entry, "summary", "")[:2000],
                        "url":          getattr(entry, "link", ""),
                        "published_at": published or datetime.utcnow(),
                        "fetched_at":   datetime.utcnow(),
                        "is_processed": False,
                    })

                all_news.extend(items)
                logger.debug(f"{source_name}: {len(items)} haber")

            except Exception as e:
                logger.error(f"Haber hatası [{source_name}]: {e}")

        if save_to_db and all_news:
            saved = db.save_news(all_news)
            logger.info(f"Toplam {saved} yeni haber kaydedildi")

        return all_news

    @staticmethod
    def get_google_news(query: str, limit: int = 10) -> list[dict]:
        """Google News üzerinden spesifik arama yap (RSS)"""
        import urllib.parse
        encoded_query = urllib.parse.quote(query)
        url = f"https://news.google.com/rss/search?q={encoded_query}&hl=tr&gl=TR&ceid=TR:tr"
        
        try:
            feed = feedparser.parse(url)
            items = []
            for entry in feed.entries[:limit]:
                items.append({
                    "source": "Google News",
                    "title": getattr(entry, "title", ""),
                    "summary": getattr(entry, "summary", ""),
                    "url": getattr(entry, "link", ""),
                    "published_at": datetime(*entry.published_parsed[:6]) if hasattr(entry, "published_parsed") else datetime.now(),
                })
            return items
        except Exception as e:
            logger.error(f"Google News search hatası [{query}]: {e}")
            return []

    @staticmethod
    def get_latest(limit: int = 30) -> list[dict]:
        """DB'den son haberleri getir, yoksa RSS'ten çek"""
        rows = db.get_latest_news(limit=limit)
        if rows:
            return [dict(row._mapping) for row in rows]
        return NewsFetcher.fetch_all(save_to_db=True)[:limit]

    @staticmethod
    def get_isyatirim_research(limit: int = 15) -> list[dict]:
        """
        İş Yatırım Araştırma (arastirma.isyatirim.com.tr) RSS feed'inden
        en güncel raporları ve analizleri çeker.
        Returns: [{"title", "url", "summary", "published_at", "categories", "source"}]
        """
        try:
            feed = feedparser.parse("https://arastirma.isyatirim.com.tr/feed/")
            items = []
            for entry in feed.entries[:limit]:
                published = None
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    published = datetime(*entry.published_parsed[:6])

                # Kategoriler (hisse kodu olabilir)
                categories = []
                if hasattr(entry, "tags"):
                    categories = [t.term for t in entry.tags if hasattr(t, "term")]

                # Özet — content:encoded varsa daha zengin, yoksa summary
                summary = ""
                if hasattr(entry, "content") and entry.content:
                    summary = entry.content[0].get("value", "")[:500]
                elif hasattr(entry, "summary"):
                    summary = entry.summary[:500]
                # HTML etiketlerini temizle
                import re
                summary = re.sub(r"<[^>]+>", " ", summary).strip()[:300]

                items.append({
                    "source":       "İş Yatırım Araştırma",
                    "title":        getattr(entry, "title", "")[:200],
                    "url":          getattr(entry, "link", ""),
                    "summary":      summary,
                    "published_at": published or datetime.utcnow(),
                    "categories":   categories,
                })
            logger.debug(f"İş Yatırım Araştırma: {len(items)} içerik çekildi")
            return items
        except Exception as e:
            logger.error(f"İş Yatırım Araştırma feed hatası: {e}")
            return []

    @staticmethod
    def get_isyatirim_research_by_symbol(symbol: str, limit: int = 5) -> list[dict]:
        """Belirli bir hisse kodu için İş Yatırım araştırma notlarını filtrele."""
        all_items = NewsFetcher.get_isyatirim_research(limit=50)
        sym_upper = symbol.upper().replace(".IS", "")
        return [
            item for item in all_items
            if sym_upper in item["title"].upper()
            or sym_upper in " ".join(item.get("categories", [])).upper()
            or sym_upper in item.get("summary", "").upper()
        ][:limit]


# ─── Teknik Analiz Hesaplayıcı ────────────────────────────────────────────────

class TechnicalAnalyzer:
    """Saf pandas ile teknik indikatör hesaplama (harici kütüphane gerekmez)"""

    # ── Yardımcı hesaplayıcılar ─────────────────────────────────────────────

    @staticmethod
    def _sma(s: pd.Series, w: int) -> pd.Series:
        return s.rolling(window=w, min_periods=w).mean()

    @staticmethod
    def _ema(s: pd.Series, w: int) -> pd.Series:
        return s.ewm(span=w, adjust=False).mean()

    @staticmethod
    def _rsi(close: pd.Series, w: int = 14) -> pd.Series:
        delta = close.diff()
        gain  = delta.clip(lower=0)
        loss  = (-delta).clip(lower=0)
        avg_g = gain.ewm(com=w - 1, min_periods=w).mean()
        avg_l = loss.ewm(com=w - 1, min_periods=w).mean()
        rs    = avg_g / avg_l.replace(0, np.nan)
        return 100 - 100 / (1 + rs)

    @staticmethod
    def _macd(close: pd.Series, fast=12, slow=26, signal=9):
        ema_f  = close.ewm(span=fast, adjust=False).mean()
        ema_s  = close.ewm(span=slow, adjust=False).mean()
        macd   = ema_f - ema_s
        sig    = macd.ewm(span=signal, adjust=False).mean()
        return macd, sig, macd - sig

    @staticmethod
    def _bollinger(close: pd.Series, w=20, dev=2):
        mid   = close.rolling(w).mean()
        std   = close.rolling(w).std()
        return mid + dev * std, mid, mid - dev * std

    @staticmethod
    def _atr(high: pd.Series, low: pd.Series, close: pd.Series, w=14) -> pd.Series:
        hl   = high - low
        hpc  = (high - close.shift()).abs()
        lpc  = (low  - close.shift()).abs()
        tr   = pd.concat([hl, hpc, lpc], axis=1).max(axis=1)
        return tr.rolling(w).mean()

    @staticmethod
    def _stoch(high: pd.Series, low: pd.Series, close: pd.Series, w=14, smooth=3):
        lo = low.rolling(w).min()
        hi = high.rolling(w).max()
        k  = 100 * (close - lo) / (hi - lo).replace(0, np.nan)
        d  = k.rolling(smooth).mean()
        return k, d

    @staticmethod
    def _obv(close: pd.Series, vol: pd.Series) -> pd.Series:
        direction = np.sign(close.diff()).fillna(0)
        return (vol * direction).cumsum()

    # ── Ana hesaplayıcı ─────────────────────────────────────────────────────

    @staticmethod
    def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
        """OHLCV DataFrame'ine saf pandas indikatörleri ekle"""
        if df.empty or len(df) < 20:
            return df

        try:
            df = df.copy()
            df.columns = [c[0].lower() if isinstance(c, tuple) else c.lower() for c in df.columns]

            close = df["close"]
            high  = df.get("high",  close)
            low   = df.get("low",   close)
            vol   = df.get("volume", None)

            ta = TechnicalAnalyzer

            # SMA / EMA
            df["SMA_20"]  = ta._sma(close, 20)
            df["SMA_50"]  = ta._sma(close, 50)
            df["SMA_200"] = ta._sma(close, 200)
            df["EMA_21"]  = ta._ema(close, 21)

            # RSI
            df["RSI_14"] = ta._rsi(close, 14)

            # MACD
            df["MACD_12_26_9"], df["MACDs_12_26_9"], df["MACDh_12_26_9"] = ta._macd(close)

            # Stochastic
            df["STOCHk_14_3_3"], df["STOCHd_14_3_3"] = ta._stoch(high, low, close)

            # Bollinger Bands
            df["BBU_20_2.0"], df["BBM_20_2.0"], df["BBL_20_2.0"] = ta._bollinger(close)

            # ATR
            df["ATRr_14"] = ta._atr(high, low, close)

            # OBV
            if vol is not None and not vol.isna().all():
                df["OBV"] = ta._obv(close, vol)

        except Exception as e:
            logger.error(f"İndikatör hesaplama hatası: {e}")

        return df

    @staticmethod
    def get_signal(df: pd.DataFrame) -> dict:
        """RSI + MACD + SMA bazlı basit sinyal üret"""
        if df.empty or len(df) < 30:
            return {"signal": "YETERSIZ_VERI", "score": 0, "reasons": []}

        df = TechnicalAnalyzer.add_indicators(df)
        score   = 0
        reasons = []
        latest  = df.iloc[-1]

        # RSI
        rsi_col = next((c for c in df.columns if "RSI" in c.upper()), None)
        if rsi_col and pd.notna(latest.get(rsi_col)):
            rsi = latest[rsi_col]
            if rsi < 30:
                score += 2; reasons.append(f"RSI aşırı satım ({rsi:.1f})")
            elif rsi > 70:
                score -= 2; reasons.append(f"RSI aşırı alım ({rsi:.1f})")
            elif rsi > 50:
                score += 1; reasons.append(f"RSI pozitif bölge ({rsi:.1f})")

        # MACD
        macd_col  = next((c for c in df.columns if c.upper().startswith("MACD_") and "HIST" not in c.upper() and "MACDS" not in c.upper() and "SIGNAL" not in c.upper()), None)
        macds_col = next((c for c in df.columns if c.upper().startswith("MACDS") or "MACD_SIGNAL" in c.upper()), None)
        if macd_col and macds_col:
            macd_val = latest.get(macd_col, 0) or 0
            macd_sig = latest.get(macds_col, 0) or 0
            if macd_val > macd_sig:
                score += 1; reasons.append("MACD sinyal üzerinde")
            else:
                score -= 1; reasons.append("MACD sinyal altında")

        # SMA 50/200 Golden/Death Cross
        sma50  = latest.get("SMA_50",  latest.get("sma_50",  None))
        sma200 = latest.get("SMA_200", latest.get("sma_200", None))
        close  = latest.get("close", latest.get("Close", None))
        if sma50 and sma200 and close:
            if sma50 > sma200:
                score += 1; reasons.append("Golden cross (SMA50 > SMA200)")
            else:
                score -= 1; reasons.append("Death cross (SMA50 < SMA200)")
            if close > sma50:
                score += 1; reasons.append("Fiyat SMA50 üzerinde")

        # Sinyal üret
        if score >= 3:
            signal = "GÜÇLÜ AL"
        elif score >= 1:
            signal = "AL"
        elif score <= -3:
            signal = "GÜÇLÜ SAT"
        elif score <= -1:
            signal = "SAT"
        else:
            signal = "NÖTR"

        return {
            "signal":  signal,
            "score":   score,
            "reasons": reasons,
        }


# ─── Merkezi Veri Servisi ─────────────────────────────────────────────────────

class DataService:
    """Tüm veri kaynaklarını birleştiren ana servis"""
    prices   = PriceFetcher()
    tcmb     = TCMBFetcher()
    news     = NewsFetcher()
    ta       = TechnicalAnalyzer()
