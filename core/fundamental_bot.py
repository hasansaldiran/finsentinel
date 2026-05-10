"""
FinSentinel — Temel Analiz Bot Komutları
core/fundamental_bot.py

Telegram botu için İş Yatırım Excel verilerini sorgulayan komutlar.
Tüm sonuçlar AI yorumuyla gelir.

Komutlar:
  /oneri [THYAO]     — AL/TUT/SAT önerileri (genel veya hisse bazlı)
  /al                — En iyi AL önerileri (potansiyele göre)
  /tut               — TUT listesi
  /sat               — SAT listesi (risk uyarısı)
  /alfaskor          — Alpha skor sıralaması top-10
  /temel THYAO       — Hisse tam temel analiz kartı
  /hedef THYAO       — Hedef fiyat ve revizyon geçmişi
  /temettu           — En yüksek temettü verimi listesi
  /yabanci           — Yabancı yatırımcı giriş/çıkış tablosu
  /performans_temel  — Temel performans verileri
  /endeks            — BIST endeks bileşenleri özeti
  /katilim           — Katılım uyumlu AL hisseleri + tam öneri detayı
"""

from pathlib import Path
from datetime import datetime
from loguru import logger
import pandas as pd

_DATA_ROOT = Path("data/isyatirim")

# Katılım dışı listeler (telegram_bot.py ile aynı)
_KATILIM_DISI_KW = [
    "banka","bank","sigort","faktor","lizing","leasing",
    "finansal kiralama","aracı kurum","menkul kıymet","portföy yönet",
    "gyo","gayrimenkul yatırım","reit",
    "alkol","bira","içki","tütün","sigara","kumar","bahis",
]
_KATILIM_DISI_KODLAR = {
    "AEFES","EFES","AKBNK","GARAN","HALKB","ISCTR","TSKB","VAKBN","YKBNK",
    "ALBRK","QNBFB","SKBNK","FIBAB","ICBCT","ANHYT","ANSGR","AVISA","GUSGR",
    "RAYSG","TURSG","AGYO","EKGYO","ISGYO","OZGYO","SNGYO","TRGYO","VKGYO",
}


# ─── Veri Yardımcıları ────────────────────────────────────────────────────────

def _latest_dir() -> Path | None:
    if not _DATA_ROOT.exists():
        return None
    dated = sorted(
        [d for d in _DATA_ROOT.iterdir()
         if d.is_dir() and len(d.name) == 10 and d.name[4] == "_"],
        reverse=True,
    )
    return dated[0] if dated else (_DATA_ROOT if any(_DATA_ROOT.glob("*.xlsx")) else None)


def _read(name: str) -> pd.DataFrame | None:
    d = _latest_dir()
    if not d:
        return None
    for ext in (".xlsx", ".xls"):
        p = d / (name + ext)
        if p.exists():
            try:
                df = pd.read_excel(p, sheet_name=0)
                df.columns = df.columns.str.strip()
                return df.dropna(how="all").reset_index(drop=True)
            except Exception:
                pass
    return None


def _num(s: pd.Series) -> pd.Series:
    return pd.to_numeric(
        s.astype(str).str.replace(",", ".", regex=False)
                     .str.replace(" ", "", regex=False)
                     .str.replace("%", "", regex=False),
        errors="coerce",
    )


def _ai(prompt: str, max_tokens: int = 350) -> str:
    try:
        from core.ai_engine import _call_best_ai
        return _call_best_ai(prompt, max_tokens=max_tokens) or ""
    except Exception:
        return ""


def _esc(s) -> str:
    import html
    return html.escape(str(s))


def _oneri_emoji(o: str) -> str:
    o = str(o).upper()
    if "AL" in o and "TUT" not in o:
        return "🟢"
    if "SAT" in o:
        return "🔴"
    if "TUT" in o:
        return "🟡"
    return "⚪"


def _is_katilim(kod: str, sektor: str = "", ad: str = "") -> bool:
    k = str(kod).upper().strip()
    if k in _KATILIM_DISI_KODLAR:
        return False
    s = str(sektor).lower()
    for kw in _KATILIM_DISI_KW:
        if kw in s:
            return False
    a = str(ad).upper()
    for kw in ["BANK","BANKAS","SİGORTA","FAKTORING","LEASING","GYO","REİT","EFES","AEFES"]:
        if kw in a:
            return False
    return True


# ─── Komut Fonksiyonları ──────────────────────────────────────────────────────

