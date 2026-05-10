"""AI Insights — lightweight rule-based insights for Emlak Endeksi.
This module provides deterministic, explainable insights derived from
aggregated city-level data. No external ML/inference required.
"""
from typing import List, Dict
import pandas as pd


def generate_rule_insights(df: pd.DataFrame, top_n: int = 5) -> List[Dict]:
    """Return a list of insight dicts: {'title','body','kind'}.

    Expects df with columns: 'il', 'fiyat', 'degisim'.
    """
    if df is None or df.empty:
        return []

    out = []
    try:
        # national averages
        mean_price = float(df['fiyat'].mean())
        mean_change = float(df['degisim'].mean())

        # most expensive / cheapest
        top = df.sort_values('fiyat', ascending=False).head(top_n)
        cheap = df.sort_values('fiyat', ascending=True).head(3)

        out.append({
            'title': f"Milli Ortalama: ₺{int(mean_price):,}/m²",
            'body': f"Genel m² ortalaması ₺{int(mean_price):,}. Ortalama yıllık değişim %{mean_change:.1f}.",
            'kind': 'info'
        })

        # fast risers
        risers = df.sort_values('degisim', ascending=False).head(3)
        riser_list = ", ".join([f"{r['il']} (+{r['degisim']:.1f}%)" for _, r in risers.iterrows()])
        out.append({'title': 'Hızlı Yükselen Bölgeler', 'body': f'{riser_list} — yatırım uzmanları dikkat etmeli.', 'kind': 'success'})

        # cheap opportunities
        cheap_list = ", ".join([f"{r['il']} (₺{int(r['fiyat']):,})" for _, r in cheap.iterrows()])
        out.append({'title': 'Değer Altı Bölgeler', 'body': f'{cheap_list} — emsal bazlı fırsat potansiyeli.', 'kind': 'info'})

        # volatility signal: identify cities with degisim far from mean
        df['z'] = (df['degisim'] - mean_change) / (df['degisim'].std() if df['degisim'].std() > 0 else 1)
        vol = df[ df['z'].abs() > 1.2 ]
        if not vol.empty:
            vlist = ", ".join([f"{r['il']} ({r['degisim']:+.1f}%)" for _, r in vol.iterrows()])
            out.append({'title': 'Volatil Bölgeler', 'body': f'{vlist} — kısa vadeli risk/ fırsat sinyali.', 'kind': 'warning'})

    except Exception:
        return out

    return out
