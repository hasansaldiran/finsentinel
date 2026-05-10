"""
FinSentinel — Agentic Risk Engine
core/risk_engine.py

Görevler:
  1. RiskAnalyzer   : Portföy pozisyonlarını anlık fiyatla kıyaslar,
                      ATR tabanlı stop-loss hesaplar, risk seviyesi atar.
  2. PredictionStore: AI tahminlerini DB'ye kaydeder / günceller.
  3. SelfCritic     : Geçmiş tahminleri gerçekleşenle kıyaslar,
                      AI'yı kendi çıktısını eleştirtir (LLM döngüsü).
  4. AgenticDecision: Tüm girdileri (portföy riski + sentiment + geçmiş
                      tahmin doğruluğu) birleştirip Groq/Gemini'ye gönderir,
                      yapılandırılmış karar çıktısı alır.

Kullanım:
    from core.risk_engine import RiskEngine
    engine = RiskEngine()
    report = engine.run_full_analysis()  # → RiskReport
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from typing import Optional

import numpy as np
import pandas as pd
import yfinance as yf
from loguru import logger
from sqlalchemy import desc

from core.db import DatabaseManager, Portfolio, AIPrediction, AIEvaluation
from core.ai_engine import _call_best_ai
from core.sentiment import SentimentFeed, SentimentResult


db = DatabaseManager()


# ─────────────────────────────────────────────────────────────────────────────
# Veri Yapıları
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class PositionRisk:
    symbol:        str
    asset_type:    str
    quantity:      float
    buy_price:     float
    current_price: float
    pnl_pct:       float          # %
    pnl_abs:       float          # TRY
    drawdown_pct:  float          # Peak'ten düşüş %
    atr:           Optional[float] # Average True Range (14g)
    atr_stop:      Optional[float] # Güncel fiyat - 2*ATR
    pct_stop:      float           # Alış fiyatının %8 altı (standart stop)
    risk_level:    str             # "kritik" | "yüksek" | "orta" | "düşük" | "ok"
    risk_flags:    list[str]       # Uyarı mesajları
    sentiment:     Optional[SentimentResult] = None


@dataclass
class RiskReport:
    generated_at:    str
    positions:       list[PositionRisk]
    portfolio_value: float
    total_pnl_pct:   float
    total_pnl_abs:   float
    critical_count:  int
    market_sentiment: Optional[SentimentResult]
    ai_decision:     str           # Ham LLM çıktısı
    stop_loss_table: list[dict]    # Yapılandırılmış stop-loss önerileri
    self_critique:   str           # Geçmiş tahminlerin eleştirisi
    accuracy_7d:     Optional[float] # Son 7 günde tahmin doğruluğu %


# ─────────────────────────────────────────────────────────────────────────────
# 1. ATR Hesaplayıcı
# ─────────────────────────────────────────────────────────────────────────────

def _calc_atr(symbol: str, period: int = 14) -> Optional[float]:
    """
    yfinance üzerinden ATR hesaplar.
    Dönüş: Son ATR değeri (TRY cinsinden fiyat hareketi).
    """
    yf_sym = symbol if symbol.endswith(".IS") else f"{symbol}.IS"
    try:
        hist = yf.download(yf_sym, period="60d", interval="1d",
                           auto_adjust=True, progress=False)
        if hist is None or len(hist) < period + 1:
            return None

        high = hist["High"].values
        low  = hist["Low"].values
        close= hist["Close"].values

        tr = np.maximum.reduce([
            high[1:] - low[1:],
            np.abs(high[1:] - close[:-1]),
            np.abs(low[1:]  - close[:-1]),
        ])
        atr = float(np.mean(tr[-period:]))
        return round(atr, 4)
    except Exception as e:
        logger.debug(f"ATR [{symbol}]: {e}")
        return None


def _calc_drawdown(symbol: str, buy_price: float) -> float:
    """
    52 haftalık en yüksekten mevcut fiyata düşüş % hesabı.
    Drawdown = (peak - current) / peak * 100
    """
    yf_sym = symbol if symbol.endswith(".IS") else f"{symbol}.IS"
    try:
        ticker = yf.Ticker(yf_sym)
        info   = ticker.fast_info
        high52 = getattr(info, "fifty_two_week_high", None)
        last   = getattr(info, "last_price", None)
        if high52 and last and high52 > 0:
            return round((float(high52) - float(last)) / float(high52) * 100, 2)
    except Exception:
        pass
    return 0.0


# ─────────────────────────────────────────────────────────────────────────────
# 2. Risk Analyzer
# ─────────────────────────────────────────────────────────────────────────────

_RISK_THRESHOLDS = {
    "kritik":  -15.0,   # P&L < -15% → kritik
    "yüksek":   -8.0,   # P&L < -8%  → yüksek
    "orta":     -4.0,   # P&L < -4%  → orta
    "düşük":    -1.0,   # P&L < -1%  → düşük
}

_STOP_PCT_DEFAULT = 8.0   # Alış fiyatının %8 altı = standart stop-loss


class RiskAnalyzer:
    """Tek pozisyon için risk metriklerini hesaplar."""

    def __init__(self, sentiment_feed: Optional[SentimentFeed] = None):
        self._sentiment = sentiment_feed or SentimentFeed()

    def analyze_position(
        self,
        position: "Portfolio",
        current_price: float,
        include_sentiment: bool = True,
    ) -> PositionRisk:
        sym      = position.symbol.replace(".IS", "")
        qty      = position.quantity
        buy_px   = position.buy_price
        cost     = buy_px * qty
        value    = current_price * qty
        pnl_abs  = value - cost
        pnl_pct  = (pnl_abs / cost * 100) if cost else 0.0

        # ATR
        atr      = _calc_atr(sym)
        atr_stop = round(current_price - 2 * atr, 2) if atr else None
        pct_stop = round(buy_px * (1 - _STOP_PCT_DEFAULT / 100), 2)

        # Peak'ten drawdown
        drawdown = _calc_drawdown(sym, buy_px)

        # Risk seviyesi
        flags: list[str] = []
        if pnl_pct <= _RISK_THRESHOLDS["kritik"]:
            level = "kritik"
            flags.append(f"⛔ Zarar %{abs(pnl_pct):.1f} — acil aksiyon gerekli")
        elif pnl_pct <= _RISK_THRESHOLDS["yüksek"]:
            level = "yüksek"
            flags.append(f"🔴 Zarar %{abs(pnl_pct):.1f} — stop-loss değerlendir")
        elif pnl_pct <= _RISK_THRESHOLDS["orta"]:
            level = "orta"
            flags.append(f"🟡 Zarar %{abs(pnl_pct):.1f} — takipte tut")
        elif pnl_pct <= _RISK_THRESHOLDS["düşük"]:
            level = "düşük"
            flags.append(f"🟢 Hafif zarar %{abs(pnl_pct):.1f}")
        else:
            level = "ok"

        # Ek uyarılar
        if atr_stop and current_price < atr_stop:
            flags.append(f"⚠️ Fiyat ATR stop altında ({atr_stop:.2f})")
        if drawdown >= 20:
            flags.append(f"📉 52H zirvesinden %{drawdown:.1f} düşük")

        # Sentiment (opsiyonel — 0.5s içinde bitirmeli)
        sent: Optional[SentimentResult] = None
        if include_sentiment:
            try:
                sent = self._sentiment.analyze_symbol(sym, limit=10, include_google=False)
                if sent.label in ("güçlü_negatif", "negatif"):
                    flags.append(f"📰 Haberler olumsuz ({sent.label})")
            except Exception as e:
                logger.debug(f"Sentiment [{sym}]: {e}")

        return PositionRisk(
            symbol=sym,
            asset_type=getattr(position, "asset_type", "bist") or "bist",
            quantity=qty,
            buy_price=buy_px,
            current_price=current_price,
            pnl_pct=round(pnl_pct, 2),
            pnl_abs=round(pnl_abs, 2),
            drawdown_pct=drawdown,
            atr=atr,
            atr_stop=atr_stop,
            pct_stop=pct_stop,
            risk_level=level,
            risk_flags=flags,
            sentiment=sent,
        )


# ─────────────────────────────────────────────────────────────────────────────
# 3. Prediction Store — DB İşlemleri
# ─────────────────────────────────────────────────────────────────────────────

class PredictionStore:
    """AI tahminlerini AIPrediction tablosuna yazar ve okur."""

    @staticmethod
    def save(
        symbol:       str,
        predicted_dir: str,
        confidence:   float,
        target_price: Optional[float],
        stop_loss:    Optional[float],
        reasoning:    str,
        price_now:    float,
        sentiment_score: float = 0.0,
        horizon_days: int = 7,
        model_used:   str = "unknown",
        asset_type:   str = "bist",
    ) -> int:
        """Yeni tahmin kaydı oluşturur. Döner: kayıt ID."""
        with db.get_session() as session:
            pred = AIPrediction(
                symbol=symbol.replace(".IS","").upper(),
                asset_type=asset_type,
                predicted_dir=predicted_dir,
                confidence=confidence,
                target_price=target_price,
                stop_loss=stop_loss,
                horizon_days=horizon_days,
                reasoning=reasoning,
                sentiment_score=sentiment_score,
                price_at_pred=price_now,
                created_at=datetime.utcnow(),
                model_used=model_used,
            )
            session.add(pred)
            session.commit()
            session.refresh(pred)
            return pred.id

    @staticmethod
    def evaluate_pending() -> int:
        """
        horizon_days geçmiş ama henüz değerlenmemiş tahminleri günceller.
        Döner: güncellenen kayıt sayısı.
        """
        updated = 0
        with db.get_session() as session:
            pending = session.query(AIPrediction).filter(
                AIPrediction.price_realized.is_(None),
                AIPrediction.created_at <= datetime.utcnow() - timedelta(days=1),
            ).all()

            for pred in pending:
                try:
                    horizon = pred.horizon_days or 7
                    eval_dt = pred.created_at + timedelta(days=horizon)
                    if datetime.utcnow() < eval_dt:
                        continue

                    # Gerçekleşen fiyatı yfinance'den çek
                    yf_sym = f"{pred.symbol}.IS" if pred.asset_type == "bist" else f"{pred.symbol}-USD"
                    hist = yf.download(yf_sym, start=eval_dt - timedelta(days=3),
                                      end=eval_dt + timedelta(days=1),
                                      progress=False, auto_adjust=True)
                    if hist is None or hist.empty:
                        continue

                    price_real = float(hist["Close"].iloc[-1])
                    pnl_pct    = round((price_real - pred.price_at_pred) / pred.price_at_pred * 100, 2) \
                                 if pred.price_at_pred else 0.0
                    actual_dir = "up" if pnl_pct > 1 else ("down" if pnl_pct < -1 else "neutral")
                    is_correct = (actual_dir == pred.predicted_dir)

                    pred.price_realized = price_real
                    pred.actual_dir     = actual_dir
                    pred.pnl_pct        = pnl_pct
                    pred.is_correct     = is_correct
                    pred.evaluated_at   = datetime.utcnow()
                    updated += 1
                except Exception as e:
                    logger.debug(f"Tahmin değerleme [{pred.symbol}]: {e}")

            session.commit()
        return updated

    @staticmethod
    def get_recent(symbol: str = None, limit: int = 30) -> list[AIPrediction]:
        with db.get_session() as session:
            q = session.query(AIPrediction)
            if symbol:
                q = q.filter(AIPrediction.symbol == symbol.replace(".IS","").upper())
            return q.order_by(desc(AIPrediction.created_at)).limit(limit).all()

    @staticmethod
    def accuracy_stats(days: int = 30) -> dict:
        """Son N günde tahmin doğruluğu istatistikleri."""
        cutoff = datetime.utcnow() - timedelta(days=days)
        with db.get_session() as session:
            evaluated = session.query(AIPrediction).filter(
                AIPrediction.evaluated_at >= cutoff,
                AIPrediction.is_correct.isnot(None),
            ).all()

        if not evaluated:
            return {"total": 0, "correct": 0, "accuracy_pct": None, "avg_pnl": None}

        correct  = sum(1 for p in evaluated if p.is_correct)
        avg_pnl  = round(sum(p.pnl_pct for p in evaluated if p.pnl_pct) / len(evaluated), 2)
        accuracy = round(correct / len(evaluated) * 100, 1)

        return {
            "total":        len(evaluated),
            "correct":      correct,
            "accuracy_pct": accuracy,
            "avg_pnl":      avg_pnl,
            "period_days":  days,
        }


# ─────────────────────────────────────────────────────────────────────────────
# 4. Self-Critic — Geçmiş Tahminleri Eleştir
# ─────────────────────────────────────────────────────────────────────────────

def _build_critique_prompt(predictions: list[AIPrediction], stats: dict) -> str:
    """Geçmiş tahminler için self-critique prompt'u oluşturur."""
    pred_lines = []
    for p in predictions[:15]:  # Token limiti: max 15 tahmin
        status = "✅ Doğru" if p.is_correct else ("❌ Yanlış" if p.is_correct is False else "⏳ Bekleniyor")
        pred_lines.append(
            f"- {p.symbol} | Tahmin: {p.predicted_dir} | "
            f"Güven: {p.confidence:.0f}% | "
            f"Gerçekleşen: {p.actual_dir or '?'} | "
            f"P&L: {p.pnl_pct:.1f}% | {status}"
        )

    return f"""Sen FinSentinel'in yapay zeka analiz modülüsün.
Aşağıda son dönemde verdiğin tahminlerin gerçekleşme kayıtları var:

{chr(10).join(pred_lines)}

İSTATİSTİKLER:
- Toplam tahmin: {stats.get('total', 0)}
- Doğru tahmin: {stats.get('correct', 0)}
- Doğruluk oranı: {stats.get('accuracy_pct', 'N/A')}%
- Ortalama P&L: {stats.get('avg_pnl', 'N/A')}%

Görevin:
1. Hangi tahminlerde yanıldın ve neden?
2. Hangi piyasa koşullarında başarılısın/başarısızsın?
3. Strateji güncellemesi: Bundan sonra nasıl farklı davranmalısın?

Yanıtını 3 bölümde ver:
[HATA ANALİZİ] ...
[GÜÇLÜ/ZAYIF YÖN] ...
[STRATEJİ GÜNCELLEMESİ] ...

Kısa ve aksiyon odaklı tut. Maksimum 300 kelime."""