def cmd_oneri(symbol: str = "") -> str:
    """
    /oneri        → Genel öneri özeti + top-10 AL
    /oneri THYAO  → O hissenin öneri kartı
    """
    df = _read("takipozet")
    if df is None:
        return "⚠️ takipozet verisi bulunamadı."

    df["Kod"] = df["Kod"].astype(str).str.strip().str.upper()

    if symbol:
        row = df[df["Kod"] == symbol.upper().strip()]
        if row.empty:
            return f"⚠️ <code>{symbol.upper()}</code> takip listesinde bulunamadı."
        r   = row.iloc[0]
        oneri = str(r.get("Öneri", "—"))
        pot   = _num(row.get("Getiri Potansiyeli (%)", pd.Series(["0"]))).iloc[0]
        hisse_adi = str(r.get("Hisse Adı", symbol))

        df_hf = _read("takiphedeffiyat")
        hedef_str = ""
        if df_hf is not None and "Kod" in df_hf.columns:
            hf_row = df_hf[df_hf["Kod"].astype(str).str.strip().str.upper() == symbol.upper()]
            if not hf_row.empty:
                cols = [c for c in hf_row.columns if "Hedef" in c or "Fiyat" in c]
                vals = [f"{c}: {_esc(hf_row.iloc[0][c])}" for c in cols[:4]]
                hedef_str = "  " + " | ".join(vals)

        df_fin = _read("temelfinansal")
        fin_str = ""
        if df_fin is not None and "Kod" in df_fin.columns:
            fr = df_fin[df_fin["Kod"].astype(str).str.strip().str.upper() == symbol.upper()]
            if not fr.empty:
                parts = []
                for col in ["F/K", "PD/DD", "FD/FAVÜK", "Net Kar Marjı (%)"]:
                    if col in fr.columns:
                        v = fr.iloc[0][col]
                        parts.append(f"{col}: <b>{_esc(v)}</b>")
                fin_str = "  " + " | ".join(parts)

        emoji = _oneri_emoji(oneri)
        pot_f = float(pot) if not pd.isna(pot) else 0

        prompt = (
            f"{symbol} ({hisse_adi}) için İş Yatırım analizi. "
            f"Öneri: {oneri}. Getiri Potansiyeli: %{pot_f:.1f}. "
            f"Finansallar: {fin_str}. "
            "Yatırımcıya 3 madde: 1) Neden bu öneri verilmiş, 2) Temel güçlü yönler, "
            "3) Önemli riskler. Net, somut, Türkçe."
        )
        ai_text = _ai(prompt, 350)

        return (
            f"🔬 <b>{symbol} — Temel Öneri Kartı</b>\n"
            f"<i>{_esc(hisse_adi)}</i>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"  Öneri  : {emoji} <b>{_esc(oneri)}</b>\n"
            f"  Pot.   : <b>%{pot_f:.1f}</b>\n"
            + (f"  Hedef  : {hedef_str}\n" if hedef_str else "")
            + (f"  Finansal: {fin_str}\n" if fin_str else "")
            + f"\n<b>🤖 AI Yorumu</b>\n{ai_text}"
        )

    # Genel özet
    if "Öneri" not in df.columns:
        return "⚠️ Öneri kolonu bulunamadı."

    al_  = int(df["Öneri"].astype(str).str.upper().str.contains("AL", na=False).sum())
    tut_ = int(df["Öneri"].astype(str).str.upper().str.contains("TUT", na=False).sum())
    sat_ = int(df["Öneri"].astype(str).str.upper().str.contains("SAT", na=False).sum())

    pot_col = "Getiri Potansiyeli (%)"
    top_al = []
    if pot_col in df.columns:
        df_al = df[df["Öneri"].astype(str).str.upper().str.contains("AL", na=False)].copy()
        df_al["_pot"] = _num(df_al[pot_col])
        df_al = df_al.dropna(subset=["_pot"]).nlargest(10, "_pot")
        for _, r in df_al.iterrows():
            top_al.append(
                f"  🟢 <code>{r['Kod']:<7}</code> "
                f"Pot:<b>%{float(r['_pot']):.1f}</b>  "
                f"[{_esc(r.get('Öneri','AL'))}]"
            )

    prompt = (
        f"İş Yatırım takip listesi özeti: AL={al_}, TUT={tut_}, SAT={sat_} hisse. "
        f"Top AL hisseler: {', '.join([l.split()[1] for l in top_al[:5]])}. "
        "2 cümle: Genel tablo ne söylüyor, yatırımcı ne yapmalı? Türkçe."
    )
    ai_text = _ai(prompt, 180)

    rows = "\n".join(top_al)
    return (
        f"📊 <b>Takip Listesi Öneri Özeti</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"  🟢 AL : <b>{al_}</b> hisse\n"
        f"  🟡 TUT: <b>{tut_}</b> hisse\n"
        f"  🔴 SAT: <b>{sat_}</b> hisse\n"
        f"\n<b>🏆 En Yüksek Potansiyelli AL'lar</b>\n{rows}\n"
        f"\n<b>🤖 AI Yorum</b>\n{ai_text}\n"
        f"\n<i>/oneri THYAO ile detay al</i>"
    )


