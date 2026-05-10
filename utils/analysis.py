"""
Kural tabanlı teknik analiz motoru.
Tüm çıktılar deterministik kurallara dayanır — rastgele metin yok.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from utils.indicators import ema, rsi, macd, bollinger


def analyze(df: pd.DataFrame) -> dict:
    """
    OHLCV DataFrame'i alır, yapılandırılmış teknik analiz sözlüğü döner.
    Minimum 30 satır gerekli.

    Dönen alanlar:
        overall       : "bullish" | "neutral" | "bearish"
        score         : int  (-6 … +6)
        trend         : str  (Türkçe etiket)
        trend_emoji   : str
        rsi_value     : float
        rsi_label     : str
        rsi_emoji     : str
        ma_label      : str
        ma_score      : int
        cross_signal  : str | None
        macd_label    : str
        vol_label     : str
        vol_emoji     : str
        bb_label      : str
        commentary    : str
    """
    if df is None or len(df) < 30:
        return _empty()

    close = df["Close"]
    n     = len(close)

    # ── İndikatörler ──────────────────────────────────────────────────────────
    e20   = ema(close, 20)
    e50   = ema(close, 50)
    e200  = ema(close, 200)
    rsi_s = rsi(close)
    ml, sl, hist = macd(close)
    bb_up, _, bb_lo = bollinger(close)

    # Son değerler
    price    = close.iloc[-1]
    v_rsi    = float(rsi_s.iloc[-1])
    v_e20    = float(e20.iloc[-1])
    v_e50    = float(e50.iloc[-1])
    v_e200   = float(e200.iloc[-1])
    v_hist   = float(hist.iloc[-1])
    v_hist_p = float(hist.iloc[-2]) if n >= 2 else 0.0
    v_bb_up  = float(bb_up.iloc[-1]) if not np.isnan(bb_up.iloc[-1]) else price
    v_bb_lo  = float(bb_lo.iloc[-1]) if not np.isnan(bb_lo.iloc[-1]) else price

    # ── RSI ───────────────────────────────────────────────────────────────────
    if   v_rsi >= 70: rsi_label, rsi_emoji = "Aşırı Alım",  "🔴"
    elif v_rsi <= 30: rsi_label, rsi_emoji = "Aşırı Satım", "🟢"
    else:             rsi_label, rsi_emoji = "Nötr",         "⚪"

    # ── MA Yapısı (ma_score: -3 … +3) ─────────────────────────────────────────
    if   price > v_e20 > v_e50 > v_e200: ma_label, ma_score = "Güçlü Yükseliş",  3
    elif price > v_e50 > v_e200:         ma_label, ma_score = "EMA50/200 Üstü",   2
    elif price > v_e200:                 ma_label, ma_score = "EMA200 Üstü",       1
    elif price < v_e20 < v_e50 < v_e200: ma_label, ma_score = "Güçlü Düşüş",    -3
    elif price < v_e50 < v_e200:         ma_label, ma_score = "EMA50/200 Altı",  -2
    elif price < v_e200:                 ma_label, ma_score = "EMA200 Altı",     -1
    else:                                ma_label, ma_score = "Karma",              0

    # ── Altın / Ölüm Kesişim (son 5 barda gerçekleştiyse) ────────────────────
    cross_signal: str | None = None
    if n >= 10:
        window     = min(5, n - 1)
        diff_now   = float(e50.iloc[-1])   - float(e200.iloc[-1])
        diff_prev  = float(e50.iloc[-(window + 1)]) - float(e200.iloc[-(window + 1)])
        if   diff_prev <= 0 < diff_now:  cross_signal = "Altın Kesişim"
        elif diff_prev >= 0 > diff_now:  cross_signal = "Ölüm Kesişimi"

    # ── MACD Sinyali ──────────────────────────────────────────────────────────
    if   v_hist > 0 and v_hist_p <= 0: macd_label = "Yükseliş Kesişimi"
    elif v_hist < 0 and v_hist_p >= 0: macd_label = "Düşüş Kesişimi"
    elif v_hist > 0:                   macd_label = "Pozitif Momentum"
    else:                              macd_label = "Negatif Momentum"

    # ── Toplam Puan → Trend Etiketi ───────────────────────────────────────────
    total = ma_score
    if   v_rsi > 55: total += 1
    elif v_rsi < 45: total -= 1
    if   v_hist > 0: total += 1
    elif v_hist < 0: total -= 1

    if   total >=  4: trend, trend_emoji, overall = "Güçlü Yükseliş", "🟢", "bullish"
    elif total >=  2: trend, trend_emoji, overall = "Yükseliş",        "🟡", "bullish"
    elif total <= -4: trend, trend_emoji, overall = "Güçlü Düşüş",    "🔴", "bearish"
    elif total <= -2: trend, trend_emoji, overall = "Düşüş",           "🔴", "bearish"
    else:             trend, trend_emoji, overall = "Yatay",            "⚪", "neutral"

    # ── Volatilite ────────────────────────────────────────────────────────────
    ret          = close.pct_change()
    recent_vol   = float(ret.tail(10).std())
    historic_vol = float(ret.std())
    if   recent_vol > historic_vol * 1.25: vol_label, vol_emoji = "Artan",  "⚠️"
    elif recent_vol < historic_vol * 0.75: vol_label, vol_emoji = "Azalan", "✅"
    else:                                  vol_label, vol_emoji = "Normal",  "➡️"

    # ── Bollinger Konumu ──────────────────────────────────────────────────────
    bb_range = v_bb_up - v_bb_lo
    bb_pos   = (price - v_bb_lo) / bb_range if bb_range > 0 else 0.5
    if   bb_pos > 0.90: bb_label = "Üst Banda Yakın"
    elif bb_pos < 0.10: bb_label = "Alt Banda Yakın"
    else:               bb_label = "Orta Aralık"

    commentary = _commentary(
        trend, v_rsi, rsi_label, ma_label, macd_label,
        cross_signal, bb_label, vol_label,
    )

    return {
        "overall":      overall,
        "score":        total,
        "trend":        trend,
        "trend_emoji":  trend_emoji,
        "rsi_value":    round(v_rsi, 1),
        "rsi_label":    rsi_label,
        "rsi_emoji":    rsi_emoji,
        "ma_label":     ma_label,
        "ma_score":     ma_score,
        "cross_signal": cross_signal,
        "macd_label":   macd_label,
        "vol_label":    vol_label,
        "vol_emoji":    vol_emoji,
        "bb_label":     bb_label,
        "commentary":   commentary,
    }


# ─────────────────────────────────────────────────────────────────────────────

def _commentary(
    trend: str, rsi_v: float, rsi_lbl: str, ma_lbl: str,
    macd_lbl: str, cross: str | None, bb_lbl: str, vol_lbl: str,
) -> str:
    parts: list[str] = []

    if   "Güçlü Yükseliş" in trend:
        parts.append("Fiyat tüm kısa-orta-uzun vadeli ortalamaların üzerinde; ana trend güçlü yükseliş yönünde.")
    elif "Yükseliş" in trend:
        parts.append("Fiyat orta vadeli hareketli ortalamaların üzerinde; yükseliş eğilimi devam ediyor.")
    elif "Güçlü Düşüş" in trend:
        parts.append("Fiyat tüm hareketli ortalamaların altında; güçlü satış baskısı mevcut.")
    elif "Düşüş" in trend:
        parts.append("Fiyat orta vadeli ortalamaların altında seyrediyor; düşüş baskısı baskın.")
    else:
        parts.append("Fiyat hareketli ortalamalar arasında sıkışmış; net bir trend yok.")

    if rsi_lbl == "Aşırı Alım":
        parts.append(f"RSI {rsi_v:.0f} ile aşırı alım bölgesinde — kısa vadeli düzeltme riski mevcut.")
    elif rsi_lbl == "Aşırı Satım":
        parts.append(f"RSI {rsi_v:.0f} ile aşırı satım bölgesinde — teknik toparlanma imkânı olabilir.")

    if   cross == "Altın Kesişim":  parts.append("EMA50/EMA200 altın kesişimi oluştu — orta vadeli yükseliş sinyali.")
    elif cross == "Ölüm Kesişimi":  parts.append("EMA50/EMA200 ölüm kesişimi oluştu — orta vadeli düşüş sinyali.")

    if   "Yükseliş Kesişimi" in macd_lbl: parts.append("MACD yükseliş kesişimi yapıyor — momentum pozitife dönüyor.")
    elif "Düşüş Kesişimi"    in macd_lbl: parts.append("MACD düşüş kesişimi yapıyor — momentum negatife dönüyor.")

    if   "Üst Banda" in bb_lbl: parts.append("Fiyat Bollinger üst bandına yaklaşmış; kısa vadeli ivme kaybı olabilir.")
    elif "Alt Banda" in bb_lbl: parts.append("Fiyat Bollinger alt bandında destek arıyor.")

    if vol_lbl == "Artan":
        parts.append("Volatilite son ortalamanın üzerinde — pozisyon yönetimine dikkat.")

    return " ".join(parts) or "Yeterli veri yok."


def _empty() -> dict:
    return {
        "overall": "neutral", "score": 0,
        "trend": "Yetersiz Veri", "trend_emoji": "⚪",
        "rsi_value": float("nan"), "rsi_label": "—", "rsi_emoji": "⚪",
        "ma_label": "—", "ma_score": 0,
        "cross_signal": None,
        "macd_label": "—",
        "vol_label": "—", "vol_emoji": "➡️",
        "bb_label": "—",
        "commentary": "Analiz için minimum 30 çubuk verisi gerekli.",
    }
