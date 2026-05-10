"""
FinSentinel — Akıllı Günlük Portföy Oluşturucu
core/smart_portfolio.py

Her gün karar motoru + haber skoru + çeşitlendirme kurallarıyla
BIST 100'den optimal portföy seçer ve performansını takip eder.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from typing import Optional

import numpy as np
import pandas as pd
import yfinance as yf
import streamlit as st
from loguru import logger
from sqlalchemy import create_engine, text

from config.settings import DB_PATH
from core.decision_engine import analyze
from utils.symbols import SECTOR_MAP
from utils.company_info import get_name

# ── DB ───────────────────────────────────────────────────────────────────────
_ENGINE = None

def _get_engine():
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = create_engine(f"sqlite:///{DB_PATH}")
    return _ENGINE


def _init_tables():
    eng = _get_engine()
    with eng.connect() as con:
        con.execute(text("""
            CREATE TABLE IF NOT EXISTS ai_portfolio_picks (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                pick_date   TEXT NOT NULL,
                ticker      TEXT NOT NULL,
                company     TEXT,
                sector      TEXT,
                score       REAL,
                strategy    TEXT,
                entry_price REAL,
                reasons     TEXT,
                UNIQUE(pick_date, ticker)
            )
        """))
        con.execute(text("""
            CREATE TABLE IF NOT EXISTS ai_portfolio_perf (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                pick_date   TEXT NOT NULL,
                eval_date   TEXT NOT NULL,
                ticker      TEXT NOT NULL,
                entry_price REAL,
                exit_price  REAL,
                pnl_pct     REAL,
                UNIQUE(pick_date, eval_date, ticker)
            )
        """))
        con.commit()

_init_tables()


# ── Haber / Momentum Skoru ───────────────────────────────────────────────────

@st.cache_data(ttl=3600, show_spinner=False)
def _news_momentum_score(ticker: str) -> float:
    """
    KAP RSS'ten son haberleri çeker, basit anahtar kelime skorlaması yapar.
    +: temettü, ihracat, büyüme, yatırım, anlaşma, sözleşme, kapasite
    -: zarar, borç, erteleme, dava, şikayet, tazminat, icra
    Dönüş: -10 ile +10 arası float
    """
    try:
        import requests, re
        url = f"https://www.kap.org.tr/tr/api/disclosures?memberOid=&subject=&fromDate=&toDate=&keyword={ticker}&pageNumber=0"
        r = requests.get(url, timeout=5)
        if r.status_code != 200:
            return 0.0
        items = r.json() if isinstance(r.json(), list) else r.json().get("data", [])
        text_blob = " ".join(
            str(item.get("title","")) + " " + str(item.get("subject",""))
            for item in items[:15]
        ).lower()

        pos_words = ["temettü","ihracat","büyüme","yatırım","anlaşma","sözleşme",
                     "kapasite","artış","kâr","ihale","sipariş","genişleme"]
        neg_words = ["zarar","borç","erteleme","dava","şikayet","tazminat",
                     "icra","iflas","konkordato","uyarı","ceza","soruşturma"]

        pos = sum(text_blob.count(w) for w in pos_words)
        neg = sum(text_blob.count(w) for w in neg_words)
        raw = (pos - neg * 1.5)
        return float(np.clip(raw, -10, 10))
    except Exception:
        return 0.0


# ── Teknik Skor ──────────────────────────────────────────────────────────────

@st.cache_data(ttl=1800, show_spinner=False)
def _get_tech_and_hist(ticker_is: str) -> tuple[int, pd.DataFrame]:
    """(tech_score, hist_df) döner — cache'li."""
    try:
        from core.fetcher import PriceFetcher, TechnicalAnalyzer
        hist = PriceFetcher.get_history(ticker_is, period="1y", interval="1d")
        if hist.empty:
            return 0, pd.DataFrame()
        hist = TechnicalAnalyzer.add_indicators(hist)
        sig  = TechnicalAnalyzer.get_signal(hist)
        return sig.get("score", 0), hist
    except Exception:
        return 0, pd.DataFrame()


@st.cache_data(ttl=3600, show_spinner=False)
def _get_yf_info(ticker_is: str) -> dict:
    try:
        return yf.Ticker(ticker_is).info or {}
    except Exception:
        return {}


# ── Çeşitlendirme Kontrolü ───────────────────────────────────────────────────

def _diversified_top(
    scored: list[dict],
    n: int = 8,
    max_per_sector: int = 2,
) -> list[dict]:
    """
    Sektör başına max_per_sector hisse alarak çeşitlendirilmiş portföy döner.
    En yüksek skoru olan hisseler önce alınır.
    """
    picked: list[dict] = []
    sector_counts: dict[str, int] = {}
    for item in scored:
        sector = item.get("sector", "Diğer")
        if sector_counts.get(sector, 0) >= max_per_sector:
            continue
        picked.append(item)
        sector_counts[sector] = sector_counts.get(sector, 0) + 1
        if len(picked) >= n:
            break
    return picked


# ── Ana Seçici ───────────────────────────────────────────────────────────────