def cmd_al(top_n: int = 10) -> str:
    """En yüksek potansiyelli AL önerileri."""
    df = _read("takipozet")
    if df is None:
        return "⚠️ Veri bulunamadı."
    df["Kod"] = df["Kod"].astype(str).str.strip().str.upper()
    al_mask = df["Öneri"].astype(str).str.upper().str.contains("AL", na=False)
    df_al = df[al_mask].copy()
    pot_col = "Getiri Potansiyeli (%)"
    if pot_col not in df_al.columns:
        return "⚠️ Getiri Potansiyeli kolonu yok."
    df_al["_pot"] = _num(df_al[pot_col])
    df_al = df_al.dropna(subset=["_pot"]).nlargest(top_n, "_pot")

    rows = []
    for i, (_, r) in enumerate(df_al.iterrows(), 1):
        ad = str(r.get("Hisse Adı", ""))[:18]
        rows.append(
            f"  {i:2}. <code>{r['Kod']:<7}</code> "
            f"<b>%{float(r['_pot']):.1f}</b>  "
            f"<i>{_esc(ad)}</i>"
        )

    prompt = (
        f"İş Yatırım en iyi {top_n} AL önerisi: "
        f"{', '.join(df_al['Kod'].tolist())}. "
        "Öne çıkan 2-3 hisseyi neden al? Ortak tema var mı? 3 cümle, Türkçe."
    )
    ai_text = _ai(prompt, 220)

    return (
        f"🟢 <b>En Yüksek Potansiyelli AL Önerileri (Top {top_n})</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        + "\n".join(rows)
        + f"\n\n<b>🤖 AI Yorum</b>\n{ai_text}"
    )


def cmd_tut() -> str:
    df = _read("takipozet")
    if df is None:
        return "⚠️ Veri bulunamadı."
    df["Kod"] = df["Kod"].astype(str).str.strip().str.upper()
    tut_mask = df["Öneri"].astype(str).str.upper().str.contains("TUT", na=False)
    df_t = df[tut_mask].copy()
    pot_col = "Getiri Potansiyeli (%)"
    if pot_col in df_t.columns:
        df_t["_pot"] = _num(df_t[pot_col])
        df_t = df_t.sort_values("_pot", ascending=False)

    rows = []
    for i, (_, r) in enumerate(df_t.head(10).iterrows(), 1):
        pot = float(r.get("_pot", 0)) if "_pot" in r.index else 0
        rows.append(
            f"  {i:2}. <code>{r['Kod']:<7}</code>  "
            f"Pot: %{pot:.1f}  {_esc(str(r.get('Hisse Adı',''))[:18])}"
        )

    prompt = (
        f"İş Yatırım TUT listesi ({len(df_t)} hisse). "
        "TUT önerisi ne anlama gelir? Bunlardan yatırım yapılabilir mi? "
        "2-3 cümle, Türkçe."
    )
    ai_text = _ai(prompt, 180)

    return (
        f"🟡 <b>TUT Önerileri ({len(df_t)} hisse)</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        + "\n".join(rows)
        + f"\n\n<b>🤖 AI Yorum</b>\n{ai_text}"
    )


def cmd_sat() -> str:
    df = _read("takipozet")
    if df is None:
        return "⚠️ Veri bulunamadı."
    df["Kod"] = df["Kod"].astype(str).str.strip().str.upper()
    sat_mask = df["Öneri"].astype(str).str.upper().str.contains("SAT", na=False)
    df_s = df[sat_mask].copy()

    rows = []
    for i, (_, r) in enumerate(df_s.iterrows(), 1):
        pot_col = "Getiri Potansiyeli (%)"
        pot = float(_num(pd.Series([r[pot_col]])).iloc[0]) if pot_col in r.index else 0
        rows.append(
            f"  {i:2}. 🔴 <code>{r['Kod']:<7}</code>  "
            f"Pot: %{pot:.1f}  {_esc(str(r.get('Hisse Adı',''))[:18])}"
        )

    if not rows:
        return "✅ Şu an SAT önerisi olan hisse yok."

    prompt = (
        f"İş Yatırım SAT önerileri: {', '.join(df_s['Kod'].tolist())}. "
        "Bu hisseler neden SAT? Ortak risk faktörü var mı? "
        "2-3 cümle uyarı tonu ile, Türkçe."
    )
    ai_text = _ai(prompt, 200)

    return (
        f"🔴 <b>SAT Önerileri — Dikkat!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        + "\n".join(rows)
        + f"\n\n<b>🤖 AI Risk Uyarısı</b>\n{ai_text}"
    )


