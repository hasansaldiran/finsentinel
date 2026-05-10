"""
FinSentinel — Ücretsiz Web Scraper Servisi
services/apify_scraper.py

Apify paid actor'ları yerine ücretsiz, key-gerektirmeyen kaynaklar kullanır.
Fonksiyon imzaları korunarak UI sayfaları (09_news.py) değiştirilmeye gerek kalmaz.

Kullanılan Kaynaklar:
  ┌──────────────────────────────────────────────────────────────────────────┐
  │ Fonksiyon                  Kaynak                         Ücret        │
  │──────────────────────────────────────────────────────────────────────────│
  │ get_google_news()          Google News RSS (feedparser)    ÜCRETSİZ    │
  │ get_tv_news()              Google News RSS + TV query      ÜCRETSİZ    │
  │ scrape_kap_disclosures()   KAP RSS + BeautifulSoup         ÜCRETSİZ    │
  │ get_yahoo_quote()          yfinance                        ÜCRETSİZ    │
  │ get_yahoo_bulk()           yfinance                        ÜCRETSİZ    │
  │ get_tv_screener()          Dahili teknik analiz (pandas)   ÜCRETSİZ    │
  │ get_twitter_sentiment()    Devre dışı (graceful degrade)   —           │
  └──────────────────────────────────────────────────────────────────────────┘
"""

import re
import urllib.parse
from datetime import datetime
from typing import Optional

import feedparser
import requests
from bs4 import BeautifulSoup
from loguru import logger

from config.settings import CACHE_TTL
from core.db import db


# ─── 1. Google Haberler — RSS (Ücretsiz, Key Gerektirmez) ────────────────────

def get_google_news(
    query: str,
    language: str = "tr",
    country: str = "TR",
    limit: int = 30,
    use_cache: bool = True,
) -> Optional[list]:
    """
    Google Haberler'den arama sonuçları — feedparser ile RSS.

    query: "BIST 100 borsa", "Türkiye ekonomi", "THYAO hisse" vb.
    language: tr, en, de vb.
    country: TR, US, DE vb.
    """
    cache_key = f"gnews_rss:{query}:{language}:{limit}"
    if use_cache:
        cached = db.cache_get(cache_key)
        if cached:
            return cached

    try:
        encoded_query = urllib.parse.quote(query)
        # Google News RSS — ücretsiz, key yok, rate limit çok cömert
        rss_url = (
            f"https://news.google.com/rss/search?"
            f"q={encoded_query}&hl={language}&gl={country}&ceid={country}:{language}"
        )

        feed = feedparser.parse(rss_url)

        if not feed.entries:
            logger.warning(f"Google News RSS boş sonuç: {query}")
            return []

        results = []
        for entry in feed.entries[:limit]:
            # Kaynak bilgisini title'dan çıkar: "Haber başlığı - Kaynak Adı"
            raw_title = getattr(entry, "title", "")
            source_name = ""
            title = raw_title

            # Google News RSS formatı: "Başlık - Kaynak"
            if " - " in raw_title:
                parts = raw_title.rsplit(" - ", 1)
                title = parts[0].strip()
                source_name = parts[1].strip()

            # <source> tag'inden kaynak al (daha güvenilir)
            if hasattr(entry, "source") and hasattr(entry.source, "title"):
                source_name = entry.source.title

            # Yayın tarihi
            published_at = ""
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                try:
                    published_at = datetime(*entry.published_parsed[:6]).isoformat()
                except Exception:
                    published_at = getattr(entry, "published", "")
            elif hasattr(entry, "published"):
                published_at = entry.published

            # Snippet/description — HTML temizle
            snippet = ""
            raw_desc = getattr(entry, "summary", "") or getattr(entry, "description", "")
            if raw_desc:
                snippet = re.sub(r"<[^>]+>", " ", raw_desc).strip()
                snippet = re.sub(r"\s+", " ", snippet)[:300]

            results.append({
                "title":       title,
                "url":         getattr(entry, "link", ""),
                "source":      source_name,
                "publishedAt": published_at,
                "date":        published_at,
                "snippet":     snippet,
                "description": snippet,
            })

        if results:
            db.cache_set(cache_key, results, CACHE_TTL["hourly"])

        logger.info(f"Google News RSS: {len(results)} makale — '{query}'")
        return results

    except Exception as e:
        logger.error(f"Google News RSS hatası [{query}]: {e}")
        return []


