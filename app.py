"""
FinSentinel — Ana Uygulama (Premium Edition)
app.py  |  Streamlit çok sayfalı platform — giriş noktası
"""
import warnings
# Suppress mplfinance FutureWarning about Series.__getitem__ position indexing
warnings.filterwarnings(
    "ignore",
    message=".*Series.__getitem__ treating keys as positions.*",
    category=FutureWarning,
)
warnings.filterwarnings("ignore", category=FutureWarning, module="mplfinance")

import streamlit as st
import hashlib
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

from config.settings import APP_PASSWORD, THEME, AUTO_REFRESH_INTERVAL, USERS
from utils.ui import apply_dark_theme, live_indicator

# ─── Sayfa Konfigürasyonu ─────────────────────────────────────────────────────

st.set_page_config(
    page_title="FinSentinel",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "Get Help":     None,
        "Report a bug": None,
        "About":        "FinSentinel — Finansal Zeka Platformu v2.0",
    }
)

apply_dark_theme()

# ─── Session Başlatma ─────────────────────────────────────────────────────────

def init_session():
    defaults = {
        "authenticated":     True,   # Login devre dışı — test modu
        "current_user":      "admin",
        "scheduler_started": False,
        "current_page":      "🎯 Bugün",
        "refresh_count":     0,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_session()


# ─── Auto Refresh ─────────────────────────────────────────────────────────────

def add_auto_refresh():
    """JavaScript tabanlı otomatik yenileme"""
    refresh_ms = AUTO_REFRESH_INTERVAL * 1000
    st.markdown(f"""
    <script>
        setTimeout(function() {{
            const btn = window.parent.document.querySelector('[data-testid="stButton"]');
            window.parent.location.reload();
        }}, {refresh_ms});
    </script>
    """, unsafe_allow_html=True)


# ─── Giriş Ekranı ─────────────────────────────────────────────────────────────

def login_page():
    # Premium login arka planı
    st.markdown(f"""
    <style>
    .stApp {{
        background: {THEME['bg_dark']};
        background-image:
            radial-gradient(ellipse at 20% 20%, #0d2040 0%, transparent 50%),
            radial-gradient(ellipse at 80% 80%, #0a1a30 0%, transparent 50%),
            radial-gradient(ellipse at 50% 50%, #0a0e1a 0%, {THEME['bg_dark']} 100%);
    }}
    </style>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 1.1, 1])
    with col2:
        st.markdown(
            f'<div style="text-align:center;padding:60px 0 40px 0">'
            f'<div style="display:inline-flex;align-items:center;justify-content:center;width:72px;height:72px;background:linear-gradient(135deg,{THEME["blue"]} 0%,{THEME["purple"]} 100%);border-radius:20px;font-size:36px;box-shadow:{THEME["glow_blue"]};margin-bottom:16px">📊</div>'
            f'<h1 style="color:{THEME["text_primary"]};font-size:34px;font-weight:800;margin:0 0 6px 0;letter-spacing:-1px">FinSentinel</h1>'
            f'<p style="color:{THEME["text_muted"]};font-size:15px;margin:0;font-weight:400">Finansal Zeka Platformu</p>'
            f'<div style="display:flex;justify-content:center;gap:16px;margin-top:14px">'
            f'<span style="color:{THEME["text_dim"]};font-size:12px">📈 Canlı Piyasa</span>'
            f'<span style="color:{THEME["text_dim"]};font-size:12px">🤖 AI Analiz</span>'
            f'<span style="color:{THEME["text_dim"]};font-size:12px">🔔 Alarmlar</span>'
            f'</div>'
            f'</div>',
            unsafe_allow_html=True
        )

        with st.form("login_form"):
            username = st.text_input(
                "Kullanıcı Adı",
                placeholder="Kullanıcı adınız...",
            )
            password = st.text_input(
                "Şifre",
                type="password",
                placeholder="Şifreniz...",
            )
            submitted = st.form_submit_button(
                "🚀 Giriş Yap",
                use_container_width=True
            )

            if submitted:
                user_info = USERS.get(username.strip())
                if user_info and user_info["password"] == password:
                    st.session_state.authenticated = True
                    st.session_state.current_user = username.strip()
                    st.rerun()
                else:
                    st.error("❌ Kullanıcı adı veya şifre hatalı")

        bg_card = THEME['bg_card']
        border  = THEME['border']
        text_dim = THEME['text_dim']
        st.markdown(
            f'<p style="text-align:center;color:{text_dim};font-size:12px;margin-top:20px">Yetkili kullanıcılar sisteme giriş yapabilir.<br>Kişisel analiz platformu — bilgilendirme amaçlıdır</p>',
            unsafe_allow_html=True
        )


# ─── Zamanlayıcı ──────────────────────────────────────────────────────────────

def ensure_scheduler():
    if not st.session_state.scheduler_started:
        try:
            from core.scheduler import start_scheduler
            start_scheduler()
            st.session_state.scheduler_started = True
        except Exception:
            pass


# ─── Navigasyon ───────────────────────────────────────────────────────────────

PAGES = {
    "🎯 Bugün":             "pages/00_bugun.py",
    "🕌 Katılım Endeksi":   "pages/22_katilim.py",
    "📊 BIST Hisseler":     "pages/24_hisseler.py",
    "📦 Yatırım Fonları":   "pages/17_funds.py",
    "🥇 Altın & Emtia":    "pages/05_commodities.py",
    "💼 Portföy":           "pages/11_portfolio.py",
    # --- Gizli sayfalar (menüde görünmez, kod içinden erişilebilir) ---
    "🇹🇷 BIST / KAP":       "pages/02_bist.py",
    "📈 Grafik Merkezi":    "pages/07_grafik.py",
    "🏛️ Makro & Sentiment": "pages/08_makro_sentiment.py",
    "📰 Haberler & KAP":    "pages/09_news.py",
    "📊 Temel Analiz":      "pages/18_temel_analiz.py",
    "🏠 Emlak Endeksi":     "pages/23_emlak_endeksi.py",
}

PAGE_GROUPS = {
    "🎯 GÜNLÜK ÖZET": [
        "🎯 Bugün",
    ],
    "📈 PİYASALAR": [
        "🕌 Katılım Endeksi",
        "📊 BIST Hisseler",
        "📦 Yatırım Fonları",
        "🥇 Altın & Emtia",
    ],
    "💼 YÖNETİM": [
        "💼 Portföy",
    ],
}


def global_search():
    """Sidebar global arama kutusu"""
    st.markdown('<div style="margin-top: -10px; margin-bottom: 20px;">', unsafe_allow_html=True)
    search_q = st.text_input(
        "Sembol Ara",
        placeholder="Hisse, Döviz, Kripto...",
        label_visibility="collapsed",
        key="global_search_input"
    )
    st.markdown('</div>', unsafe_allow_html=True)
    
    if search_q:
        # Arama mantığı — sayfa yönlendirme simülasyonu
        st.session_state.search_query = search_q
        st.session_state.current_page = "📈 Grafik Analizi"
        # st.rerun() # Hemen rerun yaparsak input temizlenmeyebilir, butona basılmış gibi davranabiliriz


def user_profile_section():
    """Sidebar kullanıcı profil kartı"""
    user = st.session_state.get("current_user", "admin")
    name = USERS.get(user, {}).get("display", "Kullanıcı")
    
    st.markdown(
        f'<div class="sidebar-user">'
        f'<div class="user-avatar">{user[0].upper()}</div>'
        f'<div class="user-info">'
        f'<div class="user-name">{name}</div>'
        f'<div class="user-status"><span class="status-dot"></span> Çevrimiçi • Premium</div>'
        f'</div>'
        f'<div style="color:{THEME["text_dim"]};cursor:pointer" title="Çıkış Yap">🚪</div>'
        f'</div>',
        unsafe_allow_html=True
    )


def sidebar_nav():
    from utils.ui import premium_divider, marquee_ticker
    
    with st.sidebar:
        # Logo & Başlık
        _blue   = THEME["blue"]
        _purple = THEME["purple"]
        _glow   = THEME["glow_blue"]
        _tp     = THEME["text_primary"]
        _tm     = THEME["text_muted"]
        st.markdown(
            f'<div style="padding:20px 0 24px 0;text-align:center">'
            f'<div style="display:inline-flex;align-items:center;justify-content:center;width:54px;height:54px;background:linear-gradient(135deg,{_blue} 0%,{_purple} 100%);border-radius:16px;font-size:28px;margin-bottom:12px;box-shadow:{_glow}">📊</div>'
            f'<div style="color:{_tp};font-size:20px;font-weight:800;letter-spacing:-0.5px">FinSentinel</div>'
            f'<div style="color:{_tm};font-size:12px;font-weight:500;opacity:0.8">Financial Intelligence v3.0</div>'
            f'</div>',
            unsafe_allow_html=True
        )

        global_search()

        # Canlı Piyasa Mini Widget
        try:
            from core.fetcher import PriceFetcher
            mini_syms = ["USDTRY=X", "GC=F", "XU100.IS", "XK030.IS"]
            mini_labels = {"USDTRY=X": "USD/TRY", "GC=F": "Altın",
                           "XU100.IS": "BIST 100", "XK030.IS": "Katılım 30"}
            import yfinance as _yf
            # Forex + emtia: bulk quotes
            _non_bist = ["USDTRY=X", "GC=F"]
            mini_data = PriceFetcher.get_bulk_quotes(_non_bist)
            # BIST endeksleri: yf.download (5 günlük, son 2 kapanış)
            for _bs in ["XU100.IS", "XK030.IS"]:
                try:
                    _df = _yf.download(_bs, period="5d", interval="1d",
                                       progress=False, auto_adjust=True)
                    if _df is not None and not _df.empty:
                        _cl_raw = _df["Close"]
                        if hasattr(_cl_raw, "squeeze"):
                            _cl_raw = _cl_raw.squeeze()
                        _cl = _cl_raw.dropna() if hasattr(_cl_raw, "dropna") else _cl_raw
                        if hasattr(_cl, "__len__") and len(_cl) >= 2:
                            _p  = float(_cl.iloc[-1]) if hasattr(_cl, "iloc") else float(_cl)
                            _pc = float(_cl.iloc[-2]) if hasattr(_cl, "iloc") else float(_cl)
                            mini_data[_bs] = {
                                "price": round(_p, 2),
                                "change_pct": round((_p - _pc) / _pc * 100, 2),
                            }
                except Exception:
                    pass

            rows_html = ""
            _tm = THEME["text_muted"]
            _tp = THEME["text_primary"]
            _b20 = THEME["border"] + "20"
            _gn = THEME["green"]
            _rd = THEME["red"]
            for sym in mini_syms:
                q = mini_data.get(sym, {})
                if "error" not in q and q:
                    pct   = q["change_pct"]
                    color = _gn if pct >= 0 else _rd
                    arrow = "▲" if pct >= 0 else "▼"
                    lbl   = mini_labels[sym]
                    p_fmt = f"{q['price']:,.2f}"
                    pc_fmt = f"{abs(pct):.2f}"
                    rows_html += (
                        f'<div style="display:flex;justify-content:space-between;padding:5px 0;border-bottom:1px solid {_b20}">'
                        f'<span style="color:{_tm};font-size:12px">{lbl}</span>'
                        f'<div style="text-align:right">'
                        f'<span style="color:{_tp};font-size:12px;font-weight:600">{p_fmt}</span>'
                        f'<span style="color:{color};font-size:11px;margin-left:6px">{arrow}{pc_fmt}%</span>'
                        f'</div></div>'
                    )

            if rows_html:
                _bg2 = THEME["bg_card2"]
                _brd = THEME["border"]
                _td  = THEME["text_dim"]
                st.markdown(
                    f'<div style="background:{_bg2};border:1px solid {_brd};border-radius:10px;padding:10px 14px;margin-bottom:16px">'
                    f'<div style="color:{_td};font-size:10px;text-transform:uppercase;letter-spacing:1px;margin-bottom:8px">⚡ Anlık Piyasa</div>'
                    f'{rows_html}</div>',
                    unsafe_allow_html=True
                )
        except Exception:
            pass

        # Grup bazlı navigasyon
        current = st.session_state.get("current_page", "🎯 Bugün")
        selected = None

        for group_name, pages in PAGE_GROUPS.items():
            premium_divider(group_name)
            
            for page in pages:
                is_active = (page == current)
                active_style = f"background:{THEME['blue_dark']};color:{THEME['blue']};border:1px solid {THEME['blue']}30;" if is_active else f"background:transparent;color:{THEME['text_muted']};border:1px solid transparent;"
                if st.button(
                    page,
                    key=f"nav_{page}",
                    use_container_width=True,
                ):
                    selected = page
                    st.session_state.current_page = page

        # Yenile butonu
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown(f"<hr style='border:none;border-top:1px solid {THEME['border']};margin:4px 0 12px 0'>", unsafe_allow_html=True)

        if st.button("🔄 Verileri Yenile", use_container_width=True, key="refresh_btn"):
            st.rerun()

        user_profile_section()

    return st.session_state.get("current_page", "🎯 Bugün")


def show_global_ticker():
    """Tüm sayfalarda görünen üst kayan yazı"""
    from core.fetcher import PriceFetcher
    from utils.ui import marquee_ticker
    
    try:
        import yfinance as _yf2
        syms = ["XU100.IS", "XK030.IS", "USDTRY=X", "GC=F", "SI=F", "CL=F"]
        labels = {"XU100.IS": "BIST 100", "XK030.IS": "KATİLIM 30",
                  "USDTRY=X": "USD/TRY", "GC=F": "ALTIN", "SI=F": "GÜMÜŞ", "CL=F": "PETROL"}

        data = PriceFetcher.get_bulk_quotes(["USDTRY=X", "GC=F", "SI=F", "CL=F"])
        for _bs in ["XU100.IS", "XK030.IS"]:
            try:
                _df = _yf2.download(_bs, period="5d", interval="1d",
                                    progress=False, auto_adjust=True)
                if _df is not None and not _df.empty:
                    _cl_raw = _df["Close"]
                    if hasattr(_cl_raw, "squeeze"):
                        _cl_raw = _cl_raw.squeeze()
                    _cl = _cl_raw.dropna() if hasattr(_cl_raw, "dropna") else _cl_raw
                    if hasattr(_cl, "__len__") and len(_cl) >= 2:
                        _p = float(_cl.iloc[-1]) if hasattr(_cl, "iloc") else float(_cl)
                        _pc = float(_cl.iloc[-2]) if hasattr(_cl, "iloc") else float(_cl)
                        data[_bs] = {"price": round(_p, 2),
                                     "change_pct": round((_p-_pc)/_pc*100, 2)}
            except Exception:
                pass
        ticker_items = []
        for s in syms:
            q = data.get(s, {})
            if "error" not in q and q:
                ticker_items.append({
                    "label": labels[s],
                    "value": f"{q['price']:,.2f}",
                    "change": q["change_pct"]
                })
        
        if ticker_items:
            marquee_ticker(ticker_items)
    except Exception:
        pass


# ─── Sayfa Yönlendirme ────────────────────────────────────────────────────────

def load_page(page_name: str):
    page_file = PAGES.get(page_name)
    if not page_file:
        st.error("Sayfa bulunamadı")
        return

    page_path = Path(__file__).parent / page_file
    if not page_path.exists():
        from utils.ui import page_header, info_box
        page_header(page_name, "Bu sayfa yakında eklenecek")
        info_box(f"<b>{page_name}</b> geliştirme aşamasında.", "info")
        return

    # ── Dinamik tarayıcı sekme başlığı ──────────────────────────────────
    import re as _re
    import streamlit.components.v1 as _components
    clean_name = _re.sub(r'[^\w\s/İĞŞÜÖÇığşüöç]', '', page_name).strip()
    _components.html(
        f"<script>window.parent.document.title = '{clean_name} | FinSentinel';</script>",
        height=0,
    )

    # Ghosting Fix: Clear previous page content before loading new one
    st.empty()

    with open(page_path, "r", encoding="utf-8") as f:
        code = f.read()
    exec(compile(code, page_file, "exec"), {"__name__": "__main__", "__file__": str(page_path)})


# ─── Ana Dashboard ────────────────────────────────────────────────────────────

def format_price(value, decimals=2):
    if value is None: return "—"
    if value >= 1000: return f"{value:,.{decimals}f}"
    return f"{value:.{decimals}f}"


def _section_divider(title: str, subtitle: str = "", icon: str = ""):
    """Premium bölüm başlığı"""
    bg2  = THEME["bg_card2"]
    brd  = THEME["border"]
    blue = THEME["blue"]
    tp   = THEME["text_primary"]
    tm   = THEME["text_muted"]
    st.markdown(
        f"<div style='background:{bg2};border:1px solid {brd};border-left:3px solid {blue};"
        f"border-radius:0 8px 8px 0;padding:10px 16px;margin:18px 0 12px 0;display:flex;"
        f"align-items:center;gap:10px'>"
        f"<span style='font-size:18px'>{icon}</span>"
        f"<div><div style='color:{tp};font-size:14px;font-weight:700'>{title}</div>"
        f"{'<div style=color:'+tm+';font-size:11px>'+subtitle+'</div>' if subtitle else ''}"
        f"</div></div>",
        unsafe_allow_html=True
    )


def main_dashboard():
    from utils.ui import page_header, metric_card, market_table, info_box, recommendation_card, section_header, live_indicator
    from core.fetcher import PriceFetcher, NewsFetcher

    # ── Başlık ────────────────────────────────────────────────────────────
    col_title, col_live = st.columns([4, 1])
    with col_title:
        page_header("📊 Piyasa Özeti", "Türkiye ve küresel piyasalar — anlık veriler")
    with col_live:
        st.markdown("<div style='margin-top:18px'></div>", unsafe_allow_html=True)
        live_indicator()

    # ── Üst Metrik Satırı ─────────────────────────────────────────────────
    priority = {
        "USD/TRY": "USDTRY=X", "EUR/TRY": "EURTRY=X",
        "BIST 100": "XU100.IS", "Altın": "GC=F",
        "BTC": "BTC-USD",      "ETH": "ETH-USD",
    }
    with st.spinner(""):
        _bist_syms  = [s for s in priority.values() if s.endswith(".IS")]
        _other_syms = [s for s in priority.values() if not s.endswith(".IS")]
        quotes = PriceFetcher.get_bulk_quotes(_other_syms)
        if _bist_syms:
            _tv = PriceFetcher.get_tv_quotes(_bist_syms)
            quotes.update(_tv if _tv else PriceFetcher.get_bulk_quotes(_bist_syms))

    cols = st.columns(len(priority))
    for col, (label, sym) in zip(cols, priority.items()):
        with col:
            q = quotes.get(sym, {})
            if "error" not in q and q:
                metric_card(label, format_price(q["price"]), q.get("change_pct", 0))
            else:
                metric_card(label, "—", 0)

    # ── AI Brifing & Duyarlılık ──────────────────────────────────────────
    _section_divider("Günlük AI Piyasa Brifing", "Yapay zeka destekli sabah raporu", "🌅")
    br_left, br_right = st.columns([2, 1])

    with br_left:
        port_sum = ""
        try:
            from sqlalchemy import text
            from core.db import db
            with db.get_session() as session:
                p_rows = session.execute(text("SELECT symbol, quantity FROM portfolio WHERE is_open=1")).fetchall()
                if p_rows:
                    port_sum = ", ".join([f"{r.symbol} ({r.quantity} adet)" for r in p_rows[:5]])
        except: pass

        if st.checkbox("🌅 Günlük Brifingimi Hazırla", value=True):
            from core.ai_engine import get_morning_briefing
            from utils.ui import morning_briefing_card
            with st.spinner("Yapay zeka piyasaları süzüyor..."):
                briefing = get_morning_briefing(quotes, NewsFetcher.get_latest(limit=5), port_sum)
                morning_briefing_card(briefing)

    with br_right:
        from utils.ui import fear_greed_gauge
        bist_ch = quotes.get("XU100.IS", {}).get("change_pct", 0) or 0
        vix_proxy = (quotes.get("BTC-USD", {}).get("change_pct", 0) or 0) * -0.5
        sentiment_score = 50 + (bist_ch * 10) + (vix_proxy * 5)
        sentiment_score = max(5, min(95, sentiment_score))

        st.markdown(
            f"<div style='background:{THEME['bg_card']};border:1px solid {THEME['border']};"
            f"border-radius:12px;padding:14px 16px;margin-bottom:12px'>"
            f"<div style='color:{THEME['text_muted']};font-size:11px;font-weight:600;"
            f"text-transform:uppercase;letter-spacing:.8px;margin-bottom:6px'>🎯 Korku & Açgözlülük</div>",
            unsafe_allow_html=True
        )
        fear_greed_gauge(sentiment_score)
        st.markdown(
            f"<div style='color:{THEME['text_muted']};font-size:10px;text-align:center;margin-top:-6px'>"
            f"BIST & Global Risk Projeksiyonu</div></div>",
            unsafe_allow_html=True
        )

        # Smart Money
        st.markdown(
            f"<div style='background:{THEME['bg_card']};border:1px solid {THEME['border']};"
            f"border-radius:12px;padding:14px 16px'>"
            f"<div style='color:{THEME['blue']};font-size:12px;font-weight:700;margin-bottom:10px'>"
            f"👔 Smart Money (Insider) Akışı</div>",
            unsafe_allow_html=True
        )
        from core.kap_fetcher import fetch_smart_money
        with st.spinner("KAP taranıyor..."):
            signals = fetch_smart_money(limit=5)
        if signals:
            for s in signals:
                st.markdown(
                    f"<div style='font-size:11px;margin-bottom:8px;padding-bottom:7px;"
                    f"border-bottom:1px solid {THEME['border']}30'>"
                    f"<span style='background:{THEME['orange']}20;color:{THEME['orange']};"
                    f"padding:1px 6px;border-radius:10px;font-size:10px'>{s['type_label']}</span>"
                    f"<div style='margin-top:4px;font-weight:600'>{s['company']}</div>"
                    f"<div style='color:{THEME['text_muted']}'>{s['title'][:55]}...</div></div>",
                    unsafe_allow_html=True
                )
        else:
            st.caption("Son 24 saatte kritik insider akışı saptanmadı.")
        st.markdown("</div>", unsafe_allow_html=True)

    # ── Alpha Radar V2 ────────────────────────────────────────────────────
    _section_divider("Alpha Radar V2", "Teknik + Hacim + Insider skorlaması", "🔥")
    from services.alpha_generator import AlphaGenerator
    AlphaGenerator.render_alpha_radar_ui()

    # ── Piyasa Fırsatları & Yönlendirme ──────────────────────────────────
    _section_divider("Piyasa Yönlendirme", "AI destekli strateji önerileri", "🧭")
    _show_market_guidance(quotes, priority)

    # ── Ana Veri Grid ─────────────────────────────────────────────────────
    _section_divider("Piyasa Verileri", "Forex · Emtia · Dünya Endeksleri · Haberler", "📡")
    left, right = st.columns([1.05, 1])

    with left:
        st.markdown(
            f"<div style='color:{THEME['text_muted']};font-size:11px;font-weight:600;"
            f"text-transform:uppercase;letter-spacing:.8px;margin-bottom:8px'>💱 Forex & Emtia</div>",
            unsafe_allow_html=True
        )
        try:
            forex_df = PriceFetcher.get_forex_overview()
            if not forex_df.empty:
                muted = THEME["text_muted"]
                st.markdown(f"<div style='color:{muted};font-size:12px;margin-bottom:6px;font-weight:600'>📍 TRY Pariteleri</div>", unsafe_allow_html=True)
                try_pairs = forex_df[forex_df["Parite"].str.contains("TRY")]
                market_table(try_pairs, "Parite", "Fiyat", "Değişim %")
                st.markdown(f"<div style='color:{muted};font-size:12px;margin:10px 0 6px;font-weight:600'>🌐 Major Pariteler</div>", unsafe_allow_html=True)
                major_pairs = forex_df[~forex_df["Parite"].str.contains("TRY")]
                market_table(major_pairs, "Parite", "Fiyat", "Değişim %")
        except Exception as e:
            info_box(f"Forex verisi yüklenemedi: {e}", "warning")

        st.markdown(
            f"<div style='color:{THEME['text_muted']};font-size:11px;font-weight:600;"
            f"text-transform:uppercase;letter-spacing:.8px;margin:16px 0 8px'>🥇 Emtia</div>",
            unsafe_allow_html=True
        )
        try:
            comm_df = PriceFetcher.get_commodity_overview()
            if not comm_df.empty:
                market_table(comm_df, "Emtia", "Fiyat", "Değişim %")
        except Exception as e:
            info_box(f"Emtia verisi yüklenemedi: {e}", "warning")

    with right:
        st.markdown(
            f"<div style='color:{THEME['text_muted']};font-size:11px;font-weight:600;"
            f"text-transform:uppercase;letter-spacing:.8px;margin-bottom:8px'>🌍 Dünya Endeksleri</div>",
            unsafe_allow_html=True
        )
        try:
            world_df = PriceFetcher.get_world_indices()
            if not world_df.empty:
                market_table(world_df, "Borsa", "Değer", "Değişim %")
        except Exception as e:
            info_box(f"Endeks verisi yüklenemedi: {e}", "warning")

        st.markdown(
            f"<div style='color:{THEME['text_muted']};font-size:11px;font-weight:600;"
            f"text-transform:uppercase;letter-spacing:.8px;margin:16px 0 8px'>📰 Son Haberler</div>",
            unsafe_allow_html=True
        )
        try:
            news = NewsFetcher.get_latest(limit=6)
            for item in news[:6]:
                title  = item.get("title",  "") if isinstance(item, dict) else getattr(item, "title", "")
                url    = item.get("url",    "") if isinstance(item, dict) else getattr(item, "url",   "")
                source = item.get("source", "") if isinstance(item, dict) else getattr(item, "source","")
                pub    = item.get("published_at","") if isinstance(item, dict) else ""
                pub_str = ""
                if pub:
                    try:
                        from datetime import datetime as dt
                        pub_dt = dt.fromisoformat(pub[:19]) if isinstance(pub, str) else pub
                        pub_str = pub_dt.strftime("%H:%M")
                    except Exception:
                        pass
                _tp  = THEME["text_primary"]
                _blue = THEME["blue"]
                _td  = THEME["text_dim"]
                _b20 = THEME["border"] + "20"
                _t85 = title[:85] + ("..." if len(title) > 85 else "")
                _pub_span = f'<span style="color:{_td};font-size:10px">{pub_str}</span>' if pub_str else ""
                st.markdown(
                    f'<div style="padding:10px 0;border-bottom:1px solid {_b20}">'
                    f'<a href="{url}" target="_blank" style="color:{_tp};font-size:13px;font-weight:500;'
                    f'text-decoration:none;line-height:1.4;display:block">{_t85}</a>'
                    f'<div style="display:flex;gap:10px;margin-top:4px">'
                    f'<span style="background:{_blue}20;color:{_blue};padding:2px 8px;border-radius:20px;font-size:10px">{source}</span>'
                    f'{_pub_span}</div></div>',
                    unsafe_allow_html=True
                )
        except Exception as e:
            info_box(f"Haberler yüklenemedi: {e}", "warning")


def _show_market_guidance(quotes: dict, priority: dict):
    """Piyasa durumuna göre kullanıcı yönlendirme kartları"""
    from utils.ui import recommendation_card

    recommendations = []

    # USD/TRY analizi
    usd = quotes.get("USDTRY=X", {})
    if "error" not in usd and usd:
        pct = usd.get("change_pct", 0)
        if pct > 1.5:
            recommendations.append(("danger",  "⚠️ TL Değer Kaybı",
                f"USD/TRY bugün <b>%{pct:.2f}</b> yükseldi. Döviz bazlı varlıklar (altın, kripto) ve ihracatçı şirketler bu ortamda avantajlı olabilir. TL mevduatı ve tahvil pozisyonlarını gözden geçirin.",
                "💸"))
        elif pct < -1.5:
            recommendations.append(("success", "✅ TL Güçleniyor",
                f"USD/TRY bugün <b>%{abs(pct):.2f}</b> geriledi. TL'nin değer kazandığı dönemlerde yerli hisse senetleri ve TL tahviller öne çıkabilir.",
                "💪"))

    # BTC analizi
    btc = quotes.get("BTC-USD", {})
    if "error" not in btc and btc:
        pct = btc.get("change_pct", 0)
        if pct > 3:
            recommendations.append(("info", "₿ Kripto Yükseliş",
                f"Bitcoin bugün <b>%{pct:.2f}</b> artışla güçlü seyrediyor. Yüksek momentum dönemlerinde altcoinler de genellikle pozitif etkilenebilir.",
                "🚀"))
        elif pct < -5:
            recommendations.append(("warning", "₿ Kripto Satış Baskısı",
                f"Bitcoin bugün <b>%{abs(pct):.2f}</b> düştü. Kripto portföyünüzdeki risk yönetimine dikkat edin, stop-loss seviyelerinizi gözden geçirin.",
                "⚡"))

    # Altın analizi
    gold = quotes.get("GC=F", {})
    if "error" not in gold and gold:
        pct = gold.get("change_pct", 0)
        if pct > 1:
            recommendations.append(("info", "🥇 Altın Güçlü",
                f"Altın bugün <b>%{pct:.2f}</b> yükseldi. Küresel belirsizlik dönemlerinde güvenli liman talebi artmaktadır.",
                "🛡️"))

    # BIST analizi
    bist = quotes.get("XU100.IS", {})
    if "error" not in bist and bist:
        pct = bist.get("change_pct", 0)
        if pct < -2:
            recommendations.append(("danger", "📉 BIST 100 Sert Düşüş",
                f"BIST 100 bugün <b>%{abs(pct):.2f}</b> geriledi. Piyasa genelinde satış baskısı var. Teknik destek seviyelerini ve bireysel hisse haberlerini takip edin.",
                "⚠️"))
        elif pct > 2:
            recommendations.append(("success", "📈 BIST 100 Güçlü",
                f"BIST 100 bugün <b>%{pct:.2f}</b> yükseldi. Bankacılık ve sanayi sektörlerinin performansını takip edin.",
                "💹"))

    # Varsayılan yönlendirme (hiç kural tetiklenmediyse)
    if not recommendations:
        recommendations.append(("neutral", "📊 Piyasa Sakin Seyrediyor",
            "Büyük çaplı hareketler gözlemlenmiyor. Grafik Analizi sayfasından ilgilendiğiniz varlıklar için teknik analiz yapabilirsiniz.",
            "🔍"))

    # Kartları göster
    if recommendations:
        cols = st.columns(min(len(recommendations), 3))
        for col, (rtype, rtitle, rcontent, ricon) in zip(cols, recommendations[:3]):
            with col:
                from utils.ui import recommendation_card
                recommendation_card(rtitle, rcontent, rtype, ricon)


# ─── Çalıştır ─────────────────────────────────────────────────────────────────

# Login devre dışı — doğrudan dashboard'a geç
ensure_scheduler()
show_global_ticker()
selected_page = sidebar_nav()

# Main Container using st.empty() to ensure fresh state on every page load
main_area = st.empty()

with main_area.container():
    load_page(selected_page)
