"""
FinSentinel — Merkezi Konfigürasyon
config/settings.py
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent.parent

# === API Anahtarları ===
ANTHROPIC_API_KEY   = os.getenv("ANTHROPIC_API_KEY", "")   # artık kullanılmıyor
GEMINI_API_KEY      = os.getenv("GEMINI_API_KEY", "")       # ücretsiz: aistudio.google.com/app/apikey
GROQ_API_KEY        = os.getenv("GROQ_API_KEY", "")         # ücretsiz+hızlı: console.groq.com
TCMB_API_KEY        = os.getenv("TCMB_API_KEY", "")
ALPHA_VANTAGE_KEY   = os.getenv("ALPHA_VANTAGE_API_KEY", "")
COINGECKO_API_KEY   = os.getenv("COINGECKO_API_KEY", "")
TELEGRAM_BOT_TOKEN  = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID    = os.getenv("TELEGRAM_CHAT_ID", "")
# Birden fazla chat ID (kişisel DM + grup) virgülle ayır:
# TELEGRAM_ALLOWED_CHATS=123456789,-1001234567890
TELEGRAM_ALLOWED_CHATS = os.getenv("TELEGRAM_ALLOWED_CHATS", "")
TV_USERNAME         = os.getenv("TV_USERNAME", "")   # TradingView kullanıcı adı
TV_PASSWORD         = os.getenv("TV_PASSWORD", "")   # TradingView şifresi

# === Massive Market Data API ===
MASSIVE_MARKET_API_KEY = os.getenv("MASSIVE_MARKET_API_KEY", "")

# === Apify ===
APIFY_API_KEY = os.getenv("APIFY_API_KEY", "")

# === Uygulama ===
APP_ENV      = os.getenv("APP_ENV", "development")
APP_PORT     = int(os.getenv("APP_PORT", 8501))
APP_HOST     = os.getenv("APP_HOST", "0.0.0.0")
APP_PASSWORD = os.getenv("APP_PASSWORD", "finsentinel2024")

# === Kullanıcılar ===
# Şifreler .env dosyasından okunur — kaynak kodda plaintext bulunmaz.
# .env'e ekle:  USER_HSALDIRAN_PASS=<şifreniz>  USER_ADMIN_PASS=<şifreniz>
import hashlib as _hl

def _pw(env_key: str) -> str:
    """Şifreyi .env'den okur, SHA-256 hash olarak saklar."""
    raw = os.getenv(env_key, "")
    return _hl.sha256(raw.encode()).hexdigest() if raw else ""

USERS = {
    "hsaldiran": {
        "password_hash": _pw("USER_HSALDIRAN_PASS"),
        "role": "user",
        "display": "Hasan Saldıran",
    },
    "admin": {
        "password_hash": _pw("USER_ADMIN_PASS"),
        "role": "admin",
        "display": "Admin",
    },
}

# === Veritabanı ===
DB_PATH = BASE_DIR / os.getenv("DB_PATH", "data/finsentinel.db")

# === Cache ===
CACHE_TTL = {
    "tick":    30,        # saniye — anlık fiyat
    "hourly":  3600,      # saatlik veri
    "daily":   86400,     # günlük veri
    "weekly":  604800,    # haftalık
}

# === BIST Endeksleri ===
BIST_INDEX = [
    "XU100.IS",   # BIST 100
    "XU030.IS",   # BIST 30
    "XBANK.IS",   # BIST Banka
    "XUSIN.IS",   # BIST Sanayi
    "XHOLD.IS",   # BIST Holding
    "XGIDA.IS",   # BIST Gıda
    "XELKT.IS",   # BIST Elektrik
    "XTCRT.IS",   # BIST Ticaret
]

