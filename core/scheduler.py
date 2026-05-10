"""
FinSentinel — Arka Plan Zamanlayıcı
core/scheduler.py
Periyodik veri çekimi, cache yenileme, alarm kontrolü
"""
import threading
from datetime import datetime
from loguru import logger
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger


# ─── Görev Fonksiyonları ──────────────────────────────────────────────────────

def refresh_market_data():
    """Her 1 dakikada bir piyasa verilerini tazele"""
    from core.fetcher import PriceFetcher
    from config.settings import BIST_INDEX, FOREX_PAIRS, CRYPTO_SYMBOLS

    logger.debug("Piyasa verisi yenileniyor...")
    try:
        # Öncelikli: TRY pariteler + BIST endeks + top kripto
        priority = BIST_INDEX[:3] + FOREX_PAIRS[:4] + CRYPTO_SYMBOLS[:5]
        PriceFetcher.get_bulk_quotes(priority)
        logger.debug(f"Piyasa verisi güncellendi ({len(priority)} sembol)")
    except Exception as e:
        logger.error(f"Piyasa yenileme hatası: {e}")


def refresh_crypto():
    """Her 3 dakikada bir kripto verisi tazele"""
    from core.fetcher import PriceFetcher
    try:
        PriceFetcher.get_crypto_overview()
        logger.debug("Kripto verisi güncellendi")
    except Exception as e:
        logger.error(f"Kripto yenileme hatası: {e}")


def fetch_news():
    """Her 30 dakikada bir haberler çekilir"""
    from core.fetcher import NewsFetcher
    try:
        items = NewsFetcher.fetch_all(save_to_db=True)
        logger.info(f"Haber çekimi tamamlandı: {len(items)} haber")
    except Exception as e:
        logger.error(f"Haber çekimi hatası: {e}")


def refresh_tcmb():
    """Her sabah 08:00'de TCMB verileri güncellenir"""
    from core.fetcher import TCMBFetcher
    try:
        logger.info("TCMB verileri güncelleniyor...")
        TCMBFetcher.get_all_macro()
        logger.info("TCMB güncelleme tamamlandı")
    except Exception as e:
        logger.error(f"TCMB güncelleme hatası: {e}")


def refresh_world_indices():
    """Her 15 dakikada bir dünya endeksleri"""
    from core.fetcher import PriceFetcher
    try:
        PriceFetcher.get_world_indices()
        logger.debug("Dünya endeksleri güncellendi")
    except Exception as e:
        logger.error(f"Endeks yenileme hatası: {e}")


def clean_cache():
    """Her gece 03:00'te süresi dolmuş cache temizlenir"""
    from core.db import db
    try:
        count = db.cache_clear_expired()
        logger.info(f"Cache temizlendi: {count} kayıt silindi")
    except Exception as e:
        logger.error(f"Cache temizleme hatası: {e}")


def check_alerts():
    """Her 5 dakikada bir aktif alarmları kontrol et"""
    from core.db import db
    from sqlalchemy import text
    try:
        with db.get_session() as session:
            alerts = session.execute(
                text("SELECT * FROM alerts WHERE is_active=1 AND triggered=0")
            ).fetchall()

        if not alerts:
            return

        from core.fetcher import PriceFetcher
        for alert in alerts:
            try:
                q = PriceFetcher.get_quote(alert.symbol, use_cache=True)
                if "error" in q:
                    continue
                price = q["price"]

                triggered = False
                if alert.alert_type == "price_above" and price >= alert.threshold:
                    triggered = True
                elif alert.alert_type == "price_below" and price <= alert.threshold:
                    triggered = True

                if triggered:
                    _trigger_alert(alert, price)
            except Exception as e:
                logger.error(f"Alarm kontrolü hatası [{alert.symbol}]: {e}")

    except Exception as e:
        logger.error(f"Alarm sistemi hatası: {e}")


