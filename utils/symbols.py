"""
BIST sembol yönetimi — tam evren, sektör haritası, format dönüşümleri.

Tüm sembol listeleri config.settings üzerinden gelir.
TradingView Scanner API ile günlük güncelleme desteklenir.
"""
from __future__ import annotations

import requests
import streamlit as st

from config.settings import BIST_30, BIST_100, BIST_ALL_KNOWN

# ─────────────────────────────────────────────────────────────────────────────
# Sektör haritası  (ticker → sektör)
# Anahtar: ".IS" eki YOK  (ör. "THYAO", "GARAN")
# ─────────────────────────────────────────────────────────────────────────────
SECTOR_MAP: dict[str, str] = {
    # Bankacılık
    "GARAN":  "Bankacılık", "AKBNK":  "Bankacılık", "YKBNK":  "Bankacılık",
    "ISCTR":  "Bankacılık", "HALKB":  "Bankacılık", "VAKBN":  "Bankacılık",
    "ALBRK":  "Bankacılık", "SKBNK":  "Bankacılık", "TSKB":   "Bankacılık",
    "ICBCT":  "Bankacılık", "ATAGY":  "Bankacılık", "TBNK":   "Bankacılık",
    "FZLGY":  "Bankacılık", "FINSN":  "Bankacılık",
    # Holding & Yatırım
    "KCHOL":  "Holding",    "SAHOL":  "Holding",    "SISE":   "Holding",
    "TKFEN":  "Holding",    "DOHOL":  "Holding",    "ENKAI":  "Holding",
    "MPARK":  "Holding",    "GLYHO":  "Holding",    "TAVHL":  "Holding",
    "ACSEL":  "Holding",    "AGHOL":  "Holding",    "TURSG":  "Holding",
    "IHLAS":  "Holding",    "NTHOL":  "Holding",    "DGKLB":  "Holding",
    "GLRYH":  "Holding",    "GLBMD":  "Holding",    "IHLGM":  "Holding",
    "ITTFH":  "Holding",    "SAFKR":  "Holding",    "POLHO":  "Holding",
    # Havacılık & Ulaşım
    "THYAO":  "Havacılık",  "PGSUS":  "Havacılık",  "CLEBI":  "Havacılık",
    # Enerji & Petrokimya
    "TUPRS":  "Enerji",     "PETKM":  "Enerji",     "AYGAZ":  "Enerji",
    "ODAS":   "Enerji",     "ZOREN":  "Enerji",     "AKSEN":  "Enerji",
    "AKSUE":  "Enerji",     "EUPWR":  "Enerji",     "AKENR":  "Enerji",
    "BIOEN":  "Enerji",     "CWENE":  "Enerji",     "GWIND":  "Enerji",
    "CENG":   "Enerji",     "ZEDUR":  "Enerji",     "WNDSL":  "Enerji",
    "OREN":   "Enerji",     "TBORG":  "Enerji",     "TRILC":  "Enerji",
    "AKFGY":  "Enerji",
    # Teknoloji & Telekomünikasyon
    "TCELL":  "Teknoloji",  "TTKOM":  "Teknoloji",  "ASELS":  "Teknoloji",
    "LOGO":   "Teknoloji",  "INDES":  "Teknoloji",  "ESCOM":  "Teknoloji",
    "NETAS":  "Teknoloji",  "FONET":  "Teknoloji",  "DGATE":  "Teknoloji",
    "OBASE":  "Teknoloji",  "SMART":  "Teknoloji",  "PCILT":  "Teknoloji",
    "ARMADA": "Teknoloji",  "BSVS":   "Teknoloji",  "DESPC":  "Teknoloji",
    "KAREL":  "Teknoloji",  "INTEM":  "Teknoloji",  "VBTYZ":  "Teknoloji",
    # Otomotiv & Makine
    "FROTO":  "Otomotiv",   "TOASO":  "Otomotiv",   "ARCLK":  "Otomotiv",
    "OTKAR":  "Otomotiv",   "DOAS":   "Otomotiv",   "TTRAK":  "Otomotiv",
    "BRISA":  "Otomotiv",   "KLMSN":  "Otomotiv",   "ASUZU":  "Otomotiv",
    "MTMTR":  "Otomotiv",   "JANTS":  "Otomotiv",
    # GYO & İnşaat
    "EKGYO":  "GYO",        "TRGYO":  "GYO",        "ISGYO":  "GYO",
    "OZGYO":  "GYO",        "VKGYO":  "GYO",        "TSGYO":  "GYO",
    "NUGYO":  "GYO",        "RGYAS":  "GYO",        "IDGYO":  "GYO",
    "HLGYO":  "GYO",        "PSGYO":  "GYO",        "YGYO":   "GYO",
    "ALGYO":  "GYO",        "AGROT":  "GYO",        "DEGYO":  "GYO",
    # Perakende
    "MGROS":  "Perakende",  "BIMAS":  "Perakende",  "SOKM":   "Perakende",
    "ADESE":  "Perakende",  "MKTES":  "Perakende",  "KOTON":  "Perakende",
    # Gıda & İçecek
    "ULKER":  "Gıda",       "CCOLA":  "Gıda",       "AEFES":  "Gıda",
    "PRKME":  "Gıda",       "TATGD":  "Gıda",       "KENT":   "Gıda",
    "PNSUT":  "Gıda",       "HURGZ":  "Gıda",       "KNFRT":  "Gıda",
    "DOBUR":  "Gıda",       "AVOD":   "Gıda",       "BANVT":  "Gıda",
    "TUKAS":  "Gıda",       "YYLGD":  "Gıda",
    # Metal & Madencilik
    "EREGL":  "Metal",      "KRDMD":  "Metal",      "KRDMB":  "Metal",
    "BRSAN":  "Metal",      "KAPLM":  "Metal",      "KUTPO":  "Metal",
    "BURCE":  "Metal",      "BURVA":  "Metal",      "ERCB":   "Metal",
    "KARTN":  "Metal",      "BFREN":  "Metal",
    "ISDMR":  "Madencilik",
    # Çimento & İnşaat Malzemeleri
    "CIMSA":  "Çimento",    "AKCNS":  "Çimento",    "NUHCM":  "Çimento",
    "GOLTS":  "Çimento",    "OYAKC":  "Çimento",    "BTCIM":  "Çimento",
    "SANKO":  "Çimento",    "BSOKE":  "Çimento",    "KONYA":  "Çimento",
    # Kimya & Plastik
    "SASA":   "Kimya",      "GUBRF":  "Kimya",      "SODA":   "Kimya",
    "EPLAS":  "Kimya",      "EMKEL":  "Kimya",      "ALKIM":  "Kimya",
    "BAGFS":  "Kimya",      "BERA":   "Kimya",      "EGGUB":  "Kimya",
    "GUBRE":  "Kimya",      "DYOBY":  "Kimya",
    # Cam & Seramik
    "IZOCM":  "Cam",        "IZFAS":  "Cam",        "SOKE":   "Cam",
    # Sigorta & Finans
    "AKGRT":  "Sigorta",    "RAYSG":  "Sigorta",    "ANHYT":  "Sigorta",
    "MPARK":  "Sigorta",
    # Tekstil & Moda
    "MAVI":   "Tekstil",    "KLNMA":  "Tekstil",    "BOSSA":  "Tekstil",
    "DAGI":   "Tekstil",    "ARSAN":  "Tekstil",    "SKTAS":  "Tekstil",
    "SUWEN":  "Tekstil",    "MNDRS":  "Tekstil",    "BRMEN":  "Tekstil",
    "ATEKS":  "Tekstil",    "SMEN":   "Tekstil",
    # Elektronik & Savunma
    "VESTL":  "Elektronik",
    # İlaç & Sağlık
    "DEVA":   "İlaç",       "ECZYT":  "İlaç",       "ECILC":  "İlaç",
    "BMEKS":  "Sağlık",     "HEKTS":  "Sağlık",
    # Spor Kulüpleri
    "BJKAS":  "Spor",       "FENER":  "Spor",       "GSRAY":  "Spor",
    "TSPOR":  "Spor",
    # Turizm & Otelcilik
    "BRYAT":  "Turizm",     "NTTUR":  "Turizm",     "METUR":  "Turizm",
    # Medya
    "IHGZT":  "Medya",
    # Lojistik & Ulaşım
    "RYSAS":  "Lojistik",   "RNSAS":  "Lojistik",   "URAS":   "Lojistik",
    "MARTI":  "Lojistik",
    # Tarım
    "ETYAT":  "Tarım",      "EMTAS":  "Tarım",      "GEREL":  "Tarım",
    # Diğer Sanayi
    "PRKAB":  "Sanayi",     "SELEC":  "Sanayi",     "GENIL":  "Sanayi",
    "ADEL":   "Sanayi",     "IHEVA":  "Sanayi",     "KARSN":  "Sanayi",
    "ORGE":   "Sanayi",     "PENGD":  "Sanayi",     "TLMAN":  "Sanayi",
    "YATAS":  "Sanayi",     "GENTS":  "Sanayi",     "PENTA":  "Sanayi",
    "OSTIM":  "Sanayi",     "TRABZ":  "Sanayi",     "UNLU":   "Sanayi",
}

