"""
FinSentinel — Ortak UI Bileşenleri (Premium Edition)
utils/ui.py
"""
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import streamlit as st
from config.settings import THEME


# ─── Renk Yardımcıları ────────────────────────────────────────────────────────

def delta_color(value: float) -> str:
    if value > 0:   return THEME["green"]
    if value < 0:   return THEME["red"]
    return THEME["text_muted"]


def direction_emoji(pct: float) -> str:
    if pct > 1:  return "▲"
    if pct < -1: return "▼"
    if pct > 0:  return "▲"
    if pct < 0:  return "▼"
    return "◆"


def format_price(value: float, decimals: int = 2) -> str:
    if value is None:
        return "—"
    if value >= 1_000_000:
        return f"{value/1_000_000:.2f}M"
    if value >= 1_000:
        return f"{value:,.{decimals}f}"
    return f"{value:.{decimals}f}"


def format_large(value: float) -> str:
    if value is None:
        return "—"
    if value >= 1e12:
        return f"${value/1e12:.2f}T"
    if value >= 1e9:
        return f"${value/1e9:.2f}B"
    if value >= 1e6:
        return f"${value/1e6:.2f}M"
    return f"${value:,.0f}"


# ─── Premium Metrik Kartları ──────────────────────────────────────────────────

def metric_card(label: str, value: str, delta: float = None, suffix: str = "", subtitle: str = ""):
    """Premium fiyat metrik kartı — glow efektli"""
    color = delta_color(delta) if delta is not None else THEME["text_muted"]
    glow  = THEME["glow_green"] if (delta and delta > 0) else (THEME["glow_red"] if (delta and delta < 0) else "none")
    delta_str = ""
    if delta is not None:
        arrow = "▲" if delta > 0 else ("▼" if delta < 0 else "◆")
        delta_str = f'<div style="color:{color};font-size:13px;font-weight:600;margin-top:2px">{arrow} {abs(delta):.2f}%</div>'

    sub_str = f'<div style="color:{THEME["text_dim"]};font-size:11px;margin-top:2px">{subtitle}</div>' if subtitle else ""

    bar_bg = ('linear-gradient(90deg,' + color + ',transparent)') if delta else 'transparent'
    st.markdown(
        f'<div style="background:{THEME["bg_card"]};border:1px solid {THEME["border"]};border-radius:12px;padding:16px 18px;text-align:center;box-shadow:{glow};transition:all 0.3s ease;position:relative;overflow:hidden">'
        f'<div style="position:absolute;top:0;left:0;right:0;height:2px;background:{bar_bg}"></div>'
        f'<div style="color:{THEME["text_muted"]};font-size:11px;text-transform:uppercase;letter-spacing:1px;margin-bottom:6px">{label}</div>'
        f'<div style="color:{THEME["text_primary"]};font-size:22px;font-weight:700;font-variant-numeric:tabular-nums;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{value}{suffix}</div>'
        f'{delta_str}{sub_str}'
        f'</div>',
        unsafe_allow_html=True
    )


def price_ticker_card(label: str, price: str, change_pct: float, volume: str = ""):
    """Yatay kompakt ticker kartı — tablo satırı için"""
    color = delta_color(change_pct)
    arrow = "▲" if change_pct > 0 else ("▼" if change_pct < 0 else "◆")
    bg = f"{THEME['green_dark']}40" if change_pct > 0 else (f"{THEME['red_dark']}40" if change_pct < 0 else "transparent")

    return (
        f'<div style="display:flex;align-items:center;justify-content:space-between;padding:10px 14px;background:{bg};border-radius:8px;margin:3px 0;border:1px solid {THEME["border"]}">'
        f'<span style="color:{THEME["text_primary"]};font-weight:600;font-size:13px;min-width:100px">{label}</span>'
        f'<span style="color:{THEME["text_primary"]};font-size:13px;font-variant-numeric:tabular-nums">{price}</span>'
        f'<span style="color:{color};font-size:13px;font-weight:600;min-width:70px;text-align:right">{arrow} {abs(change_pct):.2f}%</span>'
        f'</div>'
    )


def signal_badge(signal: str) -> str:
    """Premium sinyal rozeti"""
    styles = {
        "GÜÇLÜ AL":      (THEME["green"],  THEME["green_dark"],  "🚀"),
        "AL":            (THEME["green"],  THEME["green_dark"],  "↑"),
        "NÖTR":          (THEME["yellow"], "#2d2600",            "→"),
        "SAT":           (THEME["red"],    THEME["red_dark"],    "↓"),
        "GÜÇLÜ SAT":     (THEME["red"],    THEME["red_dark"],    "💀"),
        "YETERSIZ_VERI": (THEME["text_muted"], THEME["bg_card"], "?"),
    }
    fg, bg, icon = styles.get(signal, (THEME["text_muted"], THEME["bg_card"], "?"))
    return f'<span style="background:{bg};color:{fg};border:1px solid {fg}40;padding:4px 12px;border-radius:20px;font-size:12px;font-weight:700">{icon} {signal}</span>'


# ─── Premium Grafik Fonksiyonları ─────────────────────────────────────────────

    return fig


# ─── New Premium UI Elements ──────────────────────────────────────────────────

