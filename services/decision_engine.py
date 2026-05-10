"""
FinSentinel — AI Decision Engine (The Golden Mine)
services/decision_engine.py

Bu modül, farklı veri kaynaklarını (Teknik, Temel, Duygu, Makro) birleştirerek
tek bir "FinScore" üretir. Bu, platformun "Karar Verici" kimliğini oluşturur.
"""

import pandas as pd
import numpy as np
from core.fetcher import PriceFetcher, NewsFetcher
from core.rule_engine import explain_score
import streamlit as st

class DecisionEngine:
    @staticmethod
    def calculate_fin_score(symbol: str, quote: dict = None) -> dict:
        """
        Bir varlık için 0-100 arası tek bir 'FinScore' hesaplar.
        """
        if quote is None:
            quote = PriceFetcher.get_quote(symbol)
        
        # 1. Teknik Puan (0-100)
        # Basitçe rule_engine'deki -5/+5 skoru 0-100'e çekelim
        # Gerçekte burada TechnicalAnalyzer'dan veri çekilir
        try:
            # Örnek simülasyon (Gerçek analyzer entegrasyonu gelecek)
            tech_raw = np.random.randint(-5, 6) # -5 to +5
            tech_score = (tech_raw + 5) * 10 
        except:
            tech_score = 50

        # 2. Duygu Puanı (News Sentiment) (0-100)
        sentiment_score = 50
        try:
            news = NewsFetcher.get_latest(limit=5)
            # Burada NLP sentiment analizi yapılabilir
            # Şimdilik basit keyword eşleşmesi (mock)
            sentiment_score = 55 + np.random.randint(-15, 16)
        except:
            pass

        # 3. Temel Puan (Sektörel ve Oransal) (0-100)
        fundamental_score = 60 # Varsayılan

        # ── Ağırlıklı FinScore ──
        # %50 Teknik, %30 Duygu, %20 Temel
        fin_score = (tech_score * 0.5) + (sentiment_score * 0.3) + (fundamental_score * 0.2)
        fin_score = max(0, min(100, int(fin_score)))

        # Durum ve Renk
        if fin_score >= 80:
            status, color, icon = "GÜÇLÜ FIRSAT", "#00c896", "🚀"
        elif fin_score >= 65:
            status, color, icon = "POTANSİYEL", "#4da6ff", "📈"
        elif fin_score >= 45:
            status, color, icon = "NÖTR", "#7a93b0", "⚖️"
        elif fin_score >= 30:
            status, color, icon = "ZAYIF", "#ff9f40", "⚠️"
        else:
            status, color, icon = "RİSKLİ", "#ff4d6d", "🚫"

        return {
            "symbol": symbol,
            "score": fin_score,
            "status": status,
            "color": color,
            "icon": icon,
            "tech": tech_score,
            "sentiment": sentiment_score,
            "fundamental": fundamental_score,
            "price": quote.get("price", 0),
            "change": quote.get("change_pct", 0)
        }

    @staticmethod
    def get_opportunities(limit=5) -> list:
        """
        Piyasayı tarayıp en yüksek FinScore'a sahip varlıkları döner.
        """
        symbols = ["THYAO.IS", "GARAN.IS", "EREGL.IS", "SISE.IS", "TUPRS.IS", "KCHOL.IS", "ASELS.IS", "BIMAS.IS"]
        results = []
        
        # Test için bulk çekelim
        quotes = PriceFetcher.get_bulk_quotes(symbols)
        
        for s in symbols:
            q = quotes.get(s, {})
            if q and "error" not in q:
                results.append(DecisionEngine.calculate_fin_score(s, q))
        
        # Skora göre sırala
        results.sort(key=lambda x: x['score'], reverse=True)
        return results[:limit]

def opportunity_radar_ui():
    """
    Dashboard için Opportunity Radar UI bileşeni.
    """
    from utils.ui import section_header
    
    section_header("🔥 Yapay Zeka Fırsat Radarı", "FinScore ile en iyi yatırım fırsatları")
    
    with st.spinner("Piyasa taranıyor..."):
        opps = DecisionEngine.get_opportunities()
    
    if not opps:
        st.info("Şu an belirgin bir fırsat yakalanamadı.")
        return

    # Modern Kart Tasarımı
    cols = st.columns(len(opps))
    for i, opp in enumerate(opps):
        with cols[i]:
            st.markdown(
                f"""
                <div style="background:linear-gradient(135deg, #111827 0%, #0d121f 100%);
                            border: 1px solid {opp['color']}40;
                            border-radius: 12px;
                            padding: 15px;
                            text-align: center;
                            position: relative;
                            overflow: hidden;
                            transition: transform 0.2s;">
                    <div style="position:absolute; top:0; left:0; width:100%; height:3px; background:{opp['color']}"></div>
                    <div style="font-size: 20px; margin-bottom: 5px;">{opp['icon']}</div>
                    <div style="color: #e2eaf5; font-size: 14px; font-weight: 800;">{opp['symbol'].split('.')[0]}</div>
                    <div style="color: {opp['color']}; font-size: 24px; font-weight: 900; margin: 8px 0;">{opp['score']}</div>
                    <div style="color: {opp['color']}; font-size: 10px; font-weight: 800; text-transform: uppercase; letter-spacing: 1px;">{opp['status']}</div>
                    <div style="margin-top: 10px; border-top: 1px solid #1e3a5f; padding-top: 10px;">
                        <span style="color: {'#00c896' if opp['change'] >= 0 else '#ff4d6d'}; font-size: 12px; font-weight: 600;">
                            {'▲' if opp['change'] >= 0 else '▼'} {abs(opp['change']):.2f}%
                        </span>
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )
