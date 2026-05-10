"""
FinSentinel — Kural Tabanlı AI Yorum Motoru
core/rule_engine.py

API bağımlılığı olmadan profesyonel finansal yorumlar üretir.
Gemini API yoksa bile tam çalışır; Gemini varsa daha zengin yorum ekler.
"""
import pandas as pd
import numpy as np
from typing import Optional

# ── Teknik Terimler Sözlüğü ───────────────────────────────────────────────────

GLOSSARY = {
    "RSI": {
        "name": "RSI — Göreceli Güç Endeksi (Relative Strength Index)",
        "short": "Momentum göstergesi, 0-100 arası değer alır.",
        "detail": (
            "RSI (Relative Strength Index), bir varlığın son dönemdeki "
            "kazanç ve kayıplarını karşılaştırarak momentumu ölçer. "
            "Genellikle 14 günlük periyot kullanılır.\n\n"
            "📊 **Okuma Kılavuzu:**\n"
            "• **< 30:** Aşırı satım — varlık olduğundan ucuz olabilir, alım fırsatı sinyali\n"
            "• **30–50:** Düşüş momentumu — satış baskısı ağır basıyor\n"
            "• **50–70:** Yükseliş momentumu — alış baskısı ağır basıyor\n"
            "• **> 70:** Aşırı alım — varlık olduğundan pahalı olabilir, kar satışı yaklaşıyor\n\n"
            "⚠️ RSI tek başına yeterli değil; trend yönü ve hacimle birlikte kullanılmalıdır."
        ),
    },
    "MACD": {
        "name": "MACD — Hareketli Ortalama Yakınsama/Iraksama",
        "short": "İki EMA farkından üretilen trend-momentum göstergesi.",
        "detail": (
            "MACD (Moving Average Convergence Divergence), 12 günlük EMA ile "
            "26 günlük EMA arasındaki farkı ve bu farkın 9 günlük ortalamasını (sinyal çizgisi) gösterir.\n\n"
            "📊 **3 bileşen:**\n"
            "• **MACD Çizgisi:** 12-EMA eksi 26-EMA\n"
            "• **Sinyal Çizgisi:** MACD'nin 9 günlük EMA'sı\n"
            "• **Histogram:** MACD eksi Sinyal (momentum görselleştirmesi)\n\n"
            "📊 **Sinyaller:**\n"
            "• MACD > Sinyal → Yükseliş sinyali (bullish crossover)\n"
            "• MACD < Sinyal → Düşüş sinyali (bearish crossover)\n"
            "• Histogram pozitiften negatife dönüş → Momentum zayıflıyor"
        ),
    },
    "SMA": {
        "name": "SMA — Basit Hareketli Ortalama (Simple Moving Average)",
        "short": "Belirli dönemin kapanış fiyatlarının ortalaması.",
        "detail": (
            "SMA (Simple Moving Average), belirlenen periyottaki kapanış fiyatlarını "
            "eşit ağırlıkla ortalayarak hesaplanır.\n\n"
            "📊 **Yaygın periyotlar:**\n"
            "• **SMA 20:** Kısa vadeli trend (~1 ay)\n"
            "• **SMA 50:** Orta vadeli trend (~2.5 ay)\n"
            "• **SMA 200:** Uzun vadeli trend (~10 ay)\n\n"
            "📊 **Kullanım:**\n"
            "• Fiyat SMA üstünde → Bullish (yükseliş eğilimi)\n"
            "• Fiyat SMA altında → Bearish (düşüş eğilimi)\n"
            "• Destek/direnç seviyesi olarak da işlev görür"
        ),
    },
    "EMA": {
        "name": "EMA — Üstel Hareketli Ortalama (Exponential Moving Average)",
        "short": "Son fiyatlara daha fazla ağırlık veren hareketli ortalama.",
        "detail": (
            "EMA (Exponential Moving Average), son dönemin verilerine daha fazla "
            "ağırlık vererek piyasa değişimlerine SMA'ya göre daha hızlı tepki verir.\n\n"
            "📊 **Fark nedir?**\n"
            "• SMA: Tüm günlere eşit ağırlık\n"
            "• EMA: Yeni günlere üssel artan ağırlık\n\n"
            "Hızlı ticaret stratejilerinde EMA 9, 21 veya 55 periyotlu versiyonlar kullanılır."
        ),
    },
    "GOLDEN_CROSS": {
        "name": "Golden Cross — Altın Kesişim",
        "short": "SMA50'nin SMA200'ün üstüne çıkması — güçlü boğa sinyali.",
        "detail": (
            "Golden Cross, kısa vadeli hareketli ortalama (SMA 50) ile uzun vadeli "
            "hareketli ortalama (SMA 200) birbirini yukarı yönde kestiğinde oluşur.\n\n"
            "📈 **Anlamı:**\n"
            "• Kısa vadeli momentum uzun vadeli trendi geride bırakmış\n"
            "• Güçlü boğa (bullish) piyasası sinyali\n"
            "• Kurumsal yatırımcıların dikkat ettiği teknik sinyal\n\n"
            "⚠️ Gecikme içerebilir; büyük trendlerin başında güçlü, "
            "dar bant piyasalarda yanıltıcı olabilir."
        ),
    },
    "DEATH_CROSS": {
        "name": "Death Cross — Ölüm Kesişimi",
        "short": "SMA50'nin SMA200'ün altına inmesi — güçlü ayı sinyali.",
        "detail": (
            "Death Cross, kısa vadeli hareketli ortalama (SMA 50) ile uzun vadeli "
            "hareketli ortalama (SMA 200) birbirini aşağı yönde kestiğinde oluşur.\n\n"
            "📉 **Anlamı:**\n"
            "• Kısa vadeli momentum uzun vadeli trendin altına düşmüş\n"
            "• Güçlü ayı (bearish) piyasası sinyali\n"
            "• Büyük düşüş trendlerinin başlangıcında sıkça görülür\n\n"
            "⚠️ Genellikle fiyat düştükten sonra oluşur (lagging indicator). "
            "Diğer göstergelerle teyit alınmalı."
        ),
    },
    "BOLLINGER": {
        "name": "Bollinger Bantları",
        "short": "SMA etrafında ±2 standart sapma ile oluşturulan bant sistemi.",
        "detail": (
            "Bollinger Bantları, fiyatın volatilitesini ve olası dönüş "
            "noktalarını göstermek için kullanılır.\n\n"
            "📊 **3 bileşen:**\n"
            "• **Üst Bant:** SMA + 2×Std\n"
            "• **Orta Bant:** 20 günlük SMA\n"
            "• **Alt Bant:** SMA − 2×Std\n\n"
            "📊 **Okuma:**\n"
            "• Fiyat üst banda değerse → Aşırı alım, düzeltme bekleniyor\n"
            "• Fiyat alt banda değerse → Aşırı satım, toparlanma bekleniyor\n"
            "• Bantlar daralıyorsa → Düşük volatilite, büyük hareket yakın"
        ),
    },
    "ATR": {
        "name": "ATR — Ortalama Gerçek Aralık (Average True Range)",
        "short": "Varlığın günlük fiyat dalgalanmasını ölçen volatilite göstergesi.",
        "detail": (
            "ATR (Average True Range), fiyat hareketinin genişliğini ölçer ve "
            "stop-loss seviyeleri belirlemede yaygın kullanılır.\n\n"
            "📊 **ATR arttıkça:** Volatilite yükseliyor, risk arttı\n"
            "📊 **ATR azaldıkça:** Piyasa sakinleşiyor, sıkışma oluşuyor"
        ),
    },
    "STOCHASTIC": {
        "name": "Stochastic Osilatör",
        "short": "Kapanış fiyatını belirli periyottaki fiyat aralığıyla karşılaştırır.",
        "detail": (
            "Stochastic osilatör, kapanış fiyatının son N gündeki yüksek-düşük "
            "bandına göre nerede olduğunu yüzde olarak gösterir.\n\n"
            "📊 **%K ve %D çizgileri:**\n"
            "• **%K > 80:** Aşırı alım bölgesi\n"
            "• **%K < 20:** Aşırı satım bölgesi\n"
            "• **%K, %D'yi aşağıdan keser:** Alış sinyali\n"
            "• **%K, %D'yi yukarıdan keser:** Satış sinyali"
        ),
    },
    "VIX": {
        "name": "VIX — Korku Endeksi (CBOE Volatility Index)",
        "short": "S&P 500 opsiyon piyasasından türetilen piyasa korku ölçüsü.",
        "detail": (
            "VIX, yatırımcıların önümüzdeki 30 gün için beklediği oynaklığı "
            "opsiyon fiyatlarından hesaplar.\n\n"
            "📊 **Seviyeler:**\n"
            "• **< 15:** Sakin, düşük endişe — piyasa güvende hissediyor\n"
            "• **15–25:** Normal volatilite — tipik piyasa koşulları\n"
            "• **25–35:** Yüksek endişe — risk algısı artmış\n"
            "• **> 35:** Panik/kriz — tarihi geri alım noktaları\n\n"
            "💡 'Fırsatçı yatırımcılar' VIX 40+ gördüklerinde alım yapar (Warren Buffett etkisi)"
        ),
    },
    "OBV": {
        "name": "OBV — Dengedeki Hacim (On Balance Volume)",
        "short": "Hacim akışını fiyat hareketiyle ilişkilendiren gösterge.",
        "detail": (
            "OBV, fiyat yükseldiğinde hacmi ekler, düştüğünde çıkararak "
            "birikimli bir hacim çizgisi oluşturur.\n\n"
            "📊 **Yorumlama:**\n"
            "• OBV yükseliyor, fiyat yatay → Gizli alım baskısı, yakında yükseliş\n"
            "• OBV düşüyor, fiyat yatay → Gizli satış baskısı, yakında düşüş\n"
            "• Fiyat ve OBV aynı yönde → Trend güçlü"
        ),
    },
}


