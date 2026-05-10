"""
FinSentinel — Finansal Veri İşleme Motoru
core/data_processor.py

Yüklenen finansal tabloları (bilanço, gelir tablosu, karlılık, analist)
AI'ın anlayabileceği context string veya JSON yapılarına dönüştürür.
"""
import json
from pathlib import Path
from typing import Optional
import pandas as pd
from loguru import logger

DATA_DIR = Path(__file__).parent.parent / "data" / "uploaded"

# Her tablo tipi için olası sütun adları (Türkçe varyasyonlar dahil)
_COL_MAP = {
    "bilanco": {
        "toplam_varlik": ["toplam varlık", "toplam aktif", "total assets", "varlıklar toplamı"],
        "ozkaynak": ["özkaynak", "özkaynaklar", "equity", "özsermaye"],
        "net_borc": ["net borç", "finansal borç", "net debt", "toplam borç"],
        "nakit": ["nakit", "nakit ve nakit benzeri", "cash", "hazır değerler"],
    },
    "gelir_tablosu": {
        "gelir": ["gelir", "satışlar", "hasılat", "net satışlar", "revenue", "net revenue"],
        "brut_kar": ["brüt kâr", "brüt kar", "gross profit"],
        "faaliyet_kari": ["faaliyet kârı", "esas faaliyetlerden kâr", "ebit", "operating profit"],
        "ebitda": ["ebitda", "favök"],
        "net_kar": ["net kâr", "net kar", "net dönem kârı", "net profit", "dönem net kârı"],
    },
    "karlilik": {
        "roe": ["roe", "özkaynak kârlılığı", "özsermaye kârlılığı", "return on equity"],
        "roa": ["roa", "aktif kârlılığı", "varlık kârlılığı", "return on assets"],
        "net_marj": ["net marj", "net kâr marjı", "net profit margin"],
        "brut_marj": ["brüt marj", "brüt kâr marjı", "gross margin"],
        "ebitda_marj": ["ebitda marj", "favök marjı", "ebitda margin"],
    },
    "anlalist": {
        "kurum": ["aracı kurum", "kurum", "brokerage", "analyst"],
        "oneri": ["öneri", "tavsiye", "recommendation", "rating"],
        "hedef_fiyat": ["hedef fiyat", "fiyat hedefi", "target price", "12m hedef"],
        "tarih": ["tarih", "revizyon tarihi", "date"],
    },
}


def _find_col(df: pd.DataFrame, candidates: list[str]) -> Optional[str]:
    """DataFrame sütunları arasında aday isimlerden birini bul (case-insensitive)."""
    df_cols_lower = {c.lower().strip(): c for c in df.columns}
    for candidate in candidates:
        if candidate.lower() in df_cols_lower:
            return df_cols_lower[candidate.lower()]
    return None


def _get_period_col(df: pd.DataFrame) -> Optional[str]:
    """Dönem/yıl sütununu bul."""
    for hint in ["dönem", "yıl", "year", "period", "quarter", "çeyrek", "tarih", "date"]:
        col = _find_col(df, [hint])
        if col:
            return col
    # İlk sütun genellikle dönem olur
    return df.columns[0] if len(df.columns) > 0 else None


def _load_latest(ticker: str, table_type: str) -> Optional[pd.DataFrame]:
    """ticker/table_type için en son yüklenen CSV'yi döndür."""
    try:
        ticker_dir = DATA_DIR / ticker.upper()
        if not ticker_dir.exists():
            return None
        files = sorted(ticker_dir.glob(f"{table_type}_*.csv"), reverse=True)
        if not files:
            return None
        df = pd.read_csv(files[0], encoding="utf-8-sig")
        # Meta sütunları çıkar
        df = df.drop(columns=[c for c in df.columns if c.startswith("_")], errors="ignore")
        return df
    except Exception as e:
        logger.error(f"DataProcessor yükleme hatası [{ticker}/{table_type}]: {e}")
        return None


