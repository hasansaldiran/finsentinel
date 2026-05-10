"""
FinSentinel — Veritabanı Katmanı
core/db.py
SQLAlchemy + SQLite ile tarihsel veri ve cache yönetimi
"""
import json
import time
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Any

from sqlalchemy import (
    create_engine, Column, String, Float, Integer,
    DateTime, Text, Boolean, Index, text
)
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from loguru import logger

from config.settings import DB_PATH


class Base(DeclarativeBase):
    pass


# ─── Tablolar ──────────────────────────────────────────────────────────────────

class PriceHistory(Base):
    """OHLCV fiyat geçmişi — hisse, kripto, emtia, forex"""
    __tablename__ = "price_history"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    symbol      = Column(String(30), nullable=False)
    asset_type  = Column(String(20), nullable=False)  # bist, crypto, forex, commodity, index
    timestamp   = Column(DateTime, nullable=False)
    open        = Column(Float)
    high        = Column(Float)
    low         = Column(Float)
    close       = Column(Float)
    volume      = Column(Float)
    interval    = Column(String(10), default="1d")  # 1m, 5m, 1h, 1d vb.

    __table_args__ = (
        Index("idx_symbol_ts", "symbol", "timestamp"),
        Index("idx_asset_type", "asset_type"),
    )


class MacroData(Base):
    """TCMB ve diğer makroekonomik veriler"""
    __tablename__ = "macro_data"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    series_key  = Column(String(50), nullable=False)
    series_name = Column(String(100))
    date        = Column(DateTime, nullable=False)
    value       = Column(Float)
    unit        = Column(String(30))
    source      = Column(String(30), default="TCMB")

    __table_args__ = (
        Index("idx_series_date", "series_key", "date"),
    )


class NewsItem(Base):
    """Haberler ve duyurular"""
    __tablename__ = "news"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    source          = Column(String(50))
    title           = Column(Text, nullable=False)
    summary         = Column(Text)
    url             = Column(String(500))
    published_at    = Column(DateTime)
    fetched_at      = Column(DateTime, default=datetime.utcnow)
    sentiment_score = Column(Float)          # -1.0 (negatif) → +1.0 (pozitif)
    sentiment_label = Column(String(20))     # positive / negative / neutral
    ai_summary      = Column(Text)           # Claude özeti
    tags            = Column(Text)           # JSON list: ["BIST", "Faiz", ...]
    is_processed    = Column(Boolean, default=False)

    __table_args__ = (
        Index("idx_news_published", "published_at"),
        Index("idx_news_source", "source"),
    )


class CacheEntry(Base):
    """Genel amaçlı key-value cache (Redis yoksa)"""
    __tablename__ = "cache"

    key         = Column(String(200), primary_key=True)
    value       = Column(Text, nullable=False)   # JSON serialize edilmiş
    expires_at  = Column(Float, nullable=False)  # Unix timestamp
    created_at  = Column(Float, default=time.time)


class Alert(Base):
    """Fiyat ve sinyal alarmları"""
    __tablename__ = "alerts"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    symbol      = Column(String(30), nullable=False)
    alert_type  = Column(String(30))  # price_above, price_below, rsi_overbought vb.
    threshold   = Column(Float)
    message     = Column(Text)
    is_active   = Column(Boolean, default=True)
    triggered   = Column(Boolean, default=False)
    triggered_at= Column(DateTime)
    created_at  = Column(DateTime, default=datetime.utcnow)
    notify_telegram = Column(Boolean, default=True)
    notify_email    = Column(Boolean, default=False)


class Portfolio(Base):
    """Portföy pozisyonları"""
    __tablename__ = "portfolio"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    symbol      = Column(String(30), nullable=False)
    asset_type  = Column(String(20))
    quantity    = Column(Float, nullable=False)
    buy_price   = Column(Float, nullable=False)
    buy_date    = Column(DateTime)
    sell_price  = Column(Float)
    sell_date   = Column(DateTime)
    order_type  = Column(String(20))    # LIMIT, MARKET
    valid_type  = Column(String(20))    # DAY, GTC (Süre sonuna kadar)
    total_amount= Column(Float)         # quantity * buy_price
    notes       = Column(Text)
    is_open     = Column(Boolean, default=True)


