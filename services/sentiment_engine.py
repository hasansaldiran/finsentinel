"""
FinSentinel — AI Sentiment Analysis Engine
services/sentiment_engine.py

Bu modül, belirli bir sembol (Hisse, Kripto vb.) için güncel haberleri analiz eder
ve piyasa duyarlılığını (Sentiment) sayısallaştırır.
"""

from loguru import logger
import pandas as pd
import yfinance as yf
from core.ai_engine import _call_best_ai
from core.db import db
from datetime import datetime

class SentimentEngine:
    @staticmethod
    def _fetch_rss(url: str, source_name: str, limit: int = 8) -> list[dict]:
        """RSS feed'den haber başlıklarını çek."""
        import feedparser
        try:
            feed = feedparser.parse(url)
            items = []
            for entry in feed.entries[:limit]:
                title = entry.get("title", "").strip()
                if title:
                    items.append({
                        "title": title,
                        "publisher": source_name,
                        "link": entry.get("link", ""),
                        "provider": source_name,
                    })
            return items
        except Exception:
            return []

    @staticmethod
    def _yahoo_rss(symbol: str, limit: int = 10) -> list[dict]:
        """Yahoo Finance ticker-specific RSS feed."""
        url = f"https://finance.yahoo.com/rss/headline?s={symbol}"
        return SentimentEngine._fetch_rss(url, "Yahoo Finance", limit)

    @staticmethod
    def _bigpara_news(company_name: str, limit: int = 8) -> list[dict]:
        """BigPara (Hürriyet) haberleri."""
        import requests, urllib.parse
        try:
            q = urllib.parse.quote(company_name)
            url = f"https://bigpara.hurriyet.com.tr/api/v1/haber/search/?q={q}&limit={limit}"
            r = requests.get(url, timeout=8, headers={"User-Agent": "Mozilla/5.0"})
            data = r.json()
            rows = data if isinstance(data, list) else data.get("data", data.get("items", []))
            items = []
            for row in rows[:limit]:
                title = row.get("title", row.get("baslik", "")).strip()
                if title:
                    items.append({"title": title, "publisher": "BigPara", "link": row.get("url",""), "provider": "BigPara"})
            return items
        except Exception:
            return []

    @staticmethod
    def get_ticker_news(symbol: str) -> list[dict]:
        """Sembol bazlı güncel haberleri çoklu kaynaklardan getirir."""
        import urllib.parse
        # Şirket adını sembole dönüştür (ASELS.IS → ASELS)
        base_sym = symbol.replace(".IS","").replace("-USD","").replace("=X","")
        all_news: list[dict] = []

        # 1. Yahoo Finance ticker-specific RSS
        all_news += SentimentEngine._yahoo_rss(symbol, limit=8)

        # 2. yfinance .news
        try:
            ticker = yf.Ticker(symbol)
            yf_news = ticker.news or []
            for item in yf_news[:8]:
                title = item.get("title", "")
                if title:
                    all_news.append({"title": title, "publisher": item.get("publisher","Yahoo"), "link": item.get("link",""), "provider": "Yahoo Finance"})
        except Exception:
            pass

        # 3. Google News — sembol adı + şirket
        from core.fetcher import NewsFetcher
        for query in [f"{base_sym} hisse", f"{base_sym} borsa", f"{base_sym} şirket haberleri"]:
            all_news += NewsFetcher.get_google_news(query, limit=6)

        # 4. Investing.com TR RSS
        all_news += SentimentEngine._fetch_rss("https://tr.investing.com/rss/news.rss", "Investing.com TR", 6)

        # 5. Bloomberg HT RSS
        all_news += SentimentEngine._fetch_rss("https://www.bloomberght.com/rss", "Bloomberg HT", 5)

        # 6. BigPara (Hürriyet)
        all_news += SentimentEngine._bigpara_news(base_sym, limit=6)

        # 7. Milliyet Ekonomi RSS
        all_news += SentimentEngine._fetch_rss("https://www.milliyet.com.tr/rss/rssNew/ekonomiRss.xml", "Milliyet Ekonomi", 5)

        # 8. Haberler.com Ekonomi RSS
        all_news += SentimentEngine._fetch_rss("https://www.haberler.com/rss/ekonomi-haberleri.xml", "Haberler.com", 5)

        # 9. Ekonomim.com RSS
        all_news += SentimentEngine._fetch_rss("https://www.ekonomim.com/rss.xml", "Ekonomim.com", 5)

        # 10. Dünya Gazetesi Ekonomi RSS
        all_news += SentimentEngine._fetch_rss("https://www.dunya.com/rss/ekonomi.xml", "Dünya Gazetesi", 5)

        # Sembol ile ilişkili haberleri öne al (filtrele)
        kw = base_sym.lower()
        relevant = [n for n in all_news if kw in n.get("title","").lower() or kw in n.get("publisher","").lower()]
        other    = [n for n in all_news if n not in relevant]

        # Unique başlıklar
        seen, unique = set(), []
        for n in relevant + other:
            t = n.get("title","").strip()
            if t and t not in seen:
                seen.add(t)
                unique.append(n)

        if not unique:
            # Son çare: genel finans haberleri
            unique = NewsFetcher.get_latest(limit=8)

        return unique[:15]

    @staticmethod
    def analyze_sentiment(symbol: str, news: list[dict]) -> dict:
        """Haberleri AI ile analiz edip -100 ile +100 arası skor üretir."""
        if not news:
            return {"score": 0, "reason": "Haber bulunamadı.", "sentiment": "Nötr"}

        news_text = "\n".join([f"- {n['title']} [{n.get('provider', n.get('publisher',''))}]" for n in news[:15]])
        
        prompt = f"""
Aşağıdaki {symbol} sembolüne ait güncel haber başlıklarını analiz et ve piyasa duyarlılığını (sentiment) belirle.

Haberler:
{news_text}

Senden istediğim:
1. Duyarlılık Skoru: -100 (Aşırı Panik/Kötü) ile +100 (Aşırı Coşku/İyi) arasında bir tam sayı ver.
2. Kısa Özet: Duyarlılığın nedenini tek bir cümleyle açıkla.
3. Etiket: (Pozitif, Negatif, Nötr)

Yanıtı şu formatta ver:
SKOR: [Sayı]
NEDEN: [Cümle]
ETİKET: [Etiket]
"""
        
        try:
            response = _call_best_ai(prompt, max_tokens=200)
            
            # Yanıtı ayrıştır
            score = 0
            reason = "Analiz yapılamadı."
            sentiment = "Nötr"
            
            for line in response.split("\n"):
                if "SKOR:" in line:
                    try: score = int(line.split(":")[1].strip())
                    except: pass
                elif "NEDEN:" in line:
                    reason = line.split(":")[1].strip()
                elif "ETİKET:" in line:
                    sentiment = line.split(":")[1].strip()
            
            result = {
                "symbol": symbol,
                "score": score,
                "reason": reason,
                "sentiment": sentiment,
                "timestamp": datetime.now().isoformat()
            }
            
            # Cache'e kaydet (Opsiyonel: DB'de saklayarak geçmiş osilatör yapılabilir)
            db.cache_set(f"sentiment:{symbol}", result, ttl=3600)
            
            return result
        except Exception as e:
            logger.error(f"AI Analiz hatası [{symbol}]: {e}")
            return {"score": 0, "reason": "Yapay zeka analiz hatası.", "sentiment": "Nötr"}

    @staticmethod
    def get_sentiment_oscillator_ui(symbol: str):
        """Streamlit için Sentiment Oscillator bileşeni."""
        import streamlit as st
        import plotly.graph_objects as go

        data = db.cache_get(f"sentiment:{symbol}")
        if not data:
            with st.spinner(f"{symbol} duyarlılığı analiz ediliyor..."):
                news = SentimentEngine.get_ticker_news(symbol)
                data = SentimentEngine.analyze_sentiment(symbol, news)

        # Gauge / Oscillator Chart
        score = data.get("score", 0)
        color = "#00c896" if score > 0 else ("#ff4d6d" if score < 0 else "#7a93b0")
        
        fig = go.Figure(go.Indicator(
            mode = "gauge+number",
            value = score,
            domain = {'x': [0, 1], 'y': [0, 1]},
            title = {'text': f"AI {symbol} Duyarlılık Osilatörü", 'font': {'size': 16}},
            gauge = {
                'axis': {'range': [-100, 100], 'tickwidth': 1},
                'bar': {'color': color},
                'steps': [
                    {'range': [-100, -30], 'color': "rgba(255, 77, 106, 0.1)"},
                    {'range': [-30, 30], 'color': "rgba(122, 147, 176, 0.1)"},
                    {'range': [30, 100], 'color': "rgba(0, 200, 150, 0.1)"}
                ],
                'threshold': {
                    'line': {'color': "white", 'width': 4},
                    'thickness': 0.75,
                    'value': score
                }
            }
        ))
        fig.update_layout(height=250, margin=dict(l=20, r=20, t=40, b=20), paper_bgcolor="rgba(0,0,0,0)")
        
        st.plotly_chart(fig, width='stretch')
        st.markdown(f"🚩 **Neden:** {data.get('reason')}")
        st.caption("* Analizler Yahoo Finance, Google News, Bloomberg HT, Investing.com TR, BigPara, Milliyet, Ekonomim ve diğer finans kaynaklarından çekilen güncel haber başlıklarına dayanmaktadır.")