def _trigger_alert(alert, current_price: float):
    """Tetiklenen alarmı işle — DB güncelle + bildirim gönder"""
    from core.db import db, Alert
    from sqlalchemy import text
    import pytz
    from datetime import datetime
    from config.settings import TIMEZONE

    try:
        with db.get_session() as session:
            session.execute(
                text("""UPDATE alerts SET triggered=1, triggered_at=:now
                        WHERE id=:id"""),
                {"id": alert.id, "now": datetime.now(pytz.timezone(TIMEZONE))}
            )
            session.commit()

        msg = (
            f"🔔 ALARM: {alert.symbol}\n"
            f"📊 Tür: {alert.alert_type}\n"
            f"💰 Güncel fiyat: {current_price}\n"
            f"🎯 Hedef: {alert.threshold}\n"
            f"💬 {alert.message or ''}"
        )
        logger.info(f"Alarm tetiklendi: {msg}")

        if alert.notify_telegram:
            from core.telegram_bot import bot
            bot.send_market_alert(
                f"ALARM: {alert.symbol}",
                f"Tür: {alert.alert_type}\n💰 Güncel fiyat: {current_price}\n🎯 Hedef: {alert.threshold}\n💬 {alert.message or ''}",
                severity="warning"
            )

    except Exception as e:
        logger.error(f"Alarm tetikleme hatası: {e}")


def _send_telegram(message: str):
    """Telegram bildirimi gönder"""
    from config.settings import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
    import requests

    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return

    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        requests.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text":    message,
            "parse_mode": "HTML"
        }, timeout=10)
    except Exception as e:
        logger.error(f"Telegram gönderimi hatası: {e}")


# ─── Zamanlayıcı Yöneticisi ───────────────────────────────────────────────────

_scheduler: BackgroundScheduler = None
_lock = threading.Lock()