def build_daily_portfolio(
    universe: list[str],
    strategy: str = "dengeli",
    n_picks:  int = 8,
    min_score: float = 52.0,
) -> list[dict]:
    """
    universe   : [".IS" eki olmayan ticker listesi]
    strategy   : "dengeli" | "trader" | "temettü"
    n_picks    : portföydeki hisse sayısı
    min_score  : bu skorun altındakileri eleç

    Dönen liste: [{"ticker", "score", "sector", "company", "entry_price", "reasons"}, ...]
    """
    results: list[dict] = []

    for ticker in universe:
        ticker_is = ticker + ".IS"
        try:
            tech_score, hist_df = _get_tech_and_hist(ticker_is)
            info   = _get_yf_info(ticker_is)
            sector = SECTOR_MAP.get(ticker, info.get("sector") or "Diğer")

            # Karar motoru
            decision = analyze(
                ticker     = ticker,
                info       = info,
                hist_df    = hist_df,
                tech_score = tech_score,
                sector     = sector,
                strategy   = strategy,
            )

            # Haber momentumu ek skoru
            news_bonus = _news_momentum_score(ticker)
            final_score = min(100.0, decision.total + news_bonus * 0.5)

            # Güncel fiyat
            price = None
            try:
                price = float(info.get("currentPrice") or info.get("regularMarketPrice") or 0) or None
                if price is None and not hist_df.empty:
                    price = float(hist_df["Close"].iloc[-1])
            except Exception:
                pass

            if final_score < min_score:
                continue

            # Pozitif sinyallerin özeti
            reasons = [
                s["text"] for p in decision.pillars
                for s in p.signals if s["positive"] is True
            ][:3]

            results.append({
                "ticker":      ticker,
                "company":     get_name(ticker),
                "sector":      sector,
                "score":       round(final_score, 1),
                "base_score":  round(decision.total, 1),
                "news_bonus":  round(news_bonus, 1),
                "verdict":     decision.verdict,
                "entry_price": price,
                "reasons":     reasons,
                "p1": round(decision.p1.score, 1),
                "p2": round(decision.p2.score, 1),
                "p3": round(decision.p3.score, 1),
                "p4": round(decision.p4.score, 1),
            })
        except Exception as e:
            logger.debug(f"smart_portfolio {ticker}: {e}")
            continue

    # Skora göre sırala
    results.sort(key=lambda x: x["score"], reverse=True)

    # Çeşitlendirilmiş seçim
    return _diversified_top(results, n=n_picks, max_per_sector=2)


# ── DB Kaydet / Oku ──────────────────────────────────────────────────────────

def save_picks(picks: list[dict], pick_date: date, strategy: str):
    """Seçimleri veritabanına yazar."""
    eng = _get_engine()
    with eng.connect() as con:
        for p in picks:
            con.execute(text("""
                INSERT OR REPLACE INTO ai_portfolio_picks
                  (pick_date, ticker, company, sector, score, strategy, entry_price, reasons)
                VALUES (:pd, :tk, :co, :sc, :sr, :st, :ep, :rs)
            """), {
                "pd": str(pick_date),
                "tk": p["ticker"],
                "co": p.get("company",""),
                "sc": p.get("sector",""),
                "sr": p["score"],
                "st": strategy,
                "ep": p.get("entry_price"),
                "rs": json.dumps(p.get("reasons", []), ensure_ascii=False),
            })
        con.commit()
    logger.info(f"AI portföy kaydedildi: {pick_date} — {len(picks)} hisse")


def load_picks(pick_date: date) -> pd.DataFrame:
    """Belirli güne ait seçimleri döner."""
    eng = _get_engine()
    with eng.connect() as con:
        rows = con.execute(text(
            "SELECT * FROM ai_portfolio_picks WHERE pick_date = :d ORDER BY score DESC"
        ), {"d": str(pick_date)}).fetchall()
    if not rows:
        return pd.DataFrame()
    cols = ["id","pick_date","ticker","company","sector","score","strategy","entry_price","reasons"]
    return pd.DataFrame(rows, columns=cols)


def load_picks_range(days: int = 30) -> pd.DataFrame:
    """Son N güne ait tüm seçimleri döner."""
    eng = _get_engine()
    since = str(date.today() - timedelta(days=days))
    with eng.connect() as con:
        rows = con.execute(text(
            "SELECT * FROM ai_portfolio_picks WHERE pick_date >= :s ORDER BY pick_date DESC, score DESC"
        ), {"s": since}).fetchall()
    if not rows:
        return pd.DataFrame()
    cols = ["id","pick_date","ticker","company","sector","score","strategy","entry_price","reasons"]
    return pd.DataFrame(rows, columns=cols)


def evaluate_performance(pick_date: date) -> pd.DataFrame:
    """
    pick_date gününe ait seçimlerin ertesi iş günü performansını hesaplar.
    entry_price → bugünkü fiyat karşılaştırması.
    """
    picks_df = load_picks(pick_date)
    if picks_df.empty:
        return pd.DataFrame()

    rows = []
    eval_date = date.today()
    for _, row in picks_df.iterrows():
        ticker_is = row["ticker"] + ".IS"
        entry     = row.get("entry_price") or 0
        exit_price = None
        pnl_pct    = None
        try:
            info = _get_yf_info(ticker_is)
            exit_price = float(info.get("currentPrice") or info.get("regularMarketPrice") or 0) or None
            if exit_price and entry and entry > 0:
                pnl_pct = round((exit_price - entry) / entry * 100, 2)
        except Exception:
            pass

        rows.append({
            "pick_date":   str(pick_date),
            "eval_date":   str(eval_date),
            "ticker":      row["ticker"],
            "company":     row.get("company",""),
            "sector":      row.get("sector",""),
            "score":       row.get("score",0),
            "entry_price": entry or None,
            "exit_price":  exit_price,
            "pnl_pct":     pnl_pct,
        })

    return pd.DataFrame(rows)


def available_pick_dates() -> list[str]:
    """Portföy kaydı bulunan tarihleri döner."""
    eng = _get_engine()
    with eng.connect() as con:
        rows = con.execute(text(
            "SELECT DISTINCT pick_date FROM ai_portfolio_picks ORDER BY pick_date DESC LIMIT 60"
        )).fetchall()
    return [r[0] for r in rows]
