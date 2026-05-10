"""
FinSentinel — Canlı Veri Akışı Motoru
core/live_feed.py

Sadece belgelenmiş / açık kaynaklara bağlanır:
  • yfinance        : Yahoo Finance — BIST için ~15 dk gecikmeli, lisans gerekmez
  • Finnhub REST    : finnhub.io resmi ücretsiz API (kayıt → API key)
  • Binance WS      : Binance'in belgelenmiş public WebSocket API'si (auth yok, resmi)
  • CoinGecko REST  : Ücretsiz, belgelenmiş, RateLimited resmi API

BIST gerçek zamanlı veri için ticari lisanslı çözümler:
  Matriks, Rasyonet, Borsa İstanbul DataStore (data.borsaistanbul.com)
  Bu modül bunları entegre etmez; lisans sahibi olunursa kolayca eklenebilir.
"""

import json
import time
import threading
from datetime import datetime
from typing import Optional

import requests
import yfinance as yf
import websocket          # websocket-client>=1.8.0
from loguru import logger

from config.settings import BIST_SYMBOLS, COINGECKO_API_KEY


# ─────────────────────────────────────────────────────────────────────────────
# 1. BIST — yfinance Polling (resmi, belgelenmiş)
# ─────────────────────────────────────────────────────────────────────────────

class BistYFinanceFeed:
    """
    Yahoo Finance üzerinden BIST verisi çeker (yfinance).
    Veri ~15 dakika gecikmeli (Borsa İstanbul lisans şartı gereği Yahoo'da da gecikmeli).
    Lisans: yfinance MIT açık kaynak; Yahoo ToS kişisel/araştırma kullanımına izin verir.
    Ticari kullanım için Borsa İstanbul veri lisansı gerekir.
    """

    # 404 / delisted / Türkçe karakterli — yfinance'te çalışmayan semboller
    _BAD_SYMBOLS: frozenset = frozenset({
        "ARMADA", "BSVS", "CENG", "DEGYO", "DOBUR", "DURAN", "EISAS",
        "EMTAS", "FINSN", "GUBRE", "HAVAS", "IPEKE", "LNGSN", "LYKNS",
        "METUR", "MKTES", "MLPYT", "MNVLY", "MRCOL", "MTMTR", "NETAŞ",
        "NXION", "OFISE", "OREN",  "PRKAR", "RBIGS", "RFET",  "RNSAS",
        "SILVER","SMEN",  "STONE", "TBNK",  "TMASM", "TRABZ", "UMAS",
        "URAS",  "WHTOB", "WNDSL", "YARHL", "YGYO",  "ALTIN", "ÜLKER",
        "KOZAL", "IIAG",
    })

    @staticmethod
    def fetch_bulk(symbols: list[str]) -> dict[str, dict]:
        """
        Birden fazla '.IS' sembolü için toplu fiyat çekimi.
        symbols: ["GARAN", "THYAO"] → yfinance formatı → "GARAN.IS" eklenir otomatik
        """
        if not symbols:
            return {}

        # Geçersiz sembolleri önceden filtrele
        symbols = [
            s for s in symbols
            if s.replace(".IS", "").upper() not in BistYFinanceFeed._BAD_SYMBOLS
        ]
        if not symbols:
            return {}

        yf_symbols = [s if s.endswith(".IS") else f"{s}.IS" for s in symbols]
        result = {}

        try:
            data = yf.download(
                yf_symbols,
                period="2d",
                interval="1d",
                auto_adjust=True,
                progress=False,
                threads=False,   # thread=True yfinance 401 crumb sorununa yol açıyor
                multi_level_index=True,
                timeout=30,
            )
            if data is None or data.empty:
                return {}

            for yf_sym in yf_symbols:
                clean = yf_sym.replace(".IS", "")
                try:
                    if isinstance(data.columns, yf.download.__class__):  # type guard
                        close_col = data["Close"][yf_sym]
                    elif isinstance(data.columns, object) and hasattr(data.columns, "levels"):
                        # MultiIndex
                        close_col = data[("Close", yf_sym)] if ("Close", yf_sym) in data.columns else None
                    else:
                        close_col = data["Close"] if "Close" in data.columns else None

                    if close_col is None:
                        continue

                    closes = close_col.dropna()
                    if closes.empty:
                        continue

                    price = float(closes.iloc[-1])
                    prev  = float(closes.iloc[-2]) if len(closes) >= 2 else price
                    pct   = round((price - prev) / prev * 100, 2) if prev else 0.0

                    result[clean] = {
                        "symbol":     clean,
                        "price":      round(price, 2),
                        "prev_close": round(prev, 2),
                        "change":     round(price - prev, 2),
                        "change_pct": pct,
                        "direction":  "up" if pct > 0 else ("down" if pct < 0 else "flat"),
                        "source":     "yfinance_bist",
                        "delayed":    True,   # ~15 dk gecikme
                        "ts":         datetime.utcnow().isoformat(),
                    }
                except Exception as e:
                    logger.debug(f"yfinance parse [{yf_sym}]: {e}")
                    continue

        except Exception as e:
            logger.error(f"yfinance bulk fetch hatası: {e}")

        return result

    @staticmethod
    def fetch_single(symbol: str) -> Optional[dict]:
        """Tek sembol için detaylı bilgi (52h yüksek/düşük, hacim vb.)"""
        yf_sym = symbol if symbol.endswith(".IS") else f"{symbol}.IS"
        try:
            ticker = yf.Ticker(yf_sym)
            hist = ticker.history(period="5d", interval="1d")
            if hist is None or hist.empty:
                return None
            info = ticker.fast_info
            price = float(hist["Close"].iloc[-1])
            prev  = float(hist["Close"].iloc[-2]) if len(hist) >= 2 else price
            pct   = round((price - prev) / prev * 100, 2) if prev else 0.0
            return {
                "symbol":     symbol,
                "price":      round(price, 2),
                "prev_close": round(prev, 2),
                "change":     round(price - prev, 2),
                "change_pct": pct,
                "volume":     float(hist["Volume"].iloc[-1]) if "Volume" in hist else None,
                "high_52w":   getattr(info, "fifty_two_week_high", None),
                "low_52w":    getattr(info, "fifty_two_week_low", None),
                "direction":  "up" if pct > 0 else ("down" if pct < 0 else "flat"),
                "source":     "yfinance_bist",
                "delayed":    True,
                "ts":         datetime.utcnow().isoformat(),
            }
        except Exception as e:
            logger.error(f"yfinance single [{symbol}]: {e}")
            return None