class AIPrediction(Base):
    """
    AI'nın geçmiş yön/fiyat tahminleri.
    Risk Engine'in kendini eleştirmesi için temel tablo.
    """
    __tablename__ = "ai_predictions"

    id                = Column(Integer, primary_key=True, autoincrement=True)
    symbol            = Column(String(30), nullable=False, index=True)
    asset_type        = Column(String(20), default="bist")
    # Tahmin
    predicted_dir     = Column(String(10))   # "up" | "down" | "neutral"
    confidence        = Column(Float)         # 0-100
    target_price      = Column(Float)
    stop_loss         = Column(Float)
    horizon_days      = Column(Integer, default=7)
    reasoning         = Column(Text)          # AI'nın gerekçesi
    sentiment_score   = Column(Float)         # -1..+1 (haber sentiment girdisi)
    # Gerçekleşen
    price_at_pred     = Column(Float)         # Tahmin anındaki fiyat
    price_realized    = Column(Float)         # horizon_days sonraki fiyat
    actual_dir        = Column(String(10))    # "up" | "down" | "neutral"
    pnl_pct           = Column(Float)         # Gerçekleşen getiri %
    is_correct        = Column(Boolean)       # Tahmin doğru mu?
    # Meta
    created_at        = Column(DateTime, default=datetime.utcnow)
    evaluated_at      = Column(DateTime)
    model_used        = Column(String(50))    # "groq/llama-3.3-70b" vb.


class AIEvaluation(Base):
    """
    AI'nın kendi tahminlerini geriye dönük eleştirdiği kayıtlar.
    Her değerlendirme döneminde (haftalık) üretilir.
    """
    __tablename__ = "ai_evaluations"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    period_start    = Column(DateTime)
    period_end      = Column(DateTime)
    total_preds     = Column(Integer, default=0)
    correct_preds   = Column(Integer, default=0)
    accuracy_pct    = Column(Float)           # correct / total * 100
    avg_pnl_pct     = Column(Float)           # Ortalama getiri (doğru tahminler)
    self_critique   = Column(Text)            # AI'nın kendi eleştirisi (LLM çıktısı)
    strategy_update = Column(Text)            # Önerilen strateji güncellemesi
    created_at      = Column(DateTime, default=datetime.utcnow)


# ─── Veritabanı Yöneticisi ────────────────────────────────────────────────────