# === BIST 30 (Fiili Endeks Bileşenleri) ===
BIST_30 = [
    "GARAN.IS", "AKBNK.IS", "THYAO.IS", "KCHOL.IS", "SAHOL.IS",
    "TUPRS.IS", "ISCTR.IS", "YKBNK.IS", "BIMAS.IS", "SISE.IS",
    "TOASO.IS", "FROTO.IS", "ARCLK.IS", "TCELL.IS", "TTKOM.IS",
    "ASELS.IS", "PGSUS.IS", "ENKAI.IS", "EREGL.IS", "PETKM.IS",
    "EKGYO.IS", "MGROS.IS", "HALKB.IS", "VAKBN.IS", "KRDMD.IS",
    "ODAS.IS",  "TAVHL.IS", "DOHOL.IS", "TKFEN.IS", "OYAKC.IS",
]

# === BIST 100 (Genişletilmiş Temsili Liste) ===
BIST_100 = [
    # Bankacılık
    "GARAN.IS", "AKBNK.IS", "ISCTR.IS", "YKBNK.IS", "HALKB.IS",
    "VAKBN.IS", "ALBRK.IS", "SKBNK.IS", "TSKB.IS",
    # Holding & Yatırım
    "KCHOL.IS", "SAHOL.IS", "SISE.IS", "TKFEN.IS", "DOHOL.IS",
    "ENKAI.IS", "MPARK.IS", "GLYHO.IS", "TAVHL.IS", "ACSEL.IS", "AGHOL.IS",
    # Havacılık & Ulaşım
    "THYAO.IS", "PGSUS.IS", "CLEBI.IS",
    # Enerji & Petrokimya
    "TUPRS.IS", "PETKM.IS", "AYGAZ.IS", "ODAS.IS", "ZOREN.IS",
    "AKSEN.IS", "AKSUE.IS", "EUPWR.IS", "AKENR.IS",
    # Telekomünikasyon & Teknoloji
    "TCELL.IS", "TTKOM.IS", "ASELS.IS", "LOGO.IS",
    "INDES.IS", "ESCOM.IS", "NETAS.IS", "FONET.IS", "DGATE.IS",
    # Otomotiv
    "FROTO.IS", "TOASO.IS", "ARCLK.IS", "OTKAR.IS", "DOAS.IS",
    "TTRAK.IS", "BRISA.IS", "KLMSN.IS",
    # GYO & İnşaat
    "EKGYO.IS", "TRGYO.IS", "ISGYO.IS", "OZGYO.IS",
    "VKGYO.IS", "TSGYO.IS", "NUGYO.IS", "RGYAS.IS",
    # Perakende & Gıda
    "MGROS.IS", "BIMAS.IS", "ULKER.IS", "CCOLA.IS", "SOKM.IS",
    "AEFES.IS", "PRKME.IS", "TATGD.IS", "KENT.IS", "PNSUT.IS",
    # Metal, Madencilik & Çimento
    "EREGL.IS", "KRDMD.IS", "KRDMB.IS", "ISDMR.IS",   # KOZAL/KOZAA delisted → ISDMR (İskenderun Demir)
    "CIMSA.IS", "AKCNS.IS", "NUHCM.IS", "GOLTS.IS", "OYAKC.IS",
    # Kimya & Cam
    "SASA.IS", "GUBRF.IS", "VESTL.IS",   # SODA.IS delisted çıkarıldı
    # Sigorta & Finans
    "AKGRT.IS", "RAYSG.IS", "ANHYT.IS",
    # Tekstil & Moda
    "MAVI.IS", "KLNMA.IS",
    # Diğer Sanayi
    "KONYA.IS", "PRKAB.IS", "SELEC.IS", "TURSG.IS", "GENIL.IS",
    "ADEL.IS",  "IHEVA.IS", "KARSN.IS", "ORGE.IS",  "PENGD.IS",
    "RYSAS.IS", "TLMAN.IS", "YATAS.IS", "GENTS.IS",
]