# ── Skor ve Sinyal Açıklamaları ───────────────────────────────────────────────

SCORE_EXPLANATIONS = {
    5:  ("🚀 GÜÇLÜ AL",  "Tüm teknik göstergeler güçlü yükseliş sinyali veriyor. Momentum çok pozitif, trende katılım mantıklı görünüyor.", "#00d4aa"),
    4:  ("📈 AL",        "Çoğu gösterge pozitif. Güçlü bir yükseliş eğilimi mevcut, kısa vadeli düzeltmeler sınırlı kalabilir.", "#00d4aa"),
    3:  ("📈 AL",        "Teknik görünüm yükseliş yönünde. RSI ve trend göstergeleri alım için elverişli ortam işaret ediyor.", "#00d4aa"),
    2:  ("🟢 HAFIF AL",  "Hafif yükseliş eğilimi var. Risk/getiri dengesi alım lehine ancak pozisyon boyutunu sınırla.", "#ffd166"),
    1:  ("🟡 AL/NÖTR",   "Sinyaller karışık, hafif pozitif eğilim. Konjonktür net olmadan büyük pozisyon açmak riskli.", "#ffd166"),
    0:  ("⚪ NÖTR",      "Göstergeler net bir yön vermiyor. Piyasa kararsız; breakout beklenene kadar bekle-izle stratejisi önerilir.", "#7a93b0"),
    -1: ("🟡 SAT/NÖTR",  "Hafif negatif eğilim. Mevcut pozisyonlarda stop-loss seviyelerine dikkat et.", "#ffd166"),
    -2: ("🔴 HAFIF SAT", "Teknik baskı artıyor. Kısa vadeli düşüş riski var; yeni alım için sabır gerekiyor.", "#ff9a3c"),
    -3: ("📉 SAT",       "Çoğu gösterge negatif. Trend aşağı yönlü, satış baskısı devam edebilir.", "#ff4d6a"),
    -4: ("📉 SAT",       "Güçlü düşüş baskısı. Momentum belirgin biçimde negatif, kısa pozisyon veya nakit tercih edilebilir.", "#ff4d6a"),
    -5: ("🛑 GÜÇLÜ SAT", "Tüm göstergeler satış sinyali veriyor. Aşırı satım olmadıkça mevcut pozisyonları küçültmeyi değerlendir.", "#ff4d6a"),
}


