"""
FinSentinel — Canlı Ticker Bileşeni
components/live_ticker.py

st.components.v1.html ile çalışır.
• BIST  : Python'dan JSON inject → statik başlangıç, 30s'de bir Streamlit rerun ile taze kalır
• KRİPTO: Tarayıcıdan Binance WebSocket'e doğrudan bağlanır → gerçek zamanlı flash

Kullanım:
    from components.live_ticker import render_live_ticker

    render_live_ticker(
        bist_data=mgr.get_bist_prices(["GARAN", "THYAO", "AKBNK"]),
        crypto_pairs=["BTCUSDT", "ETHUSDT", "BNBUSDT"],
        height=68,
    )
"""

import json
import streamlit.components.v1 as components


# ─────────────────────────────────────────────────────────────────────────────
# Sabitler
# ─────────────────────────────────────────────────────────────────────────────

_TICKER_CSS = """
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { background: #0a0e1a; overflow: hidden; }

  #ticker-wrap {
    width: 100%;
    background: linear-gradient(90deg, #0a0e1a 0%, #111827 50%, #0a0e1a 100%);
    border-top: 1px solid #1e3a5f;
    border-bottom: 1px solid #1e3a5f;
    overflow: hidden;
    height: 52px;
    display: flex;
    align-items: center;
    position: relative;
  }

  /* Sol/sağ gradient fade */
  #ticker-wrap::before,
  #ticker-wrap::after {
    content: "";
    position: absolute;
    top: 0; bottom: 0;
    width: 60px;
    z-index: 2;
    pointer-events: none;
  }
  #ticker-wrap::before { left: 0;  background: linear-gradient(90deg, #0a0e1a, transparent); }
  #ticker-wrap::after  { right: 0; background: linear-gradient(-90deg, #0a0e1a, transparent); }

  #ticker-track {
    display: flex;
    gap: 0;
    white-space: nowrap;
    animation: scroll-left 60s linear infinite;
    will-change: transform;
  }
  #ticker-track:hover { animation-play-state: paused; }

  @keyframes scroll-left {
    0%   { transform: translateX(0); }
    100% { transform: translateX(-50%); }
  }

  .tick-item {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 0 18px;
    border-right: 1px solid #1e3a5f22;
    font-family: 'SF Mono', 'Fira Code', monospace;
    font-size: 12.5px;
    cursor: default;
    transition: background 0.2s;
  }
  .tick-item:hover { background: #1a2236; }

  .tick-symbol {
    color: #7a93b0;
    font-weight: 600;
    font-size: 11px;
    letter-spacing: 0.04em;
  }

  .tick-price {
    color: #e2eaf5;
    font-weight: 700;
    font-size: 13px;
    min-width: 64px;
    text-align: right;
  }

  .tick-pct {
    font-size: 11.5px;
    font-weight: 600;
    padding: 1px 5px;
    border-radius: 3px;
    min-width: 52px;
    text-align: center;
  }
  .tick-pct.up   { color: #00d4aa; background: #00d4aa12; }
  .tick-pct.down { color: #ff4d6a; background: #ff4d6a12; }
  .tick-pct.flat { color: #7a93b0; background: #7a93b012; }

  /* Flash animasyonu — fiyat güncellenince */
  @keyframes flash-up   { 0%,100%{background:transparent} 30%{background:#00d4aa22} }
  @keyframes flash-down { 0%,100%{background:transparent} 30%{background:#ff4d6a22} }
  .flash-up   { animation: flash-up   0.6s ease; }
  .flash-down { animation: flash-down 0.6s ease; }

  /* Sembol badge rengi — BIST vs CRYPTO */
  .badge-bist   { color: #4da6ff; }
  .badge-crypto { color: #c77dff; }

  /* Status dot */
  #live-dot {
    position: absolute;
    right: 10px; top: 50%;
    transform: translateY(-50%);
    z-index: 3;
    display: flex;
    align-items: center;
    gap: 4px;
    font-size: 10px;
    color: #4a6080;
  }
  .dot {
    width: 7px; height: 7px;
    border-radius: 50%;
    background: #00d4aa;
    animation: pulse 2s infinite;
  }
  @keyframes pulse {
    0%,100% { opacity: 1; transform: scale(1); }
    50%      { opacity: 0.4; transform: scale(0.8); }
  }
</style>
"""

