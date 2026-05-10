"""
FinSentinel — TradingView URL Yardımcıları
utils/tradingview.py

Her sembol için TradingView grafik sayfasına yönlendirme URL'si üretir.
"""

# ── BIST Hisse → TradingView ──────────────────────────────────────────────────
def bist_url(symbol: str) -> str:
    """GARAN veya GARAN.IS → TradingView BIST sayfası"""
    sym = symbol.replace(".IS", "").upper()
    return f"https://tr.tradingview.com/symbols/BIST:{sym}/"


# ── Kripto → TradingView ──────────────────────────────────────────────────────
_CRYPTO_EXCHANGE = {
    "BTC": "BINANCE:BTCUSDT",
    "ETH": "BINANCE:ETHUSDT",
    "BNB": "BINANCE:BNBUSDT",
    "SOL": "BINANCE:SOLUSDT",
    "XRP": "BINANCE:XRPUSDT",
    "ADA": "BINANCE:ADAUSDT",
    "AVAX": "BINANCE:AVAXUSDT",
    "DOT": "BINANCE:DOTUSDT",
    "MATIC": "BINANCE:MATICUSDT",
    "LINK": "BINANCE:LINKUSDT",
    "DOGE": "BINANCE:DOGEUSDT",
    "LTC": "BINANCE:LTCUSDT",
    "ATOM": "BINANCE:ATOMUSDT",
    "UNI": "BINANCE:UNIUSDT",
    "AAVE": "BINANCE:AAVEUSDT",
    "TRX": "BINANCE:TRXUSDT",
    "NEAR": "BINANCE:NEARUSDT",
    "FTM": "BINANCE:FTMUSDT",
    "ALGO": "BINANCE:ALGOUSDT",
    "VET": "BINANCE:VETUSDT",
    "SAND": "BINANCE:SANDUSDT",
    "MANA": "BINANCE:MANAUSDT",
    "AXS": "BINANCE:AXSUSDT",
    "CRO": "CRYPTOCOM:CROUSDT",
    "FIL": "BINANCE:FILUSDT",
    "ICP": "BINANCE:ICPUSDT",
    "EGLD": "BINANCE:EGLDUSDT",
    "THETA": "BINANCE:THETAUSDT",
    "XLM": "BINANCE:XLMUSDT",
    "ETC": "BINANCE:ETCUSDT",
}


def crypto_url(symbol: str) -> str:
    """BTC-USD veya BTC → TradingView kripto sayfası"""
    sym = symbol.replace("-USD", "").upper()
    tv = _CRYPTO_EXCHANGE.get(sym, f"BINANCE:{sym}USDT")
    return f"https://tr.tradingview.com/symbols/{tv}/"


# ── Forex → TradingView ───────────────────────────────────────────────────────
_FOREX_TV = {
    "USDTRY=X": "FX_IDC:USDTRY",
    "EURTRY=X": "FX_IDC:EURTRY",
    "GBPTRY=X": "FX_IDC:GBPTRY",
    "JPYTRY=X": "FX_IDC:JPYTRY",
    "CHFTRY=X": "FX_IDC:CHFTRY",
    "CADTRY=X": "FX_IDC:CADTRY",
    "AUDTRY=X": "FX_IDC:AUDTRY",
    "EURUSD=X": "FX:EURUSD",
    "GBPUSD=X": "FX:GBPUSD",
    "USDJPY=X": "FX:USDJPY",
    "USDCHF=X": "FX:USDCHF",
    "AUDUSD=X": "FX:AUDUSD",
    "USDCAD=X": "FX:USDCAD",
    "NZDUSD=X": "FX:NZDUSD",
    "EURGBP=X": "FX:EURGBP",
    "EURJPY=X": "FX:EURJPY",
    "GBPJPY=X": "FX:GBPJPY",
}


def forex_url(symbol: str) -> str:
    """USDTRY=X veya USD/TRY → TradingView forex sayfası"""
    tv = _FOREX_TV.get(symbol)
    if not tv:
        pair = symbol.replace("=X", "").upper()
        tv = f"FX:{pair}"
    return f"https://tr.tradingview.com/symbols/{tv}/"