def explain_score(score: int) -> tuple[str, str, str]:
    """Skora göre (etiket, açıklama, renk) döndür"""
    clamped = max(-5, min(5, int(score)))
    return SCORE_EXPLANATIONS.get(clamped, SCORE_EXPLANATIONS[0])


def explain_reason(reason: str) -> str:
    """Sinyal nedenini Türkçe açıklamaya çevir"""
    reason_lower = reason.lower()
    if "rsi aşırı satım" in reason_lower:
        return f"⬇️ {reason} → Varlık aşırı satım bölgesinde; toparlanma potansiyeli var"
    elif "rsi aşırı alım" in reason_lower:
        return f"⬆️ {reason} → Varlık aşırı alım bölgesinde; kar satışı baskısı yakın"
    elif "rsi pozitif" in reason_lower:
        return f"📊 {reason} → RSI 50 üzerinde; yükseliş momentumu hakim"
    elif "macd sinyal üzerinde" in reason_lower:
        return f"📈 {reason} → Kısa vadeli momentum uzun vadeyi geçti; yükseliş teyidi"
    elif "macd sinyal altında" in reason_lower:
        return f"📉 {reason} → MACD sinyal çizgisinin altında; düşüş baskısı devam ediyor"
    elif "golden cross" in reason_lower:
        return f"🌟 {reason} → SMA50, SMA200'ü yukarı kesti; uzun vadeli yükseliş sinyali"
    elif "death cross" in reason_lower:
        return f"💀 {reason} → SMA50, SMA200'ün altına indi; uzun vadeli düşüş uyarısı"
    elif "fiyat sma50 üzerinde" in reason_lower:
        return f"✅ {reason} → Fiyat orta vadeli trendi koruyarak SMA50 desteği üzerinde"
    elif "fiyat sma50 altında" in reason_lower:
        return f"⛔ {reason} → Fiyat orta vadeli destek SMA50'nin altına düştü"
    else:
        return f"• {reason}"