def cmd_alfaskor(top_n: int = 10) -> str:
    """Alpha skor sıralaması — percentile rank bazlı."""
    df = _read("takipozet")
    df_fin = _read("temelfinansal")
    df_yab = _read("temelyabancioran")
    if df is None:
        return "⚠️ Veri bulunamadı."

    df["Kod"] = df["Kod"].astype(str).str.strip().str.upper()
    pot_col = "Getiri Potansiyeli (%)"
    if pot_col not in df.columns:
        return "⚠️ Potansiyel kolonu yok."

    df["_pot"] = _num(df[pot_col])
    df["_alpha"] = df["_pot"].rank(pct=True) * 100

    al_mask = df["Öneri"].astype(str).str.upper().str.contains("AL", na=False)
    df = df[al_mask].copy()

    if df_fin is not None and "Kod" in df_fin.columns and "F/K" in df_fin.columns:
        df_fin2 = df_fin[["Kod","F/K"]].copy()
        df_fin2["Kod"] = df_fin2["Kod"].astype(str).str.strip().str.upper()
        df = df.merge(df_fin2, on="Kod", how="left")
        df["_alpha"] += (_num(df["F/K"]) < 10).fillna(False).astype(int) * 10

    if df_yab is not None and "Kod" in df_yab.columns:
        deg_col = next((c for c in df_yab.columns if "Değişim" in c), None)
        if deg_col:
            dy = df_yab[["Kod", deg_col]].copy()
            dy["Kod"] = dy["Kod"].astype(str).str.strip().str.upper()
            df = df.merge(dy, on="Kod", how="left", suffixes=("","_y"))
            df["_alpha"] += (_num(df[deg_col]) > 0).fillna(False).astype(int) * 15

    df = df.dropna(subset=["_alpha"]).nlargest(top_n, "_alpha")

    rows = []
    for i, (_, r) in enumerate(df.iterrows(), 1):
        alpha = float(r["_alpha"])
        pot   = float(r["_pot"]) if not pd.isna(r.get("_pot")) else 0
        ad    = str(r.get("Hisse Adı",""))[:16]
        rows.append(
            f"  {i:2}. <code>{r['Kod']:<7}</code>  "
            f"Alpha:<b>{alpha:.0f}</b>  Pot:%{pot:.1f}  "
            f"<i>{_esc(ad)}</i>"
        )

    prompt = (
        f"Alpha skor sıralaması top-{top_n}: {', '.join(df['Kod'].tolist())}. "
        "Bu hisselerin öne çıkma nedenleri neler? Sektör dağılımı? "
        "2-3 cümle, Türkçe."
    )
    ai_text = _ai(prompt, 200)

    return (
        f"⚡ <b>Alpha Skor Sıralaması — Top {top_n}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        + "\n".join(rows)
        + f"\n\n<b>🤖 AI Yorum</b>\n{ai_text}"
    )


