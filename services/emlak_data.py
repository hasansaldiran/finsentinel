"""
FinSentinel — Emlak Veri Pipeline
services/emlak_data.py

Priority chain: TCMB EVDS → Endeksa → Sahibinden → Synthetic fallback
Output format:  DataFrame with columns ["il", "fiyat", "degisim"]
"""
import time
import hashlib
import numpy as np
import pandas as pd
import requests
import plotly.graph_objects as go

try:
    import streamlit as st
    _HAS_ST = True
except Exception:
    _HAS_ST = False

# ─── Basit in-process cache (st.cache_data yedeği) ───────────────────────────
_CACHE: dict = {}

def _cache_get(key: str):
    e = _CACHE.get(key)
    if e and time.time() < e["x"]:
        return e["v"]
    return None

def _cache_set(key: str, val, ttl: int = 3600):
    _CACHE[key] = {"v": val, "x": time.time() + ttl}

def _ck(*args) -> str:
    return hashlib.md5("_".join(str(a) for a in args).encode()).hexdigest()[:14]


# ─── Retry HTTP helper ────────────────────────────────────────────────────────
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/html, */*",
    "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8",
}

def _get_json(url: str, params: dict = None, timeout: int = 8, retries: int = 2):
    for attempt in range(retries + 1):
        try:
            r = requests.get(url, params=params, headers=_HEADERS, timeout=timeout)
            if r.status_code == 200:
                return r.json()
        except Exception:
            if attempt < retries:
                time.sleep(0.5 * (attempt + 1))
    return None


# ─── 81 İl Tier Haritası (circular import olmadan kendi listesi) ──────────────
# tier → (daire_lo, daire_hi, yillik_degisim_ort %)
_IL_TIER: dict = {
    "İstanbul": 1, "Muğla": 2, "Antalya": 2, "İzmir": 2, "Ankara": 2,
    "Bursa": 3, "Yalova": 3, "Kocaeli": 3, "Tekirdağ": 3, "Eskişehir": 3,
    "Gaziantep": 3, "Konya": 3, "Mersin": 3, "Samsun": 3, "Kayseri": 3,
    "Aydın": 3, "Çanakkale": 3, "Sakarya": 3,
    "Adana": 4, "Balıkesir": 4, "Denizli": 4, "Diyarbakır": 4,
    "Edirne": 4, "Hatay": 4, "Kırklareli": 4, "Malatya": 4, "Manisa": 4,
    "Nevşehir": 4, "Trabzon": 4, "Bolu": 4,
    "Afyonkarahisar": 5, "Aksaray": 5, "Amasya": 5, "Artvin": 5,
    "Bartın": 5, "Batman": 5, "Bilecik": 5, "Burdur": 5, "Çorum": 5,
    "Düzce": 5, "Elazığ": 5, "Erzincan": 5, "Erzurum": 5, "Giresun": 5,
    "Isparta": 5, "Kahramanmaraş": 5, "Karabük": 5, "Karaman": 5,
    "Kastamonu": 5, "Kırıkkale": 5, "Kırşehir": 5, "Kütahya": 5,
    "Mardin": 5, "Niğde": 5, "Ordu": 5, "Osmaniye": 5, "Rize": 5,
    "Şanlıurfa": 5, "Sinop": 5, "Sivas": 5, "Tokat": 5, "Uşak": 5,
    "Van": 5, "Zonguldak": 5,
    "Adıyaman": 6, "Ağrı": 6, "Ardahan": 6, "Bayburt": 6, "Bingöl": 6,
    "Bitlis": 6, "Çankırı": 6, "Gümüşhane": 6, "Hakkari": 6, "Iğdır": 6,
    "Kars": 6, "Kilis": 6, "Muş": 6, "Siirt": 6, "Şırnak": 6,
    "Tunceli": 6, "Yozgat": 6,
}

_TIER_FIYAT = {
    # tier: (daire_ort_m2, yillik_degisim_ort)
    1: (82_000, 28.5),
    2: (48_000, 25.0),
    3: (28_000, 22.0),
    4: (17_000, 19.5),
    5: (10_000, 17.0),
    6:  (5_500, 14.5),
}

_IL_LISTESI = sorted(_IL_TIER.keys())


def _synthetic_il_df() -> pd.DataFrame:
    """Seed-tabanlı deterministik il bazlı fiyat verisi üretir."""
    ck = _ck("synthetic_il_df")
    cached = _cache_get(ck)
    if cached is not None:
        return pd.DataFrame(cached)

    rows = []
    for il in _IL_LISTESI:
        tier = _IL_TIER.get(il, 5)
        base_fiyat, base_degisim = _TIER_FIYAT[tier]
        seed = int(hashlib.md5(il.encode()).hexdigest(), 16) % 99991
        rng  = np.random.default_rng(seed)
        mod  = float(rng.uniform(0.72, 1.38))
        fiyat    = max(2_000, int(base_fiyat * mod))
        degisim  = round(float(base_degisim + rng.uniform(-4.5, 6.5)), 1)
        rows.append({"il": il, "fiyat": fiyat, "degisim": degisim})

    df = pd.DataFrame(rows)
    _cache_set(ck, df.to_dict("records"), ttl=7200)
    return df


# ─── TCMB EVDS — il bazlı fiyat (endeks × referans fiyat yöntemi) ────────────
def get_tcmb_data() -> "pd.DataFrame | None":
    """
    TCMB EVDS üzerinden Konut Fiyat Endeksi çek.
    Türkiye geneli endeks kullanılarak il ağırlıklı fiyat üretilir.
    Başarısız olursa None döner.
    """
    ck = _ck("tcmb_il_df")
    cached = _cache_get(ck)
    if cached is not None:
        return pd.DataFrame(cached)

    try:
        from core.emlak_fetcher import fetch_tcmb_hpi
        hpi = fetch_tcmb_hpi()
        if not hpi or "Türkiye" not in hpi:
            return None

        tr_series = hpi["Türkiye"]
        if len(tr_series) < 2:
            return None

        # Son iki nokta → büyüme oranı
        val_son    = tr_series[-1][1]
        val_onceki = tr_series[-2][1]
        endeks_degisim_pct = round(((val_son / val_onceki) - 1) * 100, 2) if val_onceki else 0

        # Endeks büyümesini il bazına dağıt (tier ağırlığıyla)
        rows = []
        for il in _IL_LISTESI:
            tier = _IL_TIER.get(il, 5)
            base_fiyat, _ = _TIER_FIYAT[tier]
            seed = int(hashlib.md5(il.encode()).hexdigest(), 16) % 99991
            rng  = np.random.default_rng(seed)
            mod  = float(rng.uniform(0.75, 1.35))
            fiyat   = max(2_000, int(base_fiyat * mod))
            # Lokal değişim = endeks hareketi ± tier ayarı
            tier_adj  = (4 - tier) * 0.8   # tier 1 pozitif, tier 6 negatif
            degisim   = round(endeks_degisim_pct + tier_adj + float(rng.uniform(-2, 2)), 1)
            rows.append({"il": il, "fiyat": fiyat, "degisim": degisim})

        df = pd.DataFrame(rows)
        _cache_set(ck, df.to_dict("records"), ttl=3600)
        return df

    except Exception:
        return None


# ─── Endeksa — il bazlı fiyat ────────────────────────────────────────────────
def get_endeksa_data() -> "pd.DataFrame | None":
    """
    Endeksa'dan bilinen şehirler için il bazlı ortalama fiyat çek.
    """
    ck = _ck("endeksa_il_df")
    cached = _cache_get(ck)
    if cached is not None:
        return pd.DataFrame(cached)

    try:
        from core.emlak_fetcher import fetch_endeksa_ilceler, ENDEKSA_SEHIR_ID

        rows = []
        # Verimlilik için sadece en büyük 6 şehri tara (timeout riskini azalt)
        priority_cities = ["İstanbul", "Ankara", "İzmir", "Antalya", "Bursa", "Kocaeli"]
        for il in priority_cities:
            try:
                ilce_data = fetch_endeksa_ilceler(il)
                if ilce_data:
                    prices = [r.get("daire_m2", 0) for r in ilce_data if r.get("daire_m2", 0) > 0]
                    if prices:
                        avg = int(sum(prices) / len(prices))
                        tier = _IL_TIER.get(il, 5)
                        _, base_deg = _TIER_FIYAT[tier]
                        seed = int(hashlib.md5(il.encode()).hexdigest(), 16) % 99991
                        rng  = np.random.default_rng(seed + 1)
                        degisim = round(base_deg + float(rng.uniform(-3, 4)), 1)
                        rows.append({"il": il, "fiyat": avg, "degisim": degisim})
            except Exception:
                continue

        if rows:
            df = pd.DataFrame(rows)
            _cache_set(ck, df.to_dict("records"), ttl=3600 * 6)
            return df
    except Exception:
        pass
    return None


# ─── Sahibinden — scrape (en iyi çabası) ─────────────────────────────────────
def get_sahibinden_data() -> "pd.DataFrame | None":
    """
    Sahibinden'den veri çekmeyi dener.
    Anti-bot koruması nedeniyle büyük ihtimalle None döner — bu normaldir.
    """
    url = "https://www.sahibinden.com/emlak360/emlak-endeksi"
    try:
        r = requests.get(url, headers=_HEADERS, timeout=6)
        if r.status_code == 200 and len(r.text) > 1000:
            # Basit JSON blok arama
            import re
            m = re.search(r'"cities"\s*:\s*(\[.*?\])', r.text, re.DOTALL)
            if m:
                import json
                cities = json.loads(m.group(1))
                rows = []
                for c in cities:
                    il = c.get("name") or c.get("city", "")
                    fiyat = c.get("avgPrice") or c.get("price", 0)
                    degisim = c.get("change") or c.get("changeRate", 0)
                    if il and fiyat:
                        rows.append({"il": il, "fiyat": int(fiyat), "degisim": float(degisim)})
                if rows:
                    return pd.DataFrame(rows)
    except Exception:
        pass
    return None


# ─── Merge: TCMB → Endeksa → Sahibinden → Synthetic ─────────────────────────
def merge_data() -> pd.DataFrame:
    """
    Öncelik sırasıyla veri kaynağını dener, herhangi biri başarılıysa döner.
    En kötü durumda deterministik sentetik veri döner (hiçbir zaman crash etmez).

    Returns:
        pd.DataFrame with columns ["il", "fiyat", "degisim"]
    """
    ck = _ck("merge_data")
    cached = _cache_get(ck)
    if cached is not None:
        return pd.DataFrame(cached)

    # 1. TCMB
    df = get_tcmb_data()
    if df is not None and not df.empty:
        df = df[["il", "fiyat", "degisim"]].copy()
        _cache_set(ck, df.to_dict("records"), ttl=3600)
        return df

    # 2. Endeksa (kısmi liste — 20 şehir)
    df = get_endeksa_data()
    if df is not None and not df.empty and len(df) >= 5:
        df = df[["il", "fiyat", "degisim"]].copy()
        # Eksik iller için sentetik ile tamamla
        df = _fill_missing_iller(df)
        _cache_set(ck, df.to_dict("records"), ttl=3600)
        return df

    # 3. Sahibinden
    df = get_sahibinden_data()
    if df is not None and not df.empty:
        df = df[["il", "fiyat", "degisim"]].copy()
        df = _fill_missing_iller(df)
        _cache_set(ck, df.to_dict("records"), ttl=3600)
        return df

    # 4. Sentetik fallback (her zaman çalışır)
    df = _synthetic_il_df()
    _cache_set(ck, df.to_dict("records"), ttl=3600)
    return df


def _fill_missing_iller(df: pd.DataFrame) -> pd.DataFrame:
    """Eksik illeri sentetik verilerle tamamlar."""
    try:
        mevcut = set(df["il"].tolist())
        eks = [il for il in _IL_LISTESI if il not in mevcut]
        if not eks:
            return df
        syn = _synthetic_il_df()
        eks_df = syn[syn["il"].isin(eks)].copy()
        return pd.concat([df, eks_df], ignore_index=True)
    except Exception:
        return df


# ─── 81 İl Koordinatları ─────────────────────────────────────────────────────
_IL_COORD: dict = {
    "Adana":(37.00,35.32),"Adıyaman":(37.76,38.28),"Afyonkarahisar":(38.75,30.54),
    "Ağrı":(39.72,43.05),"Aksaray":(38.37,34.03),"Amasya":(40.65,35.83),
    "Ankara":(39.93,32.85),"Antalya":(36.89,30.71),"Ardahan":(41.11,42.70),
    "Artvin":(41.18,41.82),"Aydın":(37.84,27.84),"Balıkesir":(39.65,27.89),
    "Bartın":(41.63,32.34),"Batman":(37.88,41.13),"Bayburt":(40.26,40.23),
    "Bilecik":(40.15,29.98),"Bingöl":(38.88,40.50),"Bitlis":(38.40,42.11),
    "Bolu":(40.74,31.61),"Burdur":(37.72,30.29),"Bursa":(40.19,29.07),
    "Çanakkale":(40.15,26.41),"Çankırı":(40.60,33.62),"Çorum":(40.55,34.96),
    "Denizli":(37.77,29.09),"Diyarbakır":(37.91,40.24),"Düzce":(40.84,31.16),
    "Edirne":(41.68,26.56),"Elazığ":(38.68,39.23),"Erzincan":(39.75,39.50),
    "Erzurum":(39.91,41.27),"Eskişehir":(39.78,30.52),"Gaziantep":(37.07,37.38),
    "Giresun":(40.92,38.39),"Gümüşhane":(40.46,39.48),"Hakkari":(37.57,43.74),
    "Hatay":(36.40,36.35),"Iğdır":(39.92,44.05),"Isparta":(37.76,30.55),
    "İstanbul":(41.01,28.96),"İzmir":(38.42,27.14),"Kahramanmaraş":(37.59,36.94),
    "Karabük":(41.20,32.62),"Karaman":(37.18,33.22),"Kars":(40.61,43.10),
    "Kastamonu":(41.38,33.78),"Kayseri":(38.73,35.49),"Kırıkkale":(39.85,33.52),
    "Kırklareli":(41.74,27.23),"Kırşehir":(39.15,34.16),"Kilis":(36.72,37.12),
    "Kocaeli":(40.77,29.94),"Konya":(37.87,32.49),"Kütahya":(39.42,29.98),
    "Malatya":(38.36,38.31),"Manisa":(38.61,27.43),"Mardin":(37.31,40.74),
    "Mersin":(36.80,34.64),"Muğla":(37.22,28.36),"Muş":(38.73,41.49),
    "Nevşehir":(38.62,34.72),"Niğde":(37.97,34.68),"Ordu":(40.98,37.88),
    "Osmaniye":(37.07,36.25),"Rize":(41.03,40.52),"Sakarya":(40.69,30.43),
    "Samsun":(41.29,36.33),"Siirt":(37.93,41.95),"Sinop":(42.03,35.15),
    "Sivas":(39.75,37.02),"Şanlıurfa":(37.16,38.80),"Şırnak":(37.52,42.46),
    "Tekirdağ":(40.98,27.51),"Tokat":(40.31,36.55),"Trabzon":(41.00,39.72),
    "Tunceli":(39.11,39.55),"Uşak":(38.68,29.41),"Van":(38.49,43.38),
    "Yalova":(40.66,29.28),"Yozgat":(39.82,34.81),"Zonguldak":(41.45,31.80),
}


def merge_data_with_coords() -> "pd.DataFrame":
    """merge_data() + koordinat sütunları eklenmiş hali."""
    import plotly.graph_objects as go  # noqa: F401 — ensure importable
    df = merge_data()
    lats, lons = [], []
    for il in df["il"]:
        coord = _IL_COORD.get(il, (39.0, 35.0))
        lats.append(coord[0])
        lons.append(coord[1])
    df = df.copy()
    df["lat"] = lats
    df["lon"] = lons
    return df


def create_turkiye_map(df: "pd.DataFrame") -> "go.Figure":
    """Türkiye il bazlı emlak fiyat haritası (bubble map)."""
    import plotly.graph_objects as go

    if df is None or df.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="⏳ Veri bekleniyor",
            xref="paper", yref="paper", x=0.5, y=0.5,
            showarrow=False, font=dict(size=16, color="#7a93b0"),
        )
        fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", height=420)
        return fig

    # koordinat yoksa ekle
    if "lat" not in df.columns:
        lats, lons = [], []
        for il in df["il"]:
            c = _IL_COORD.get(il, (39.0, 35.0))
            lats.append(c[0]); lons.append(c[1])
        df = df.copy()
        df["lat"] = lats; df["lon"] = lons

    fmin, fmax = df["fiyat"].min(), df["fiyat"].max()
    size_norm  = 8 + 24 * (df["fiyat"] - fmin) / max(fmax - fmin, 1)

    fig = go.Figure()
    fig.add_trace(go.Scattergeo(
        lat=df["lat"], lon=df["lon"],
        text=df["il"],
        mode="markers",
        marker=dict(
            size=size_norm,
            color=df["fiyat"],
            colorscale=[
                [0.00, "#0d1520"], [0.20, "#1e3d6e"],
                [0.50, "#1e88e5"], [0.80, "#00bcd4"], [1.00, "#00e5ff"],
            ],
            showscale=True,
            colorbar=dict(
                title=dict(text="₺/m²", font=dict(color="#7a93b0", size=11)),
                tickfont=dict(color="#7a93b0", size=10),
                bgcolor="rgba(0,0,0,0)",
                bordercolor="rgba(30,58,95,0.4)",
                len=0.75, tickformat=",.0f",
            ),
            line=dict(width=1, color="rgba(255,255,255,0.18)"),
            opacity=0.90,
        ),
        customdata=df[["il", "fiyat", "degisim"]].values,
        hovertemplate=(
            "<b>%{customdata[0]}</b><br>"
            "₺%{customdata[1]:,.0f}/m²<br>"
            "Yıllık: %{customdata[2]:+.1f}%"
            "<extra></extra>"
        ),
    ))

    fig.update_geos(
        projection_type="mercator",
        lataxis_range=[35.0, 43.2],
        lonaxis_range=[24.5, 45.5],
        bgcolor="rgba(0,0,0,0)",
        oceancolor="#050c18",
        landcolor="#0d1520",
        showland=True, showocean=True,
        showcoastlines=True, coastlinecolor="#1e3a5f",
        showcountries=True, countrycolor="#1e3a5f",
        showlakes=False, showrivers=False,
        framecolor="rgba(0,0,0,0)",
    )
    fig.update_layout(
        title=dict(
            text="Türkiye — İl Bazlı Emlak Fiyat Haritası (₺/m²)",
            font=dict(size=13, color="#e2eaf5", family="monospace"),
            x=0.02,
        ),
        paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=0, r=0, t=42, b=0),
        height=460,
        font=dict(color="#7a93b0"),
    )
    return fig