# ── Kural Tabanlı Yorum Üretici ───────────────────────────────────────────────

def generate_commentary(
    signal: dict,
    symbol: str = "",
    asset_type: str = "varlık",
    price: Optional[float] = None,
    change_pct: Optional[float] = None,
    extra_context: Optional[dict] = None,
) -> str:
    """
    Teknik sinyal verilerinden profesyonel Türkçe yorum üret.
    Gemini API'ye ihtiyaç duymaz.

    Args:
        signal: TechnicalAnalyzer.get_signal() çıktısı
        symbol: Sembol adı (ör. "GARAN", "BTC", "EUR/USD")
        asset_type: "hisse", "kripto", "forex", "emtia", "endeks"
        price: Güncel fiyat
        change_pct: Günlük değişim %
        extra_context: Ek gösterge verileri (rsi, macd vb.)

    Returns:
        Markdown formatında profesyonel yorum metni
    """
    score   = signal.get("score", 0)
    reasons = signal.get("reasons", [])
    sig     = signal.get("signal", "NÖTR")

    label, score_desc, color = explain_score(score)

    lines = []

    # Başlık
    if symbol:
        lines.append(f"### 🤖 {symbol} — Teknik Analiz Yorumu\n")
    else:
        lines.append("### 🤖 Teknik Analiz Yorumu\n")

    # Fiyat bilgisi
    if price is not None:
        price_str = f"{price:,.4f}" if price < 10 else f"{price:,.2f}"
        change_str = ""
        if change_pct is not None:
            direction = "▲" if change_pct >= 0 else "▼"
            c_color_word = "yükseliyor" if change_pct >= 0 else "düşüyor"
            change_str = f" — Günlük {direction} **{abs(change_pct):.2f}%** {c_color_word}"
        lines.append(f"**Güncel Fiyat:** {price_str}{change_str}\n")

    # Sinyal kutusu
    lines.append(f"**Genel Değerlendirme:** {label}")
    lines.append(f"> {score_desc}\n")

    # Aktif sinyaller
    if reasons:
        lines.append("**📋 Aktif Sinyaller:**")
        for r in reasons:
            lines.append(explain_reason(r))
        lines.append("")

    # Detaylı analiz (kurallara göre)
    analysis_parts = []

    # RSI analizi
    rsi_val = (extra_context or {}).get("rsi")
    if rsi_val is not None:
        if rsi_val < 30:
            analysis_parts.append(
                f"**RSI ({rsi_val:.1f}):** Aşırı satım bölgesindedir. "
                "Bu bölge genellikle kısa vadeli toparlanma öncesini işaret eder. "
                "Ancak trend aşağı yönlüyse RSI düşük seyrini koruyabilir."
            )
        elif rsi_val > 70:
            analysis_parts.append(
                f"**RSI ({rsi_val:.1f}):** Aşırı alım bölgesindedir. "
                "Kar realizasyonu baskısı artabilir. Yeni alım yapmadan önce "
                "RSI'nın 70 altına geri çekilmesini beklemek daha ihtiyatlı olabilir."
            )
        else:
            analysis_parts.append(
                f"**RSI ({rsi_val:.1f}):** {'Pozitif' if rsi_val > 50 else 'Negatif'} bölgede. "
                f"Momentum {'yükseliş' if rsi_val > 50 else 'düşüş'} tarafında."
            )

    # Trend analizi (skor bazlı)
    if score >= 3:
        analysis_parts.append(
            f"**Trend:** {symbol or asset_type.capitalize()} güçlü yükseliş trendi içinde. "
            "Trend takipçi stratejiler için elverişli ortam. "
            "Stop-loss'u en yakın destek seviyesine çekmeyi unutma."
        )
    elif score >= 1:
        analysis_parts.append(
            f"**Trend:** Hafif pozitif eğilim var. "
            "Piyasa yükselen tarafı tercih ediyor ancak net bir kırılım henüz gerçekleşmedi."
        )
    elif score == 0:
        analysis_parts.append(
            f"**Trend:** Yatay seyir — piyasa net bir yön seçemedi. "
            "Kırılım yönünü beklemek veya küçük pozisyonla izlemek mantıklı olabilir."
        )
    elif score <= -1:
        analysis_parts.append(
            f"**Trend:** Düşüş baskısı hakim. "
            "Mevcut pozisyonlarda zarar durdurma seviyelerini gözden geçir. "
            "Yeni alım için teknik görünümün iyileşmesini bekle."
        )

    # Golden/Death Cross
    has_golden = any("golden" in r.lower() for r in reasons)
    has_death  = any("death" in r.lower() for r in reasons)
    if has_golden:
        analysis_parts.append(
            "**Golden Cross:** SMA50, SMA200'ü yukarı kesti. "
            "Bu teknik oluşum kurumsal yatırımcılar tarafından yakından takip edilir "
            "ve uzun vadeli yükseliş trendlerinin başlangıcını işaret edebilir."
        )
    elif has_death:
        analysis_parts.append(
            "**Death Cross:** SMA50, SMA200'ün altına indi. "
            "Uzun vadeli yatırımcılar için önemli bir uyarı sinyali. "
            "Tarihe bakıldığında Death Cross'lar genellikle önemli düşüşlerin ortasında oluşur."
        )

    if analysis_parts:
        lines.append("**🔍 Detaylı Analiz:**")
        lines.extend(analysis_parts)
        lines.append("")

    # Risk uyarısı ve aksiyon önerisi
    lines.append("---")
    if score >= 3:
        lines.append(
            "💡 **Aksiyon:** Trend güçlü. Pozisyon açarken mutlaka stop-loss belirle. "
            "Hedef: yakın direnç seviyeleri."
        )
    elif score >= 1:
        lines.append(
            "💡 **Aksiyon:** Dikkatli alım değerlendirilebilir. "
            "Küçük pozisyonla başlayıp trend teyidini bekle."
        )
    elif score == 0:
        lines.append(
            "💡 **Aksiyon:** Bekle-izle. Kenar bandın kırılmasını veya hacim artışını bekle."
        )
    elif score <= -3:
        lines.append(
            "💡 **Aksiyon:** Pozisyon küçült veya hedge et. "
            "Teknik görünüm iyileşene kadar yeni alım yapma."
        )
    else:
        lines.append(
            "💡 **Aksiyon:** Mevcut pozisyonlarda stop-loss seviyelerini gözden geçir."
        )

    lines.append(
        "\n⚠️ *Bu yorum otomatik kural motoru tarafından üretilmiştir. "
        "Yatırım tavsiyesi değildir. Finansal kararlarınızı kendi araştırmanıza dayandırın.*"
    )

    return "\n".join(lines)