def cmd_temel(symbol: str) -> str:
    """Hisse tam temel analiz kartı — tüm veriler."""
    if not symbol:
        return "❓ Kullanım: /temel THYAO"

    sym = symbol.upper().strip()
    df_oz  = _read("takipozet")
    df_fin = _read("temelfinansal")
    df_yab = _read("temelyabancioran")
    df_hf  = _read("takiphedeffiyat")
    df_tem = _read("takiptemettu")
    df_per = _read("temelperformans")

    sections = []

    # ── Öneri & Potansiyel ────────────────────────────────────────────────────
    if df_oz is not None and "Kod" in df_oz.columns:
        row = df_oz[df_oz["Kod"].astype(str).str.strip().str.upper() == sym]
        if not row.empty:
            r = row.iloc[0]
            oneri = str(r.get("Öneri","—"))
            pot   = _num(row["Getiri Potansiyeli (%)"]).iloc[0] if "Getiri Potansiyeli (%)" in row.columns else 0
            hisse_adi = str(r.get("Hisse Adı", sym))
            emoji = _oneri_emoji(oneri)
            sections.append(
                f"<b>📋 Öneri & Beklenti</b>\n"
                f"  Hisse Adı : {_esc(hisse_adi)}\n"
                f"  Öneri     : {emoji} <b>{_esc(oneri)}</b>\n"
                f"  Getiri Pot: <b>%{float(pot):.1f}</b>"
            )

    # ── Finansal Oranlar ──────────────────────────────────────────────────────
    if df_fin is not None and "Kod" in df_fin.columns:
        fr = df_fin[df_fin["Kod"].astype(str).str.strip().str.upper() == sym]
        if not fr.empty:
            r   = fr.iloc[0]
            fin_cols = ["F/K","PD/DD","FD/FAVÜK","Net Kar Marjı (%)","ROE (%)","ROA (%)"]
            fin_rows = []
            for col in fin_cols:
                if col in r.index:
                    fin_rows.append(f"  {col:<20}: <b>{_esc(r[col])}</b>")
            if fin_rows:
                sections.append("<b>📊 Finansal Oranlar</b>\n" + "\n".join(fin_rows))

    # ── Hedef Fiyat ───────────────────────────────────────────────────────────
    if df_hf is not None and "Kod" in df_hf.columns:
        hr = df_hf[df_hf["Kod"].astype(str).str.strip().str.upper() == sym]
        if not hr.empty:
            r    = hr.iloc[0]
            hcols = [c for c in r.index if "Hedef" in c or "Fiyat" in c]
            hrows = [f"  {c}: <b>{_esc(r[c])}</b>" for c in hcols[:5]]
            if hrows:
                sections.append("<b>🎯 Hedef Fiyat</b>\n" + "\n".join(hrows))

    # ── Temettü ───────────────────────────────────────────────────────────────
    if df_tem is not None and "Kod" in df_tem.columns:
        tr = df_tem[df_tem["Kod"].astype(str).str.strip().str.upper() == sym]
        if not tr.empty:
            r     = tr.iloc[0]
            tcols = [c for c in r.index if "Temettü" in c or "Verim" in c]
            trows = [f"  {c}: <b>{_esc(r[c])}</b>" for c in tcols[:4]]
            if trows:
                sections.append("<b>💰 Temettü</b>\n" + "\n".join(trows))

    # ── Yabancı Yatırımcı ─────────────────────────────────────────────────────
    if df_yab is not None and "Kod" in df_yab.columns:
        yr  = df_yab[df_yab["Kod"].astype(str).str.strip().str.upper() == sym]
        if not yr.empty:
            r     = yr.iloc[0]
            ycols = [c for c in r.index if "Yabancı" in c or "Değişim" in c or "Oran" in c]
            yrows = [f"  {c}: <b>{_esc(r[c])}</b>" for c in ycols[:4]]
            if yrows:
                sections.append("<b>👔 Yabancı Yatırımcı</b>\n" + "\n".join(yrows))

    # ── Performans ────────────────────────────────────────────────────────────
    if df_per is not None and "Kod" in df_per.columns:
        pr = df_per[df_per["Kod"].astype(str).str.strip().str.upper() == sym]
        if not pr.empty:
            r     = pr.iloc[0]
            pcols = [c for c in r.index if "%" in c or "Performans" in c or "Getiri" in c]
            prows = [f"  {c}: <b>{_esc(r[c])}</b>" for c in pcols[:5]]
            if prows:
                sections.append("<b>📈 Performans</b>\n" + "\n".join(prows))

    if not sections:
        return f"⚠️ <code>{sym}</code> için veri bulunamadı."

    # AI yorum
    combined = " | ".join(s.replace("\n"," ") for s in sections)
    prompt = (
        f"{sym} temel analiz özeti: {combined[:500]}. "
        "Bu verilere göre hisse AL mı TUT mu SAT mı? Neden? "
        "3 madde: güçlü yön, zayıf yön, yatırım kararı. Türkçe."
    )
    ai_text = _ai(prompt, 350)

    return (
        f"🔬 <b>{sym} — Tam Temel Analiz</b>\n"
        f"<i>{datetime.now().strftime('%d %b %Y %H:%M')}</i>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        + "\n\n".join(sections)
        + f"\n\n<b>🤖 AI Değerlendirme</b>\n{ai_text}"
    )