# ─────────────────────────────────────────────────────────────────────────────

_UNIVERSE: dict[str, list[str]] = {
    "30":  BIST_30,
    "100": BIST_100,
    "all": BIST_ALL_KNOWN,
}


def get_bist_tickers(universe: str = "all") -> dict[str, str]:
    """
    {display_label: yf_symbol} döner, alfabetik sıralı.

    display_label = ".IS" eki olmayan ticker  (ör. "THYAO")
    yf_symbol     = yfinance formatı           (ör. "THYAO.IS")

    universe: "30" | "100" | "all"
    """
    source = _UNIVERSE.get(universe, BIST_ALL_KNOWN)
    return {s.replace(".IS", ""): s for s in sorted(set(source))}


def get_sector_groups(universe: str = "all") -> dict[str, list[str]]:
    """
    {sektör_adı: [ticker, ...]} döner.
    Sektörü bilinmeyen semboller "Diğer" grubuna girer.
    Her grup içinde semboller alfabetik sıralı.
    """
    tickers = get_bist_tickers(universe)
    groups: dict[str, list[str]] = {}
    for ticker in tickers:
        sector = SECTOR_MAP.get(ticker, "Diğer")
        groups.setdefault(sector, []).append(ticker)
    return {k: sorted(v) for k, v in sorted(groups.items())}