def render_glossary_term(term_key: str) -> str:
    """
    Tek bir teknik terimin detay açıklamasını HTML kart olarak döndür.
    Streamlit st.markdown(unsafe_allow_html=True) ile kullanılır.
    """
    term = GLOSSARY.get(term_key)
    if not term:
        return ""
    return (
        f'<details style="margin:4px 0;cursor:pointer">'
        f'<summary style="font-size:12px;color:#4da6ff;font-weight:600">'
        f'❓ {term["name"]}</summary>'
        f'<div style="background:#111827;border:1px solid #1e3a5f;border-radius:6px;'
        f'padding:12px;margin-top:6px;font-size:12px;color:#7a93b0;line-height:1.7">'
        f'{term["short"]}</div>'
        f'</details>'
    )


def render_score_card(score: int, show_reasons: bool = True, reasons: list = None) -> str:
    """Skor kartını HTML olarak döndür"""
    label, desc, color = explain_score(score)
    bar_width = int((score + 5) / 10 * 100)  # -5..+5 → 0..100%

    reasons_html = ""
    if show_reasons and reasons:
        items = "".join(
            f'<div style="padding:3px 0;font-size:11px;color:#7a93b0">{explain_reason(r)}</div>'
            for r in reasons
        )
        reasons_html = f'<div style="margin-top:8px">{items}</div>'

    return (
        f'<div style="background:#111827;border:1px solid #1e3a5f;border-left:3px solid {color};'
        f'border-radius:8px;padding:14px;margin:8px 0">'
        f'<div style="display:flex;justify-content:space-between;align-items:center">'
        f'<span style="color:{color};font-size:14px;font-weight:700">{label}</span>'
        f'<span style="color:#7a93b0;font-size:12px">Skor: {score:+d}</span>'
        f'</div>'
        f'<div style="background:#1e3a5f;border-radius:4px;height:6px;margin:8px 0">'
        f'<div style="background:{color};width:{bar_width}%;height:6px;border-radius:4px;'
        f'transition:width 0.3s"></div>'
        f'</div>'
        f'<div style="color:#e2eaf5;font-size:12px;line-height:1.5">{desc}</div>'
        f'{reasons_html}'
        f'</div>'
    )