# ─── 2. TradingView Haberler — Google News + TV Query ────────────────────────

def get_tv_news(
    symbol: str = None,
    limit: int = 30,
    use_cache: bool = True,
) -> Optional[list]:
    """
    TradingView odaklı finansal haberler — Google News RSS ile.
    symbol: Belirli bir sembol (ör. "BIST:THYAO") veya None (genel haberler)
    """
    cache_key = f"tv_news_rss:{symbol or 'global'}:{limit}"
    if use_cache:
        cached = db.cache_get(cache_key)
        if cached:
            return cached

    # Sorgu oluştur
    if symbol:
        # "BIST:THYAO" → "THYAO hisse borsa analiz"
        clean_sym = symbol.replace("BIST:", "").replace("NASDAQ:", "").replace("BINANCE:", "").strip()
        query = f"{clean_sym} hisse borsa analiz"
    else:
        query = "borsa finans piyasa analiz"

    try:
        # Çoklu sorgu ile zenginleştirilmiş sonuçlar
        all_results = []

        # Ana sorgu
        main_results = get_google_news(
            query=query,
            language="tr",
            country="TR",
            limit=limit,
            use_cache=False,
        )
        if main_results:
            all_results.extend(main_results)

        # Ek sorgu: TradingView odaklı (İngilizce)
        if len(all_results) < limit:
            tv_query = f"{symbol or 'market'} TradingView analysis"
            tv_results = get_google_news(
                query=tv_query,
                language="en",
                country="US",
                limit=min(10, limit - len(all_results)),
                use_cache=False,
            )
            if tv_results:
                all_results.extend(tv_results)

        # Sonuçları TV formatına uyarla
        formatted = []
        for item in all_results[:limit]:
            formatted.append({
                "title":     item.get("title", ""),
                "url":       item.get("url", ""),
                "link":      item.get("url", ""),
                "source":    item.get("source", ""),
                "provider":  item.get("source", "Google News"),
                "published": item.get("publishedAt", ""),
                "date":      item.get("date", ""),
                "summary":   item.get("snippet", ""),
                "body":      item.get("description", ""),
            })

        if formatted:
            db.cache_set(cache_key, formatted, CACHE_TTL["hourly"])

        logger.info(f"TV News (RSS): {len(formatted)} haber — {symbol or 'genel'}")
        return formatted

    except Exception as e:
        logger.error(f"TV News RSS hatası [{symbol}]: {e}")
        return []


# ─── 3. KAP Scraper — Kamuyu Aydınlatma Platformu ────────────────────────────