def cmd_hedef(symbol: str) -> str:
    """Hedef fiyat ve revizyon bilgisi."""
    if not symbol:
        return "❓ Kullanım: /hedef THYAO"
    sym    = symbol.upper().strip()
    df_hf  = _read("takiphedeffiyat")
    df_oz  = _read("takipozet")
    if df_hf is None:
        return "⚠️ takiphedeffiyat verisi yok."

    row = df_hf[df_hf["Kod"].astype(str).str.strip().str.upper() == sym] if "Kod" in df_hf.columns else pd.DataFrame()
    if row.empty:
        return f"⚠️ <code>{sym}</code> için hedef fiyat verisi yok."

    r     = row.iloc[0]
    lines = [f"  {c}: <b>{_esc(r[c])}</b>" for c in r.index if str(r[c]).strip() not in ("","nan","—")]

    oneri_str = ""
    if df_oz is not None and "Kod" in df_oz.columns:
        oz = df_oz[df_oz["Kod"].astype(str).str.strip().str.upper() == sym]
        if not oz.empty:
            oneri_str = str(oz.iloc[0].get("Öneri",""))

    prompt = (
        f"{sym} hedef fiyat verileri: {dict(r)}. Öneri: {oneri_str}. "
        "Hedef fiyat mevcut fiyata göre ne söylüyor? Alım fırsatı var mı? "
        "2-3 cümle, Türkçe."
    )
    ai_text = _ai(prompt, 200)

    return (
        f"🎯 <b>{sym} — Hedef Fiyat</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        + "\n".join(lines[:12])
        + f"\n\n<b>🤖 AI Yorum</b>\n{ai_text}"
    )


def cmd_temettu(top_n: int = 10) -> str:
    df = _read("takiptemettu")
    if df is None:
        return "⚠️ takiptemettu verisi yok."
    tv_col = next((c for c in df.columns if "Verim" in c or "Temettü" in c), None)
    if not tv_col:
        return "⚠️ Temettü verimi kolonu bulunamadı."
    df["Kod"] = df["Kod"].astype(str).str.strip().str.upper()
    df["_tv"] = _num(df[tv_col])
    df = df.dropna(subset=["_tv"]).nlargest(top_n, "_tv")

    rows = []
    for i, (_, r) in enumerate(df.iterrows(), 1):
        tv = float(r["_tv"])
        rows.append(
            f"  {i:2}. 💰 <code>{r['Kod']:<7}</code>  "
            f"Verim: <b>%{tv:.1f}</b>  "
            f"{_esc(str(r.get('Hisse Adı',''))[:16])}"
        )

    prompt = (
        f"En yüksek temettü verimli hisseler: "
        f"{', '.join(df['Kod'].tolist())}. "
        "Temettü yatırımı için değerlendirme, 2-3 cümle, Türkçe."
    )
    ai_text = _ai(prompt, 180)

    return (
        f"💰 <b>En Yüksek Temettü Verimi — Top {top_n}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        + "\n".join(rows)
        + f"\n\n<b>🤖 AI Yorum</b>\n{ai_text}"
    )


def cmd_yabanci(top_n: int = 10) -> str:
    df = _read("temelyabancioran")
    if df is None:
        return "⚠️ temelyabancioran verisi yok."
    df["Kod"] = df["Kod"].astype(str).str.strip().str.upper()
    deg_col = next((c for c in df.columns if "Değişim" in c), None)
    if not deg_col:
        return "⚠️ Değişim kolonu bulunamadı."
    df["_deg"] = _num(df[deg_col])

    girenler = df.nlargest(top_n, "_deg")
    cikanlar = df.nsmallest(top_n, "_deg")

    def fmt(rows, emoji):
        return "\n".join(
            f"  {emoji} <code>{r['Kod']:<7}</code>  {r['_deg']:+.3f}%  "
            f"{_esc(str(r.get('Hisse Adı',''))[:14])}"
            for _, r in rows.iterrows()
            if not pd.isna(r["_deg"])
        )

    smart_giris = int((df["_deg"] > 0).sum())
    smart_cikis = int((df["_deg"] < 0).sum())

    prompt = (
        f"Yabancı yatırımcı hareketi. Giriş yapılan: {', '.join(girenler['Kod'].head(5).tolist())}. "
        f"Çıkış yapılan: {', '.join(cikanlar['Kod'].head(5).tolist())}. "
        "Smart money ne söylüyor? 2-3 cümle, Türkçe."
    )
    ai_text = _ai(prompt, 200)

    return (
        f"👔 <b>Yabancı Yatırımcı Hareketi</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"  📈 Net Giriş: <b>{smart_giris}</b> hisse\n"
        f"  📉 Net Çıkış: <b>{smart_cikis}</b> hisse\n"
        f"\n<b>⬆️ En Fazla Alım</b>\n{fmt(girenler.head(5), '🟢')}\n"
        f"\n<b>⬇️ En Fazla Satım</b>\n{fmt(cikanlar.head(5), '🔴')}\n"
        f"\n<b>🤖 AI Yorum</b>\n{ai_text}"
    )