_TICKER_JS = """
<script>
(function() {
  // ── Binance WebSocket ────────────────────────────────────────────────
  const cryptoPairs = {crypto_pairs_json};

  if (cryptoPairs.length === 0) return;

  const streams = cryptoPairs.map(p => p.toLowerCase() + '@miniTicker').join('/');
  const wsUrl   = `wss://stream.binance.com:9443/stream?streams=${streams}`;

  let ws;
  let retryDelay = 2000;

  function connect() {
    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      retryDelay = 2000;
      setStatus(true);
    };

    ws.onmessage = (evt) => {
      try {
        const env  = JSON.parse(evt.data);
        const data = env.data || env;
        if (data.e !== '24hrMiniTicker') return;

        const symbol = data.s.toUpperCase();          // "BTCUSDT"
        const price  = parseFloat(data.c);
        const open   = parseFloat(data.o);
        const pct    = open ? ((price - open) / open * 100) : 0;

        updateTicker(symbol, price, pct, 'crypto');
      } catch(e) { /* ignore */ }
    };

    ws.onerror = () => setStatus(false);
    ws.onclose = () => {
      setStatus(false);
      setTimeout(connect, retryDelay);
      retryDelay = Math.min(retryDelay * 2, 30000);
    };
  }

  connect();

  // ── DOM Güncelle ─────────────────────────────────────────────────────
  function updateTicker(symbol, price, pct, type) {
    // Her iki kopyadaki (sonsuz loop için çift track) item'ları güncelle
    const items = document.querySelectorAll(`[data-symbol="${symbol}"]`);
    if (!items.length) return;

    const dir      = pct > 0 ? 'up' : (pct < 0 ? 'down' : 'flat');
    const arrow    = pct > 0 ? '▲' : (pct < 0 ? '▼' : '▸');
    const priceStr = formatPrice(price, type);
    const pctStr   = `${arrow} ${Math.abs(pct).toFixed(2)}%`;

    items.forEach(item => {
      const priceEl = item.querySelector('.tick-price');
      const pctEl   = item.querySelector('.tick-pct');

      if (!priceEl || !pctEl) return;

      // Flash efekti
      item.classList.remove('flash-up', 'flash-down');
      void item.offsetWidth; // reflow
      if (dir !== 'flat') item.classList.add(`flash-${dir}`);

      priceEl.textContent = priceStr;
      pctEl.textContent   = pctStr;
      pctEl.className     = `tick-pct ${dir}`;
    });
  }

  function formatPrice(price, type) {
    if (type === 'crypto') {
      return price >= 1000 ? price.toLocaleString('tr-TR', {minimumFractionDigits: 2, maximumFractionDigits: 2})
           : price >= 1    ? price.toFixed(4)
                           : price.toFixed(6);
    }
    return price.toLocaleString('tr-TR', {minimumFractionDigits: 2, maximumFractionDigits: 2});
  }

  function setStatus(live) {
    const dot = document.querySelector('.dot');
    if (dot) dot.style.background = live ? '#00d4aa' : '#ff4d6a';
  }
})();
</script>
"""


# ─────────────────────────────────────────────────────────────────────────────
# Yardımcı — HTML item oluşturucu
# ─────────────────────────────────────────────────────────────────────────────

def _build_item(data: dict, asset_type: str) -> str:
    """Tek ticker item'ı için HTML string üretir."""
    symbol    = data.get("symbol", "???")
    price     = data.get("price", 0.0) or 0.0
    pct       = data.get("change_pct", 0.0) or 0.0
    direction = data.get("direction", "flat")

    arrow = "▲" if direction == "up" else ("▼" if direction == "down" else "▸")
    pct_str   = f"{arrow} {abs(pct):.2f}%"
    dir_class = direction   # "up" | "down" | "flat"

    # Fiyat formatlama
    if asset_type == "crypto":
        if price >= 1000:
            price_str = f"{price:,.2f}"
        elif price >= 1:
            price_str = f"{price:.4f}"
        else:
            price_str = f"{price:.6f}"
        badge_class = "badge-crypto"
    else:
        price_str   = f"{price:,.2f}"
        badge_class = "badge-bist"

    # Sembol görünen adı — ".IS" suffix'ini kaldır
    display_sym = symbol.replace(".IS", "").replace("USDT", "/USDT")

    return (
        f'<div class="tick-item" data-symbol="{symbol}">'
        f'  <span class="tick-symbol {badge_class}">{display_sym}</span>'
        f'  <span class="tick-price">{price_str}</span>'
        f'  <span class="tick-pct {dir_class}">{pct_str}</span>'
        f'</div>'
    )