def scrape_kap_disclosures(
    ticker: str = None,
    limit: int = 30,
    use_cache: bool = True,
) -> Optional[list]:
    """
    KAP'tan özel durum açıklamalarını çeker.
    Birincil: KAP JSON API (bugünün bildirimleri)
    İkincil: Google News — KAP duyuru haberleri
    Üçüncül: Genel finans haberlerinden KAP duyuruları

    ticker: "THYAO" gibi hisse kodu — None ise tüm son duyurular
    """
    cache_key = f"kap_free:{ticker or 'all'}:{limit}"
    if use_cache:
        cached = db.cache_get(cache_key)
        if cached:
            return cached

    results = []

    # ── Yöntem 1: KAP JSON API — Bugünün Bildirimleri ─────────────────────
    # KAP'ın SPA arka planında kullandığı API endpoint'leri
    kap_api_urls = [
        "https://www.kap.org.tr/tr/api/memberDisclosureIndex",
        "https://www.kap.org.tr/tr/api/discIndex",
    ]

    for api_url in kap_api_urls:
        if results:
            break
        try:
            headers = {
                "Accept": "application/json, text/plain, */*",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Referer": "https://www.kap.org.tr/tr",
                "Origin": "https://www.kap.org.tr",
            }

            resp = requests.get(api_url, headers=headers, timeout=20)

            if resp.status_code == 200:
                try:
                    data = resp.json()
                    items_list = data if isinstance(data, list) else data.get("memberDisclosureIndexes", data.get("disclosures", []))

                    for item in (items_list or [])[:limit * 2]:
                        if isinstance(item, dict):
                            title = (
                                item.get("disclosureTitle", "")
                                or item.get("title", "")
                                or item.get("summary", "")
                            )
                            disc_ticker = (
                                item.get("stockCodes", "")
                                or item.get("companyCode", "")
                                or item.get("memberCode", "")
                            )
                            date_str = (
                                item.get("publishDate", "")
                                or item.get("disclosureDate", "")
                                or item.get("date", "")
                            )
                            disc_id = item.get("disclosureIndex", item.get("id", ""))
                            url = f"https://www.kap.org.tr/tr/Bildirim/{disc_id}" if disc_id else ""

                            if title:
                                results.append({
                                    "title":  title,
                                    "date":   date_str,
                                    "ticker": disc_ticker,
                                    "url":    url,
                                    "source": "KAP",
                                })

                    if results:
                        logger.info(f"KAP API ({api_url.split('/')[-1]}): {len(results)} duyuru")
                except (ValueError, KeyError) as e:
                    logger.debug(f"KAP API JSON parse hatası: {e}")
        except requests.exceptions.Timeout:
            logger.warning(f"KAP API timeout: {api_url}")
        except Exception as e:
            logger.warning(f"KAP API hatası [{api_url}]: {e}")

    # ── Yöntem 2: BeautifulSoup — KAP Ana Sayfa ──────────────────────────
    if not results:
        try:
            kap_url = "https://www.kap.org.tr/tr"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "tr-TR,tr;q=0.9",
            }
            resp = requests.get(kap_url, headers=headers, timeout=20)

            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")

                # KAP'ın bildirim tablosu CSS seçicileri
                selectors = [
                    "div.w-clearfix.w-inline-block.comp-cell-row-div",
                    "div.comp-cell-row-div",
                    "tr.disclosure-row",
                    "div[class*='bildirim']",
                ]

                for sel in selectors:
                    rows = soup.select(sel)
                    if rows:
                        for row in rows[:limit]:
                            try:
                                cells = row.select("div.comp-cell, td")
                                if len(cells) >= 2:
                                    texts = [c.get_text(strip=True) for c in cells]
                                    link_el = row.find("a")
                                    link_url = ""
                                    if link_el and link_el.get("href"):
                                        href = link_el["href"]
                                        link_url = href if href.startswith("http") else f"https://www.kap.org.tr{href}"

                                    # Heuristik: kısa, büyük harfli metin = ticker
                                    detected_ticker = ""
                                    for t in texts:
                                        if len(t) <= 6 and t.isalpha() and t.isupper():
                                            detected_ticker = t
                                            break

                                    title = link_el.get_text(strip=True) if link_el else texts[-1] if texts else ""
                                    date_text = texts[0] if texts else ""

                                    if title and len(title) > 3:
                                        results.append({
                                            "title":  title,
                                            "date":   date_text,
                                            "ticker": detected_ticker,
                                            "url":    link_url,
                                            "source": "KAP",
                                        })
                            except Exception:
                                continue
                        if results:
                            break

                if results:
                    logger.info(f"KAP scraping: {len(results)} duyuru")
        except Exception as e:
            logger.warning(f"KAP scraping hatası: {e}")

    # ── Yöntem 3: Google News — KAP Duyuru Haberleri ──────────────────────
    if not results:
        try:
            # Daha spesifik sorgu: "KAP özel durum açıklaması" + ticker
            if ticker:
                kap_query = f"{ticker} KAP özel durum açıklaması bildirim"
            else:
                kap_query = "KAP özel durum açıklaması borsa bildirim duyuru"

            gn_results = get_google_news(
                query=kap_query,
                language="tr",
                country="TR",
                limit=limit,
                use_cache=False,
            )
            if gn_results:
                for item in gn_results:
                    title = item.get("title", "")
                    # KAP dışı haberleri filtrele
                    if any(kw in title.lower() for kw in ["kap", "bildirim", "duyuru", "açıklama", "özel durum"]):
                        results.append({
                            "title":  title,
                            "date":   item.get("publishedAt", ""),
                            "ticker": ticker or "",
                            "url":    item.get("url", ""),
                            "source": "KAP (haber)",
                        })

                # Eğer KAP filtresi çok az sonuç verdiyse geri kalanı da ekle
                if len(results) < 5 and gn_results:
                    for item in gn_results:
                        title = item.get("title", "")
                        if title not in [r["title"] for r in results]:
                            results.append({
                                "title":  title,
                                "date":   item.get("publishedAt", ""),
                                "ticker": ticker or "",
                                "url":    item.get("url", ""),
                                "source": "Finans (KAP ilişkili)",
                            })
                            if len(results) >= limit:
                                break

                logger.info(f"KAP (Google News): {len(results)} sonuç")
        except Exception as e:
            logger.warning(f"KAP Google fallback hatası: {e}")

    # Ticker filtresi
    if ticker and results:
        ticker_upper = ticker.upper().strip()
        filtered = [
            r for r in results
            if ticker_upper in r.get("ticker", "").upper()
            or ticker_upper in r.get("title", "").upper()
        ]
        if filtered:
            results = filtered

    # Boş ve kısa başlıkları filtrele
    results = [r for r in results if r.get("title") and len(r["title"]) > 5][:limit]

    if results:
        db.cache_set(cache_key, results, CACHE_TTL["hourly"])

    return results