# ─────────────────────────────────────────────────────────────────────────────
# 2. BIST — Finnhub Resmi API (opsiyonel, ücretsiz tier)
#    Kayıt: https://finnhub.io/register  (ücretsiz, kişisel kullanım)
#    BIST sembol formatı: "IST:GARAN"
#    Not: Ücretsiz tier'da BIST hisseleri sınırlı olabilir.
# ─────────────────────────────────────────────────────────────────────────────

class FinnhubFeed:
    """
    Finnhub resmi REST API.
    Lisans: Ücretsiz tier — kişisel/araştırma kullanımı için izinli.
    Rate limit: 60 req/dakika (ücretsiz).
    API Docs: https://finnhub.io/docs/api
    """

    _BASE = "https://finnhub.io/api/v1"

    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("Finnhub API key gerekli. https://finnhub.io/register adresinden ücretsiz alın.")
        self.api_key = api_key
        self._session = requests.Session()
        self._session.headers.update({"X-Finnhub-Token": api_key})

    def get_quote(self, symbol: str) -> Optional[dict]:
        """
        BIST için symbol: "IST:GARAN"
        ABD için symbol: "AAPL"
        """
        try:
            r = self._session.get(
                f"{self._BASE}/quote",
                params={"symbol": symbol},
                timeout=8,
            )
            r.raise_for_status()
            d = r.json()
            if not d or d.get("c", 0) == 0:
                return None
            price = float(d["c"])
            prev  = float(d["pc"]) if d.get("pc") else price
            pct   = round((price - prev) / prev * 100, 2) if prev else 0.0
            return {
                "symbol":     symbol,
                "price":      price,
                "prev_close": prev,
                "change":     round(price - prev, 4),
                "change_pct": pct,
                "high":       float(d.get("h", 0)),
                "low":        float(d.get("l", 0)),
                "open":       float(d.get("o", 0)),
                "direction":  "up" if pct > 0 else ("down" if pct < 0 else "flat"),
                "source":     "finnhub",
                "delayed":    False,  # Finnhub paid → gerçek zamanlı; free → gecikmeli olabilir
                "ts":         datetime.utcnow().isoformat(),
            }
        except requests.HTTPError as e:
            logger.warning(f"Finnhub HTTP hatası [{symbol}]: {e}")
            return None
        except Exception as e:
            logger.error(f"Finnhub quote hatası [{symbol}]: {e}")
            return None