# === Tüm Bilinen BIST Hisseleri (~300+) ===
# Not: 404 veren, delistenmiş veya Türkçe karakterli semboller kaldırıldı.
BIST_ALL_KNOWN = BIST_100 + [
    # Ek Bankacılık & Finans
    "ICBCT.IS", "ATAGY.IS", "FZLGY.IS",
    # Ek Holding & Yatırım
    "DGKLB.IS", "GLRYH.IS", "GLBMD.IS", "NTHOL.IS", "IHLAS.IS",
    "IHLGM.IS", "ITTFH.IS",
    # Ek Enerji & Sanayi
    "ZEDUR.IS", "GWIND.IS", "CWENE.IS", "BIOEN.IS", "TBORG.IS", "TRILC.IS",
    # Ek Teknoloji & Yazılım
    "PCILT.IS", "SMART.IS", "OBASE.IS", "DESPC.IS", "KAREL.IS",
    "INTEM.IS", "VBTYZ.IS", "ARDYZ.IS",
    # Ek Otomotiv & Makine
    "ASUZU.IS", "JANTS.IS",
    # Ek GYO
    "IDGYO.IS", "HLGYO.IS", "PSGYO.IS", "ALGYO.IS", "AGROT.IS",
    # Ek Perakende, Gıda & İçecek
    "HURGZ.IS", "KNFRT.IS", "AVOD.IS",
    "BANVT.IS", "TUKAS.IS", "BSOKE.IS", "YYLGD.IS",
    # Ek Tekstil & Hazırgiyim
    "BOSSA.IS", "DAGI.IS", "ARSAN.IS", "SKTAS.IS", "SUWEN.IS",
    "MNDRS.IS", "BRMEN.IS", "ATEKS.IS",
    # Ek Kimya & Plastik
    "EPLAS.IS", "EMKEL.IS", "ALKIM.IS", "BAGFS.IS", "BERA.IS",
    "EGGUB.IS", "DYOBY.IS",
    # Ek Çimento & İnşaat Malzemeleri
    "BTCIM.IS", "ADESE.IS",
    # Ek Metal & Demir-Çelik
    "KAPLM.IS", "BRSAN.IS", "KUTPO.IS", "BURCE.IS", "BURVA.IS",
    "ERCB.IS", "KARTN.IS", "BFREN.IS",
    # Ek Tarım & Hayvancılık
    "ETYAT.IS", "GEREL.IS", "GENTS.IS",
    # Ek İlaç & Sağlık
    "DEVA.IS", "ECZYT.IS", "ECILC.IS", "BMEKS.IS", "HEKTS.IS",
    # Ek Medya & Eğlence
    "BJKAS.IS", "FENER.IS", "GSRAY.IS", "TSPOR.IS", "IHGZT.IS",
    # Ek Lojistik & Depo
    "RYSAS.IS", "MARTI.IS",
    # Ek Turizm & Otelcilik
    "BRYAT.IS", "NTTUR.IS",
    # Ek Cam & Seramik
    "IZOCM.IS", "IZFAS.IS", "SOKE.IS",
    # Ek Enerji (Yenilenebilir)
    "EUPWR.IS", "AKFGY.IS",
    # Ek Madencilik
    "ISDMR.IS",
    # Ek Diğer (doğrulanmış)
    "OYAYO.IS", "POLHO.IS", "SAMAT.IS", "SANFM.IS", "SEYKM.IS",
    "TLMAN.IS", "TRCAS.IS", "TUREX.IS", "ULUFA.IS",
    "UNLU.IS",  "USAK.IS",  "YBTAS.IS",
    "YKSLN.IS", "YONGA.IS", "DENGE.IS", "DOKTA.IS",
    "DURDO.IS", "EDIP.IS",  "FADE.IS",  "GESAN.IS", "GMTAS.IS",
    "GOODY.IS", "GRSEL.IS", "HDFGS.IS", "KATMR.IS",
    "KAYSE.IS", "KORDS.IS", "KOTON.IS", "KRONT.IS", "LKMNH.IS",
    "LMKDC.IS", "MAKTK.IS", "MANAS.IS",
    "MEDTR.IS", "MEGMT.IS", "MEPET.IS", "MRDIN.IS", "MRSHL.IS", "MTRKS.IS",
    "NATEN.IS", "NIBAS.IS", "ONCSM.IS",
    "OSTIM.IS", "PAMEL.IS", "PENTA.IS", "PSDTC.IS",
    "REEDR.IS", "RTALB.IS", "SDTTR.IS", "TEKTU.IS", "TERA.IS",
    "TUCLK.IS", "TURGG.IS", "FLAP.IS",
]