def parse_financials_to_context(ticker: str) -> dict:
    """
    Ticker için tüm yüklü finansal tabloları okur,
    analiz için hem JSON yapısı hem okunabilir context string döndürür.

    Returns:
        {
            "ticker": str,
            "json_data": dict,          # AI'a JSON olarak verilebilir
            "context_string": str,      # AI prompt'una doğrudan eklenebilir
            "available_tables": list[str]
        }
    """
    result = {
        "ticker": ticker.upper(),
        "json_data": {},
        "context_string": "",
        "available_tables": [],
    }
    lines = [f"## {ticker.upper()} Finansal Veri Özeti\n"]

    for table_type, col_map in _COL_MAP.items():
        df = _load_latest(ticker, table_type)
        if df is None or df.empty:
            continue

        result["available_tables"].append(table_type)
        period_col = _get_period_col(df)
        table_data = []

        lines.append(f"\n### {table_type.replace('_', ' ').title()}")

        for _, row in df.iterrows():
            row_dict = {}
            if period_col and pd.notna(row.get(period_col)):
                row_dict["dönem"] = str(row[period_col])

            for key, candidates in col_map.items():
                col = _find_col(df, candidates)
                if col and pd.notna(row.get(col)):
                    try:
                        row_dict[key] = float(str(row[col]).replace(",", ".").replace(" ", ""))
                    except (ValueError, TypeError):
                        row_dict[key] = str(row[col])

            if len(row_dict) > 1:  # Sadece dönem değil, en az 1 veri var
                table_data.append(row_dict)

        if table_data:
            result["json_data"][table_type] = table_data
            # Context için tablo formatı
            for row_dict in table_data:
                period = row_dict.get("dönem", "?")
                metrics = {k: v for k, v in row_dict.items() if k != "dönem"}
                metrics_str = ", ".join(f"{k}={v}" for k, v in metrics.items())
                lines.append(f"  - {period}: {metrics_str}")

    # Analist tavsiyeleri özel format
    df_analyst = _load_latest(ticker, "anlalist")
    if df_analyst is not None and not df_analyst.empty:
        result["available_tables"].append("anlalist")
        lines.append("\n### Analist Tavsiyeleri")
        try:
            col_map_a = _COL_MAP["anlalist"]
            col_kurum = _find_col(df_analyst, col_map_a["kurum"])
            col_oneri = _find_col(df_analyst, col_map_a["oneri"])
            col_hedef = _find_col(df_analyst, col_map_a["hedef_fiyat"])
            col_tarih = _find_col(df_analyst, col_map_a["tarih"])

            analyst_rows = []
            for _, row in df_analyst.iterrows():
                a = {}
                if col_kurum:
                    a["kurum"] = str(row.get(col_kurum, ""))
                if col_oneri:
                    a["öneri"] = str(row.get(col_oneri, ""))
                if col_hedef:
                    try:
                        a["hedef_fiyat"] = float(str(row.get(col_hedef, "")).replace(",", "."))
                    except (ValueError, TypeError):
                        a["hedef_fiyat"] = str(row.get(col_hedef, ""))
                if col_tarih:
                    a["tarih"] = str(row.get(col_tarih, ""))
                if a:
                    analyst_rows.append(a)
                    lines.append(
                        f"  - {a.get('kurum','?')} | {a.get('öneri','?')} | "
                        f"Hedef: {a.get('hedef_fiyat','?')} | {a.get('tarih','')}"
                    )

            if analyst_rows:
                result["json_data"]["anlalist"] = analyst_rows
        except Exception as e:
            logger.error(f"DataProcessor analist parse hatası [{ticker}]: {e}")

    if not result["available_tables"]:
        result["context_string"] = f"{ticker} için yüklü finansal veri bulunamadı."
    else:
        result["context_string"] = "\n".join(lines)

    return result


def get_growth_trends(ticker: str) -> str:
    """
    Gelir tablosu ve karlılık verilerinden büyüme trendini hesaplar,
    AI prompt'una eklenebilecek metin döndürür.
    """
    lines = [f"## {ticker.upper()} Büyüme Trendleri"]
    try:
        df = _load_latest(ticker, "gelir_tablosu")
        if df is None or df.empty:
            return f"{ticker} için gelir tablosu verisi yok."

        col_map = _COL_MAP["gelir_tablosu"]
        col_gelir = _find_col(df, col_map["gelir"])
        col_net_kar = _find_col(df, col_map["net_kar"])
        period_col = _get_period_col(df)

        if col_gelir:
            gelir_series = pd.to_numeric(df[col_gelir], errors="coerce").dropna()
            if len(gelir_series) >= 2:
                yoy = ((gelir_series.iloc[-1] / gelir_series.iloc[0]) ** (1 / max(len(gelir_series) - 1, 1)) - 1) * 100
                lines.append(f"- Gelir CAGR ({len(gelir_series)} dönem): %{yoy:.1f}")

        if col_net_kar:
            kar_series = pd.to_numeric(df[col_net_kar], errors="coerce").dropna()
            if len(kar_series) >= 2:
                cagr = ((kar_series.iloc[-1] / kar_series.iloc[0]) ** (1 / max(len(kar_series) - 1, 1)) - 1) * 100
                lines.append(f"- Net Kâr CAGR ({len(kar_series)} dönem): %{cagr:.1f}")
                # Son 3 dönem net kâr
                recent = kar_series.tail(4).tolist()
                lines.append(f"- Son dönem net kârlar: {[f'{v:.0f}' for v in recent]}")

    except Exception as e:
        logger.error(f"DataProcessor büyüme trend hatası [{ticker}]: {e}")
        lines.append(f"Hesaplama hatası: {e}")

    return "\n".join(lines)
