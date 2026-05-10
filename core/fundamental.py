"""
FinSentinel — Temel Analiz Motoru
core/fundamental.py

Veri Kaynakları (tümü yasal):
  • yfinance  : quarterly_financials, quarterly_balance_sheet, cashflow, info
                Yahoo Finance → KAP bildirimi verileri derleme, ~1-2 çeyrek gecikme
  • KAP API   : Resmi bildirim linkleri (kap_fetcher üzerinden)

Hesaplanan Kategoriler:
  • Karlılık   : Brüt/Net/EBITDA marjı, ROE, ROA
  • Borçluluk  : D/E, Net Borç/EBITDA, Cari Oran, Asit-Test
  • Gelir Tab. : Çeyreklik gelir, COGS, EBITDA, Net Kar zaman serisi
  • Getiri Mat.: 1G 1H 1A 3A 6A YTD 1Y 3Y 5Y

Kullanım:
    from core.fundamental import FundamentalEngine
    eng = FundamentalEngine("GARAN")
    profitability = eng.karlılık()
    debt          = eng.borçluluk()
    income        = eng.gelir_tablosu()
    returns       = eng.getiri_matrisi()
"""

from __future__ import annotations

import warnings
from datetime import datetime, date
from typing import Optional

import numpy as np
import pandas as pd
import yfinance as yf
from loguru import logger

warnings.filterwarnings("ignore", category=FutureWarning)


# ─────────────────────────────────────────────────────────────────────────────
# Yardımcılar
# ─────────────────────────────────────────────────────────────────────────────

def _safe(val, default=None):
    """NaN / None / sıfır güvenli okuma."""
    try:
        if val is None:
            return default
        f = float(val)
        return default if (np.isnan(f) or np.isinf(f)) else f
    except (TypeError, ValueError):
        return default


def _pct(val, default=None):
    """0-1 aralığındaki değeri yüzdeye çevirir (None-safe)."""
    v = _safe(val)
    return round(v * 100, 2) if v is not None else default


def _ratio(num, den, default=None, round_digits=2):
    n = _safe(num)
    d = _safe(den)
    if n is None or d is None or d == 0:
        return default
    return round(n / d, round_digits)


def _milyon(val, default=None) -> Optional[float]:
    """Değeri milyona böler (TL/USD cinsinden)."""
    v = _safe(val)
    return round(v / 1_000_000, 2) if v is not None else default


def _row(df: pd.DataFrame, *keys) -> Optional[pd.Series]:
    """DataFrame satırını birden fazla anahtar ismiyle bulmaya çalışır."""
    if df is None or df.empty:
        return None
    for key in keys:
        if key in df.index:
            return df.loc[key]
        # Büyük-küçük harf ve boşluk toleransı
        matches = [i for i in df.index if str(i).lower().replace(" ", "") == key.lower().replace(" ", "")]
        if matches:
            return df.loc[matches[0]]
    return None


def _latest(series: Optional[pd.Series]) -> Optional[float]:
    """Serinin en son NaN olmayan değerini döner."""
    if series is None:
        return None
    clean = series.dropna()
    return _safe(clean.iloc[0]) if not clean.empty else None   # yfinance: en yeni = sol


def _col_dates(df: pd.DataFrame) -> list[str]:
    """DataFrame'deki kolon tarihlerini 'Ç3 2024' formatına çevirir."""
    labels = []
    for col in df.columns:
        try:
            dt = pd.to_datetime(col)
            q  = (dt.month - 1) // 3 + 1
            labels.append(f"Ç{q} {dt.year}")
        except Exception:
            labels.append(str(col)[:10])
    return labels


# ─────────────────────────────────────────────────────────────────────────────
# Ana Motor
# ─────────────────────────────────────────────────────────────────────────────