# Tekrar edenleri temizle
BIST_ALL_KNOWN = list(dict.fromkeys(BIST_ALL_KNOWN))

# Geriye dönük uyumluluk için BIST_SYMBOLS = BIST_100
BIST_SYMBOLS = list(dict.fromkeys(BIST_100))

# === Forex Pariteleri (Genişletilmiş) ===
FOREX_PAIRS = [
    # TRY pariteleri
    "USDTRY=X", "EURTRY=X", "GBPTRY=X", "JPYTRY=X",
    "CHFTRY=X", "CADTRY=X", "AUDTRY=X",  # RUBTRY=X Yahoo Finance'de mevcut değil
    # Major paritetler
    "EURUSD=X", "GBPUSD=X", "USDJPY=X", "USDCHF=X",
    "AUDUSD=X", "USDCAD=X", "NZDUSD=X", "EURGBP=X",
    "EURJPY=X", "GBPJPY=X",
]

# Forex etiketleri
FOREX_LABELS = {
    "USDTRY=X": "USD/TRY", "EURTRY=X": "EUR/TRY",
    "GBPTRY=X": "GBP/TRY", "JPYTRY=X": "JPY/TRY",
    "CHFTRY=X": "CHF/TRY", "CADTRY=X": "CAD/TRY",
    "AUDTRY=X": "AUD/TRY",
    "EURUSD=X": "EUR/USD", "GBPUSD=X": "GBP/USD",
    "USDJPY=X": "USD/JPY", "USDCHF=X": "USD/CHF",
    "AUDUSD=X": "AUD/USD", "USDCAD=X": "USD/CAD",
    "NZDUSD=X": "NZD/USD", "EURGBP=X": "EUR/GBP",
    "EURJPY=X": "EUR/JPY", "GBPJPY=X": "GBP/JPY",
}

# === Kripto Paralar (Genişletilmiş) ===
CRYPTO_SYMBOLS = [
    # Majörler
    "BTC-USD", "ETH-USD", "BNB-USD", "SOL-USD", "XRP-USD",
    "ADA-USD", "AVAX-USD", "DOT-USD", "POL-USD",  "LINK-USD",
    # Altcoinler
    "DOGE-USD", "LTC-USD", "ATOM-USD", "AAVE-USD",
    "TRX-USD",  "NEAR-USD", "ALGO-USD", "VET-USD",
    "SAND-USD", "MANA-USD", "AXS-USD", "CRO-USD", "FIL-USD",
    "ICP-USD",  "EGLD-USD", "THETA-USD","XLM-USD", "ETC-USD",
]

# === Emtia / Madenler (Tam Liste) ===
COMMODITY_SYMBOLS = {
    # Kıymetli Madenler
    "Altın (XAU/USD)":      "GC=F",
    "Gümüş (XAG/USD)":     "SI=F",
    "Platin (XPT/USD)":    "PL=F",
    "Paladyum (XPD/USD)":  "PA=F",
    # Enerji
    "Ham Petrol (WTI)":    "CL=F",
    "Brent Petrol":        "BZ=F",   # Yahoo Finance Brent futures
    "Doğalgaz":            "NG=F",
    "Isıtma Yağı":         "HO=F",
    "Benzin (RBOB)":       "RB=F",
    # Endüstriyel Metaller
    "Bakır":               "HG=F",
    "Alüminyum":           "ALI=F",
    "Çelik":               "HRC=F",
    # Tarım
    "Buğday":              "ZW=F",
    "Mısır":               "ZC=F",
    "Soya Fasulyesi":      "ZS=F",
    "Şeker":               "SB=F",
    "Kahve":               "KC=F",
    "Kakao":               "CC=F",
    "Pamuk":               "CT=F",
}

