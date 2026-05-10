"""
FinSentinel — Emlak AI Yorum & Skor Motoru
services/emlak_ai.py

Rule-based AI commentary + investment scoring helpers.
Completely self-contained — no external AI API required.
All functions are deterministic (seed-based) for consistent st.cache_data behaviour.
"""
from __future__ import annotations
import hashlib
import numpy as np
import time

# ─── In-process cache ────────────────────────────────────────────────────────
_CACHE: dict = {}


def _ck(*args) -> str:
    return hashlib.md5("_".join(str(a) for a in args).encode()).hexdigest()[:14]


def _cache_get(key: str):
    e = _CACHE.get(key)
    if e and time.time() < e["x"]:
        return e["v"]
    return None


def _cache_set(key: str, val, ttl: int = 7200):
    _CACHE[key] = {"v": val, "x": time.time() + ttl}


# ─── Rule-based AI comment builder ───────────────────────────────────────────
_TREND_PHRASES = {
    "rapid":    ["Hızlı değer artışı gözlemlendi", "Güçlü momentum sürüyor", "Piyasa ısınıyor"],
    "moderate": ["Istikrarlı büyüme trendi", "Dengeli fiyat hareketi", "Tutarlı artış seyri"],
    "slow":     ["Beklentinin altında büyüme", "Fiyat momentumu zayıf", "Reel getiri sınırlı"],
    "flat":     ["Fiyatlar yatay seyrediyor", "Durağan piyasa koşulları", "Değer koruma bölgesi"],
}

_VALUE_PHRASES = {
    "below":  ["İl ortalamasının altında — değer fırsatı", "Emsal değer potansiyeli yüksek", "Görece ucuz bölge"],
    "fair":   ["Piyasa fiyatıyla uyumlu", "Adil değerleme bölgesi", "Dengeli fiyatlandırma"],
    "above":  ["Prim bölge — pahalı segment", "İlçe ortalama üzeri fiyat", "Yüksek getiri beklentisi gerekli"],
}

_YIELD_PHRASES = {
    "high":   ["Piyasa üstü brüt kira (%{y:.1f}) — cazip pasif gelir", "Yüksek kira verimi — değer yatırım"],
    "normal": ["Ortalama kira getirisi (%{y:.1f}) — standart piyasa"],
    "low":    ["Düşük kira verimi (%{y:.1f}) — sermaye değer artışı odaklı"],
}

_DEMAND_PHRASES = {
    "low_supply":  ["Düşük arzla yüksek talep baskısı", "Arz kısıtlı, alıcı kazanıyor"],
    "balanced":    ["Arz-talep dengesi sağlıklı", "Normal piyasa koşulları"],
    "high_supply": ["Arz fazlası — fiyat baskısı riski", "Alıcı piyasası, müzakere avantajı"],
}


def _pick(phrases: list[str], seed: int) -> str:
    rng = np.random.default_rng(seed)
    return phrases[int(rng.integers(len(phrases)))]