def tv_to_yf(tv_sym: str) -> str:
    """TradingView → yfinance format dönüşümü.  "BIST:THYAO" → "THYAO.IS"."""
    if tv_sym.startswith("BIST:"):
        return tv_sym[5:] + ".IS"
    return tv_sym


@st.cache_data(ttl=86400, show_spinner=False)
def fetch_full_bist() -> dict[str, str]:
    """
    TradingView Scanner API'den tüm BIST evrenini çeker (~500-600 sembol).
    BIST_ALL_KNOWN ile birleştirilir ve alfabetik sıralanır.
    24 saatlik önbellek — uygulama başlangıcında bir kez çalışır.

    Ağ isteği başarısız olursa BIST_ALL_KNOWN'a döner (graceful fallback).
    """
    tv_tickers: list[str] = []
    try:
        resp = requests.post(
            "https://scanner.tradingview.com/turkey/scan",
            json={
                "columns": ["name", "market_cap_basic"],
                "range":   [0, 1000],
                "sort":    {"sortBy": "market_cap_basic", "sortOrder": "desc"},
            },
            headers={
                "Content-Type": "application/json",
                "User-Agent":   "Mozilla/5.0",
            },
            timeout=15,
        )
        if resp.status_code == 200:
            for item in resp.json().get("data", []):
                raw    = ((item.get("d") or [None])[0] or "")
                ticker = raw.replace("BIST:", "").strip()
                if ticker:
                    tv_tickers.append(ticker)
    except Exception:
        pass

    # Birleştir: statik BIST_ALL_KNOWN + dinamik TV listesi
    base   = {s.replace(".IS", "") for s in BIST_ALL_KNOWN}
    merged = sorted(base | set(tv_tickers))
    return {t: f"{t}.IS" for t in merged}