def run_self_critique(days: int = 30) -> tuple[str, dict]:
    """
    Geçmiş tahminleri değerlendirir, AI'yı kendini eleştirtir.
    Döner: (critique_text, stats_dict)
    """
    # 1. Önce değerlendirilmemiş tahminleri güncelle
    updated = PredictionStore.evaluate_pending()
    logger.info(f"Self-critic: {updated} tahmin değerlendirildi.")

    # 2. İstatistikleri hesapla
    stats = PredictionStore.accuracy_stats(days=days)

    # 3. Değerlendirilmiş tahminleri çek
    with db.get_session() as session:
        evaluated = session.query(AIPrediction).filter(
            AIPrediction.evaluated_at.isnot(None)
        ).order_by(desc(AIPrediction.evaluated_at)).limit(20).all()

    if not evaluated:
        return "Henüz değerlendirilebilecek geçmiş tahmin bulunmuyor.", stats

    # 4. LLM self-critique
    prompt = _build_critique_prompt(evaluated, stats)
    try:
        critique = _call_best_ai(prompt, max_tokens=500)
    except Exception as e:
        critique = f"AI eleştiri üretilemedi: {e}"

    # 5. DB'ye kaydet
    if stats.get("total", 0) > 0:
        with db.get_session() as session:
            eval_rec = AIEvaluation(
                period_start=datetime.utcnow() - timedelta(days=days),
                period_end=datetime.utcnow(),
                total_preds=stats["total"],
                correct_preds=stats["correct"],
                accuracy_pct=stats.get("accuracy_pct"),
                avg_pnl_pct=stats.get("avg_pnl"),
                self_critique=critique,
                strategy_update="",
                created_at=datetime.utcnow(),
            )
            session.add(eval_rec)
            session.commit()

    return critique, stats