def render_glossary_pills(terms: list) -> str:
    """
    Birden fazla teknik terimi küçük açıklamalı pill'ler olarak göster.
    Her pill tıklanabilir/expandable.
    """
    pills_html = []
    for key in terms:
        term = GLOSSARY.get(key, {})
        if term:
            pills_html.append(
                f'<span title="{term["short"]}" style="'
                f'display:inline-block;background:#1a2236;border:1px solid #1e3a5f;'
                f'border-radius:12px;padding:3px 10px;margin:3px;font-size:11px;'
                f'color:#4da6ff;cursor:help">'
                f'{term["name"].split("—")[0].strip()}'
                f'</span>'
            )
    return '<div style="margin:6px 0">' + "".join(pills_html) + "</div>"


def generate_market_commentary(df_row: dict, asset_type: str = "endeks") -> str:
    """
    Tek bir varlık satırından (fiyat, değişim %) kısa piyasa yorumu üret.
    Piyasa özeti ve dünya borsaları sayfalarında kullanılır.
    """
    change = df_row.get("change_pct", df_row.get("Değişim %", 0)) or 0
    name = df_row.get("name", df_row.get("Borsa", "Varlık"))

    if change >= 3:
        return f"🚀 {name} bugün güçlü yükseliş performansı sergiliyor. Alıcı baskısı belirgin."
    elif change >= 1:
        return f"📈 {name} yüksekte. Yatırımcı iştahı pozitif."
    elif change >= -1:
        return f"➡️ {name} yatay seyir. Piyasa net bir yön arayışında."
    elif change >= -3:
        return f"📉 {name} düşüşte. Satış baskısı mevcut, destek seviyeleri takip edilmeli."
    else:
        return f"🔴 {name} sert düşüyor. Teknik destek kırılmış olabilir, dikkatli ol."


