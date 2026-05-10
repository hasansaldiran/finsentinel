"""
Pro Chart Engine — Plotly tabanlı profesyonel grafik oluşturucu.
TradingView bağımsız; BIST dahil tüm varlıklar için kullanılabilir.
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from config.settings import THEME
from utils.indicators import ema, rsi, macd, bollinger, vwap as calc_vwap

# Renk sabitleri (THEME bazlı)
_BG      = THEME.get("bg_dark",  "#0a0e1a")
_BG_CARD = THEME.get("bg_card",  "#111827")
_GRID    = THEME.get("border",   "#1e3a5f")
_TEXT    = THEME.get("text_primary", "#e2eaf5")
_MUTED   = THEME.get("text_muted",   "#7a93b0")
_GREEN   = THEME.get("green",   "#00d4aa")
_RED     = THEME.get("red",     "#ff4d6a")
_BLUE    = THEME.get("blue",    "#4da6ff")
_YELLOW  = THEME.get("yellow",  "#ffd166")
_PURPLE  = THEME.get("purple",  "#c77dff")
_ORANGE  = THEME.get("orange",  "#ff9a3c")
_CYAN    = THEME.get("cyan",    "#00d4ff")


def pro_chart(
    df: pd.DataFrame,
    title: str = "",
    height: int = 620,
    show_ema: bool = True,
    show_bb: bool = True,
    show_vwap: bool = False,
    show_volume: bool = True,
    show_rsi: bool = True,
    show_macd: bool = False,
) -> go.Figure:
    """
    Professional OHLCV chart with configurable overlays and subplots.
    Returns a Plotly Figure ready for st.plotly_chart().
    """
    if df is None or df.empty:
        fig = go.Figure()
        fig.update_layout(
            title="Veri yok", paper_bgcolor=_BG_CARD,
            plot_bgcolor=_BG_CARD, font=dict(color=_TEXT),
        )
        return fig

    close = df["Close"]

    # ── Subplot yapısı ────────────────────────────────────────────────────────
    n_rows, row_heights = _row_layout(show_volume, show_rsi, show_macd)
    _r = 2   # next available row counter
    r_candle = 1
    r_vol  = _r if show_volume else None; _r += int(show_volume)
    r_rsi  = _r if show_rsi   else None; _r += int(show_rsi)
    r_macd = _r if show_macd  else None

    fig = make_subplots(
        rows=n_rows, cols=1,
        shared_xaxes=True,
        row_heights=row_heights,
        vertical_spacing=0.025,
    )

    # ── Candlestick ───────────────────────────────────────────────────────────
    fig.add_trace(go.Candlestick(
        x=df.index,
        open=df["Open"], high=df["High"],
        low=df["Low"],   close=close,
        increasing_line_color=_GREEN, increasing_fillcolor=_GREEN,
        decreasing_line_color=_RED,   decreasing_fillcolor=_RED,
        name="Fiyat", showlegend=False,
        whiskerwidth=0.6,
    ), row=r_candle, col=1)

    # ── EMA Overlays ──────────────────────────────────────────────────────────
    if show_ema:
        _ema_cfg = [
            (20,  _BLUE,   "solid", 1.3),
            (50,  _YELLOW, "solid", 1.5),
            (200, _ORANGE, "dash",  1.8),
        ]
        for period, color, dash, width in _ema_cfg:
            if len(df) >= period:
                fig.add_trace(go.Scatter(
                    x=df.index, y=ema(close, period),
                    mode="lines",
                    line=dict(color=color, width=width, dash=dash),
                    name=f"EMA{period}", opacity=0.9,
                ), row=r_candle, col=1)

    # ── Bollinger Bands ───────────────────────────────────────────────────────
    if show_bb and len(df) >= 20:
        bb_up, _, bb_lo = bollinger(close)
        fig.add_trace(go.Scatter(
            x=df.index, y=bb_up,
            mode="lines",
            line=dict(color=_PURPLE, width=1, dash="dot"),
            name="BB", opacity=0.65, showlegend=True,
        ), row=r_candle, col=1)
        fig.add_trace(go.Scatter(
            x=df.index, y=bb_lo,
            mode="lines",
            line=dict(color=_PURPLE, width=1, dash="dot"),
            name="BB Alt", opacity=0.65, showlegend=False,
            fill="tonexty",
            fillcolor="rgba(199,125,255,0.05)",
        ), row=r_candle, col=1)

    # ── VWAP ─────────────────────────────────────────────────────────────────
    if show_vwap:
        vwap_s = calc_vwap(df)
        fig.add_trace(go.Scatter(
            x=df.index, y=vwap_s,
            mode="lines",
            line=dict(color=_CYAN, width=1.8, dash="dashdot"),
            name="VWAP", opacity=0.9,
        ), row=r_candle, col=1)

    # ── Volume ────────────────────────────────────────────────────────────────
    if show_volume and r_vol is not None:
        has_vol = "Volume" in df.columns and df["Volume"].sum() > 0
        if has_vol:
            bar_colors = [
                _GREEN if float(c) >= float(o) else _RED
                for o, c in zip(df["Open"], close)
            ]
            fig.add_trace(go.Bar(
                x=df.index, y=df["Volume"],
                marker_color=bar_colors, opacity=0.55,
                name="Hacim", showlegend=False,
            ), row=r_vol, col=1)

    # ── RSI ───────────────────────────────────────────────────────────────────
    if show_rsi and r_rsi is not None:
        rsi_s = rsi(close)
        fig.add_trace(go.Scatter(
            x=df.index, y=rsi_s,
            mode="lines", line=dict(color=_BLUE, width=1.6),
            name="RSI", showlegend=False,
        ), row=r_rsi, col=1)
        for lvl, clr in [(70, _RED), (50, _MUTED), (30, _GREEN)]:
            fig.add_hline(
                y=lvl, line_dash="dot", line_color=clr,
                line_width=1, opacity=0.5, row=r_rsi, col=1,
            )

    # ── MACD ──────────────────────────────────────────────────────────────────
    if show_macd and r_macd is not None:
        ml, sl, hist_s = macd(close)
        hist_colors = [_GREEN if float(v) >= 0 else _RED for v in hist_s]
        fig.add_trace(go.Bar(
            x=df.index, y=hist_s,
            marker_color=hist_colors, opacity=0.65,
            name="MACD Hist", showlegend=False,
        ), row=r_macd, col=1)
        fig.add_trace(go.Scatter(
            x=df.index, y=ml,
            mode="lines", line=dict(color=_BLUE, width=1.5),
            name="MACD", showlegend=False,
        ), row=r_macd, col=1)
        fig.add_trace(go.Scatter(
            x=df.index, y=sl,
            mode="lines", line=dict(color=_ORANGE, width=1.3),
            name="Sinyal", showlegend=False,
        ), row=r_macd, col=1)
        fig.add_hline(
            y=0, line_dash="dot", line_color=_MUTED,
            line_width=1, opacity=0.5, row=r_macd, col=1,
        )

    # ── Global Layout ─────────────────────────────────────────────────────────
    fig.update_layout(
        title=dict(text=title, font=dict(color=_TEXT, size=13, family="monospace"), x=0.01),
        paper_bgcolor=_BG_CARD,
        plot_bgcolor=_BG_CARD,
        font=dict(color=_TEXT, size=11),
        height=height,
        xaxis_rangeslider_visible=False,
        legend=dict(
            orientation="h", x=0, y=1.02,
            bgcolor="rgba(0,0,0,0)",
            font=dict(size=10, color=_MUTED),
        ),
        margin=dict(l=60, r=15, t=55, b=20),
        hovermode="x unified",
        hoverlabel=dict(
            bgcolor=_BG_CARD,
            font=dict(color=_TEXT, size=11),
        ),
    )

    # ── Subplot Axis Styling ──────────────────────────────────────────────────
    _axis_style = dict(gridcolor=_GRID, showgrid=True, zeroline=False, linecolor=_GRID)

    for i in range(1, n_rows + 1):
        xkey = f"xaxis{i if i > 1 else ''}"
        ykey = f"yaxis{i if i > 1 else ''}"
        fig.update_layout(**{
            xkey: {**_axis_style, "showticklabels": i == n_rows},
            ykey: {**_axis_style},
        })

    # RSI y-axis: fixed 0-100
    if show_rsi and r_rsi is not None:
        ykey = f"yaxis{r_rsi}"
        fig.update_layout(**{ykey: {**_axis_style, "range": [0, 100]}})

    return fig


def mini_chart(
    df: pd.DataFrame,
    height: int = 360,
) -> go.Figure:
    """
    Compact candlestick with EMA20/50 overlay — for multi-chart grids.
    No subplots, no RSI/MACD. Minimal margins.
    """
    if df is None or df.empty:
        fig = go.Figure()
        fig.update_layout(paper_bgcolor=_BG_CARD, plot_bgcolor=_BG_CARD, height=height)
        return fig

    close = df["Close"]
    fig   = go.Figure()

    fig.add_trace(go.Candlestick(
        x=df.index,
        open=df["Open"], high=df["High"],
        low=df["Low"],   close=close,
        increasing_line_color=_GREEN, increasing_fillcolor=_GREEN,
        decreasing_line_color=_RED,   decreasing_fillcolor=_RED,
        name="", showlegend=False, whiskerwidth=0.5,
    ))

    for period, color, width in [(20, _BLUE, 1.2), (50, _YELLOW, 1.5)]:
        if len(df) >= period:
            fig.add_trace(go.Scatter(
                x=df.index, y=ema(close, period),
                mode="lines",
                line=dict(color=color, width=width),
                name=f"EMA{period}", showlegend=False, opacity=0.85,
            ))

    fig.update_layout(
        paper_bgcolor=_BG_CARD, plot_bgcolor=_BG_CARD,
        font=dict(color=_TEXT, size=10),
        height=height,
        xaxis_rangeslider_visible=False,
        xaxis=dict(gridcolor=_GRID, showgrid=True, zeroline=False, showticklabels=False),
        yaxis=dict(gridcolor=_GRID, showgrid=True, zeroline=False),
        margin=dict(l=5, r=5, t=8, b=5),
        showlegend=False,
        hovermode=False,
    )
    return fig


# ─────────────────────────────────────────────────────────────────────────────

def _row_layout(volume: bool, rsi_: bool, macd_: bool) -> tuple[int, list[float]]:
    """Compute row count and proportional heights."""
    heights: list[float] = [1.0]          # candle always row 1
    if volume: heights.append(0.22)
    if rsi_:   heights.append(0.28)
    if macd_:  heights.append(0.30)
    total = sum(heights)
    return len(heights), [h / total for h in heights]