class DatabaseManager:
    """SQLite veritabanı yöneticisi — singleton"""

    _instance: Optional["DatabaseManager"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(
            f"sqlite:///{DB_PATH}",
            connect_args={"check_same_thread": False},
            echo=False,
        )
        self.SessionLocal = sessionmaker(bind=self.engine, expire_on_commit=False)
        Base.metadata.create_all(self.engine)
        
        # Migrations: Add new columns if they don't exist
        with self.engine.connect() as conn:
            for col, col_type in [
                ("order_type",  "VARCHAR(20)"),
                ("valid_type",  "VARCHAR(20)"),
                ("total_amount","FLOAT"),
            ]:
                try:
                    conn.execute(text(f"ALTER TABLE portfolio ADD COLUMN {col} {col_type}"))
                    conn.commit()
                except Exception:
                    pass  # Kolon zaten var
            # Yeni tablolar (AIPrediction, AIEvaluation) Base.metadata.create_all ile oluşturulur

        self._initialized = True
        logger.info(f"Veritabanı başlatıldı: {DB_PATH}")

    def get_session(self) -> Session:
        return self.SessionLocal()

    # ── Cache İşlemleri ─────────────────────────────────────────────────────

    def cache_set(self, key: str, value: Any, ttl: int = 3600) -> None:
        """Cache'e değer yaz"""
        with self.get_session() as session:
            entry = session.get(CacheEntry, key)
            serialized = json.dumps(value, default=str, ensure_ascii=False)
            if entry:
                entry.value      = serialized
                entry.expires_at = time.time() + ttl
                entry.created_at = time.time()
            else:
                session.add(CacheEntry(
                    key=key,
                    value=serialized,
                    expires_at=time.time() + ttl,
                ))
            session.commit()

    def cache_get(self, key: str) -> Optional[Any]:
        """Cache'den değer oku — süresi dolmuşsa None döner"""
        with self.get_session() as session:
            entry = session.get(CacheEntry, key)
            if not entry:
                return None
            if time.time() > entry.expires_at:
                session.delete(entry)
                session.commit()
                return None
            return json.loads(entry.value)

    def cache_clear_expired(self) -> int:
        """Süresi dolmuş cache kayıtlarını temizle"""
        with self.get_session() as session:
            result = session.execute(
                text("DELETE FROM cache WHERE expires_at < :now"),
                {"now": time.time()}
            )
            session.commit()
            return result.rowcount

    # ── Fiyat Geçmişi ───────────────────────────────────────────────────────

    def save_prices(self, records: list[dict]) -> int:
        """Toplu fiyat kaydet — duplicate'leri atla"""
        if not records:
            return 0
        saved = 0
        with self.get_session() as session:
            for rec in records:
                exists = session.execute(
                    text("""SELECT 1 FROM price_history
                            WHERE symbol=:s AND timestamp=:t AND interval=:i"""),
                    {"s": rec["symbol"], "t": rec["timestamp"], "i": rec.get("interval","1d")}
                ).fetchone()
                if not exists:
                    session.add(PriceHistory(**rec))
                    saved += 1
            session.commit()
        return saved

    def get_prices(self, symbol: str, days: int = 365, interval: str = "1d"):
        """Sembol için fiyat geçmişi getir"""
        since = datetime.utcnow() - timedelta(days=days)
        with self.get_session() as session:
            rows = session.execute(
                text("""SELECT * FROM price_history
                        WHERE symbol=:s AND interval=:i AND timestamp >= :since
                        ORDER BY timestamp ASC"""),
                {"s": symbol, "i": interval, "since": since}
            ).fetchall()
        return rows

    # ── Haber İşlemleri ─────────────────────────────────────────────────────

    def save_news(self, items: list[dict]) -> int:
        """Haberleri kaydet — URL bazlı duplicate kontrolü"""
        saved = 0
        with self.get_session() as session:
            for item in items:
                url = item.get("url", "")
                if url:
                    exists = session.execute(
                        text("SELECT 1 FROM news WHERE url=:u"), {"u": url}
                    ).fetchone()
                    if exists:
                        continue
                session.add(NewsItem(**item))
                saved += 1
            session.commit()
        return saved

    def get_latest_news(self, limit: int = 50, source: str = None):
        """Son haberleri getir"""
        with self.get_session() as session:
            q = "SELECT * FROM news"
            params = {}
            if source:
                q += " WHERE source=:src"
                params["src"] = source
            q += " ORDER BY published_at DESC LIMIT :lim"
            params["lim"] = limit
            return session.execute(text(q), params).fetchall()

    # ── Makro Veri ──────────────────────────────────────────────────────────

    def save_macro(self, records: list[dict]) -> int:
        """Makro ekonomik veri kaydet"""
        saved = 0
        with self.get_session() as session:
            for rec in records:
                exists = session.execute(
                    text("SELECT 1 FROM macro_data WHERE series_key=:k AND date=:d"),
                    {"k": rec["series_key"], "d": rec["date"]}
                ).fetchone()
                if not exists:
                    session.add(MacroData(**rec))
                    saved += 1
            session.commit()
        return saved

    def get_macro(self, series_key: str, months: int = 24):
        """Makro veri getir"""
        since = datetime.utcnow() - timedelta(days=months * 30)
        with self.get_session() as session:
            return session.execute(
                text("""SELECT date, value, unit FROM macro_data
                        WHERE series_key=:k AND date >= :since
                        ORDER BY date ASC"""),
                {"k": series_key, "since": since}
            ).fetchall()


# Singleton erişim noktası
db = DatabaseManager()