# ─── 4. TradingView Screener — Dahili Teknik Analiz ──────────────────────────

def get_tv_screener(
    market: str = "turkey",
    interval: str = "1D",
    limit: int = 50,
    use_cache: bool = True,
) -> Optional[list]:
    """
    TradingView screener sinyalleri — yfinance + dahili teknik analiz ile.

    Apify actor'ı yerine projede zaten bulunan TechnicalAnalyzer kullanılır.
    market: turkey, america, crypto, forex vb.
    interval: 1D, 1W vb.
    """
    cache_key = f"tv_screener_free:{market}:{interval}:{limit}"
    if use_cache:
        cached = db.cache_get(cache_key)
        if cached:
            return cached

    try:
        import yfinance as yf
        from config.settings import BIST_30

        # Market'e göre sembol listesi seç
        if market == "turkey":
            symbols = [f"{s}" for s in BIST_30[:limit]]
        elif market == "crypto":
            symbols = ["BTC-USD", "ETH-USD", "BNB-USD", "SOL-USD", "XRP-USD",
                       "ADA-USD", "AVAX-USD", "DOT-USD", "LINK-USD", "DOGE-USD"][:limit]
        elif market == "america":
            symbols = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META",
                       "TSLA", "JPM", "V", "WMT"][:limit]
        else:
            symbols = [f"{s}" for s in BIST_30[:limit]]

        # interval haritası
        period_map = {
            "1m": "1d", "5m": "5d", "15m": "5d", "1h": "1mo",
            "4h": "3mo", "1D": "6mo", "1W": "2y", "1M": "10y",
        }
        yf_period = period_map.get(interval, "6mo")

        results = []
        for sym in symbols[:limit]:
            try:
                hist = yf.download(sym, period=yf_period, interval="1d",
                                   progress=False, auto_adjust=True,
                                   multi_level_index=False)
                if hist is None or hist.empty or len(hist) < 20:
                    continue

                close = hist["Close"]
                high  = hist.get("High", close)
                low   = hist.get("Low", close)

                current = float(close.iloc[-1])

                # RSI (14)
                delta = close.diff()
                gain  = delta.clip(lower=0).ewm(com=13, min_periods=14).mean()
                loss  = (-delta).clip(lower=0).ewm(com=13, min_periods=14).mean()
                rs    = gain / loss.replace(0, float("nan"))
                rsi   = float((100 - 100 / (1 + rs)).iloc[-1])

                # MACD
                ema12 = close.ewm(span=12, adjust=False).mean()
                ema26 = close.ewm(span=26, adjust=False).mean()
                macd_line = ema12 - ema26
                signal_line = macd_line.ewm(span=9, adjust=False).mean()
                macd_val = float(macd_line.iloc[-1])
                signal_val = float(signal_line.iloc[-1])
                macd_hist = float((macd_line - signal_line).iloc[-1])

                # Moving Averages
                sma20  = float(close.rolling(20).mean().iloc[-1]) if len(close) >= 20 else None
                sma50  = float(close.rolling(50).mean().iloc[-1]) if len(close) >= 50 else None
                sma200 = float(close.rolling(200).mean().iloc[-1]) if len(close) >= 200 else None
                ema9   = float(close.ewm(span=9, adjust=False).mean().iloc[-1])
                ema21  = float(close.ewm(span=21, adjust=False).mean().iloc[-1])

                # Genel sinyal
                score = 0
                if rsi < 30: score += 2
                elif rsi > 70: score -= 2
                elif rsi > 50: score += 1
                else: score -= 1

                if macd_val > signal_val: score += 1
                else: score -= 1

                if sma50 and sma200:
                    if sma50 > sma200: score += 1
                    else: score -= 1
                if sma20 and current > sma20: score += 1

                if score >= 3: rec = "STRONG_BUY"
                elif score >= 1: rec = "BUY"
                elif score <= -3: rec = "STRONG_SELL"
                elif score <= -1: rec = "SELL"
                else: rec = "NEUTRAL"

                results.append({
                    "symbol":      sym.replace(".IS", ""),
                    "price":       round(current, 2),
                    "rsi":         round(rsi, 2),
                    "macd":        round(macd_val, 4),
                    "macd_signal": round(signal_val, 4),
                    "macd_hist":   round(macd_hist, 4),
                    "sma20":       round(sma20, 2) if sma20 else None,
                    "sma50":       round(sma50, 2) if sma50 else None,
                    "sma200":      round(sma200, 2) if sma200 else None,
                    "ema9":        round(ema9, 2),
                    "ema21":       round(ema21, 2),
                    "recommend":   rec,
                    "score":       score,
                    "interval":    interval,
                    "market":      market,
                })
            except Exception as e:
                logger.debug(f"Screener hata [{sym}]: {e}")
                continue

        if results:
            db.cache_set(cache_key, results, CACHE_TTL["hourly"])

        logger.info(f"TV Screener (dahili): {len(results)} sinyal — {market}/{interval}")
        return results

    except Exception as e:
        logger.error(f"TV Screener hatası [{market}]: {e}")
        return None