# ─────────────────────────────────────────────────────────────────────────────
# 3. KRİPTO — Binance Public WebSocket (server-side thread)
#    API Docs: https://binance-docs.github.io/apidocs/spot/en/#individual-symbol-mini-ticker-stream
#    Auth: Gerekmez. Tamamen açık, belgelenmiş endpoint.
# ─────────────────────────────────────────────────────────────────────────────

class BinanceLiveFeed:
    """
    Binance'in resmi belgelenmiş miniTicker WebSocket stream'i.
    • Auth gerektirmez
    • Rate limit yok (WebSocket)
    • Docs: https://binance-docs.github.io/apidocs/spot/en/
    """

    _WS_URL = "wss://stream.binance.com:9443/stream?streams={streams}"

    def __init__(self, pairs: list[str]):
        self.pairs = [p.upper() for p in pairs]
        self.price_cache: dict[str, dict] = {}
        self._ws: Optional[websocket.WebSocketApp] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._retry_delay = 2

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._run_loop, daemon=True, name="BinanceWS"
        )
        self._thread.start()
        logger.info(f"Binance WS başlatıldı ({len(self.pairs)} parite)")

    def stop(self):
        self._running = False
        if self._ws:
            try:
                self._ws.close()
            except Exception:
                pass

    def get(self, symbol: str) -> Optional[dict]:
        return self.price_cache.get(symbol.upper())

    def _build_url(self) -> str:
        streams = "/".join(f"{p.lower()}@miniTicker" for p in self.pairs)
        return self._WS_URL.format(streams=streams)

    def _run_loop(self):
        while self._running:
            try:
                self._ws = websocket.WebSocketApp(
                    self._build_url(),
                    on_message=self._on_message,
                    on_error=self._on_error,
                    on_close=self._on_close,
                )
                self._ws.run_forever(ping_interval=20, ping_timeout=10)
            except Exception as e:
                logger.error(f"Binance WS döngü hatası: {e}")
            if self._running:
                time.sleep(self._retry_delay)
                self._retry_delay = min(self._retry_delay * 2, 60)

    def _on_message(self, ws, raw: str):
        try:
            data = json.loads(raw).get("data", {})
            if data.get("e") != "24hrMiniTicker":
                return
            symbol = data["s"].upper()
            price  = float(data["c"])
            open_  = float(data["o"])
            pct    = round((price - open_) / open_ * 100, 3) if open_ else 0.0
            self.price_cache[symbol] = {
                "symbol":     symbol,
                "price":      price,
                "open":       open_,
                "high":       float(data["h"]),
                "low":        float(data["l"]),
                "volume":     float(data["v"]),
                "change_pct": pct,
                "direction":  "up" if pct > 0 else ("down" if pct < 0 else "flat"),
                "source":     "binance_ws",
                "delayed":    False,
                "ts":         datetime.utcfromtimestamp(data["E"] / 1000).isoformat(),
            }
            self._retry_delay = 2
        except Exception as e:
            logger.debug(f"Binance mesaj parse: {e}")

    def _on_error(self, ws, error):
        logger.warning(f"Binance WS hata: {error}")

    def _on_close(self, ws, code, msg):
        logger.info(f"Binance WS kapandı code={code}")