def premium_divider(label: str = "", icon: str = ""):
    """Gradientli premium bölücü line"""
    _blue = THEME["blue"]
    _border = THEME["border"]
    _tm = THEME["text_muted"]
    label_html = f'<span style="background:{THEME["bg_dark"]};padding:0 15px;color:{_tm};font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:2px;display:flex;align-items:center;gap:8px">{icon} {label}</span>' if label else ""
    st.markdown(
        f'<div style="display:flex;align-items:center;margin:30px 0 20px 0">'
        f'<div style="flex:1;height:1px;background:linear-gradient(90deg,transparent,{_border},{_blue}40)"></div>'
        f'{label_html}'
        f'<div style="flex:1;height:1px;background:linear-gradient(90deg,{_blue}40,{_border},transparent)"></div>'
        f'</div>',
        unsafe_allow_html=True
    )


def glass_card(content: str, title: str = "", icon: str = "", glow: bool = False):
    """Modern glassmorphism kartı"""
    _glow = THEME["glow_blue"] if glow else "none"
    _bg = "rgba(17, 24, 39, 0.7)"
    _border = "rgba(77, 166, 255, 0.2)"
    _header = f'<div style="color:{THEME["blue"]};font-size:12px;font-weight:800;margin-bottom:10px;display:flex;align-items:center;gap:8px">{icon} {title}</div>' if title else ""
    
    st.markdown(
        f'<div style="background:{_bg};backdrop-filter:blur(10px);-webkit-backdrop-filter:blur(10px);'
        f'border:1px solid {_border};border-radius:16px;padding:20px;box-shadow:{_glow};margin:10px 0">'
        f'{_header}'
        f'<div style="color:{THEME["text_primary"]};font-size:14px;line-height:1.6">{content}</div>'
        f'</div>',
        unsafe_allow_html=True
    )