# === Dünya Borsaları (Genişletilmiş) ===
WORLD_INDICES = {
    # Türkiye
    "BIST 100 (TR)":          "XU100.IS",
    "BIST 30 (TR)":           "XU030.IS",
    # Amerika
    "S&P 500 (ABD)":          "^GSPC",
    "Nasdaq 100 (ABD)":       "^NDX",
    "Dow Jones (ABD)":        "^DJI",
    "Russell 2000 (ABD)":     "^RUT",
    "VIX (Korku Endeksi)":    "^VIX",
    # Avrupa
    "DAX (Almanya)":          "^GDAXI",
    "FTSE 100 (İngiltere)":   "^FTSE",
    "CAC 40 (Fransa)":        "^FCHI",
    "Euro Stoxx 50":          "^STOXX50E",
    "AEX (Hollanda)":         "^AEX",
    "SMI (İsviçre)":          "^SSMI",
    "IBEX 35 (İspanya)":      "^IBEX",
    # Asya-Pasifik
    "Nikkei 225 (Japonya)":   "^N225",
    "Hang Seng (HK)":         "^HSI",
    "Shanghai (Çin)":         "000001.SS",
    "Kospi (G. Kore)":        "^KS11",
    "ASX 200 (Avustralya)":   "^AORD",
    "Sensex (Hindistan)":     "^BSESN",
    # Diğer
    "Bovespa (Brezilya)":     "^BVSP",
    "TSX (Kanada)":           "^GSPTSE",
    "Tadawul (S. Arabistan)": "^TASI.SR",
}

# === TCMB Veri Serileri ===
TCMB_SERIES = {
    "TUFE_Yillik":      "TP.FG.J0",
    "TUFE_Aylik":       "TP.FG.J01",
    "UFE_Yillik":       "TP.FG.J2",
    "Politika_Faizi":   "TP.MB.S.AOFON",
    "USD_TRY_Kur":      "TP.DK.USD.A.YTL",
    "EUR_TRY_Kur":      "TP.DK.EUR.A.YTL",
    "Rezerv_Doviz":     "TP.AB.B1",
    "M2_Para_Arzi":     "TP.MA2.TL",
    "Buyume_GDP":       "TP.GSYIHB.G",
    "Isizlik":          "TP.TIG01",
    "Cari_Denge":       "TP.OB.A01",
}

# === Haber RSS Kaynakları ===
NEWS_RSS_FEEDS = {
    # ── Türkiye — Araştırma & Borsa ─────────────────────────────────────────
    "İş Yatırım Araştırma": "https://arastirma.isyatirim.com.tr/feed/",
    "KAP":                  "https://www.kap.org.tr/tr/duyuru/rss",
    # ── Türkiye — Genel Ekonomi ─────────────────────────────────────────────
    "Dünya Bülteni":        "https://www.dunya.com/rss/ekonomi.xml",
    "Bloomberg HT":         "https://www.bloomberght.com/rss",
    "Ekonomim.com":         "https://www.ekonomim.com/rss.xml",
    "Haberler Ekonomi":     "https://www.haberler.com/rss/ekonomi-haberleri.xml",
    "Mynet Finans":         "https://finans.mynet.com/rss/haber",
    "Para Analiz":          "https://www.paraanaliz.com/feed/",
    "Finans Gündem":        "https://www.finansgundem.com/rss.xml",
    "NTV Para":             "https://www.ntv.com.tr/ekonomi.rss",
    # ── Global ──────────────────────────────────────────────────────────────
    "Reuters Business":     "https://feeds.reuters.com/reuters/businessNews",
    "Investing TR":         "https://tr.investing.com/rss/news.rss",
    "Yahoo Finance":        "https://finance.yahoo.com/news/rssindex",
    # ── Kripto ──────────────────────────────────────────────────────────────
    "CoinTelegraph":        "https://cointelegraph.com/rss/tag/altcoins",
    "CryptoSlate":          "https://cryptoslate.com/feed/",
    "CoinDesk":             "https://www.coindesk.com/arc/outboundfeeds/rss/",
}