# ─── 5. Twitter/X Sentiment — Graceful Degrade ──────────────────────────────

def get_twitter_sentiment(
    symbols: list[str],
    limit: int = 100,
    use_cache: bool = True,
) -> Optional[list]:
    """
    Twitter/X sentiment analizi.

    ⚠️ Ücretsiz güvenilir bir Twitter scraping kaynağı bulunmadığından
    bu fonksiyon graceful degrade yapar.

    Alternatif: Google News'ten sentiment çıkar.
    """
    cache_key = f"twitter_sent_free:{','.join(symbols)}:{limit}"
    if use_cache:
        cached = db.cache_get(cache_key)
        if cached:
            return cached

    logger.info("Twitter sentiment: Ücretsiz kaynak yok — Google News ile alternatif sentiment oluşturuluyor")

    # Google News'ten sembollere ait haberleri çekip basit sentiment üret
    POS_WORDS = [
        "yükseldi", "arttı", "kazandı", "rekor", "büyüdü", "güçlendi",
        "olumlu", "başarı", "kar", "ivme", "zirve", "rally", "pozitif",
        "bullish", "surge", "gain", "high", "growth", "profit", "strong",
    ]
    NEG_WORDS = [
        "düştü", "geriledi", "kayıp", "zarar", "kriz", "endişe", "risk",
        "çöktü", "negatif", "olumsuz", "düşüş", "alarm", "panik",
        "bearish", "crash", "loss", "drop", "decline", "weak", "sell",
    ]

    results = []
    for sym in symbols[:5]:  # Max 5 sembol
        try:
            clean_sym = sym.upper().lstrip("$")
            news = get_google_news(
                query=f"{clean_sym} hisse borsa",
                language="tr",
                limit=min(15, limit // len(symbols)),
                use_cache=True,
            )

            if not news:
                continue

            for item in news:
                title = item.get("title", "").lower()
                pos = sum(1 for w in POS_WORDS if w in title)
                neg = sum(1 for w in NEG_WORDS if w in title)

                if pos > neg:
                    sentiment = "bullish"
                elif neg > pos:
                    sentiment = "bearish"
                else:
                    sentiment = "neutral"

                results.append({
                    "symbol":    f"${clean_sym}",
                    "text":      item.get("title", ""),
                    "source":    item.get("source", "Google News"),
                    "url":       item.get("url", ""),
                    "sentiment": sentiment,
                    "date":      item.get("publishedAt", ""),
                    "likes":     0,
                    "retweets":  0,
                    "note":      "Google News'ten türetilmiş sentiment (Twitter API ücretsiz değil)",
                })
        except Exception as e:
            logger.debug(f"Sentiment hata [{sym}]: {e}")

    if results:
        db.cache_set(cache_key, results, CACHE_TTL["hourly"])

    return results if results else None


# ─── 6. Yahoo Finance — yfinance (Zaten Projede Var) ─────────────────────────

def get_yahoo_quote(symbol: str, use_cache: bool = True) -> Optional[dict]:
    """
    Yahoo Finance'den hisse verisi — yfinance kütüphanesi ile.
    symbol: "THYAO.IS", "AAPL", "BTC-USD", "XU100.IS" vb.
    """
    cache_key = f"yahoo_free:{symbol}"
    if use_cache:
        cached = db.cache_get(cache_key)
        if cached:
            return cached

    try:
        import yfinance as yf
        ticker = yf.Ticker(symbol)
        info = ticker.fast_info
        hist = ticker.history(period="5d", interval="1d")

        if hist is None or hist.empty:
            return None

        close = float(hist["Close"].iloc[-1])
        prev  = float(hist["Close"].iloc[-2]) if len(hist) >= 2 else close
        change = close - prev
        pct = round((change / prev * 100), 2) if prev != 0 else 0

        data = {
            "symbol":       symbol,
            "price":        round(close, 4),
            "prev_close":   round(prev, 4),
            "change":       round(change, 4),
            "change_pct":   pct,
            "high_52w":     getattr(info, "fifty_two_week_high", None),
            "low_52w":      getattr(info, "fifty_two_week_low", None),
            "volume":       int(hist["Volume"].iloc[-1]) if "Volume" in hist else None,
            "updated_at":   datetime.now().isoformat(),
        }

        db.cache_set(cache_key, data, CACHE_TTL["tick"])
        return data

    except Exception as e:
        logger.error(f"Yahoo Finance hatası [{symbol}]: {e}")
        return None


def get_yahoo_bulk(symbols: list[str], use_cache: bool = True) -> Optional[list]:
    """
    Birden fazla sembol için Yahoo Finance verisi.
    """
    cache_key = f"yahoo_bulk_free:{','.join(sorted(symbols))}"
    if use_cache:
        cached = db.cache_get(cache_key)
        if cached:
            return cached

    results = []
    for sym in symbols:
        data = get_yahoo_quote(sym, use_cache=use_cache)
        if data:
            results.append(data)

    if results:
        db.cache_set(cache_key, results, CACHE_TTL["tick"])

    return results if results else None


# ─── Sağlık Kontrolü ──────────────────────────────────────────────────────────

def health_check() -> dict:
    """
    Servislerin durumunu kontrol eder.
    Artık Apify yerine ücretsiz kaynaklar kullanılıyor.
    """
    status = {
        "status":           "ok",
        "provider":         "Ücretsiz Kaynaklar (Apify gerekmiyor)",
        "google_news_rss":  "unknown",
        "kap_api":          "unknown",
        "yfinance":         "unknown",
        "twitter_sentiment": "devre dışı (ücretsiz API yok)",
    }

    # Google News RSS testi
    try:
        feed = feedparser.parse(
            "https://news.google.com/rss/search?q=test&hl=tr&gl=TR&ceid=TR:tr"
        )
        if feed.entries:
            status["google_news_rss"] = f"ok ({len(feed.entries)} sonuç)"
        else:
            status["google_news_rss"] = "boş sonuç"
    except Exception as e:
        status["google_news_rss"] = f"hata: {e}"

    # KAP API testi
    try:
        resp = requests.get(
            "https://www.kap.org.tr/tr/api/memberDisclosureIndex",
            headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
            timeout=10,
        )
        if resp.status_code == 200:
            status["kap_api"] = "ok"
        else:
            status["kap_api"] = f"HTTP {resp.status_code}"
    except Exception as e:
        status["kap_api"] = f"erişilemez (Google News fallback aktif)"

    # yfinance testi
    try:
        import yfinance as yf
        data = yf.download("GARAN.IS", period="1d", progress=False, auto_adjust=True,
                           multi_level_index=False)
        if data is not None and not data.empty:
            status["yfinance"] = "ok"
        else:
            status["yfinance"] = "veri yok"
    except Exception as e:
        status["yfinance"] = f"hata: {e}"

    # Genel durum
    if any("hata" in str(v) for v in status.values()):
        status["status"] = "partial"

    return status