def morning_briefing_card(content: str):
    """AI tarafından oluşturulan sabah brifingini şık bir şekilde sunar"""
    html = f"""
    <div style="background:linear-gradient(135deg, {THEME['bg_card']} 0%, #0a192f 100%); 
                border: 1px solid {THEME['blue']}40; border-radius:15px; padding:20px; 
                box-shadow: 0 10px 30px rgba(0,0,0,0.5); margin-bottom:25px; position:relative; overflow:hidden">
        <div style="position:absolute; top:-20px; right:-20px; width:150px; height:150px; 
                    background:radial-gradient(circle, {THEME['blue']}20 0%, transparent 70%); 
                    border-radius:50%; z-index:0"></div>
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:15px; position:relative; z-index:1">
            <h3 style="margin:0; color:{THEME['text_primary']}; font-size:18px">🌤️ Günlük Finansal Brifing</h3>
            <span style="background:{THEME['blue']}20; color:{THEME['blue']}; padding:4px 10px; border-radius:20px; font-size:10px; font-weight:700">AI PRO</span>
        </div>
        <div style="color:{THEME['text_primary']}; font-size:13px; line-height:1.6; position:relative; z-index:1">
            {_md_to_html(content)}
        </div>
        <div style="margin-top:15px; border-top:1px solid {THEME['border']}40; padding-top:15px; color:{THEME['text_muted']}; font-size:11px; font-style:italic">
            🔍 Bu analiz portföyünüz ve güncel piyasa verilerine özel olarak anlık oluşturulmuştur.
        </div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


def fear_greed_gauge(value: int):
    """Korku ve Açgözlülük Endeksi — Premium Gauge Grafiği"""
    label = "Aşırı Korku" if value < 20 else ("Korku" if value < 40 else ("Nötr" if value < 60 else ("Açgözlülük" if value < 80 else "Aşırı Açgözlülük")))
    
    fig = go.Figure(go.Indicator(
        mode = "gauge+number",
        value = value,
        number = {'font': {'size': 40, 'color': THEME['text_primary']}, 'suffix': ''},
        domain = {'x': [0, 1], 'y': [0, 1]},
        title = {'text': f"DUYARLILIK: {label}", 'font': {'size': 12, 'color': THEME['text_muted'], 'weight': 'bold'}},
        gauge = {
            'axis': {'range': [0, 100], 'tickwidth': 1, 'tickcolor': THEME['text_muted'], 'tickmode': 'array', 'tickvals': [0, 20, 40, 60, 80, 100]},
            'bar': {'color': THEME['blue'], 'thickness': 0.2},
            'bgcolor': "rgba(0,0,0,0)",
            'borderwidth': 0,
            'steps': [
                {'range': [0, 20], 'color': '#ff4d6d'},
                {'range': [20, 40], 'color': '#ff758f'},
                {'range': [40, 60], 'color': '#ffd166'},
                {'range': [60, 80], 'color': '#06d6a0'},
                {'range': [80, 100], 'color': '#00c896'}
            ],
            'threshold': {
                'line': {'color': THEME['text_primary'], 'width': 4},
                'thickness': 0.8,
                'value': value
            }
        }
    ))
    fig.update_layout(
        height=220, 
        margin=dict(l=30, r=30, t=40, b=10), 
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color=THEME["text_muted"], family="Inter")
    )
    st.plotly_chart(fig, width="stretch")


def marquee_ticker(items: list):
    """Global kayan yazı ticker - bloomberg stili"""
    # items: list of dicts {"label": "USD/TRY", "value": "32.45", "change": 0.5}
    ticker_items = ""
    for item in items:
        color = THEME["green"] if item["change"] >= 0 else THEME["red"]
        arrow = "▲" if item["change"] >= 0 else "▼"
        ticker_items += (
            f'<div class="ticker-item">'
            f'<span class="ticker-label">{item["label"]}</span>'
            f'<span class="ticker-value">{item["value"]}</span>'
            f'<span class="ticker-delta" style="color:{color}">{arrow} {abs(item["change"]):.2f}%</span>'
            f'</div>'
        )

    st.markdown(f"""
    <style>
    .ticker-wrap {{
        width: 100%;
        overflow: hidden;
        background: {THEME['bg_card']};
        border-bottom: 1px solid {THEME['border']};
        padding: 8px 0;
        position: fixed;
        top: 0;
        left: 0;
        z-index: 999999;
    }}
    .ticker {{
        display: flex;
        white-space: nowrap;
        animation: marquee 40s linear infinite;
    }}
    .ticker:hover {{ animation-play-state: paused; }}
    .ticker-item {{
        display: inline-flex;
        align-items: center;
        padding: 0 25px;
        border-right: 1px solid {THEME['border']}60;
    }}
    .ticker-label {{ color: {THEME['text_muted']}; font-size: 11px; font-weight: 700; text-transform: uppercase; margin-right: 8px; }}
    .ticker-value {{ color: {THEME['text_primary']}; font-size: 13px; font-weight: 700; font-variant-numeric: tabular-nums; margin-right: 6px; }}
    .ticker-delta {{ font-size: 11px; font-weight: 700; }}
    @keyframes marquee {{
        0% {{ transform: translateX(0); }}
        100% {{ transform: translateX(-50%); }}
    }}
    /* Ticker varken main contenti aşağı kaydır */
    .block-container {{ margin-top: 35px !important; }}
    </style>
    <div class="ticker-wrap">
        <div class="ticker">
            {ticker_items} {ticker_items}
        </div>
    </div>
    """, unsafe_allow_html=True)


def _chart_layout(fig, height: int = 520, title: str = ""):
    """Ortak premium grafik layout ayarları"""
    fig.update_layout(
        height=height,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor=THEME["bg_card"],
        font=dict(color=THEME["text_muted"], size=12, family="Inter, sans-serif"),
        legend=dict(
            bgcolor="rgba(0,0,0,0.5)",
            bordercolor=THEME["border"],
            borderwidth=1,
            orientation="h",
            y=1.02,
            font=dict(size=11),
        ),
        margin=dict(l=10, r=10, t=40 if title else 20, b=10),
        hovermode="x unified",
        hoverlabel=dict(
            bgcolor=THEME["bg_card2"],
            bordercolor=THEME["border"],
            font=dict(color=THEME["text_primary"], size=12),
        ),
        title=dict(text=title, font=dict(color=THEME["text_primary"], size=14), x=0.02) if title else None,
    )
    fig.update_xaxes(
        gridcolor=THEME["border"], showgrid=True, zeroline=False,
        showspikes=True, spikecolor=THEME["border"], spikethickness=1,
        tickfont=dict(color=THEME["text_muted"]),
    )
    fig.update_yaxes(
        gridcolor=THEME["border"], showgrid=True, zeroline=False,
        tickfont=dict(color=THEME["text_muted"]),
    )
    return fig


def candlestick_chart(
    df: pd.DataFrame,
    symbol: str,
    show_volume: bool = True,
    show_ma: bool = True,
    height: int = 540,
) -> go.Figure:
    """Premium mum grafik"""
    if df.empty:
        return go.Figure()

    # Yinelenen kolonları kaldır (narwhals DuplicateError önlemi)
    df = df.loc[:, ~df.columns.duplicated()]

    col_map = {c.lower(): c for c in df.columns}
    open_c  = col_map.get("open",  "open")
    high_c  = col_map.get("high",  "high")
    low_c   = col_map.get("low",   "low")
    close_c = col_map.get("close", "close")
    vol_c   = col_map.get("volume","volume")
    date_c  = col_map.get("date",  col_map.get("datetime", "date"))

    rows = 2 if (show_volume and vol_c in df.columns) else 1
    row_heights = [0.72, 0.28] if rows == 2 else [1.0]

    fig = make_subplots(
        rows=rows, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.02,
        row_heights=row_heights,
    )

    # Mum çubuğu
    fig.add_trace(go.Candlestick(
        x=df[date_c],
        open=df[open_c], high=df[high_c],
        low=df[low_c],   close=df[close_c],
        name=symbol,
        increasing_line_color=THEME["green"],
        decreasing_line_color=THEME["red"],
        increasing_fillcolor=THEME["green"],
        decreasing_fillcolor=THEME["red"],
        line=dict(width=1),
    ), row=1, col=1)

    # Hareketli Ortalamalar
    if show_ma:
        ma_cfg = [
            ("SMA_20",  "SMA 20",  THEME["yellow"], 1.2),
            ("SMA_50",  "SMA 50",  THEME["blue"],   1.2),
            ("SMA_200", "SMA 200", THEME["purple"], 1.5),
            ("EMA_21",  "EMA 21",  THEME["cyan"],   1.0),
        ]
        for col_name, label, color, width in ma_cfg:
            if col_name in df.columns:
                fig.add_trace(go.Scatter(
                    x=df[date_c], y=df[col_name],
                    name=label, mode="lines",
                    line=dict(color=color, width=width),
                    opacity=0.85,
                ), row=1, col=1)

    # Bollinger Bantları
    if "BBU_20_2.0" in df.columns and "BBL_20_2.0" in df.columns:
        fig.add_trace(go.Scatter(
            x=df[date_c], y=df["BBU_20_2.0"],
            name="BB Üst", mode="lines",
            line=dict(color=THEME["blue"], width=0.8, dash="dot"),
            opacity=0.5, showlegend=False,
        ), row=1, col=1)
        fig.add_trace(go.Scatter(
            x=df[date_c], y=df["BBL_20_2.0"],
            name="BB Alt", mode="lines",
            line=dict(color=THEME["blue"], width=0.8, dash="dot"),
            fill="tonexty",
            fillcolor="rgba(77,166,255,0.04)",
            opacity=0.5, showlegend=False,
        ), row=1, col=1)

    # Hacim
    if rows == 2 and vol_c in df.columns:
        colors = [
            THEME["green"] if (c >= o) else THEME["red"]
            for c, o in zip(df[close_c], df[open_c])
        ]
        fig.add_trace(go.Bar(
            x=df[date_c], y=df[vol_c],
            name="Hacim",
            marker_color=colors,
            opacity=0.5,
            showlegend=False,
        ), row=2, col=1)

    fig.update_layout(
        height=height,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor=THEME["bg_card"],
        font=dict(color=THEME["text_muted"], size=12),
        legend=dict(bgcolor="rgba(0,0,0,0.4)", bordercolor=THEME["border"],
                    orientation="h", y=1.02, font=dict(size=10)),
        xaxis_rangeslider_visible=False,
        margin=dict(l=10, r=10, t=20, b=10),
        hovermode="x unified",
        hoverlabel=dict(bgcolor=THEME["bg_card2"], bordercolor=THEME["border"],
                        font=dict(color=THEME["text_primary"])),
    )
    for i in range(1, rows + 1):
        fig.update_xaxes(gridcolor=THEME["border"], showgrid=True, zeroline=False,
                         showspikes=True, spikecolor=THEME["border"], row=i, col=1)
        fig.update_yaxes(gridcolor=THEME["border"], showgrid=True, zeroline=False, row=i, col=1)
    return fig


def rsi_chart(df: pd.DataFrame, height: int = 180) -> go.Figure:
    """Premium RSI grafiği"""
    rsi_col  = next((c for c in df.columns if "RSI" in c.upper()), None)
    date_col = "date" if "date" in df.columns else "Date"
    if not rsi_col:
        return go.Figure()

    fig = go.Figure()
    # Bölge renkleri
    fig.add_hrect(y0=70, y1=100, fillcolor=THEME["red"],   opacity=0.06, line_width=0)
    fig.add_hrect(y0=0,  y1=30,  fillcolor=THEME["green"], opacity=0.06, line_width=0)
    fig.add_hline(y=70, line=dict(color=THEME["red"],   width=1, dash="dot"))
    fig.add_hline(y=50, line=dict(color=THEME["text_dim"], width=1, dash="dot"))
    fig.add_hline(y=30, line=dict(color=THEME["green"], width=1, dash="dot"))

    rsi_vals = df[rsi_col]
    colors = [THEME["red"] if v > 70 else (THEME["green"] if v < 30 else THEME["yellow"])
              for v in rsi_vals.fillna(50)]

    fig.add_trace(go.Scatter(
        x=df[date_col], y=rsi_vals,
        name="RSI 14", mode="lines",
        line=dict(color=THEME["yellow"], width=1.8),
    ))
    fig = _chart_layout(fig, height, "RSI (14)")
    fig.update_layout(yaxis=dict(range=[0, 100]))
    return fig


def macd_chart(df: pd.DataFrame, height: int = 180) -> go.Figure:
    """MACD grafiği"""
    macd_col  = next((c for c in df.columns if c.startswith("MACD_") and "s" not in c.lower() and "h" not in c.lower()), None)
    macds_col = next((c for c in df.columns if c.upper().startswith("MACDS")), None)
    macdh_col = next((c for c in df.columns if c.upper().startswith("MACDH")), None)
    date_col  = "date" if "date" in df.columns else "Date"

    if not macd_col:
        return go.Figure()

    fig = go.Figure()
    if macdh_col in (df.columns if macdh_col else []):
        colors = [THEME["green"] if v >= 0 else THEME["red"] for v in df[macdh_col].fillna(0)]
        fig.add_trace(go.Bar(
            x=df[date_col], y=df[macdh_col],
            name="Histogram", marker_color=colors, opacity=0.6,
        ))
    if macd_col:
        fig.add_trace(go.Scatter(x=df[date_col], y=df[macd_col], name="MACD",
                                 line=dict(color=THEME["blue"], width=1.5)))
    if macds_col:
        fig.add_trace(go.Scatter(x=df[date_col], y=df[macds_col], name="Sinyal",
                                 line=dict(color=THEME["orange"], width=1.5)))
    fig.add_hline(y=0, line=dict(color=THEME["text_dim"], width=1, dash="dot"))
    return _chart_layout(fig, height, "MACD (12,26,9)")


def line_chart(
    df: pd.DataFrame,
    x_col: str,
    y_col: str,
    title: str = "",
    color: str = None,
    height: int = 320,
    fill: bool = True,
) -> go.Figure:
    """Premium çizgi grafik — gradient fill"""
    c = color or THEME["blue"]
    fig = go.Figure()

    # Gradient dolgu efekti için üst-alt çift iz
    # Parse hex color to rgba for fill
    def _hex_to_rgba(hex_color: str, alpha: float) -> str:
        h = hex_color.lstrip("#")
        if len(h) == 6:
            r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
            return f"rgba({r},{g},{b},{alpha})"
        return f"rgba(77,166,255,{alpha})"

    fill_color = _hex_to_rgba(c, 0.15) if fill else None

    fig.add_trace(go.Scatter(
        x=df[x_col], y=df[y_col],
        mode="lines",
        name=title,
        line=dict(color=c, width=2.5),
        fill="tozeroy" if fill else None,
        fillcolor=fill_color,
    ))
    return _chart_layout(fig, height, title)


def market_table(df: pd.DataFrame, label_col: str, price_col: str, change_col: str) -> None:
    """Heatmap yerine premium tablo gösterimi"""
    if df.empty:
        return

    # IMPORTANT: No leading whitespace or blank lines — markdown treats 4-space-indented HTML as code blocks
    bg_card  = THEME["bg_card"]
    txt_p    = THEME["text_primary"]
    txt_m    = THEME["text_muted"]
    gn       = THEME["green"]
    rd       = THEME["red"]
    gn_dark  = THEME["green_dark"]
    rd_dark  = THEME["red_dark"]

    html = '<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(155px,1fr));gap:8px;padding:4px 0">'
    for _, row in df.iterrows():
        _pct_raw = row.get(change_col, 0)
        _pri_raw = row.get(price_col, 0)
        pct   = 0.0 if pd.isna(_pct_raw) else float(_pct_raw)
        price = 0.0 if pd.isna(_pri_raw) else float(_pri_raw)
        label = str(row.get(label_col, ""))
        color = gn if pct > 0 else (rd if pct < 0 else txt_m)
        bg    = f"{gn_dark}60" if pct > 0 else (f"{rd_dark}60" if pct < 0 else bg_card)
        arrow = "▲" if pct > 0 else ("▼" if pct < 0 else "◆")
        bar_w = round(min(abs(pct) * 10, 100), 1)
        pct_str = f"{abs(pct):.2f}"
        price_str = format_price(price)
        html += (
            f'<div style="background:{bg};border:1px solid {color}30;border-radius:10px;padding:10px 12px;position:relative;overflow:hidden">'
            f'<div style="position:absolute;bottom:0;left:0;height:2px;width:{bar_w}%;background:{color};opacity:0.6"></div>'
            f'<div style="color:{txt_m};font-size:11px;margin-bottom:4px">{label}</div>'
            f'<div style="color:{txt_p};font-size:15px;font-weight:700;font-variant-numeric:tabular-nums">{price_str}</div>'
            f'<div style="color:{color};font-size:12px;font-weight:600;margin-top:2px">{arrow} {pct_str}%</div>'
            f'</div>'
        )
    html += '</div>'
    st.markdown(html, unsafe_allow_html=True)


def market_heatmap(df: pd.DataFrame, label_col: str, value_col: str, height: int = 360) -> go.Figure:
    """Gelişmiş piyasa ısı haritası"""
    if df.empty:
        return go.Figure()

    df = df.copy()
    df[value_col] = pd.to_numeric(df[value_col], errors="coerce").fillna(0)

    # customdata ile yüzdeyi texttemplate'e geçir — %{color} treemap'te NaN döndürebilir
    fig = px.treemap(
        df,
        path=[label_col],
        values=df[value_col].abs().clip(lower=0.1) + 0.5,
        color=value_col,
        color_continuous_scale=[
            [0.0, "#5a0020"],
            [0.2, "#ff4d6a"],
            [0.5, "#1a2236"],
            [0.8, "#00d4aa"],
            [1.0, "#005a47"],
        ],
        color_continuous_midpoint=0,
        custom_data=[value_col],
    )
    fig.update_traces(
        textfont_size=12,
        textfont_color="white",
        texttemplate="<b>%{label}</b><br>%{customdata[0]:.2f}%",
        hovertemplate="<b>%{label}</b><br>Değişim: %{customdata[0]:.2f}%<extra></extra>",
    )
    fig.update_layout(
        height=height,
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color=THEME["text_primary"]),
        margin=dict(l=5, r=5, t=5, b=5),
        coloraxis_showscale=False,
    )
    return fig


def recommendation_card(title: str, content: str, type: str = "info", icon: str = "💡"):
    """Kullanıcı yönlendirme kartı"""
    colors = {
        "info":    (THEME["blue"],   THEME["blue_dark"]),
        "success": (THEME["green"],  THEME["green_dark"]),
        "warning": (THEME["yellow"], "#2d2600"),
        "danger":  (THEME["red"],    THEME["red_dark"]),
        "neutral": (THEME["text_muted"], THEME["bg_card2"]),
    }
    fg, bg = colors.get(type, colors["info"])
    tp = THEME["text_primary"]
    st.markdown(
        f'<div style="background:{bg};border:1px solid {fg}40;border-left:3px solid {fg};'
        f'border-radius:0 10px 10px 0;padding:14px 18px;margin:8px 0">'
        f'<div style="color:{fg};font-size:13px;font-weight:700;margin-bottom:6px">{icon} {title}</div>'
        f'<div style="color:{tp};font-size:13px;line-height:1.6">{content}</div>'
        f'</div>',
        unsafe_allow_html=True
    )


# ─── Premium UI Components ────────────────────────────────────────────────────

def nav_tip(text: str):
    """Navigasyon pusulası ve bilgi kutusu — Premium Edition"""
    st.markdown(
        f'''
        <div style="background:linear-gradient(90deg, {THEME['bg_card2']} 0%, transparent 100%); 
                    border-left: 3px solid {THEME['blue']}; padding: 12px 20px; 
                    margin: 10px 0 20px 0; border-radius: 0 10px 10px 0;
                    display: flex; align-items: center; gap: 15px;">
            <div style="font-size: 20px;">🧭</div>
            <div style="color: {THEME['text_primary']}; font-size: 13px; line-height: 1.6; font-weight: 500;">
                {text}
            </div>
        </div>
        ''',
        unsafe_allow_html=True
    )

def ai_insight_box(title: str, commentary: str, icon: str = "🤖", color: str = None):
    """Otonom AI içgörü kutusu"""
    border_color = color or THEME.get("blue", "#4da6ff")
    st.markdown(
        f'<div class="ai-insight-box" style="border-left-color: {border_color}">'
        f'<div class="ai-insight-header" style="color: {border_color}">{icon} {title}</div>'
        f'<div class="ai-insight-content">{commentary}</div>'
        f'</div>',
        unsafe_allow_html=True
    )

# ─── Streamlit Page Helpers ───────────────────────────────────────────────────

def page_header(title: str, subtitle: str = "", badge: str = ""):
    """Premium sayfa başlığı — iyileştirilmiş padding ve görsel"""
    blue   = THEME["blue"]
    tp     = THEME["text_primary"]
    tm     = THEME["text_muted"]
    border = THEME["border"]
    badge_html = f'<span style="background:{blue}20;color:{blue};padding:4px 12px;border-radius:20px;font-size:10px;margin-left:12px;font-weight:700;letter-spacing:1px;text-transform:uppercase">{badge}</span>' if badge else ""
    sub_html   = f'<p style="color:{tm};font-size:14px;margin:8px 0 0 0;line-height:1.5">{subtitle}</p>' if subtitle else ""
    
    st.markdown(
        f'<div style="margin-bottom:30px;padding-bottom:20px;border-bottom:1px solid {border}">'
        f'<div style="display:flex;align-items:center;">'
        f'<h1 style="margin:0;color:{tp};font-size:28px;font-weight:800;letter-spacing:-0.5px">{title}</h1>'
        f'{badge_html}</div>'
        f'{sub_html}</div>',
        unsafe_allow_html=True
    )


def section_header(title: str, subtitle: str = ""):
    """Alt bölüm başlığı"""
    tp = THEME["text_primary"]
    tm = THEME["text_muted"]
    sub_html = f'<span style="color:{tm};font-size:12px;margin-left:8px">{subtitle}</span>' if subtitle else ""
    st.markdown(
        f'<div style="margin:16px 0 10px 0;display:flex;align-items:center">'
        f'<span style="color:{tp};font-size:15px;font-weight:700">{title}</span>'
        f'{sub_html}</div>',
        unsafe_allow_html=True
    )


def data_delay_banner(source: str = "Yahoo Finance", delay_min: int = 15):
    """
    Piyasa saatlerinde (10:00–18:30) veri gecikmesi uyarı bandı gösterir.
    Borsa kapalıysa önceki kapanış verisini bildiren hafif bir not gösterir.
    """
    from datetime import datetime, time as dtime
    import streamlit as st
    now = datetime.now()
    h, m = now.hour, now.minute
    market_open  = dtime(10, 0)
    market_close = dtime(18, 30)
    is_trading = dtime(h, m) >= market_open and dtime(h, m) <= market_close

    yellow = THEME.get("yellow", "#f4c542")
    muted  = THEME.get("text_muted", "#8899aa")

    if is_trading:
        st.markdown(
            f'<div style="display:flex;align-items:center;gap:8px;padding:6px 14px;'
            f'background:{yellow}15;border:1px solid {yellow}40;border-radius:8px;'
            f'margin-bottom:12px;font-size:12px;color:{yellow}">'
            f'⏱ <b>Piyasa verileri ~{delay_min} dk gecikmeli</b> &nbsp;·&nbsp; Kaynak: {source}'
            f'</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f'<div style="display:flex;align-items:center;gap:8px;padding:6px 14px;'
            f'background:#ffffff08;border:1px solid #ffffff15;border-radius:8px;'
            f'margin-bottom:12px;font-size:12px;color:{muted}">'
            f'📋 Borsa kapalı — gösterilen veriler son kapanış fiyatlarıdır ({source})'
            f'</div>',
            unsafe_allow_html=True,
        )


def info_box(text: str, type: str = "info"):
    """Premium bilgi kutusu"""
    colors = {
        "info":    (THEME["blue"],   THEME["blue_dark"]),
        "success": (THEME["green"],  THEME["green_dark"]),
        "warning": (THEME["yellow"], "#2d2600"),
        "error":   (THEME["red"],    THEME["red_dark"]),
    }
    fg, bg = colors.get(type, colors["info"])
    icons = {"info": "ℹ️", "success": "✅", "warning": "⚠️", "error": "❌"}
    tp = THEME["text_primary"]
    ico = icons.get(type, "")
    st.markdown(
        f'<div style="background:{bg};border:1px solid {fg}30;border-left:3px solid {fg};'
        f'padding:12px 16px;border-radius:0 8px 8px 0;margin:8px 0;font-size:13px;color:{tp};line-height:1.5">'
        f'{ico} {text}</div>',
        unsafe_allow_html=True
    )


def _md_to_html(text: str) -> str:
    """Basit markdown → HTML dönüşümü"""
    import re
    lines, out = text.split("\n"), []
    for line in lines:
        s = line.rstrip()
        if re.match(r'^### ', s):
            s = f'<h4 style="margin:10px 0 4px 0;color:#e2eaf5">{s[4:]}</h4>'
        elif re.match(r'^## ', s):
            s = f'<h3 style="margin:12px 0 4px 0;color:#e2eaf5">{s[3:]}</h3>'
        elif re.match(r'^# ', s):
            s = f'<h2 style="margin:14px 0 4px 0;color:#e2eaf5">{s[2:]}</h2>'
        elif re.match(r'^> ', s):
            s = f'<blockquote style="border-left:3px solid #4da6ff;padding-left:10px;margin:4px 0;color:#7a93b0">{s[2:]}</blockquote>'
        elif s == '---' or s == '___':
            s = '<hr style="border-color:#1e3a5f;margin:8px 0">'
        else:
            # inline: bold, italic, code
            s = re.sub(r'\*\*\*(.+?)\*\*\*', r'<b><i>\1</i></b>', s)
            s = re.sub(r'\*\*(.+?)\*\*',     r'<b>\1</b>', s)
            s = re.sub(r'\*(.+?)\*',          r'<i>\1</i>', s)
            s = re.sub(r'`(.+?)`',            r'<code style="background:#1a2a45;padding:1px 4px;border-radius:3px">\1</code>', s)
            if s:
                s = s + '<br>'
        out.append(s)
    return "".join(out)

def ai_response_box(text: str):
    """Premium AI yanıt kutusu"""
    blue   = THEME["blue"]
    tp     = THEME["text_primary"]
    border = THEME["border"]
    glow   = THEME["glow_blue"]
    body   = _md_to_html(text)
    st.markdown(
        f'<div style="background:linear-gradient(135deg,#0d1a2d 0%,#0a1420 100%);border:1px solid {blue}40;'
        f'border-radius:12px;padding:18px 22px;margin:12px 0;font-size:14px;line-height:1.7;color:{tp};box-shadow:{glow}">'
        f'<div style="color:{blue};font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:1.5px;margin-bottom:12px">🤖 FinSentinel AI Analiz</div>'
        f'<div style="border-top:1px solid {border};padding-top:12px">{body}</div>'
        f'</div>',
        unsafe_allow_html=True
    )


def live_indicator():
    """Canlı veri göstergesi — yanıp sönen nokta"""
    st.markdown(f"""<style>