# ─────────────────────────────────────────────────────────────────────────────
# Ana Render Fonksiyonu
# ─────────────────────────────────────────────────────────────────────────────

def render_live_ticker(
    bist_data: dict[str, dict],
    crypto_pairs: list[str] | None = None,
    crypto_snapshot: dict[str, dict] | None = None,
    height: int = 68,
) -> None:
    """
    Canlı ticker bileşenini render eder.

    Args:
        bist_data       : {"GARAN": {...}, "THYAO": {...}} — LiveFeedManager'dan
        crypto_pairs    : ["BTCUSDT", "ETHUSDT"] — tarayıcıda WS'e bağlanılacak
        crypto_snapshot : {"BTCUSDT": {...}} — başlangıç fiyatı (opsiyonel, WS henüz bağlanmadıysa)
        height          : bileşen yüksekliği (px)
    """
    crypto_pairs    = crypto_pairs or []
    crypto_snapshot = crypto_snapshot or {}

    # ── HTML item'larını oluştur ──────────────────────────────────────────
    items_html = ""

    # BIST item'ları
    for sym, data in bist_data.items():
        if data and "price" in data:
            items_html += _build_item(data, "bist")

    # Kripto snapshot item'ları (WS bağlanmadan önceki ilk değerler)
    for sym in crypto_pairs:
        data = crypto_snapshot.get(sym, {"symbol": sym, "price": 0.0, "change_pct": 0.0, "direction": "flat"})
        items_html += _build_item(data, "crypto")

    if not items_html:
        return   # Gösterecek veri yok

    # Sonsuz scroll için item listesi 2x çoğaltılır
    track_html = f'<div id="ticker-track">{items_html}{items_html}</div>'

    js_filled = _TICKER_JS.replace(
        "{crypto_pairs_json}", json.dumps(crypto_pairs)
    )

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>{_TICKER_CSS}</head>
    <body>
      <div id="ticker-wrap">
        {track_html}
        <div id="live-dot">
          <div class="dot"></div>
          <span>CANLI</span>
        </div>
      </div>
      {js_filled}
    </body>
    </html>
    """

    components.html(html, height=height, scrolling=False)


# ─────────────────────────────────────────────────────────────────────────────
# Hızlı Entegrasyon Örneği (sayfa başına ekle)
# ─────────────────────────────────────────────────────────────────────────────

INTEGRATION_EXAMPLE = '''
# pages/01_market_overview.py dosyasına ekle:

import streamlit as st
from core.live_feed import get_live_manager
from components.live_ticker import render_live_ticker

# Singleton manager — ilk çağrıda thread'leri başlatır
if "live_manager" not in st.session_state:
    st.session_state.live_manager = get_live_manager()

mgr = st.session_state.live_manager

# Gösterilecek semboller
BIST_TICKER  = ["GARAN", "THYAO", "AKBNK", "TUPRS", "EREGL",
                "KCHOL", "SISE",  "FROTO", "TCELL", "BIMAS"]
CRYPTO_PAIRS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT"]

render_live_ticker(
    bist_data       = mgr.get_bist_prices(BIST_TICKER),
    crypto_pairs    = CRYPTO_PAIRS,
    crypto_snapshot = mgr.get_crypto_prices(CRYPTO_PAIRS),
)

# 30 saniyede bir BIST verisini yenilemek için:
# from streamlit_autorefresh import st_autorefresh
# st_autorefresh(interval=30_000, key="ticker_refresh")
'''