# ─────────────────────────────────────────────────────────────────────────────
# 4. KRİPTO — CoinGecko REST (fallback / snapshot)
#    API Docs: https://www.coingecko.com/api/documentation
#    Free tier: 30 req/dakika, kayıt opsiyonel
# ─────────────────────────────────────────────────────────────────────────────

_COINGECKO_ID_MAP = {
    "BTCUSDT": "bitcoin", "ETHUSDT": "ethereum", "BNBUSDT": "binancecoin",
    "SOLUSDT": "solana",  "XRPUSDT": "ripple",   "ADAUSDT": "cardano",
    "DOGEUSDT":"dogecoin","AVAXUSDT":"avalanche-2","DOTUSDT":"polkadot",
    "LINKUSDT":"chainlink","LTCUSDT":"litecoin",  "TRXUSDT":"tron",
    "MATICUSDT":"matic-network","NEARUSDT":"near","ATOMUSDT":"cosmos",
}


def fetch_coingecko_snapshot(
    pairs: list[str],
    vs_currency: str = "usd",
) -> dict[str, dict]:
    """
    CoinGecko resmi API ile anlık kripto fiyatları.
    Binance WS henüz bağlanmamışsa başlangıç değeri olarak kullanılır.
    """
    ids = [_COINGECKO_ID_MAP[p] for p in pairs if p in _COINGECKO_ID_MAP]
    if not ids:
        return {}

    params: dict = {
        "ids": ",".join(ids),
        "vs_currencies": vs_currency,
        "include_24hr_change": "true",
        "include_24hr_vol": "true",
    }
    headers: dict = {}
    if COINGECKO_API_KEY:
        headers["x-cg-demo-api-key"] = COINGECKO_API_KEY

    try:
        r = requests.get(
            "https://api.coingecko.com/api/v3/simple/price",
            params=params,
            headers=headers,
            timeout=10,
        )
        r.raise_for_status()
        raw = r.json()

        # id → Binance symbol reverse map
        id_to_symbol = {v: k for k, v in _COINGECKO_ID_MAP.items()}
        result = {}
        for cg_id, vals in raw.items():
            sym = id_to_symbol.get(cg_id)
            if not sym:
                continue
            price = float(vals.get(vs_currency, 0))
            pct   = float(vals.get(f"{vs_currency}_24h_change", 0))
            result[sym] = {
                "symbol":     sym,
                "price":      price,
                "change_pct": round(pct, 3),
                "volume_24h": float(vals.get(f"{vs_currency}_24h_vol", 0)),
                "direction":  "up" if pct > 0 else ("down" if pct < 0 else "flat"),
                "source":     "coingecko",
                "delayed":    False,
                "ts":         datetime.utcnow().isoformat(),
            }
        return result
    except Exception as e:
        logger.error(f"CoinGecko snapshot hatası: {e}")
        return {}


# ─────────────────────────────────────────────────────────────────────────────
# 5. LiveFeedManager — Singleton Yönetici
# ─────────────────────────────────────────────────────────────────────────────

_DEFAULT_CRYPTO_PAIRS = [
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT",
    "ADAUSDT", "DOGEUSDT", "AVAXUSDT", "DOTUSDT", "LINKUSDT",
    "LTCUSDT", "TRXUSDT", "MATICUSDT", "NEARUSDT", "ATOMUSDT",
]
_BIST_POLL_INTERVAL = 60  # saniye — yfinance gecikmeli, sık sorgu gerekmez