# İş Yatırım Araştırma feed URL'si (diğer modüllerde doğrudan kullanım için)
ISYATIRIM_ARASTIRMA_FEED = "https://arastirma.isyatirim.com.tr/feed/"

# === Periyot Etiketleri ===
PERIODS = {
    "1g":  {"yf": "1d",  "label": "1 Gün"},
    "1h":  {"yf": "5d",  "label": "1 Hafta"},
    "1a":  {"yf": "1mo", "label": "1 Ay"},
    "3a":  {"yf": "3mo", "label": "3 Ay"},
    "6a":  {"yf": "6mo", "label": "6 Ay"},
    "1y":  {"yf": "1y",  "label": "1 Yıl"},
    "5y":  {"yf": "5y",  "label": "5 Yıl"},
    "10y": {"yf": "10y", "label": "10 Yıl"},
    "max": {"yf": "max", "label": "Tüm Zamanlar"},
}

# === Zaman Dilimleri ===
TIMEZONE = "Europe/Istanbul"

# === Teknik İndikatörler ===
TA_CONFIG = {
    "RSI_period":    14,
    "MACD_fast":     12,
    "MACD_slow":     26,
    "MACD_signal":   9,
    "BB_period":     20,
    "BB_std":        2,
    "SMA_periods":   [20, 50, 200],
    "EMA_periods":   [9, 21, 55],
    "ATR_period":    14,
    "STOCH_k":       14,
    "STOCH_d":       3,
}

# === Auto-Refresh Süresi (saniye) ===
AUTO_REFRESH_INTERVAL = 30   # 30 saniyede bir yenile

# === Renk Teması (Premium Dark) ===
THEME = {
    "bg_dark":      "#0a0e1a",
    "bg_card":      "#111827",
    "bg_card2":     "#1a2236",
    "bg_input":     "#1f2d45",
    "border":       "#1e3a5f",
    "border_light": "#2a4a6b",
    "text_primary": "#e2eaf5",
    "text_muted":   "#7a93b0",
    "text_dim":     "#4a6080",
    "green":        "#00d4aa",
    "green_dark":   "#005a47",
    "red":          "#ff4d6a",
    "red_dark":     "#5a0020",
    "yellow":       "#ffd166",
    "gold":         "#f7c948",
    "blue":         "#4da6ff",
    "blue_dark":    "#0d2a4a",
    "purple":       "#c77dff",
    "orange":       "#ff9a3c",
    "cyan":         "#00d4ff",
    "gradient_1":   "linear-gradient(135deg, #0a0e1a 0%, #0d1b35 100%)",
    "gradient_2":   "linear-gradient(135deg, #111827 0%, #1a2236 100%)",
    "glow_green":   "0 0 20px rgba(0,212,170,0.15)",
    "glow_red":     "0 0 20px rgba(255,77,106,0.15)",
    "glow_blue":    "0 0 20px rgba(77,166,255,0.15)",
}
# === Katılım Endeksi & Şirket Bilgileri ===
KATILIM_30_HISSELER = {
    "ASELS": {"ad": "Aselsan Elektronik"}, "TCELL": {"ad": "Turkcell İletişim"},
    "TTKOM": {"ad": "Türk Telekomunikasyon"}, "NETAS": {"ad": "Netaş Telekomünikasyon"},
    "LOGO":  {"ad": "Logo Yazılım"}, "KFEIN": {"ad": "Kafein Yazılım"},
    "THYAO": {"ad": "Türk Hava Yolları"}, "PGSUS": {"ad": "Pegasus Hava Taşımacılığı"},
    "CLEBI": {"ad": "Çelebi Hava Servisi"}, "BIMAS": {"ad": "BİM Birleşik Mağazalar"},
    "MGROS": {"ad": "Migros Ticaret"}, "SOKM":  {"ad": "Şok Marketler"},
    "ULKER": {"ad": "Ülker Bisküvi"}, "TATGD": {"ad": "Tat Gıda"},
    "FROTO": {"ad": "Ford Otomotiv"}, "TOASO": {"ad": "Tofaş Oto. Fab."},
    "OTKAR": {"ad": "Otokar"}, "VESTL": {"ad": "Vestel Elektronik"},
    "ARCLK": {"ad": "Arçelik"}, "EREGL": {"ad": "Ereğli Demir Çelik"},
    "KRDMD": {"ad": "Kardemir (D)"}, "CEMAS": {"ad": "Çemaş Döküm"},
    "TUPRS": {"ad": "Tüpraş"}, "PETKM": {"ad": "Petkim Petrokimya"},
    "GUBRF": {"ad": "Gübre Fabrikaları"}, "ZOREN": {"ad": "Zorlu Enerji"},
    "ODAS":  {"ad": "Odaş Elektrik"}, "AKENR": {"ad": "Akenerji"},
    "AKSEN": {"ad": "Aksa Enerji"}, "SISE":  {"ad": "Şişe Cam"},
    # KOZAA ve IPEKE yfinance'te 404 veriyor — listeden çıkarıldı
    "SASA":  {"ad": "SASA Polyester"}, "ENKAI": {"ad": "Enka İnşaat"},
    "TKFEN": {"ad": "Tekfen Holding"}, "OYAKC": {"ad": "Oyak Çimento"},
    "AKCNS": {"ad": "Akçansa Çimento"}, "CIMSA": {"ad": "Çimsa Çimento"},
    "EKGYO": {"ad": "Emlak Konut GYO"}, "KCHOL": {"ad": "Koç Holding"},
    "DOHOL": {"ad": "Doğan Holding"}, "DEVA":  {"ad": "Deva Holding"},
    "SELEC": {"ad": "Selçuk Ecza Deposu"}, "ECILC": {"ad": "Eczacıbaşı İlaç"},
}