def start_scheduler() -> BackgroundScheduler:
    """Zamanlayıcıyı başlat (Streamlit'te bir kere çalışır)"""
    global _scheduler

    with _lock:
        if _scheduler and _scheduler.running:
            return _scheduler

        _scheduler = BackgroundScheduler(
            timezone="Europe/Istanbul",
            job_defaults={"coalesce": True, "max_instances": 1}
        )

        # Her 1 dakikada: piyasa verisi
        _scheduler.add_job(
            refresh_market_data,
            IntervalTrigger(minutes=1),
            id="market_refresh",
            name="Piyasa Verisi Yenileme",
            replace_existing=True,
        )

        # Her 3 dakikada: kripto
        _scheduler.add_job(
            refresh_crypto,
            IntervalTrigger(minutes=3),
            id="crypto_refresh",
            name="Kripto Yenileme",
            replace_existing=True,
        )

        # Her 15 dakikada: dünya endeksleri
        _scheduler.add_job(
            refresh_world_indices,
            IntervalTrigger(minutes=15),
            id="indices_refresh",
            name="Endeks Yenileme",
            replace_existing=True,
        )

        # Her 30 dakikada: haberler
        _scheduler.add_job(
            fetch_news,
            IntervalTrigger(minutes=30),
            id="news_fetch",
            name="Haber Çekimi",
            replace_existing=True,
        )

        # Her 5 dakikada: alarm kontrolü
        _scheduler.add_job(
            check_alerts,
            IntervalTrigger(minutes=5),
            id="alert_check",
            name="Alarm Kontrolü",
            replace_existing=True,
        )

        # Her sabah 08:00: TCMB verileri
        _scheduler.add_job(
            refresh_tcmb,
            CronTrigger(hour=8, minute=0),
            id="tcmb_refresh",
            name="TCMB Güncelleme",
            replace_existing=True,
        )

        # Her gece 03:00: cache temizliği
        _scheduler.add_job(
            clean_cache,
            CronTrigger(hour=3, minute=0),
            id="cache_clean",
            name="Cache Temizliği",
            replace_existing=True,
        )

        # ════════════════════════════════════════════════════════════════
        # TELEGRAM AKILLI BRİFİNG SİSTEMİ
        # Hafta içi  : 09:00 sabah | 10:00 açılış | 12:00 14:00 16:00 18:00 | 13:30 öğlen | 22:00 akşam
        # Hafta sonu / tatil: 10:00 sabah | 15:00 öğle | 22:00 akşam
        # Catchup    : Program açılışında geçen brifingleri telafi et
        # ════════════════════════════════════════════════════════════════
        from core.telegram_bot import bot

        # 09:00 — Sabah Brifingi (hafta içi + hafta sonu her gün)
        _scheduler.add_job(
            bot.send_morning_briefing,
            CronTrigger(hour=9, minute=0),
            id="tg_morning",
            name="Telegram Sabah Brifingi (09:00)",
            replace_existing=True,
        )

        # 10:00 — Borsa Açılış Brifingi (sadece hafta içi işlem günleri)
        _scheduler.add_job(
            bot.send_market_open,
            CronTrigger(hour=10, minute=0, day_of_week="mon-fri"),
            id="tg_market_open",
            name="Telegram Borsa Açılış (10:00 Hafta İçi)",
            replace_existing=True,
        )

        # 12:00, 14:00, 16:00, 18:00 — Hafta içi 2 saatlik güncelleme
        for _h in (12, 14, 16, 18):
            def _make_hourly(h=_h):
                def _job(): bot.send_hourly_update(hour=h)
                _job.__name__ = f"hourly_{h}"
                return _job
            _scheduler.add_job(
                _make_hourly(_h),
                CronTrigger(hour=_h, minute=0, day_of_week="mon-fri"),
                id=f"tg_hourly_{_h}",
                name=f"Telegram {_h}:00 Güncelleme",
                replace_existing=True,
            )

        # 13:30 — Öğlen Seansı Arası Brifingi (hafta içi)
        _scheduler.add_job(
            bot.send_noon_briefing,
            CronTrigger(hour=13, minute=30, day_of_week="mon-fri"),
            id="tg_noon",
            name="Telegram Öğlen Seansı Brifingi (13:30)",
            replace_existing=True,
        )

        # 22:00 — Akşam / Gün Sonu Özeti (her gün)
        _scheduler.add_job(
            bot.send_evening_summary,
            CronTrigger(hour=22, minute=0),
            id="tg_evening",
            name="Telegram Akşam Özeti (22:00)",
            replace_existing=True,
        )

        # ── Hafta Sonu & Resmi Tatil ─────────────────────────────────────
        # 10:00 sabah / 15:00 öğle / 22:00 akşam
        # send_weekend_briefing içindeki _is_trading_day() zaten hafta içini filtreler
        def _wknd_morning(): bot.send_weekend_briefing("morning")
        def _wknd_noon():    bot.send_weekend_briefing("noon")
        def _wknd_evening(): bot.send_weekend_briefing("evening")

        _scheduler.add_job(
            _wknd_morning,
            CronTrigger(hour=10, minute=0, day_of_week="sat,sun"),
            id="tg_wknd_morning",
            name="Telegram Hafta Sonu/Tatil Sabah (10:00)",
            replace_existing=True,
        )
        _scheduler.add_job(
            _wknd_noon,
            CronTrigger(hour=15, minute=0, day_of_week="sat,sun"),
            id="tg_wknd_noon",
            name="Telegram Hafta Sonu/Tatil Öğle (15:00)",
            replace_existing=True,
        )
        _scheduler.add_job(
            _wknd_evening,
            CronTrigger(hour=22, minute=0, day_of_week="sat,sun"),
            id="tg_wknd_evening",
            name="Telegram Hafta Sonu/Tatil Akşam (22:00)",
            replace_existing=True,
        )

        # ── Bot Alarm Kontrolü: Her 5 dk fiyat alarmları ─────────────────
        def _check_bot_alarms():
            try:
                from core.bot_portfolio import check_alarms
                triggered = check_alarms()
                for a in triggered:
                    arrow = "📈" if a["direction"] == "above" else "📉"
                    msg = (
                        f"🔔 <b>ALARM TETİKLENDİ — {a['symbol']}</b>\n"
                        f"{arrow} Fiyat <b>{a['threshold']:,.2f} ₺</b> seviyesini "
                        f"{'aştı' if a['direction']=='above' else 'kırdı'}!\n"
                        f"  Güncel: <b>{a.get('current_price',0):,.2f} ₺</b>"
                    )
                    cid = a.get("chat_id") or str(bot.chat_id)
                    bot.send_message(msg, chat_id=cid)
            except Exception as e:
                logger.debug(f"Bot alarm kontrol hatası: {e}")

        _scheduler.add_job(
            _check_bot_alarms,
            IntervalTrigger(minutes=5),
            id="bot_alarm_check",
            name="Bot Fiyat Alarm Kontrolü (5dk)",
            replace_existing=True,
        )

        # ── Trade Alert: Her 5 dk açık işlem stop/hedef kontrolü ────────
        _scheduler.add_job(
            bot.send_trade_alerts,
            IntervalTrigger(minutes=5),
            id="tg_trade_alerts",
            name="Trade Stop/Hedef Kontrolü (5dk)",
            replace_existing=True,
        )

        # ── Balina Alarmı: Hafta içi 30 dk'da bir ───────────────────────
        _scheduler.add_job(
            bot.send_whale_alert,
            IntervalTrigger(minutes=30),
            id="tg_whale_alert",
            name="Balina/Smart Money Alarm (30dk)",
            replace_existing=True,
        )

        # ── Haber Sentiment Kırmızı Liste: Hafta içi 09:30 ──────────────
        _scheduler.add_job(
            bot.send_sentiment_redlist,
            CronTrigger(hour=9, minute=30, day_of_week="mon-fri"),
            id="tg_sentiment_redlist",
            name="Haber Sentiment Kırmızı Liste (09:30)",
            replace_existing=True,
        )

        # ── Catchup: Program Açılışında Gecikmeli Brifing Kontrolü ───────
        # 60 saniye sonra bir kere çalışır, gerekirse telafi brifingi gönderir
        import datetime as _dt
        _catchup_time = _dt.datetime.now() + _dt.timedelta(seconds=60)
        _scheduler.add_job(
            bot.send_catchup_briefing,
            "date",
            run_date=_catchup_time,
            id="tg_catchup",
            name="Telegram Catchup Brifingi (Başlangıç)",
            replace_existing=True,
        )

        _scheduler.start()
        logger.info("⏰ Zamanlayıcı başlatıldı — tüm görevler aktif")

        # ── Telegram Komut Dinleyici — ayrı daemon thread ────────────────
        def _start_cmd_listener():
            try:
                bot.listen_commands(poll_interval=3)
            except Exception as e:
                logger.error(f"Komut dinleyici thread hatası: {e}")

        _cmd_thread = threading.Thread(
            target=_start_cmd_listener,
            name="telegram-cmd-listener",
            daemon=True,
        )
        _cmd_thread.start()
        logger.info("📨 Telegram komut dinleyici thread başlatıldı")

        return _scheduler


def stop_scheduler():
    """Zamanlayıcıyı durdur"""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Zamanlayıcı durduruldu")


def get_scheduler_status() -> list[dict]:
    """Zamanlayıcı görev durumları"""
    global _scheduler
    if not _scheduler or not _scheduler.running:
        return []

    jobs = []
    for job in _scheduler.get_jobs():
        next_run = job.next_run_time
        jobs.append({
            "id":       job.id,
            "name":     job.name,
            "next_run": next_run.strftime("%H:%M:%S") if next_run else "—",
            "running":  True,
        })
    return jobs