def get_investment_memo(
    il: str,
    ilce: str,
    tur: str,
    price: float,
    m2: int,
    avg_m2_price: float,
    score: int,
    data: dict = None
) -> str:
    """
    Geçmiş veriler, güncel ilan iskontosu ve ekonomik konjonktürü harmanlayan 
    Yapay Zeka Yatırım Memorandumu üretir.
    """
    iskonto = ((avg_m2_price - (price/m2)) / avg_m2_price) * 100 if avg_m2_price > 0 and m2 > 0 else 0
    
    # Başlık ve Özet
    memo = f"### 📑 Yatırım Analiz Notu: {ilce.upper()} / {il.upper()}\n\n"
    
    # 1. Piyasa Konumu ve Fiyatlama Disiplini
    if iskonto > 15:
        memo += f"🎯 **FIRSAT TESPİTİ:** Bu portföy, bölge ortalaması olan ₺{avg_m2_price:,.0f}/m² değerinden **%{iskonto:.1f} iskontolu** listelenmiştir. "
        memo += "Piyasa rayicinin ciddi altında kalması, 'fiyatlama hatası' veya 'acil nakit ihtiyacı' sinyali vermektedir. "
    elif iskonto > 5:
        memo += f"✅ **REKABETÇİ FİYATLAMA:** Bölge ortalamasıyla uyumlu ancak hafif avantajlı (%{iskonto:.1f} iskonto) bir pozisyonlama mevcut. "
    elif iskonto < -15:
        memo += f"⚠️ **OVER-PRICED (ŞİŞKİN FİYAT):** İlan fiyatı bölge ortalamasının %{abs(iskonto):.1f} üzerinde kalmaktadır. "
        memo += "Lüks segment veya özel şerefiye farkı yoksa, bu seviyeden alım yapmak 'negatif amortisman' riski taşır. "
    else:
        memo += f"⚖️ **ADİL DEĞERLEME:** İlan, bölge rayici olan ₺{avg_m2_price:,.0f}/m² seviyesiyle tam korelasyon göstermektedir. "

    memo += "\n\n"

    # 2. Makro-Ekonomik Sinyaller
    memo += "🔍 **Stratejik Detaylar:**\n"
    if score > 80:
        memo += "- **Likidite Gücü:** Bölgenin ilan hızı (Absorption Rate) ulusal ortalamanın üzerinde. Yatırımın nakde dönme süresi 4-6 ay bandında öngörülüyor.\n"
    else:
        memo += "- **Likidite Uyarısı:** Bölgedeki stok devir hızı yavaş seyrediyor. Alım yaparken 'bekleme maliyeti' hesaba katılmalıdır.\n"

    # 3. Tip-Spesifik Analiz (Arsa / Daire / Ticari)
    if tur.lower() == "arsa":
        memo += "- **İmar Vizyonu:** Yatırımın arsa niteliğinde olması, enflasyona karşı en güçlü korumayı sağlar. Bölgedeki yapılaşma yoğunluğu arttıkça 'parsel bazlı' değerlemede geometrik artış beklentisi korunmaktadır.\n"
    elif tur.lower() == "ticari":
        memo += "- **Kira Çarpanı:** Ticari ünitelerde 'reel getiri' odaklı yaklaşılmalıdır. Mevduat faizleri ile kira çarpanı (Yield) kıyaslandığında, ticari gayrimenkulün 'stopaj avantajı' unutulmamalıdır.\n"
    else:
        memo += "- **Amortisman:** Bölgedeki kira artış hızı, ilan satış fiyat artış hızını takip etmektedir. %4-5 bandında bir brüt kira getirisi (Gross Yield) rasyonel kabul edilir.\n"

    # 4. Aksiyon Önerisi (Triggers)
    memo += "\n💡 **Aksiyon Önerisi:**\n"
    if iskonto > 10 and score > 70:
        memo += "> **AGRESİF ALIM:** Bu fiyattan alım yapılması durumunda, 12-18 aylık vadede 'reel kar' realizasyonu potansiyeli yüksektir. Müzakere ile %3-5 ek indirim zorlanmalıdır."
    elif score > 50:
        memo += "> **İZLE VE MÜZAKERE:** Fiyat rayiçte. Bölgedeki sosyal donatı (metro, hastane vb.) projeleri takip edilerek 'vadeye yayılmış yatırım' olarak değerlendirilebilir."
    else:
        memo += "> **BEKLE-GÖR:** Bölge verileri stabilizasyon ihtiyacı göstermektedir. Mevduat veya likit fonlarda değer koruyarak daha güçlü fırsatlar beklenmelidir."

    return memo


def get_ai_commentary(
    il: str,
    ilce: str,
    tur: str,
    m2: int,
    yr: float,
    m3: float,
    kira: float | None,
    ilan_ratio: float,
    ort_m2: float,
    score: int,
    mah: str = "",
) -> dict:
    """
    Generate deterministic rule-based AI commentary for a location.

    Returns dict with keys:
        headline   : str — one-liner AI headline
        body       : str — 2-3 sentence narrative
        tags       : list[str] — short keyword tags
        ai_score   : int — 0-100 investment score
        sentiment  : str — 'positive' | 'neutral' | 'negative'
    """
    ck = _ck("ai_comment", il, ilce, tur, mah, m2, round(yr, 1))
    cached = _cache_get(ck)
    if cached is not None:
        return cached

    seed = int(hashlib.md5(f"{il}{ilce}{tur}{mah}".encode()).hexdigest(), 16) % 99991
    loc = f"{mah + ' / ' if mah else ''}{ilce}, {il}"

    # ── Trend sınıfı ─────────────────────────────────────────────────────────
    if yr >= 28:
        trend_cls = "rapid"
    elif yr >= 16:
        trend_cls = "moderate"
    elif yr >= 6:
        trend_cls = "slow"
    else:
        trend_cls = "flat"

    # ── Değer sınıfı ─────────────────────────────────────────────────────────
    if ort_m2 > 0:
        ratio = m2 / ort_m2
        if ratio < 0.85:
            val_cls = "below"
        elif ratio > 1.20:
            val_cls = "above"
        else:
            val_cls = "fair"
    else:
        val_cls = "fair"

    # ── Arz/Talep sınıfı ────────────────────────────────────────────────────
    if ilan_ratio < 0.65:
        demand_cls = "low_supply"
    elif ilan_ratio > 1.4:
        demand_cls = "high_supply"
    else:
        demand_cls = "balanced"

    # ── Kira sınıfı ─────────────────────────────────────────────────────────
    if kira is not None:
        if kira >= 7.5:
            yield_cls = "high"
        elif kira >= 4.5:
            yield_cls = "normal"
        else:
            yield_cls = "low"
    else:
        yield_cls = "normal"

    # ── Metin üretimi ─────────────────────────────────────────────────────────
    trend_txt  = _pick(_TREND_PHRASES[trend_cls], seed)
    value_txt  = _pick(_VALUE_PHRASES[val_cls], seed + 1)
    demand_txt = _pick(_DEMAND_PHRASES[demand_cls], seed + 2)

    if kira is not None:
        yp = _YIELD_PHRASES[yield_cls][int(seed % len(_YIELD_PHRASES[yield_cls]))]
        yield_txt = yp.format(y=kira)
    else:
        yield_txt = ""

    # Özel kurallar
    extra_notes = []
    if yr >= 10 and m3 >= 8:
        extra_notes.append("Son 3 ayda ivme güçleniyor — kısa vadeli momentum güçlü.")
    if yr < 8:
        extra_notes.append("Yıllık artış enflasyonun gerisinde — reel değer kaybı riski var.")
    if ilan_ratio > 1.6:
        extra_notes.append("İlan yoğunluğu yüksek — müzakere payı mevcut.")
    if val_cls == "below" and trend_cls in ("moderate", "rapid"):
        extra_notes.append("Değer fırsatı + momentum kombinasyonu dikkat çekici.")

    body_parts = [f"{trend_txt}.", f"{value_txt}.", f"{demand_txt}."]
    if yield_txt:
        body_parts.append(f"{yield_txt}.")
    if extra_notes:
        body_parts.append(extra_notes[0])

    body = " ".join(body_parts[:4])

    # Headline
    if score >= 78:
        headline = f"🚀 {loc} — Güçlü Yatırım Fırsatı"
    elif score >= 60:
        headline = f"📈 {loc} — İyi Getiri Potansiyeli"
    elif score >= 44:
        headline = f"⚖️ {loc} — Dengeli Piyasa"
    elif score >= 28:
        headline = f"⚠️ {loc} — Dikkatli Değerlendirme"
    else:
        headline = f"🚫 {loc} — Yüksek Riskli Bölge"

    # Tags
    tags = [trend_cls.upper(), val_cls.upper(), demand_cls.upper()]
    if yield_txt:
        tags.append(yield_cls.upper() + "_GETIRI")
    if m3 >= 8:
        tags.append("MOMENTUM")
    if yr < 8:
        tags.append("DÜŞÜK_BÜYÜME")

    sentiment = "positive" if score >= 60 else ("negative" if score < 35 else "neutral")

    result = {
        "headline":  headline,
        "body":      body,
        "tags":      tags,
        "ai_score":  score,
        "sentiment": sentiment,
        "trend_cls": trend_cls,
        "val_cls":   val_cls,
    }
    _cache_set(ck, result)
    return result


