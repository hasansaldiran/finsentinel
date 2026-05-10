"""
FinSentinel — Bütünleşik Karar Motoru
core/decision_engine.py

4 pillar'ı birleştirir ve strateji moduna göre ağırlıklandırır:
  P1 — Değerleme  (F/K, PD/DD, FD/FAVÖK, Net Borç/FAVÖK)
  P2 — Büyüme & Kârlılık (ROE, Net Marj, Satış Büyümesi)
  P3 — Teknik (mevcut rule_engine skoru + hacim)
  P4 — Hikaye & Makro (sektörel güç, temettü, KAP aktivitesi)

Strateji Modları:
  "trader"   → Teknik + kısa vade ağırlıklı
  "temettü"  → Temel + ROE + temettü verimi ağırlıklı
  "dengeli"  → Eşit ağırlık
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional
import numpy as np
import pandas as pd

# ─────────────────────────────────────────────────────────────────────────────
# Strateji ağırlıkları  (P1, P2, P3, P4) — toplam 1.0
# ─────────────────────────────────────────────────────────────────────────────
STRATEGY_WEIGHTS: dict[str, tuple[float, float, float, float]] = {
    "trader":  (0.15, 0.15, 0.50, 0.20),
    "dengeli": (0.28, 0.27, 0.30, 0.15),
    "temettü": (0.30, 0.35, 0.15, 0.20),
}

# ─────────────────────────────────────────────────────────────────────────────
# Sektörel F/K ve FD/FAVÖK referans değerleri
# ─────────────────────────────────────────────────────────────────────────────
SECTOR_PE: dict[str, float] = {
    "Bankacılık": 7.0,  "Holding": 10.0, "Havacılık": 12.0,
    "Enerji": 9.0,      "Teknoloji": 20.0, "Otomotiv": 8.0,
    "GYO": 8.0,         "Perakende": 14.0, "Gıda": 11.0,
    "Metal": 7.0,       "Çimento": 8.0,    "Kimya": 9.0,
    "Sigorta": 9.0,     "Tekstil": 8.0,    "Elektronik": 11.0,
    "İlaç": 13.0,       "Sağlık": 14.0,    "Lojistik": 10.0,
    "Madencilik": 8.0,  "Sanayi": 9.0,     "Finans": 8.0,
}

SECTOR_EVEB: dict[str, float] = {
    "Bankacılık": 6.0,  "Holding": 8.0,  "Havacılık": 7.0,
    "Enerji": 6.0,      "Teknoloji": 15.0, "Otomotiv": 5.0,
    "GYO": 10.0,        "Perakende": 8.0,  "Gıda": 7.0,
    "Metal": 5.0,       "Çimento": 6.0,    "Kimya": 7.0,
    "Sigorta": 7.0,     "Tekstil": 5.0,    "Elektronik": 8.0,
    "İlaç": 10.0,       "Sağlık": 10.0,    "Lojistik": 7.0,
    "Madencilik": 5.0,  "Sanayi": 6.0,     "Finans": 7.0,
}


# ─────────────────────────────────────────────────────────────────────────────
# Veri sınıfları
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class PillarScore:
    name:    str
    score:   float          # 0-100
    weight:  float          # strateji ağırlığı
    signals: list[dict]     # {"text": str, "positive": bool}
    na_count: int = 0       # eksik veri sayısı

    @property
    def weighted(self) -> float:
        return self.score * self.weight


@dataclass
class DecisionResult:
    ticker:   str
    strategy: str
    p1:       PillarScore   # Değerleme
    p2:       PillarScore   # Büyüme & Kârlılık
    p3:       PillarScore   # Teknik
    p4:       PillarScore   # Hikaye & Makro
    total:    float         # 0-100
    verdict:  str           # "GÜÇLÜ AL" | "AL" | "NÖTR" | "SAT" | "GÜÇLÜ SAT"
    color:    str
    summary:  str
    data_completeness: float  # 0-1

    @property
    def pillars(self) -> list[PillarScore]:
        return [self.p1, self.p2, self.p3, self.p4]


# ─────────────────────────────────────────────────────────────────────────────
# Yardımcılar
# ─────────────────────────────────────────────────────────────────────────────

def _safe(v, default=None) -> Optional[float]:
    try:
        f = float(v)
        return None if (np.isnan(f) or np.isinf(f) or f == 0) else f
    except Exception:
        return default


def _score_ratio(value: Optional[float], good: float, bad: float,
                 lower_is_better: bool = True) -> Optional[float]:
    """
    Bir oranı 0-100 arasına normalize eder.
    lower_is_better=True → değer küçüldükçe skor artar (F/K, borç gibi)
    lower_is_better=False → değer büyüdükçe skor artar (ROE, marj gibi)
    """
    if value is None:
        return None
    if lower_is_better:
        # bad değerinde 0, good değerinde 100
        if bad == good:
            return 50.0
        raw = (bad - value) / (bad - good) * 100
    else:
        if bad == good:
            return 50.0
        raw = (value - bad) / (good - bad) * 100
    return float(np.clip(raw, 0, 100))


def _verdict(score: float) -> tuple[str, str, str]:
    """(etiket, renk, emoji_etiket)"""
    if score >= 72:  return "GÜÇLÜ AL",  "#10b981", "🚀 GÜÇLÜ AL"
    if score >= 58:  return "AL",        "#34d399", "📈 AL"
    if score >= 45:  return "HAFIF AL",  "#fbbf24", "🟢 HAFIF AL"
    if score >= 35:  return "NÖTR",      "#94a3b8", "⚪ NÖTR"
    if score >= 25:  return "HAFIF SAT", "#f97316", "🔴 HAFIF SAT"
    if score >= 15:  return "SAT",       "#ef4444", "📉 SAT"
    return              "GÜÇLÜ SAT",     "#dc2626", "🛑 GÜÇLÜ SAT"


# ─────────────────────────────────────────────────────────────────────────────
# Pillar Hesaplayıcılar
# ─────────────────────────────────────────────────────────────────────────────

def _p1_valuation(info: dict, sector: str) -> PillarScore:
    """P1 — Değerleme: F/K, PD/DD, FD/FAVÖK, Net Borç/FAVÖK"""
    signals: list[dict] = []
    scores:  list[float] = []
    na = 0

    ref_pe   = SECTOR_PE.get(sector, 10.0)
    ref_eveb = SECTOR_EVEB.get(sector, 8.0)

    # F/K
    pe = _safe(info.get("trailingPE") or info.get("forwardPE"))
    if pe and pe > 0:
        s = _score_ratio(pe, good=ref_pe * 0.6, bad=ref_pe * 2.0, lower_is_better=True)
        if s is not None:
            scores.append(s)
            if pe < ref_pe * 0.7:
                signals.append({"text": f"F/K {pe:.1f}x — sektör ortalamasının altında (ucuz)", "positive": True})
            elif pe > ref_pe * 1.5:
                signals.append({"text": f"F/K {pe:.1f}x — sektör ortalamasının çok üstünde (pahalı)", "positive": False})
            else:
                signals.append({"text": f"F/K {pe:.1f}x — sektör ortalamasına yakın", "positive": None})
    else:
        na += 1

    # PD/DD
    pb = _safe(info.get("priceToBook"))
    if pb is not None and pb > 0:
        s = _score_ratio(pb, good=0.8, bad=4.0, lower_is_better=True)
        if s is not None:
            scores.append(s)
            if pb < 1.0:
                signals.append({"text": f"PD/DD {pb:.2f}x — defter değerinin altında (iskontolu)", "positive": True})
            elif pb < 2.0:
                signals.append({"text": f"PD/DD {pb:.2f}x — makul bölge", "positive": None})
            else:
                signals.append({"text": f"PD/DD {pb:.2f}x — defter değerinin çok üstünde", "positive": False})
    else:
        na += 1

    # FD/FAVÖK (EV/EBITDA)
    eveb = _safe(info.get("enterpriseToEbitda"))
    if eveb and eveb > 0:
        s = _score_ratio(eveb, good=ref_eveb * 0.6, bad=ref_eveb * 2.5, lower_is_better=True)
        if s is not None:
            scores.append(s)
            if eveb < ref_eveb * 0.7:
                signals.append({"text": f"FD/FAVÖK {eveb:.1f}x — operasyonel değerleme ucuz", "positive": True})
            elif eveb > ref_eveb * 1.8:
                signals.append({"text": f"FD/FAVÖK {eveb:.1f}x — operasyonel değerleme yüksek", "positive": False})
            else:
                signals.append({"text": f"FD/FAVÖK {eveb:.1f}x — makul bölge", "positive": None})
    else:
        na += 1

    # Net Borç / FAVÖK  (debt_to_equity proxy olarak)
    de = _safe(info.get("debtToEquity"))
    if de is not None and de >= 0:
        # D/E 50 = düşük borç, 300+ = tehlikeli
        s = _score_ratio(de, good=30, bad=300, lower_is_better=True)
        if s is not None:
            scores.append(s)
            if de < 50:
                signals.append({"text": f"D/E {de:.0f}% — borçluluk düşük, finansal sağlık iyi", "positive": True})
            elif de < 150:
                signals.append({"text": f"D/E {de:.0f}% — borçluluk yönetilebilir", "positive": None})
            else:
                signals.append({"text": f"D/E {de:.0f}% — yüksek borçluluk, faiz riski var", "positive": False})
    else:
        na += 1

    final = float(np.mean(scores)) if scores else 40.0
    return PillarScore("Değerleme", final, 0.0, signals, na)


def _p2_growth(info: dict) -> PillarScore:
    """P2 — Büyüme & Kârlılık: ROE, Net Marj, Satış Büyümesi, Brüt Marj"""
    signals: list[dict] = []
    scores:  list[float] = []
    na = 0

    # ROE
    roe = _safe(info.get("returnOnEquity"))
    if roe is not None:
        roe_pct = roe * 100
        s = _score_ratio(roe_pct, good=25.0, bad=-5.0, lower_is_better=False)
        if s is not None:
            scores.append(s)
            if roe_pct >= 20:
                signals.append({"text": f"ROE %{roe_pct:.1f} — özsermaye verimliliği mükemmel", "positive": True})
            elif roe_pct >= 10:
                signals.append({"text": f"ROE %{roe_pct:.1f} — yeterli kârlılık", "positive": None})
            else:
                signals.append({"text": f"ROE %{roe_pct:.1f} — özsermaye verimliliği zayıf", "positive": False})
    else:
        na += 1

    # Net Kâr Marjı
    npm = _safe(info.get("profitMargins"))
    if npm is not None:
        npm_pct = npm * 100
        s = _score_ratio(npm_pct, good=15.0, bad=-2.0, lower_is_better=False)
        if s is not None:
            scores.append(s)
            if npm_pct >= 12:
                signals.append({"text": f"Net Marj %{npm_pct:.1f} — satışların büyük bölümü cebe kalıyor", "positive": True})
            elif npm_pct >= 5:
                signals.append({"text": f"Net Marj %{npm_pct:.1f} — makul marj", "positive": None})
            else:
                signals.append({"text": f"Net Marj %{npm_pct:.1f} — ince marj, baskıya duyarlı", "positive": False})
    else:
        na += 1

    # Satış Büyümesi (Gelir Artışı)
    rev_growth = _safe(info.get("revenueGrowth"))
    if rev_growth is not None:
        rg_pct = rev_growth * 100
        s = _score_ratio(rg_pct, good=20.0, bad=-10.0, lower_is_better=False)
        if s is not None:
            scores.append(s)
            if rg_pct >= 15:
                signals.append({"text": f"Satış Büyümesi %{rg_pct:.1f} — güçlü gelir artışı, pazar payı kazanıyor", "positive": True})
            elif rg_pct >= 0:
                signals.append({"text": f"Satış Büyümesi %{rg_pct:.1f} — ılımlı büyüme", "positive": None})
            else:
                signals.append({"text": f"Satış Büyümesi %{rg_pct:.1f} — gelir küçülüyor, dikkat", "positive": False})
    else:
        na += 1

    # EPS Büyümesi
    eps_g = _safe(info.get("earningsGrowth"))
    if eps_g is not None:
        eg_pct = eps_g * 100
        s = _score_ratio(eg_pct, good=25.0, bad=-15.0, lower_is_better=False)
        if s is not None:
            scores.append(s)
            if eg_pct >= 20:
                signals.append({"text": f"EPS Büyümesi %{eg_pct:.1f} — kâr artışı güçlü", "positive": True})
            elif eg_pct >= 0:
                signals.append({"text": f"EPS Büyümesi %{eg_pct:.1f} — kâr artıyor", "positive": None})
            else:
                signals.append({"text": f"EPS Büyümesi %{eg_pct:.1f} — kâr azalıyor", "positive": False})
    else:
        na += 1

    final = float(np.mean(scores)) if scores else 40.0
    return PillarScore("Büyüme & Kârlılık", final, 0.0, signals, na)


def _p3_technical(tech_score: int, hist_df: pd.DataFrame) -> PillarScore:
    """P3 — Teknik: rule_engine skoru + hacim doğrulaması"""
    signals: list[dict] = []
    na = 0

    # rule_engine skoru (-5/+5) → 0-100
    tech_100 = (tech_score + 5) / 10 * 100

    label_map = {
        5: ("Tüm teknik göstergeler güçlü AL sinyali veriyor", True),
        4: ("Çoğu gösterge yükseliş yönünde", True),
        3: ("Teknik görünüm pozitif", True),
        2: ("Hafif yükseliş eğilimi var", True),
        1: ("Sinyaller karışık, hafif pozitif", None),
        0: ("Teknik olarak nötr, net yön yok", None),
        -1: ("Hafif negatif eğilim", None),
        -2: ("Teknik baskı artıyor", False),
        -3: ("Trend aşağı yönlü, satış baskısı var", False),
        -4: ("Güçlü düşüş baskısı", False),
        -5: ("Tüm teknik göstergeler SAT sinyali veriyor", False),
    }
    txt, pos = label_map.get(tech_score, ("Teknik sinyal hesaplanamadı", None))
    signals.append({"text": f"Teknik Puan {tech_score:+d}/5 — {txt}", "positive": pos})

    # Hacim doğrulaması
    if not hist_df.empty and "Volume" in hist_df.columns and "Close" in hist_df.columns:
        try:
            recent   = hist_df.tail(5)
            avg_vol  = hist_df["Volume"].rolling(20).mean().iloc[-1]
            last_vol = hist_df["Volume"].iloc[-1]
            price_up = hist_df["Close"].iloc[-1] > hist_df["Close"].iloc[-6]
            rel_vol  = last_vol / avg_vol if avg_vol > 0 else 1.0

            if price_up and rel_vol > 1.3:
                signals.append({"text": f"Hacim {rel_vol:.1f}x ortalamanın üstünde & fiyat yükseliyor — teyit var", "positive": True})
                tech_100 = min(100, tech_100 + 8)
            elif not price_up and rel_vol > 1.3:
                signals.append({"text": f"Hacim {rel_vol:.1f}x yüksek ama fiyat düşüyor — satış baskısı güçlü", "positive": False})
                tech_100 = max(0, tech_100 - 8)
            else:
                signals.append({"text": f"Hacim normal seviyelerde ({rel_vol:.1f}x)", "positive": None})
        except Exception:
            na += 1

        # 200 günlük SMA kontrolü
        try:
            if len(hist_df) >= 200:
                sma200 = hist_df["Close"].rolling(200).mean().iloc[-1]
                price  = hist_df["Close"].iloc[-1]
                if price > sma200:
                    signals.append({"text": f"Fiyat 200G SMA üstünde ({price:.2f} > {sma200:.2f}) — uzun vadeli trend pozitif", "positive": True})
                else:
                    signals.append({"text": f"Fiyat 200G SMA altında ({price:.2f} < {sma200:.2f}) — uzun vadeli trend negatif", "positive": False})
                    tech_100 = max(0, tech_100 - 10)
        except Exception:
            na += 1
    else:
        na += 2

    return PillarScore("Teknik", float(np.clip(tech_100, 0, 100)), 0.0, signals, na)


def _p4_story(info: dict, strategy: str) -> PillarScore:
    """P4 — Hikaye & Makro: Temettü, Analist, Beta, Sektör"""
    signals: list[dict] = []
    scores:  list[float] = []
    na = 0

    # Temettü Verimi
    div_yield = _safe(info.get("dividendYield") or info.get("trailingAnnualDividendYield"))
    if div_yield is not None and div_yield > 0:
        dy_pct = div_yield * 100
        # Temettü stratejisinde daha fazla ağırlık
        weight = 1.5 if strategy == "temettü" else 1.0
        s = _score_ratio(dy_pct, good=5.0, bad=0.0, lower_is_better=False)
        if s is not None:
            scores.extend([s] * int(weight + 0.5))
            if dy_pct >= 4:
                signals.append({"text": f"Temettü Verimi %{dy_pct:.2f} — cazip pasif gelir", "positive": True})
            elif dy_pct >= 1.5:
                signals.append({"text": f"Temettü Verimi %{dy_pct:.2f} — makul temettü", "positive": None})
    else:
        if strategy == "temettü":
            signals.append({"text": "Temettü yok/veri eksik — temettü stratejisi için olumsuz", "positive": False})
            scores.append(20.0)
        na += 1

    # Analist Tavsiyesi
    rec = (info.get("recommendationKey") or "").lower()
    rec_map = {
        "strong_buy": (90, "Analist konsensüsü: Güçlü AL", True),
        "buy":        (75, "Analist konsensüsü: AL", True),
        "hold":       (50, "Analist konsensüsü: TUT", None),
        "underperform":(30,"Analist konsensüsü: DÜŞÜK PERFORMANS", False),
        "sell":       (15, "Analist konsensüsü: SAT", False),
        "strong_sell":(5,  "Analist konsensüsü: Güçlü SAT", False),
    }
    if rec in rec_map:
        s, txt, pos = rec_map[rec]
        scores.append(float(s))
        signals.append({"text": txt, "positive": pos})
    else:
        na += 1

    # Beta (volatilite riski)
    beta = _safe(info.get("beta"))
    if beta is not None:
        if beta < 0.8:
            signals.append({"text": f"Beta {beta:.2f} — düşük volatilite, defansif hisse", "positive": True if strategy == "temettü" else None})
            scores.append(65.0)
        elif beta < 1.3:
            signals.append({"text": f"Beta {beta:.2f} — piyasayla paralel hareket", "positive": None})
            scores.append(55.0)
        else:
            signals.append({"text": f"Beta {beta:.2f} — yüksek volatilite, piyasadan sert hareket eder", "positive": True if strategy == "trader" else False})
            scores.append(40.0)
    else:
        na += 1

    # 52 Hafta Konumu
    high52 = _safe(info.get("fiftyTwoWeekHigh"))
    low52  = _safe(info.get("fiftyTwoWeekLow"))
    price  = _safe(info.get("currentPrice") or info.get("regularMarketPrice"))
    if all(v is not None for v in [high52, low52, price]) and high52 > low52:
        pos_pct = (price - low52) / (high52 - low52) * 100
        if pos_pct <= 25:
            signals.append({"text": f"52H Konum: %{pos_pct:.0f} — 52 hafta dibine yakın (potansiyel fırsat)", "positive": True})
            scores.append(70.0)
        elif pos_pct >= 80:
            signals.append({"text": f"52H Konum: %{pos_pct:.0f} — 52 hafta zirvesine yakın (dikkatli ol)", "positive": False})
            scores.append(35.0)
        else:
            signals.append({"text": f"52H Konum: %{pos_pct:.0f} — orta bölgede", "positive": None})
            scores.append(55.0)
    else:
        na += 1

    final = float(np.mean(scores)) if scores else 40.0
    return PillarScore("Hikaye & Makro", float(np.clip(final, 0, 100)), 0.0, signals, na)


# ─────────────────────────────────────────────────────────────────────────────
# Ana Fonksiyon
# ─────────────────────────────────────────────────────────────────────────────

def analyze(
    ticker:     str,
    info:       dict,
    hist_df:    pd.DataFrame,
    tech_score: int,
    sector:     str = "Diğer",
    strategy:   str = "dengeli",   # "trader" | "dengeli" | "temettü"
) -> DecisionResult:
    """
    Tüm pillar'ları hesaplar, strateji ağırlıklarıyla birleştirir
    ve nihai karar kartını döner.
    """
    w1, w2, w3, w4 = STRATEGY_WEIGHTS.get(strategy, STRATEGY_WEIGHTS["dengeli"])

    p1 = _p1_valuation(info, sector)
    p2 = _p2_growth(info)
    p3 = _p3_technical(tech_score, hist_df)
    p4 = _p4_story(info, strategy)

    p1.weight = w1
    p2.weight = w2
    p3.weight = w3
    p4.weight = w4

    total = p1.weighted + p2.weighted + p3.weighted + p4.weighted

    v_label, v_color, v_emoji = _verdict(total)

    # Özet metin üret
    pos_signals = [s["text"] for p in [p1, p2, p3, p4]
                   for s in p.signals if s["positive"] is True]
    neg_signals = [s["text"] for p in [p1, p2, p3, p4]
                   for s in p.signals if s["positive"] is False]

    strategy_label = {"trader": "Trader", "dengeli": "Dengeli", "temettü": "Temettü"}[strategy]
    summary_parts = [f"**{strategy_label} modu** ile analiz edildi."]
    if pos_signals:
        summary_parts.append(f"Güçlü yanlar: {'; '.join(pos_signals[:2])}.")
    if neg_signals:
        summary_parts.append(f"Riskler: {'; '.join(neg_signals[:2])}.")

    total_na = p1.na_count + p2.na_count + p3.na_count + p4.na_count
    total_fields = 16
    completeness = max(0.0, 1.0 - total_na / total_fields)

    return DecisionResult(
        ticker   = ticker.replace(".IS", "").upper(),
        strategy = strategy,
        p1 = p1, p2 = p2, p3 = p3, p4 = p4,
        total    = round(total, 1),
        verdict  = v_emoji,
        color    = v_color,
        summary  = " ".join(summary_parts),
        data_completeness = round(completeness, 2),
    )