@keyframes pulse {{
    0%,100% {{ opacity:1; transform:scale(1); }}
    50% {{ opacity:0.4; transform:scale(0.8); }}
}}
.live-dot {{
    display:inline-block;width:8px;height:8px;
    background:{THEME['green']};border-radius:50%;
    animation:pulse 1.5s infinite;margin-right:6px;
    box-shadow:0 0 6px {THEME['green']};
}}
</style>""", unsafe_allow_html=True)
    st.markdown(
        f'<div style="display:flex;align-items:center;color:{THEME["text_muted"]};font-size:12px">'
        f'<span class="live-dot"></span><span>Canlı Veri</span>'
        f'</div>',
        unsafe_allow_html=True
    )


def apply_dark_theme():
    """FinSentinel Premium Dark Tema"""
    st.markdown(f"""<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
@import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200&display=block');
/* Inter font — ikon elementleri hariç tüm elementlere uygula */
*:not([data-testid="stIconMaterial"]):not([class*="material"]) {{ font-family: 'Inter', sans-serif !important; }}
/* Material Icons font — Streamlit ikonları için geri yükle */
[data-testid="stIconMaterial"] {{
    font-family: 'Material Symbols Rounded' !important;
    font-variation-settings: 'FILL' 0, 'wght' 300, 'GRAD' 0, 'opsz' 24;
    font-size: 20px !important;
    user-select: none;
    vertical-align: middle;
}}
.stApp {{
    background: {THEME['bg_dark']};
    background-image: radial-gradient(ellipse at top, #0d1b35 0%, {THEME['bg_dark']} 70%);
}}
/* Toolbar / header gizle — içerik üstüne binmesini önle */
header[data-testid="stHeader"] {{ display: none !important; }}
.stDeployButton {{ display: none !important; }}
#MainMenu {{ display: none !important; }}
footer {{ display: none !important; }}
.block-container {{
    padding-top: 1.5rem !important;
    padding-bottom: 2rem !important;
    max-width: 1400px !important;
}}

/* Sidebar */
div[data-testid="stSidebar"] {{ background: {THEME['bg_card']}; border-right: 1px solid {THEME['border']}; }}
div[data-testid="stSidebar"] > div {{ background: transparent; }}
/* Streamlit nav gizle */
[data-testid="stSidebarNav"] {{ display: none !important; }}
section[data-testid="stSidebar"] > div:first-child > div:first-child ul {{ display: none !important; }}

/* Sidebar kapatma butonlarını gizle — sidebar her zaman açık kalır */
[data-testid="collapsedControl"] {{ display: none !important; }}
[data-testid="stSidebarCollapseButton"] {{ display: none !important; }}
button[aria-label="Close sidebar"] {{ display: none !important; }}
button[aria-label="Open sidebar"]  {{ display: none !important; }}
/* Sidebar her zaman görünür ve tam genişlikte */
section[data-testid="stSidebar"] {{
    min-width: 280px !important;
    width: 280px !important;
    transform: none !important;
    display: flex !important;
    visibility: visible !important;
}}
/* Buttons */
.stButton > button {{ background: {THEME['blue_dark']}; border: 1px solid {THEME['blue']}50; color: {THEME['blue']}; border-radius: 8px; font-weight: 600; transition: all 0.2s; }}
.stButton > button:hover {{ background: {THEME['blue']}25; border-color: {THEME['blue']}; box-shadow: {THEME['glow_blue']}; transform: translateY(-1px); }}
/* Inputs */
.stTextInput > div > div > input,
.stNumberInput > div > div > input,
.stSelectbox > div > div,
.stTextArea > div > textarea {{ background: {THEME['bg_input']} !important; border: 1px solid {THEME['border']} !important; color: {THEME['text_primary']} !important; border-radius: 8px !important; }}
.stTextInput > div > div > input:focus,
.stSelectbox > div > div:focus {{ border-color: {THEME['blue']} !important; box-shadow: {THEME['glow_blue']} !important; }}
/* Selectbox dropdown arrow */
[data-baseweb="select"] svg {{ fill: {THEME['text_muted']} !important; }}
/* Tabs */
.stTabs [data-baseweb="tab-list"] {{ background: transparent; border-bottom: 1px solid {THEME['border']}; gap: 4px; }}
.stTabs [data-baseweb="tab"] {{ background: transparent; color: {THEME['text_muted']}; border-radius: 8px 8px 0 0; border: none; padding: 8px 16px; font-weight: 500; }}
.stTabs [aria-selected="true"] {{ background: {THEME['blue_dark']}; color: {THEME['blue']} !important; border-bottom: 2px solid {THEME['blue']}; }}
/* DataFrames */
.stDataFrame {{ border-radius: 10px; overflow: hidden; border: 1px solid {THEME['border']}; }}
.stDataFrame [data-testid="stDataFrameResizable"] {{ background: {THEME['bg_card']}; }}
/* Radio */
.stRadio > div {{ gap: 4px; }}
.stRadio label {{ color: {THEME['text_muted']} !important; padding: 6px 10px; border-radius: 8px; transition: all 0.2s; }}
.stRadio label:hover {{ background: {THEME['bg_card2']}; color: {THEME['text_primary']} !important; }}
/* Expander */
.streamlit-expanderHeader {{ background: {THEME['bg_card2']}; border: 1px solid {THEME['border']}; border-radius: 8px; color: {THEME['text_primary']} !important; }}
/* Metrics */
[data-testid="stMetric"] {{ background: {THEME['bg_card']}; border: 1px solid {THEME['border']}; border-radius: 10px; padding: 14px; }}
/* Spinner */
.stSpinner > div {{ border-top-color: {THEME['blue']} !important; }}
/* Progress */
.stProgress > div > div {{ background: {THEME['blue']}; }}
/* Toast */
[data-baseweb="notification"] {{ background: {THEME['bg_card2']} !important; border: 1px solid {THEME['border']} !important; }}
[data-baseweb="toaster"] {{ z-index: 9999; }}
/* Scrollbar */
::-webkit-scrollbar {{ width: 6px; height: 6px; }}
::-webkit-scrollbar-track {{ background: {THEME['bg_dark']}; }}
::-webkit-scrollbar-thumb {{ background: {THEME['border']}; border-radius: 3px; }}
::-webkit-scrollbar-thumb:hover {{ background: {THEME['blue']}60; }}
h1, h2, h3, h4 {{ color: {THEME['text_primary']} !important; }}
/* Form submit */
[data-testid="stFormSubmitButton"] > button {{ background: {THEME['blue']} !important; color: white !important; border: none !important; font-weight: 700 !important; }}
[data-testid="stFormSubmitButton"] > button:hover {{ background: {THEME['blue']}dd !important; box-shadow: {THEME['glow_blue']}; }}
/* Alerts */
div[class*="stAlert"] {{ border-radius: 10px; border: 1px solid; }}

/* User Profile Section in Sidebar */
.sidebar-user {{
    background: {THEME['bg_card2']};
    border: 1px solid {THEME['border']};
    border-radius: 12px;
    padding: 12px 15px;
    margin-top: 20px;
    display: flex;
    align-items: center;
    gap: 12px;
}}
.user-avatar {{
    width: 36px;
    height: 36px;
    background: linear-gradient(135deg, {THEME['blue']}, {THEME['purple']});
    border-radius: 10px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: white;
    font-weight: 800;
    font-size: 14px;
}}
.user-info {{ flex: 1; }}
.user-name {{ color: {THEME['text_primary']}; font-size: 13px; font-weight: 700; }}
.user-status {{ color: {THEME['green']}; font-size: 10px; display: flex; align-items: center; gap: 4px; }}
.status-dot {{ width: 6px; height: 6px; background: {THEME['green']}; border-radius: 50%; box-shadow: 0 0 5px {THEME['green']}; }}

/* Search Input Customization */
.stTextInput > div > div > input {{
    background: {THEME['bg_input']}30 !important;
    border: 1px solid {THEME['border']}50 !important;
    transition: all 0.3s;
}}
.stTextInput > div > div > input:focus {{
    background: {THEME['bg_input']} !important;
    border-color: {THEME['blue']} !important;
    box-shadow: {THEME['glow_blue']} !important;
}}

/* Ghosting Fix: Fade in content on page load */
@keyframes fadeInApp {{
    0% {{ opacity: 0; transform: translateY(8px); filter: blur(2px); }}
    100% {{ opacity: 1; transform: translateY(0); filter: blur(0); }}
}}
.block-container {{
    animation: fadeInApp 0.5s cubic-bezier(0.16, 1, 0.3, 1);
}}
</style>""", unsafe_allow_html=True)