# ─────────────────────────────────────────────────────────────────────────────
# 5. Agentic Decision — Tüm Girdileri Birleştir
# ─────────────────────────────────────────────────────────────────────────────

def _build_decision_prompt(
    positions: list[PositionRisk],
    market_sent: Optional[SentimentResult],
    stats: dict,
    critique_summary: str,
) -> str:
    """Risk Engine'in karar prompt'unu oluşturur."""
    pos_lines = []
    for p in positions:
        sent_label = p.sentiment.label_en if p.sentiment else "unknown"
        pos_lines.append(
            f"  {p.symbol}: K/Z={p.pnl_pct:+.1f}% | Risk={p.risk_level} | "
            f"ATR-Stop={p.atr_stop or 'N/A'} | Haber={sent_label} | "
            f"Flags: {'; '.join(p.risk_flags) or 'yok'}"
        )

    market_score = f"{market_sent.score:+.2f} ({market_sent.label_en})" if market_sent else "N/A"
    accuracy     = f"{stats.get('accuracy_pct','N/A')}%" if stats.get("accuracy_pct") else "yetersiz veri"

    return f"""Sen FinSentinel Risk Engine'i olarak görev yapıyorsun.
Aşağıdaki verilere dayanarak portföy risk kararları üret.

PORTFÖY POZİSYONLARI:
{chr(10).join(pos_lines) or '  Pozisyon bulunamadı.'}

PİYASA SENTİMENTİ: {market_score}
GEÇMİŞ DOĞRULUK: {accuracy} (son 30 gün, {stats.get('total', 0)} tahmin)
ÖNCEKİ KENDİ ELEŞTİRİM: {critique_summary[:200]}

GÖREV:
Her pozisyon için JSON formatında karar ver:
{{
  "kararlar": [
    {{
      "sembol": "...",
      "aksiyon": "TUTE | AZALT | KAPAT | EKLE",
      "stop_loss_onerisi": float_or_null,
      "gerekce": "...",
      "oncelik": "acil | yüksek | normal"
    }}
  ],
  "genel_degerlendirme": "...",
  "piyasa_gorusu": "..."
}}

Sadece JSON çıktısı ver. Markdown yok, açıklama yok."""


