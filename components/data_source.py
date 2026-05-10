"""
FinSentinel — Veri Kaynağı Rozeti
components/data_source.py

Her veri içeren sayfada standart biçimde
"Kaynak: X • Çekilme: HH:MM • Gecikme: ~N dk" bilgisini gösterir.
Kullanıcı güvenini artırmak ve verinin tazeliğini şeffafça iletmek için
tek merkezi bileşen.

Kullanım:
    from components.data_source import data_source_badge

    # Sayfanın üstünde (veya her blok altında):
    data_source_badge(
        source="Yahoo Finance",
        fetched_at=datetime.now(),
        delay_minutes=15,
        note="Realtime WebSocket olmadığı için ~15 dk gecikme",
    )
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

import streamlit as st


_BADGE_CSS = """
<style>
.fs-source-badge {
  display: inline-flex;
  flex-wrap: wrap;
  gap: 6px 14px;
  padding: 6px 12px;
  margin: 4px 0 10px 0;
  border-radius: 8px;
  background: rgba(255,255,255,0.04);
  border: 1px solid rgba(255,255,255,0.08);
  font-size: 12px;
  color: #9ca3af;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}
.fs-source-badge b { color: #d1d5db; font-weight: 600; }
.fs-source-badge .fs-fresh  { color: #10b981; }
.fs-source-badge .fs-stale  { color: #f59e0b; }
.fs-source-badge .fs-old    { color: #ef4444; }
.fs-source-badge .fs-sep    { color: #4b5563; }
</style>
"""

_CSS_INJECTED_KEY = "_fs_source_badge_css_injected"


def _inject_css_once() -> None:
    if not st.session_state.get(_CSS_INJECTED_KEY):
        st.markdown(_BADGE_CSS, unsafe_allow_html=True)
        st.session_state[_CSS_INJECTED_KEY] = True


def _freshness_class(fetched_at: datetime) -> str:
    age_min = (datetime.now() - fetched_at).total_seconds() / 60
    if age_min < 5:
        return "fs-fresh"
    if age_min < 30:
        return "fs-stale"
    return "fs-old"


def data_source_badge(
    source: str,
    fetched_at: Optional[datetime] = None,
    delay_minutes: Optional[int] = None,
    note: str = "",
    symbol_count: Optional[int] = None,
) -> None:
    """
    Veri kaynağı rozetini çizer.

    Args:
        source: "Yahoo Finance", "İş Yatırım", "KAP", "Binance WS" vb.
        fetched_at: Verinin çekildiği zaman (None ise "şimdi" varsayılır).
        delay_minutes: Kaynaktan gelen doğal gecikme (örn. Yahoo 15dk gecikmeli).
        note: Ek açıklama (opsiyonel).
        symbol_count: Kaç sembolün yüklendiği (opsiyonel).
    """
    _inject_css_once()
    if fetched_at is None:
        fetched_at = datetime.now()

    fresh_cls = _freshness_class(fetched_at)
    age_min = int((datetime.now() - fetched_at).total_seconds() / 60)
    age_txt = "az önce" if age_min < 1 else f"{age_min} dk önce"

    parts = [
        f"<span>Kaynak: <b>{source}</b></span>",
        f"<span class='fs-sep'>•</span>",
        f"<span class='{fresh_cls}'>Çekilme: <b>{fetched_at.strftime('%H:%M:%S')}</b> ({age_txt})</span>",
    ]
    if delay_minutes is not None:
        parts += [
            "<span class='fs-sep'>•</span>",
            f"<span>Gecikme: <b>~{delay_minutes} dk</b></span>",
        ]
    if symbol_count is not None:
        parts += [
            "<span class='fs-sep'>•</span>",
            f"<span>{symbol_count} sembol</span>",
        ]
    if note:
        parts += ["<span class='fs-sep'>•</span>", f"<span><i>{note}</i></span>"]

    html = f"<div class='fs-source-badge'>{''.join(parts)}</div>"
    st.markdown(html, unsafe_allow_html=True)


def multi_source_badge(sources: list[dict]) -> None:
    """
    Birden fazla kaynak varsa hepsini tek satırda gösterir.
    sources: [{"source": "...", "fetched_at": dt, "delay_minutes": 15}, ...]
    """
    _inject_css_once()
    chips = []
    for s in sources:
        fa = s.get("fetched_at") or datetime.now()
        cls = _freshness_class(fa)
        txt = (
            f"<b>{s.get('source','?')}</b> "
            f"<span class='{cls}'>{fa.strftime('%H:%M')}</span>"
        )
        if s.get("delay_minutes") is not None:
            txt += f" <span class='fs-sep'>(~{s['delay_minutes']}dk)</span>"
        chips.append(f"<span>{txt}</span>")
    html = (
        "<div class='fs-source-badge'>"
        + "<span class='fs-sep'>•</span>".join(chips)
        + "</div>"
    )
    st.markdown(html, unsafe_allow_html=True)