class FundamentalEngine:
    """
    Tek sembol için tüm temel analiz hesaplamalarını yürütür.

    Örnek:
        eng = FundamentalEngine("GARAN")
        k   = eng.karlılık()     # dict
        b   = eng.borçluluk()    # dict
        g   = eng.gelir_tablosu() # pd.DataFrame
        r   = eng.getiri_matrisi()# dict
        s   = eng.özet_kart()    # dict (P/E, P/B, EV/EBITDA, …)
    """

    def __init__(self, symbol: str):
        # ".IS" ekle (BIST), yoksa olduğu gibi bırak (US/global)
        self.symbol   = symbol.upper().replace(".IS", "")
        self.yf_sym   = f"{self.symbol}.IS"
        self._ticker  = yf.Ticker(self.yf_sym)
        self._info: dict        = {}
        self._fin_q: pd.DataFrame   = pd.DataFrame()   # çeyreklik gelir tablosu
        self._bal_q: pd.DataFrame   = pd.DataFrame()   # çeyreklik bilanço
        self._cf:   pd.DataFrame    = pd.DataFrame()   # yıllık nakit akış
        self._price_hist: pd.DataFrame = pd.DataFrame()
        self._loaded = False

    # ── Veri Yükleme ─────────────────────────────────────────────────────

    def load(self) -> "FundamentalEngine":
        """Tüm yfinance verilerini bir kerede çeker (lazy + cached)."""
        if self._loaded:
            return self
        try:
            self._info  = self._ticker.info or {}
        except Exception as e:
            logger.warning(f"[{self.symbol}] info hatası: {e}")

        try:
            self._fin_q = self._ticker.quarterly_financials
        except Exception as e:
            logger.warning(f"[{self.symbol}] quarterly_financials hatası: {e}")

        try:
            self._bal_q = self._ticker.quarterly_balance_sheet
        except Exception as e:
            logger.warning(f"[{self.symbol}] quarterly_balance_sheet hatası: {e}")

        try:
            self._cf = self._ticker.cashflow
        except Exception as e:
            logger.warning(f"[{self.symbol}] cashflow hatası: {e}")

        try:
            self._price_hist = self._ticker.history(period="5y", interval="1d", auto_adjust=True)
        except Exception as e:
            logger.warning(f"[{self.symbol}] history hatası: {e}")

        self._loaded = True
        return self

    # ── 1. Karlılık Oranları ─────────────────────────────────────────────

    def karlılık(self) -> dict:
        """
        Döner: {
          "brut_kar_marji": float,   # %
          "net_kar_marji":  float,   # %
          "ebitda_marji":   float,   # %
          "roe":            float,   # %
          "roa":            float,   # %
          "faaliyet_marji": float,   # %
          "trailingPE":     float,
          "forwardPE":      float,
          "veri_donemi":    str,
        }
        """
        self.load()
        q  = self._fin_q
        bq = self._bal_q
        inf = self._info

        # Gelir tablosu satırları (yfinance isimleri değişkenlik gösterebilir)
        gelir     = _row(q, "Total Revenue", "Revenue", "Revenues")
        brut_kar  = _row(q, "Gross Profit")
        net_kar   = _row(q, "Net Income", "Net Income Common Stockholders")
        ebitda    = _row(q, "EBITDA", "Normalized EBITDA")
        faaliyet  = _row(q, "Operating Income", "EBIT")

        # TTM (son 4 çeyrek toplamı)
        def _ttm(series: Optional[pd.Series]) -> Optional[float]:
            if series is None:
                return None
            vals = series.dropna()
            return float(vals.iloc[:4].sum()) if len(vals) >= 1 else None

        gelir_ttm    = _ttm(gelir)
        brut_kar_ttm = _ttm(brut_kar)
        net_kar_ttm  = _ttm(net_kar)
        ebitda_ttm   = _ttm(ebitda)
        faaliyet_ttm = _ttm(faaliyet)

        # Bilanço (en son çeyrek)
        ozk   = _latest(_row(bq, "Stockholders Equity", "Common Stock Equity", "Total Equity Gross Minority Interest"))
        varlik= _latest(_row(bq, "Total Assets"))

        def _marj(num, den):
            r = _ratio(num, den)
            return round(r * 100, 2) if r is not None else None

        return {
            "brut_kar_marji": _marj(brut_kar_ttm, gelir_ttm),
            "net_kar_marji":  _marj(net_kar_ttm,  gelir_ttm),
            "ebitda_marji":   _marj(ebitda_ttm,   gelir_ttm),
            "faaliyet_marji": _marj(faaliyet_ttm, gelir_ttm),
            "roe":            _marj(net_kar_ttm,  ozk),
            "roa":            _marj(net_kar_ttm,  varlik),
            "trailing_pe":    _safe(inf.get("trailingPE")),
            "forward_pe":     _safe(inf.get("forwardPE")),
            "gelir_ttm_mn":   _milyon(gelir_ttm),
            "net_kar_ttm_mn": _milyon(net_kar_ttm),
            "veri_donemi":    _col_dates(q)[0] if not q.empty else "—",
        }

    # ── 2. Borçluluk Oranları ─────────────────────────────────────────────

    def borçluluk(self) -> dict:
        """
        Döner: {
          "borc_ozkaynak":    float,   # D/E
          "net_borc_ebitda":  float,
          "cari_oran":        float,
          "asit_test":        float,
          "toplam_borc_mn":   float,   # milyon
          "net_borc_mn":      float,   # milyon
          "ozkaynak_mn":      float,   # milyon
          "varlik_mn":        float,   # milyon
        }
        """
        self.load()
        bq = self._bal_q
        q  = self._fin_q

        # Bilanço satırları
        toplam_borc   = _latest(_row(bq, "Total Debt", "Long Term Debt And Capital Lease Obligation"))
        kisa_borc     = _latest(_row(bq, "Current Debt", "Short Term Debt", "Current Debt And Capital Lease Obligation"))
        uzun_borc     = _latest(_row(bq, "Long Term Debt"))
        ozk           = _latest(_row(bq, "Stockholders Equity", "Common Stock Equity", "Total Equity Gross Minority Interest"))
        varlik        = _latest(_row(bq, "Total Assets"))
        nakit         = _latest(_row(bq, "Cash And Cash Equivalents", "Cash Cash Equivalents And Short Term Investments"))
        donen_varlik  = _latest(_row(bq, "Current Assets", "Total Current Assets"))
        kisa_yukumluluk = _latest(_row(bq, "Current Liabilities", "Total Current Liabilities Net Minority Interest"))
        stok          = _latest(_row(bq, "Inventory"))

        # EBITDA TTM
        ebitda_ser = _row(q, "EBITDA", "Normalized EBITDA")
        ebitda_ttm = float(ebitda_ser.dropna().iloc[:4].sum()) if (ebitda_ser is not None and not ebitda_ser.dropna().empty) else None

        net_borc = (toplam_borc or 0) - (nakit or 0)

        # Asit-test: (Dönen Varlık - Stok) / Kısa Yükümlülük
        asit_num = (donen_varlik or 0) - (stok or 0)

        return {
            "borc_ozkaynak":    _ratio(toplam_borc, ozk),
            "net_borc_ebitda":  _ratio(net_borc, ebitda_ttm),
            "cari_oran":        _ratio(donen_varlik, kisa_yukumluluk),
            "asit_test":        _ratio(asit_num, kisa_yukumluluk),
            "toplam_borc_mn":   _milyon(toplam_borc),
            "kisa_borc_mn":     _milyon(kisa_borc),
            "uzun_borc_mn":     _milyon(uzun_borc),
            "net_borc_mn":      _milyon(net_borc),
            "nakit_mn":         _milyon(nakit),
            "ozkaynak_mn":      _milyon(ozk),
            "varlik_mn":        _milyon(varlik),
            "veri_donemi":      _col_dates(bq)[0] if not bq.empty else "—",
        }

    # ── 3. Gelir Tablosu Zaman Serisi ────────────────────────────────────

    def gelir_tablosu(self, donem: str = "quarterly") -> pd.DataFrame:
        """
        Çeyreklik (quarterly) veya yıllık (annual) gelir tablosu.
        Döner: DataFrame — kolonlar dönemler, satırlar kalemler (Türkçe etiket).

        donem: "quarterly" | "annual"
        """
        self.load()
        if donem == "annual":
            q = self._ticker.financials if not self._fin_q.empty else self._fin_q
        else:
            q = self._fin_q

        if q is None or q.empty:
            return pd.DataFrame()

        # Almak istediğimiz satırlar (yfinance adı → Türkçe etiket)
        satir_map = {
            "Total Revenue":            "Gelir (Net Satışlar)",
            "Revenue":                  "Gelir (Net Satışlar)",
            "Gross Profit":             "Brüt Kar",
            "Operating Income":         "Faaliyet Karı (EBIT)",
            "EBIT":                     "Faaliyet Karı (EBIT)",
            "EBITDA":                   "EBITDA",
            "Normalized EBITDA":        "EBITDA",
            "Net Income":               "Net Kar",
            "Net Income Common Stockholders": "Net Kar",
            "Basic EPS":                "Hisse Başı Kazanç (EPS)",
            "Diluted EPS":              "Hisse Başı Kazanç (EPS)",
        }

        rows = {}
        seen_labels: set[str] = set()
        for yf_key, label in satir_map.items():
            if label in seen_labels:
                continue
            if yf_key in q.index:
                rows[label] = q.loc[yf_key]
                seen_labels.add(label)

        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame(rows).T
        df.columns = _col_dates(q)

        # Milyona böl (EPS hariç)
        for idx in df.index:
            if "EPS" not in idx:
                df.loc[idx] = df.loc[idx].apply(lambda x: _milyon(x))

        return df

    # ── 4. Getiri Matrisi ─────────────────────────────────────────────────

    def getiri_matrisi(self) -> dict:
        """
        Tarihsel getiri hesabı.
        Döner: {
          "1G": float, "1H": float, "1A": float, "3A": float,
          "6A": float, "YTD": float, "1Y": float, "3Y": float, "5Y": float,
          "son_fiyat": float, "para_birimi": str
        }
        """
        self.load()
        hist = self._price_hist

        if hist is None or hist.empty or "Close" not in hist.columns:
            return {}

        close = hist["Close"].dropna()
        if close.empty:
            return {}

        now   = close.index[-1]
        last  = float(close.iloc[-1])

        def _ret(days: int = None, dt: date = None) -> Optional[float]:
            """Belirli gün veya tarihten bu güne getiri (%)."""
            try:
                if dt is not None:
                    # YTD: yıl başından bu yana
                    ref_idx = close.index[close.index >= pd.Timestamp(dt)]
                    if ref_idx.empty:
                        return None
                    ref = float(close.loc[ref_idx[0]])
                else:
                    target = now - pd.Timedelta(days=days)
                    subset = close[close.index <= target]
                    if subset.empty:
                        return None
                    ref = float(subset.iloc[-1])
                if ref == 0:
                    return None
                return round((last - ref) / ref * 100, 2)
            except Exception:
                return None

        ytd_start = date(now.year, 1, 1)

        return {
            "1G":       _ret(1),
            "1H":       _ret(7),
            "1A":       _ret(30),
            "3A":       _ret(90),
            "6A":       _ret(180),
            "YTD":      _ret(dt=ytd_start),
            "1Y":       _ret(365),
            "3Y":       _ret(365 * 3),
            "5Y":       _ret(365 * 5),
            "son_fiyat":    last,
            "para_birimi":  self._info.get("currency", "TRY"),
            "son_guncelleme": str(now.date()),
        }

    # ── 5. Özet Değerleme Kartı ──────────────────────────────────────────

    def özet_kart(self) -> dict:
        """
        Sayfanın üst kısmındaki KPI kartları için hızlı erişim.
        Döner: piyasa değeri, P/E, P/B, F/K, temettü verimi vb.
        """
        self.load()
        inf = self._info
        return {
            "şirket_adı":       inf.get("longName") or inf.get("shortName") or self.symbol,
            "sektör":           inf.get("sector", "—"),
            "endüstri":         inf.get("industry", "—"),
            "piyasa_değeri_mn": _milyon(inf.get("marketCap")),
            "trailing_pe":      _safe(inf.get("trailingPE")),
            "forward_pe":       _safe(inf.get("forwardPE")),
            "pb_oran":          _safe(inf.get("priceToBook")),
            "ps_oran":          _safe(inf.get("priceToSalesTrailing12Months")),
            "ev_ebitda":        _safe(inf.get("enterpriseToEbitda")),
            "beta":             _safe(inf.get("beta")),
            "temettu_verimi":   _pct(inf.get("dividendYield")),
            "52h_yuksek":       _safe(inf.get("fiftyTwoWeekHigh")),
            "52h_dusuk":        _safe(inf.get("fiftyTwoWeekLow")),
            "hedef_fiyat":      _safe(inf.get("targetMeanPrice")),
            "analist_sayi":     inf.get("numberOfAnalystOpinions"),
            "öneri":            inf.get("recommendationKey", "—").upper(),
            "calisan_sayisi":   inf.get("fullTimeEmployees"),
            "para_birimi":      inf.get("currency", "TRY"),
        }

    # ── 6. Sektör Karşılaştırma Yardımcısı ──────────────────────────────

    @staticmethod
    def çoklu_getiri(symbols: list[str]) -> pd.DataFrame:
        """
        Birden fazla sembol için getiri matrisini tek DataFrame'de toplar.
        Tarayıcıda Heatmap / tablo için kullanılır.

        Döner: DataFrame — index=semboller, kolonlar=dönemler
        """
        records = []
        for sym in symbols:
            try:
                eng = FundamentalEngine(sym)
                ret = eng.getiri_matrisi()
                if ret:
                    row = {"Sembol": sym}
                    row.update({k: ret.get(k) for k in ["1G","1H","1A","3A","6A","YTD","1Y","3Y","5Y"]})
                    records.append(row)
            except Exception as e:
                logger.debug(f"çoklu_getiri [{sym}]: {e}")

        if not records:
            return pd.DataFrame()

        df = pd.DataFrame(records).set_index("Sembol")
        return df