class LiveFeedManager:
    """
    Singleton feed yöneticisi.

    BIST  → yfinance polling (60s aralık, ~15dk gecikmeli)
            opsiyonel: Finnhub (FINNHUB_API_KEY .env'de tanımlıysa devreye girer)
    KRİPTO → Binance WebSocket (gerçek zamanlı, tarayıcı JS ile senkron)
              fallback: CoinGecko snapshot

    Streamlit entegrasyonu:
        if "live_manager" not in st.session_state:
            st.session_state.live_manager = get_live_manager()
        mgr = st.session_state.live_manager
    """

    def __init__(
        self,
        crypto_pairs: list[str] = _DEFAULT_CRYPTO_PAIRS,
        bist_symbols: list[str] | None = None,
        finnhub_api_key: str = "",
    ):
        self._crypto_pairs = crypto_pairs
        self._bist_symbols = bist_symbols or BIST_SYMBOLS[:30]  # ilk 30 yeterli
        self._finnhub_key  = finnhub_api_key

        self.price_cache: dict[str, dict] = {"BIST": {}, "CRYPTO": {}}
        self.binance = BinanceLiveFeed(crypto_pairs)
        self._finnhub: Optional[FinnhubFeed] = None

        self._bist_thread: Optional[threading.Thread] = None
        self._bist_running = False
        self._started = False

    def start(self):
        if self._started:
            return
        self._started = True

        # Finnhub opsiyonel
        if self._finnhub_key:
            try:
                self._finnhub = FinnhubFeed(self._finnhub_key)
                logger.info("Finnhub feed aktif.")
            except ValueError as e:
                logger.warning(str(e))

        # CoinGecko başlangıç snapshot (WS bağlanmadan önce)
        snap = fetch_coingecko_snapshot(self._crypto_pairs)
        self.price_cache["CRYPTO"].update(snap)

        # Binance WS thread
        self.binance.start()

        # BIST polling thread
        self._bist_running = True
        self._bist_thread = threading.Thread(
            target=self._bist_poll_loop, daemon=True, name="BistPoller"
        )
        self._bist_thread.start()
        logger.info("LiveFeedManager başlatıldı.")

    def stop(self):
        self._bist_running = False
        self.binance.stop()
        self._started = False

    # ── BIST Polling ──────────────────────────────────────────────────────

    def _bist_poll_loop(self):
        while self._bist_running:
            try:
                data = BistYFinanceFeed.fetch_bulk(self._bist_symbols)
                if data:
                    self.price_cache["BIST"].update(data)
                    logger.debug(f"BIST cache: {len(data)} sembol güncellendi (yfinance)")
            except Exception as e:
                logger.error(f"BIST poll hatası: {e}")
            time.sleep(_BIST_POLL_INTERVAL)

    # ── Public API ────────────────────────────────────────────────────────

    def get_bist_prices(self, symbols: list[str] | None = None) -> dict[str, dict]:
        cache = self.price_cache["BIST"]
        if symbols is None:
            return cache
        return {s: cache[s] for s in symbols if s in cache}

    # Geriye dönük uyumluluk: telegram_bot._get_bist_movers get_bist_data() çağırıyor
    def get_bist_data(self, symbols: list[str] | None = None) -> dict[str, dict]:
        return self.get_bist_prices(symbols)

    def get_crypto_prices(self, symbols: list[str] | None = None) -> dict[str, dict]:
        # Binance cache'i merge et
        self.price_cache["CRYPTO"].update(self.binance.price_cache)
        cache = self.price_cache["CRYPTO"]
        if symbols is None:
            return cache
        return {s: cache[s] for s in symbols if s in cache}

    def get_ticker_data(
        self,
        bist_symbols: list[str],
        crypto_symbols: list[str],
    ) -> list[dict]:
        items = []
        for s in bist_symbols:
            d = self.price_cache["BIST"].get(s)
            if d:
                items.append(d)
        for s in crypto_symbols:
            d = self.binance.price_cache.get(s) or self.price_cache["CRYPTO"].get(s)
            if d:
                items.append(d)
        return items


# ── Modül-level singleton ──────────────────────────────────────────────────

_manager_instance: Optional[LiveFeedManager] = None


def get_live_manager(
    crypto_pairs: list[str] = _DEFAULT_CRYPTO_PAIRS,
    finnhub_api_key: str = "",
) -> LiveFeedManager:
    """
    İlk çağrıda oluşturur ve thread'leri başlatır.
    Sonraki çağrılarda aynı instance döner.
    """
    global _manager_instance
    if _manager_instance is None:
        import os
        key = finnhub_api_key or os.getenv("FINNHUB_API_KEY", "")
        _manager_instance = LiveFeedManager(
            crypto_pairs=crypto_pairs,
            finnhub_api_key=key,
        )
        _manager_instance.start()
    return _manager_instance