XKTUM_SEMBOLLER = [
    # Teknoloji & Telekomünikasyon
    "ASELS","KFEIN","LOGO","NETAS","INDES","ARDYZ","AYES",
    "DGATE","DGNMO","DESPC","FONET","INTEM","MAVI","MEKAG","MMCAS","OZGYO",
    "PSDTC","RYGYO","SDTTR","SMART","TCELL","TTKOM","SILVR","VBTYZ",
    # Havacılık & Ulaşım
    "THYAO","PGSUS","CLEBI",
    # Otomotiv & Sanayi
    "BFREN","DOAS","FROTO","TOASO","OTKAR","ARCLK","VESTL","ASUZU",
    "BAKAB","DARDL","DNISI","EGEEN","FORMT",
    # Perakende & Gıda
    "BIMAS","MGROS","SOKM","ULKER","TATGD","ALYAG","BANVT","BRKO",
    "DURDO","HEKTS","KNFRT","KRVGD","PENGD","PINSU","PNSUT","SELVA",
    "SKTAS","TUKAS","TMPOL","VKGYO","FLAP","GEDZA","GEREL","GOODY",
    # Metal & Kimya
    "EREGL","KRDMD","CEMAS","ALCAR","ALKIM","ALKLC","BSOKE","BURVA",
    "CANTE","CELHA","CEMTS","CRFSA","DESA","DITAS","DYOBY","ERBOS","ERSU",
    "FMIZP","GESAN","GLYHO","BRSAN","GUBRF",
    # Enerji
    "TUPRS","ZOREN","ODAS","AKENR","AKSEN","AKFGY","AKSA","ALGYO","AYDEM",
    "BERA","EUPWR","PETKM",
    # Diğer Sanayi
    "ALMAD","ANELE","ANGEN","ATAKP","ATEKS",
    "SASA","KRTEK","SISE","BIENY","OYAKC","AKCNS","CIMSA","ENKAI","TKFEN",
    "AFYON","BUCIM","KONYA","MRDIN","NUHCM","EKGYO","IHLGM","KCHOL","DOHOL",
    "DEVA","SELEC","ECILC","HATEK","HURGZ","ESCOM","FENER","GRSEL","GSDHO",
    # HAVAS, IPEKE, KOZAA, PRKAR → yfinance'te 404, listeden çıkarıldı
]