def cmd_performans_temel(top_n: int = 10) -> str:
    df = _read("temelperformans")
    if df is None:
        return "⚠️ temelperformans verisi yok."
    df["Kod"] = df["Kod"].astype(str).str.strip().str.upper()
    pct_cols = [c for c in df.columns if "%" in c or "Getiri" in c or "Performans" in c]
    if not pct_cols:
        return "⚠️ Performans kolonu bulunamadı."

    main_col = pct_cols[0]
    df["_p"] = _num(df[main_col])
    df = df.dropna(subset=["_p"]).sort_values("_p", ascending=False)

    yukselenler = df.head(top_n)
    dusenler    = df.tail(top_n)

    def fmt(rows, emoji):
        return "\n".join(
            f"  {emoji} <code>{r['Kod']:<7}</code>  "
            f"<b>{float(r['_p']):+.1f}%</b>  "
            f"{_esc(str(r.get('Hisse Adı',''))[:14])}"
            for _, r in rows.iterrows()
        )

    prompt = (
        f"Temel performans liderleri: {', '.join(yukselenler['Kod'].head(5).tolist())}. "
        f"Geride kalanlar: {', '.join(dusenler['Kod'].head(5).tolist())}. "
        "Performans farkı neden? 2 cümle, Türkçe."
    )
    ai_text = _ai(prompt, 180)

    return (
        f"📈 <b>Temel Performans Tablosu</b> ({main_col})\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>🏆 En Çok Yükselen</b>\n{fmt(yukselenler, '🟢')}\n"
        f"\n<b>📉 En Çok Düşen</b>\n{fmt(dusenler, '🔴')}\n"
        f"\n<b>🤖 AI Yorum</b>\n{ai_text}"
    )


def cmd_endeks() -> str:
    df = _read("endeksbist")
    if df is None:
        return "⚠️ endeksbist verisi yok."
    total = len(df)
    cols  = df.columns.tolist()

    # Öneri dağılımı varsa
    ozet_line = f"  Toplam {total} hisse"
    df_oz = _read("takipozet")
    al_ = tut_ = sat_ = 0
    if df_oz is not None and "Öneri" in df_oz.columns:
        al_  = int(df_oz["Öneri"].astype(str).str.upper().str.contains("AL",  na=False).sum())
        tut_ = int(df_oz["Öneri"].astype(str).str.upper().str.contains("TUT", na=False).sum())
        sat_ = int(df_oz["Öneri"].astype(str).str.upper().str.contains("SAT", na=False).sum())
        ozet_line = f"  🟢 AL:{al_}  🟡 TUT:{tut_}  🔴 SAT:{sat_}"

    # İlk 15 satır
    preview = df.head(15).to_string(index=False, max_cols=6)[:600]

    prompt = (
        f"BIST endeks bileşenleri. AL:{al_}, TUT:{tut_}, SAT:{sat_}. "
        "Genel endeks görünümü nasıl? 2 cümle, Türkçe."
    )
    ai_text = _ai(prompt, 150)

    return (
        f"📊 <b>BIST Endeks Özeti</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{ozet_line}\n"
        f"\n<code>{_esc(preview)}</code>\n"
        f"\n<b>🤖 AI Yorum</b>\n{ai_text}"
    )


