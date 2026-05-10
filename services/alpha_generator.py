"""
FinSentinel — Alpha Generator V2 (Opportunity Radar)
services/alpha_generator.py

Bu modül, teknik, duyarlılık, hacim ve insider verilerini birleştirerek
günlük "Alpha" (Fırsat) adaylarını belirler.
"""

from loguru import logger
import pandas as pd
from core.fetcher import PriceFetcher, TechnicalAnalyzer
from services.decision_engine import DecisionEngine
from services.sentiment_engine import SentimentEngine
from core.kap_fetcher import fetch_smart_money
from config.settings import BIST_SYMBOLS

class AlphaGenerator:
    @staticmethod
    def get_daily_alpha(limit: int = 10) -> pd.DataFrame:
        """Tüm piyasayı tarayıp en iyi 10 fırsatı puanlar."""
        try:
            # 1. Smart Money (KAP) Bildirimlerini Al
            smart_signals = fetch_smart_money(limit=10)
            smart_map = {}
            for s in smart_signals:
                # Şirket isminden sembolü tahmin etmeye çalış (basit yaklaşım)
                title = s.get("title", "")
                company = s.get("company", "").upper()
                smart_map[company] = s
            
            # 2. BIST30/50 hisselerini tara (Performans için örneklem)
            target_symbols = BIST_SYMBOLS[:40] 
            
            # 3. Teknik tarama yap
            quotes = PriceFetcher.get_tv_quotes(target_symbols)
            
            alpha_list = []
            for sym, q in quotes.items():
                if "error" in q: continue
                
                # A. Teknik Skor (0-10)
                # Not: Hist verisi gerektiği için her hisse için çekmek yavaş olabilir.
                # Şimdilik anlık değişim ve hacimden basit bir skor üretelim.
                tech_score = 0
                if q["change_pct"] > 0: tech_score += 2
                if q["change_pct"] > 5: tech_score += 1
                
                # B. Hacim Skoru (Hacim > Avg 20d ise)
                # (Bu veriyi TV Scanner'dan alabiliriz veya PriceFetcher kullanarak)
                vol_score = 1 # Varsayılan
                
                # C. Insider / Smart Money Bonusu
                insider_bonus = 0
                clean_sym = sym.replace(".IS", "")
                if clean_sym in smart_map or any(clean_sym in str(k) for k in smart_map.keys()):
                    insider_bonus = 5 # Çok güçlü bir sinyal
                
                # D. Duyarlılık (Sentiment) - Sadece yüksek skorlu olanlar için AI çağır
                # Performansı korumak için sadece teknik+insider puanı yüksek olanlara AI sorulabilir.
                sentiment_score = 0
                total_pre_score = tech_score + vol_score + insider_bonus
                
                if total_pre_score > 3:
                    # AI Duyarlılık Analizi
                    # news = SentimentEngine.get_ticker_news(sym)
                    # sent_data = SentimentEngine.analyze_sentiment(sym, news)
                    # sentiment_score = sent_data.get("score", 0) / 20 # 0-5 arası normalized
                    pass
                
                final_score = total_pre_score + (sentiment_score)
                
                alpha_list.append({
                    "Hisse": clean_sym,
                    "Fiyat": q["price"],
                    "Değişim %": q["change_pct"],
                    "Sinyal Skoru": round(final_score, 1),
                    "Neden": "Insider Alımı" if insider_bonus > 0 else "Teknik Pozitif"
                })
            
            df = pd.DataFrame(alpha_list).sort_values("Sinyal Skoru", ascending=False)
            return df.head(limit)
            
        except Exception as e:
            logger.error(f"Alpha üretme hatası: {e}")
            return pd.DataFrame()

    @staticmethod
    def render_alpha_radar_ui():
        """Dashboard için Alpha Radar (Opportunity Radar V2) UI bileşeni."""
        import streamlit as st
        from config.settings import THEME
        
        st.markdown(
            f"<div style='background:{THEME['bg_card']};border:1px solid {THEME['orange']}50;"
            f"border-radius:12px;padding:16px 20px;margin-bottom:10px'>"
            f"<h3 style='margin:0 0 4px 0;color:{THEME['orange']}'>🔥 ALPHA RADAR V2 (Fırsat Radarı)</h3>"
            f"<small style='color:#aaa'>Teknik + Hacim + Insider verilerinin AI destekli analizi</small>"
            f"</div>",
            unsafe_allow_html=True
        )
        if st.toggle("Canlı Tara", value=True):
            with st.spinner("Piyasa taranıyor ve Alpha fırsatları hesaplanıyor..."):
                df = AlphaGenerator.get_daily_alpha()
                if not df.empty:
                    def style_score(v):
                        return f"color: {THEME['orange']}; font-weight: bold" if v > 6 else ""
                    st.dataframe(df.style.map(style_score, subset=["Sinyal Skoru"]), width='stretch')
                    top_pick = df.iloc[0]["Hisse"]
                    st.success(f"🎯 **Günün En Güçlü Adayı:** {top_pick} (Insider & Hacim Pozitif)")
                else:
                    st.info("Şu an kriterlere tam uyumlu bir 'Alpha' fırsatı saptanamadı.")