# ── Emtia → TradingView ───────────────────────────────────────────────────────
_COMMODITY_TV = {
    "GC=F":  "TVC:GOLD",
    "SI=F":  "TVC:SILVER",
    "PL=F":  "TVC:PLATINUM",
    "PA=F":  "TVC:PALLADIUM",
    "CL=F":  "TVC:USOIL",
    "BZ=F":  "TVC:UKOIL",
    "NG=F":  "TVC:NATGAS",
    "HO=F":  "NYMEX:HO1!",
    "RB=F":  "NYMEX:RB1!",
    "HG=F":  "COMEX:HG1!",
    "ALI=F": "CME:ALI1!",
    "HRC=F": "CME:HR1!",
    "ZW=F":  "CBOT:ZW1!",
    "ZC=F":  "CBOT:ZC1!",
    "ZS=F":  "CBOT:ZS1!",
    "SB=F":  "ICEUS:SB1!",
    "KC=F":  "ICEUS:KC1!",
    "CC=F":  "ICEUS:CC1!",
    "CT=F":  "ICEUS:CT1!",
}


def commodity_url(symbol: str) -> str:
    """GC=F → TradingView emtia sayfası"""
    tv = _COMMODITY_TV.get(symbol.upper())
    if not tv:
        return f"https://tr.tradingview.com/search/?q={symbol}"
    return f"https://tr.tradingview.com/symbols/{tv}/"


# ── Dünya Endeksleri → TradingView ───────────────────────────────────────────
_INDEX_TV = {
    "^GSPC":    "SP:SPX",
    "^NDX":     "NASDAQ:NDX",
    "^DJI":     "DJ:DJI",
    "^RUT":     "TVC:RUT",
    "^VIX":     "CBOE:VIX",
    "^GDAXI":   "XETR:DAX",
    "^FTSE":    "SPREADEX:UK100",
    "^FCHI":    "EURONEXT:PX1",
    "^STOXX50E":"TVC:SX5E",
    "^AEX":     "EURONEXT:AEX",
    "^SSMI":    "TVC:SMI",
    "^IBEX":    "BME:IBC",
    "^N225":    "TVC:NI225",
    "^HSI":     "TVC:HSI",
    "000001.SS":"SSE:000001",
    "^KS11":    "KRX:KOSPI",
    "^AORD":    "ASX:XAO",
    "^BSESN":   "BSE:SENSEX",
    "^BVSP":    "BMFBOVESPA:IBOV",
    "^GSPTSE":  "TSX:TSX",
    "^TASI.SR": "TADAWUL:TASI",
    "XU100.IS": "BIST:XU100",
    "XU030.IS": "BIST:XU030",
    "XBANK.IS": "BIST:XBANK",
}


def index_url(symbol: str) -> str:
    """^GSPC → TradingView endeks sayfası"""
    tv = _INDEX_TV.get(symbol)
    if not tv:
        return f"https://tr.tradingview.com/search/?q={symbol}"
    return f"https://tr.tradingview.com/symbols/{tv}/"


# ── Genel URL üretici ─────────────────────────────────────────────────────────
def get_url(symbol: str, asset_type: str = "auto") -> str:
    """
    Otomatik sembol tipini tahmin ederek doğru TradingView URL'si döndür.

    asset_type: "bist", "crypto", "forex", "commodity", "index", "auto"
    """
    if asset_type == "bist" or symbol.endswith(".IS"):
        return bist_url(symbol)
    elif asset_type == "crypto" or symbol.endswith("-USD"):
        return crypto_url(symbol)
    elif asset_type == "forex" or symbol.endswith("=X"):
        return forex_url(symbol)
    elif asset_type == "commodity" or symbol.endswith("=F"):
        return commodity_url(symbol)
    elif asset_type == "index" or symbol.startswith("^") or symbol in _INDEX_TV:
        return index_url(symbol)
    else:
        return f"https://tr.tradingview.com/search/?q={symbol}"


def tv_badge(symbol: str, label: str = None, asset_type: str = "auto") -> str:
    """
    Streamlit markdown için TradingView link badge'i döndür.
    st.markdown(tv_badge("GARAN.IS"), unsafe_allow_html=True) şeklinde kullanılır.
    """
    url = get_url(symbol, asset_type)
    display = label or symbol.replace(".IS", "").replace("-USD", "").replace("=X", "")
    return (
        f'<a href="{url}" target="_blank" title="TradingView\'de {display} grafiğini aç" '
        f'style="color:#4da6ff;font-size:11px;text-decoration:none;border:1px solid #1e3a5f;'
        f'border-radius:4px;padding:1px 6px;margin-left:4px">📈 TV</a>'
    )


def make_tv_link_col(symbols: list, asset_type: str = "auto") -> list:
    """DataFrame için TradingView link sütunu oluştur"""
    return [
        f'<a href="{get_url(s, asset_type)}" target="_blank">📈 TV</a>'
        for s in symbols
    ]