def cmd_katilim_full(top_n: int = 5) -> str:
    """
    Katılım hisselerini AL/TUT/SAT + potansiyel + finansal verilerle listeler.
    """
    df_oz  = _read("takipozet")
    df_fin = _read("temelfinansal")
    df_yab = _read("temelyabancioran")
    df_ozet = _read("temelozet")
    if df_oz is None:
        return "⚠️ Veri bulunamadı."

    df = df_oz.copy()
    df["Kod"] = df["Kod"].astype(str).str.strip().str.upper()

    # Sektör ekle
    sek_col = None
    if df_ozet is not None and "Kod" in df_ozet.columns:
        sc = next((c for c in df_ozet.columns
                   if c.lower().replace("ö","o").replace("ü","u") in ("sektor","sektör","sector")), None)
        if sc:
            sek_col = sc
            ds = df_ozet[["Kod", sc]].copy()
            ds["Kod"] = ds["Kod"].astype(str).str.strip().str.upper()
            df = df.merge(ds, on="Kod", how="left")

    # Hisse adı
    ad_col = next((c for c in df.columns if "Hisse Adı" in c), None)

    # Katılım filtresi
    def _kat(row):
        return _is_katilim(
            row["Kod"],
            str(row[sek_col]).lower() if sek_col and sek_col in row.index else "",
            str(row[ad_col]) if ad_col else "",
        )

    df["_kat"] = df.apply(_kat, axis=1)
    df_k = df[df["_kat"]].copy()

    if df_k.empty:
        return "⚠️ Katılım uyumlu hisse bulunamadı."

    # F/K ekle
    if df_fin is not None and "Kod" in df_fin.columns and "F/K" in df_fin.columns:
        df_fin2 = df_fin[["Kod","F/K"]].copy()
        df_fin2["Kod"] = df_fin2["Kod"].astype(str).str.strip().str.upper()
        df_k = df_k.merge(df_fin2, on="Kod", how="left", suffixes=("","_f"))

    # Yabancı değişim
    if df_yab is not None and "Kod" in df_yab.columns:
        deg_col = next((c for c in df_yab.columns if "Değişim" in c), None)
        if deg_col:
            dy = df_yab[["Kod", deg_col]].copy()
            dy["Kod"] = dy["Kod"].astype(str).str.strip().str.upper()
            df_k = df_k.merge(dy, on="Kod", how="left", suffixes=("","_y"))

    pot_col = "Getiri Potansiyeli (%)"
    if pot_col not in df_k.columns:
        return "⚠️ Potansiyel kolonu yok."

    df_k["_pot"] = _num(df_k[pot_col])
    df_k["_pot_valid"] = df_k["_pot"].fillna(0)

    # Tüm öneriler — AL sıralaması önde
    al_mask  = df_k["Öneri"].astype(str).str.upper().str.contains("AL",  na=False)
    tut_mask = df_k["Öneri"].astype(str).str.upper().str.contains("TUT", na=False)
    sat_mask = df_k["Öneri"].astype(str).str.upper().str.contains("SAT", na=False)

    df_al  = df_k[al_mask].nlargest(top_n, "_pot_valid")
    df_tut = df_k[tut_mask].nlargest(3, "_pot_valid")
    df_sat = df_k[sat_mask].head(3)

    def fmt_rows(rows, prefix):
        lines = []
        for _, r in rows.iterrows():
            pot   = float(r.get("_pot_valid", 0))
            fk    = r.get("F/K","—") if "F/K" in r.index else "—"
            deg_c = next((c for c in r.index if "Değişim" in c and "_y" in c), None)
            yab   = f"Yab:{float(_num(pd.Series([r[deg_c]])).iloc[0]):+.2f}%" if deg_c and not pd.isna(r.get(deg_c)) else ""
            ad    = str(r.get(ad_col,"")) if ad_col else ""
            lines.append(
                f"  {prefix} <code>{r['Kod']:<7}</code>  "
                f"Pot:<b>%{pot:.1f}</b>  F/K:{_esc(fk)}  "
                f"{yab}  <i>{_esc(ad[:14])}</i>"
            )
        return "\n".join(lines)

    al_count  = int(al_mask.sum())
    tut_count = int(tut_mask.sum())
    sat_count = int(sat_mask.sum())

    prompt = (
        f"Katılım uyumlu hisseler: AL={al_count}, TUT={tut_count}, SAT={sat_count}. "
        f"Top AL: {', '.join(df_al['Kod'].tolist())}. "
        "Katılım yatırımcısı için 3 madde öneri, Türkçe."
    )
    ai_text = _ai(prompt, 280)

    result = (
        f"☪️ <b>Katılım Hisseleri — Detaylı Analiz</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"  🟢 AL:{al_count}  🟡 TUT:{tut_count}  🔴 SAT:{sat_count}  "
        f"(Toplam {len(df_k)} katılım hissesi)\n"
    )
    if not df_al.empty:
        result += f"\n<b>🟢 AL Önerileri (Top {top_n})</b>\n{fmt_rows(df_al, '🟢')}\n"
    if not df_tut.empty:
        result += f"\n<b>🟡 TUT Önerileri</b>\n{fmt_rows(df_tut, '🟡')}\n"
    if not df_sat.empty:
        result += f"\n<b>🔴 SAT Önerileri — Dikkat</b>\n{fmt_rows(df_sat, '🔴')}\n"
    result += f"\n<b>🤖 AI Yorum</b>\n{ai_text}"
    return result