def generate_crypto_fear_commentary(fng_value: int) -> str:
    """Fear & Greed endeksinden piyasa yorumu"""
    if fng_value <= 20:
        return (
            "**😨 Aşırı Korku Bölgesi**\n\n"
            "Piyasa panik içinde. Tarihe bakıldığında bu bölgeler uzun vadeli yatırımcılar için "
            "cazip alım fırsatları sunmuştur. \"Başkalar korkarken cesur ol\" — Warren Buffett. "
            "Ancak dip ne zaman oluşacağını kimse bilemez; kademeli alım stratejisi önerilebilir."
        )
    elif fng_value <= 40:
        return (
            "**😟 Korku Bölgesi**\n\n"
            "Yatırımcılar temkinli. Piyasa iç çekmiş durumda. "
            "Bu bölge genellikle dibe yakın oluşur ama satış baskısı devam edebilir. "
            "Risk yönetimi ön planda tutulmalı."
        )
    elif fng_value <= 60:
        return (
            "**😐 Nötr Bölge**\n\n"
            "Piyasa yön arayışında. Alıcı ve satıcılar dengelenmiş durumda. "
            "Trend kırılımı beklenene kadar büyük pozisyon açmak riskli."
        )
    elif fng_value <= 80:
        return (
            "**😊 Açgözlülük Bölgesi**\n\n"
            "Piyasa iyimser. Fomo (kaçırma korkusu) hâkim olmaya başlıyor. "
            "Bu seviyede alım yapmak genellikle daha risklidir; "
            "mevcut pozisyonlarda kâr realizasyonu değerlendirilebilir."
        )
    else:
        return (
            "**🤑 Aşırı Açgözlülük Bölgesi**\n\n"
            "Piyasa çok ısındı. Herkes alıyor, ancak tarihsel veriler bu seviyelerin "
            "yakın vadeli düzeltmelerin habercisi olduğunu gösteriyor. "
            "\"Başkalar açgözlüyken korkak ol\" — Warren Buffett."
        )


# ── Sembol bazlı AI yorumu (Gemini önce, yoksa kural tabanlı) ─────────────────

def smart_commentary(
    signal: dict,
    symbol: str,
    quote: dict,
    asset_type: str = "hisse",
    use_gemini: bool = True,
) -> str:
    """
    Önce Gemini ile yorum dene, başarısız olursa kural motorunu kullan.
    Bu fonksiyon tüm 'AI Analiz' butonlarında çağrılır.
    """
    # Kural bazlı yorum her zaman hazır
    rsi_val = None
    for c in (signal.get("_df_last", {}) or {}):
        if "RSI" in c.upper():
            rsi_val = signal["_df_last"].get(c)
            break

    rule_commentary = generate_commentary(
        signal=signal,
        symbol=symbol,
        asset_type=asset_type,
        price=quote.get("price"),
        change_pct=quote.get("change_pct"),
        extra_context={"rsi": rsi_val},
    )

    if not use_gemini:
        return rule_commentary

    # AI ile zenginleştir (Groq varsa önce Groq, yoksa Gemini)
    try:
        from core.ai_engine import _call_best_ai
        from config.settings import GEMINI_API_KEY, GROQ_API_KEY
        if not GEMINI_API_KEY and not GROQ_API_KEY:
            return rule_commentary

        price_str = f"{quote.get('price', 'N/A')}"
        change_str = f"{quote.get('change_pct', 0):+.2f}%"
        reasons_str = ", ".join(signal.get("reasons", ["Veri yok"]))

        prompt = (
            f"Sen deneyimli bir Türk finansal analistsin. "
            f"Aşağıdaki teknik verileri kısa (3-4 cümle), profesyonel ve Türkçe olarak yorumla:\n\n"
            f"Varlık: {symbol} ({asset_type})\n"
            f"Fiyat: {price_str}, Günlük: {change_str}\n"
            f"Teknik sinyal: {signal.get('signal', 'NÖTR')} (Skor: {signal.get('score', 0)})\n"
            f"Aktif göstergeler: {reasons_str}\n\n"
            f"Yorumunu yatırım tavsiyesi vermeden, sadece teknik bulgulara dayandır. "
            f"Markdown formatı kullan. Kısa tut."
        )

        ai_text = _call_best_ai(prompt, max_tokens=400)
        if ai_text and not ai_text.startswith("⚠️") and len(ai_text) > 50:
            return rule_commentary + "\n\n---\n#### 🧠 AI Teknik Analizi\n" + ai_text
        return rule_commentary
    except Exception:
        return rule_commentary