class AgenticDecision:
    """Portföy + sentiment + geçmiş verileri birleştirerek AI kararı üretir."""

    @staticmethod
    def decide(
        positions:    list[PositionRisk],
        market_sent:  Optional[SentimentResult],
        stats:        dict,
        critique_sum: str = "",
    ) -> tuple[str, list[dict]]:
        """
        LLM'e karar verdirtir.
        Döner: (raw_text, structured_decisions_list)
        """
        prompt = _build_decision_prompt(positions, market_sent, stats, critique_sum)
        try:
            raw = _call_best_ai(prompt, max_tokens=800)
        except Exception as e:
            return f"AI karar üretilemedi: {e}", []

        # JSON parse dene
        decisions: list[dict] = []
        try:
            # LLM bazen markdown code block içine sarar
            clean = raw.strip().strip("```json").strip("```").strip()
            parsed = json.loads(clean)
            decisions = parsed.get("kararlar", [])
        except (json.JSONDecodeError, AttributeError):
            # Parse başarısız → ham metin döner, UI raw gösterir
            pass

        return raw, decisions


# ─────────────────────────────────────────────────────────────────────────────
# 6. Ana Risk Engine — Orkestratör
# ─────────────────────────────────────────────────────────────────────────────

class RiskEngine:
    """
    Tüm bileşenleri yönetir.
    Tek giriş noktası: run_full_analysis()

    Akış:
      1. DB'den açık pozisyonları oku
      2. yfinance'den güncel fiyatları çek
      3. Her pozisyon için PositionRisk hesapla
      4. Piyasa sentimentini çek (RSS)
      5. Self-critique çalıştır
      6. AgenticDecision üret
      7. En kritik pozisyonlar için yeni AIPrediction kaydet
      8. RiskReport döndür
    """

    def __init__(self):
        self._analyzer  = RiskAnalyzer()
        self._sentiment = SentimentFeed()

    def run_full_analysis(
        self,
        include_sentiment: bool = True,
        run_critique:      bool = True,
    ) -> RiskReport:
        logger.info("Risk Engine: analiz başlatıldı.")

        # ── 1. Açık pozisyonlar ────────────────────────────────────────
        with db.get_session() as session:
            open_pos: list[Portfolio] = session.query(Portfolio).filter(
                Portfolio.is_open == True  # noqa: E712
            ).all()

        if not open_pos:
            logger.info("Risk Engine: açık pozisyon yok.")
            return RiskReport(
                generated_at=datetime.utcnow().isoformat(),
                positions=[], portfolio_value=0, total_pnl_pct=0, total_pnl_abs=0,
                critical_count=0, market_sentiment=None,
                ai_decision="Portföyde açık pozisyon bulunmuyor.",
                stop_loss_table=[], self_critique="", accuracy_7d=None,
            )

        # ── 2. Güncel fiyatlar (toplu yfinance) ───────────────────────
        symbols  = [p.symbol.replace(".IS","") for p in open_pos]
        yf_syms  = [f"{s}.IS" for s in symbols]
        prices: dict[str, float] = {}

        try:
            data = yf.download(
                yf_syms, period="2d", interval="1d",
                auto_adjust=True, progress=False, threads=True,
                multi_level_index=True,
            )
            for yf_s in yf_syms:
                sym = yf_s.replace(".IS","")
                try:
                    if isinstance(data.columns, pd.MultiIndex):
                        close_col = data[("Close", yf_s)]
                    else:
                        close_col = data["Close"]
                    vals = close_col.dropna()
                    if not vals.empty:
                        prices[sym] = float(vals.iloc[-1])
                except Exception:
                    pass
        except Exception as e:
            logger.error(f"Risk Engine yfinance hatası: {e}")

        # ── 3. Her pozisyon için risk hesapla ─────────────────────────
        position_risks: list[PositionRisk] = []
        total_cost  = 0.0
        total_value = 0.0

        for pos in open_pos:
            sym     = pos.symbol.replace(".IS","")
            cur_px  = prices.get(sym, pos.buy_price)   # fiyat yoksa alış fiyatı
            risk    = self._analyzer.analyze_position(
                pos, cur_px, include_sentiment=include_sentiment
            )
            position_risks.append(risk)
            total_cost  += pos.buy_price * pos.quantity
            total_value += cur_px * pos.quantity

        total_pnl_abs = total_value - total_cost
        total_pnl_pct = (total_pnl_abs / total_cost * 100) if total_cost else 0.0
        critical_cnt  = sum(1 for r in position_risks if r.risk_level == "kritik")

        # ── 4. Piyasa sentimenti ───────────────────────────────────────
        market_sent: Optional[SentimentResult] = None
        if include_sentiment:
            try:
                market_sent = self._sentiment.analyze_market(limit=20)
            except Exception as e:
                logger.warning(f"Piyasa sentimenti hatası: {e}")

        # ── 5. Self-critique ──────────────────────────────────────────
        critique_text = ""
        stats = {"total": 0, "correct": 0, "accuracy_pct": None}
        if run_critique:
            try:
                critique_text, stats = run_self_critique(days=30)
            except Exception as e:
                logger.warning(f"Self-critique hatası: {e}")

        accuracy_7d = PredictionStore.accuracy_stats(days=7).get("accuracy_pct")

        # ── 6. Agentic karar ──────────────────────────────────────────
        critique_sum = critique_text[:300] if critique_text else ""
        raw_decision, decisions = AgenticDecision.decide(
            position_risks, market_sent, stats, critique_sum
        )

        # ── 7. Kritik pozisyonlar için tahmin kaydet ───────────────────
        for risk in position_risks:
            if risk.risk_level in ("kritik", "yüksek"):
                sent_score = risk.sentiment.score if risk.sentiment else 0.0
                # Gelen karardan bu sembol için aksiyon bul
                action_info = next(
                    (d for d in decisions if d.get("sembol","").upper() == risk.symbol), {}
                )
                direction = "down" if action_info.get("aksiyon","") in ("KAPAT","AZALT") else "up"
                try:
                    PredictionStore.save(
                        symbol=risk.symbol,
                        predicted_dir=direction,
                        confidence=70.0,
                        target_price=None,
                        stop_loss=action_info.get("stop_loss_onerisi") or risk.atr_stop,
                        reasoning=action_info.get("gerekce", "Risk Engine otomatik kaydı"),
                        price_now=risk.current_price,
                        sentiment_score=sent_score,
                        horizon_days=7,
                        model_used="risk_engine/agentic",
                    )
                except Exception as e:
                    logger.debug(f"Tahmin kayıt hatası [{risk.symbol}]: {e}")

        # ── 8. Stop-loss tablosu ───────────────────────────────────────
        sl_table = [
            {
                "Sembol":        r.symbol,
                "Güncel Fiyat":  r.current_price,
                "Alış Fiyatı":   r.buy_price,
                "K/Z %":         r.pnl_pct,
                "ATR Stop":      r.atr_stop,
                "% Stop (%8)":   r.pct_stop,
                "Risk Seviyesi": r.risk_level,
                "AI Aksiyon":    next(
                    (d.get("aksiyon","—") for d in decisions
                     if d.get("sembol","").upper() == r.symbol), "—"
                ),
            }
            for r in position_risks
        ]

        logger.info(f"Risk Engine: {len(position_risks)} pozisyon analiz edildi.")
        return RiskReport(
            generated_at=datetime.utcnow().isoformat(),
            positions=position_risks,
            portfolio_value=round(total_value, 2),
            total_pnl_pct=round(total_pnl_pct, 2),
            total_pnl_abs=round(total_pnl_abs, 2),
            critical_count=critical_cnt,
            market_sentiment=market_sent,
            ai_decision=raw_decision,
            stop_loss_table=sl_table,
            self_critique=critique_text,
            accuracy_7d=accuracy_7d,
        )