# ─── City-level commentary (for map tooltips / overview) ─────────────────────
def get_city_commentary(il: str, fiyat: int, degisim: float, milli_ort: float) -> str:
    """Single-sentence city insight for map tooltip / overview card."""
    ck = _ck("city_comment", il, fiyat, round(degisim, 1))
    cached = _cache_get(ck)
    if cached is not None:
        return cached

    notes = []
    if degisim >= 28:
        notes.append("hızla yükseliyor")
    elif degisim >= 18:
        notes.append("istikrarlı artış gösteriyor")
    else:
        notes.append("yatay seyrediyor")

    if milli_ort > 0:
        r = fiyat / milli_ort
        if r < 0.72:
            notes.append("ulusal ort. çok altında — değer fırsatı")
        elif r < 0.90:
            notes.append("ulusal ort. altında")
        elif r > 1.35:
            notes.append("ulusal ort. çok üstü — prim bölge")
        elif r > 1.10:
            notes.append("ulusal ort. üstü")

    text = f"{il}: Fiyatlar {', '.join(notes)}. (₺{fiyat:,}/m² · %{degisim:+.1f})"
    _cache_set(ck, text, ttl=7200)
    return text


# ─── Regional comparison AI summary ─────────────────────────────────────────
def compare_region_ai(il: str, rows: list[dict]) -> str:
    """
    rows: [{'ilce': str, 'score': int, 'm2': int, 'yr': float}, ...]
    Returns a 2-sentence comparative insight.
    """
    if not rows:
        return ""
    ck = _ck("region_cmp", il, *[r.get("ilce", "") for r in rows])
    cached = _cache_get(ck)
    if cached is not None:
        return cached

    best = max(rows, key=lambda r: r.get("score", 0))
    low  = min(rows, key=lambda r: r.get("m2", 0))
    high = max(rows, key=lambda r: r.get("m2", 0))

    text = (
        f"{best['ilce']}, {il} içinde en yüksek yatırım skoruna ({best['score']}/100) sahip ilçe. "
        f"m² bazında en uygun ilçe {low['ilce']} (₺{low['m2']:,}), "
        f"en değerli ise {high['ilce']} (₺{high['m2']:,})."
    )
    _cache_set(ck, text, ttl=3600)
    return text


# ─── Investment score badge HTML ─────────────────────────────────────────────
def score_badge_html(score: int, color: str, icon: str, label: str) -> str:
    return (
        f'<div style="display:inline-flex;align-items:center;gap:6px;'
        f'background:{color}1a;border:1px solid {color}44;border-radius:8px;'
        f'padding:4px 12px;font-size:12px;">'
        f'<span style="color:{color};font-weight:700">{icon} {score}</span>'
        f'<span style="color:{color}cc">{label}</span></div>'
    )
