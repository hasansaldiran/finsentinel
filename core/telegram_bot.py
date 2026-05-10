"""
FinSentinel — Akıllı Telegram Bot Servisi
core/telegram_bot.py

Güvenli, AI destekli yatırım rehberliği sunan Telegram botu.
İş Yatırım temel analiz verileri + katılım hissesi odaklı brifinglerle donatılmıştır.
"""

import os
import json
import html as _html
import requests
from datetime import datetime, timedelta
from pathlib import Path
from loguru import logger
from config.settings import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from core.fundamental_bot import (
    cmd_oneri, cmd_al, cmd_tut, cmd_sat,
    cmd_alfaskor, cmd_temel, cmd_hedef,
    cmd_temettu, cmd_yabanci, cmd_performans_temel,
    cmd_endeks, cmd_katilim_full,
)

# ─── Sabitler ────────────────────────────────────────────────────────────────

_DATA_ROOT       = Path("data/isyatirim")
_LAST_BRIFING_FILE = Path("data/last_briefing.json")

# Türkiye resmi tatil günleri (YYYY-MM-DD)
_RESMI_TATILLER = {
    "2025-01-01","2025-04-23","2025-05-01","2025-05-19",
    "2025-06-30","2025-07-01","2025-07-02","2025-07-03",
    "2025-08-30","2025-09-05","2025-09-06","2025-09-07",
    "2025-09-08","2025-10-29",
    "2026-01-01","2026-03-20","2026-03-21","2026-03-22",
    "2026-04-23","2026-05-01","2026-05-19",
    "2026-05-27","2026-05-28","2026-05-29","2026-05-30",
    "2026-08-30","2026-10-29",
}

# Resmi XKTUM katılım hisseleri (228 sembol) — tek kaynak: pages/katilim_data.py
try:
    import sys as _sys, os as _os
    _proj_root = str(Path(__file__).resolve().parent.parent)
    if _proj_root not in _sys.path:
        _sys.path.insert(0, _proj_root)
    from pages.katilim_data import XKTUM_SEMBOLLER as _XKTUM_SET
    _XKTUM_SET = set(_XKTUM_SET)
except Exception:
    _XKTUM_SET = set()  # fallback: boş küme — tüm hisseler geçer

# ─── Güvenlik ─────────────────────────────────────────────────────────────────

def _allowed_ids() -> set:
    ids = set()
    if TELEGRAM_CHAT_ID:
        ids.add(str(TELEGRAM_CHAT_ID).strip())
    for cid in os.getenv("TELEGRAM_ALLOWED_CHATS", "").split(","):
        cid = cid.strip()
        if cid:
            ids.add(cid)
    return ids

ALLOWED_CHAT_IDS: set = _allowed_ids()


# ─── TelegramBot ──────────────────────────────────────────────────────────────

class TelegramBot:
    def __init__(self):
        self.token    = TELEGRAM_BOT_TOKEN
        self.chat_id  = TELEGRAM_CHAT_ID
        self.base_url = f"https://api.telegram.org/bot{self.token}"

    # ── Komut Kaydı (setMyCommands) ───────────────────────────────────────────

    def register_commands(self):
        """
        Telegram'a komut listesini bildirir.
        Bu olmadan grup/kişisel sohbette '/' yazınca picker boş kalır,
        gönder butonu pasifleşir.
        """
        if not self.token:
            return
        commands = [
            # Piyasa
            {"command": "durum",       "description": "Katılım endeksleri + altın + kur anlık özet"},
            {"command": "katilim",     "description": "XKTUM katılım hisseleri öne çıkanlar (228 hisse)"},
            {"command": "altin",       "description": "Altın (TL/ONS/gram) & gümüş fiyatları"},
            {"command": "doviz",       "description": "USD/TRY EUR/TRY kur bilgisi"},
            {"command": "fonlar",      "description": "Katılım yatırım fonları performansı"},
            {"command": "sektor",      "description": "XKTUM sektör dağılımı ve rotasyon sinyali"},
            # Analiz
            {"command": "firsat",      "description": "Günün en yüksek alpha skorlu katılım hissesi"},
            {"command": "analiz",      "description": "Hisse detay analizi — /analiz THYAO"},
            {"command": "risk",        "description": "Risk notu Düşük/Orta/Yüksek/Kritik — /risk THYAO"},
            {"command": "sorgula",     "description": "Eleştirel ön analiz — /sorgula THYAO"},
            # Temel Analiz
            {"command": "oneri",       "description": "AL/TUT/SAT özeti — /oneri veya /oneri THYAO"},
            {"command": "al",          "description": "En iyi AL önerileri (katılım uyumlu)"},
            {"command": "alfaskor",    "description": "Alpha skor sıralaması top-10 (XKTUM)"},
            {"command": "temel",       "description": "Tam temel analiz kartı — /temel THYAO"},
            {"command": "hedef",       "description": "Hedef fiyat geçmişi — /hedef THYAO"},
            {"command": "temettu",     "description": "En yüksek temettü verimi (katılım hisseleri)"},
            {"command": "endeks",      "description": "XK030 / XKTUM endeks bileşenleri özeti"},
            # Portföy
            {"command": "portfoy",     "description": "Portföy özeti ve P&L"},
            {"command": "ekle",        "description": "Hisse ekle — /ekle THYAO 100 300.50"},
            {"command": "kaldir",      "description": "Portföyden çıkar — /kaldir THYAO"},
            # Alarmlar
            {"command": "alarm",       "description": "Fiyat alarmı kur — /alarm THYAO 350 yukari"},
            {"command": "alarmlar",    "description": "Aktif alarmlarım"},
            {"command": "alarmsil",    "description": "Alarm sil — /alarmsil THYAO"},
            # İşlem takip
            {"command": "izle",        "description": "Stop/hedef takibi — /izle THYAO 300 280 340"},
            {"command": "kapat",       "description": "İşlemi kapat — /kapat THYAO"},
            {"command": "acikislemler","description": "Aktif takip listesi"},
            {"command": "performans",  "description": "Geçmiş işlem istatistikleri"},
            # Haberler
            {"command": "haber",       "description": "Son haberler — /haber veya /haber THYAO"},
            {"command": "kap",         "description": "Son KAP özel durum açıklamaları"},
            # Planlama
            {"command": "plan",        "description": "Çok dönemli yatırım planı — /plan veya /plan THYAO"},
            {"command": "uzunvade",    "description": "1-5 yıllık uzun vadeli yatırım görüşü"},
            # Acil & Yardım
            {"command": "panic",       "description": "Acil durum raporu"},
            {"command": "yardim",      "description": "Yardım menüsü — /yardim [kategori]"},
        ]
        try:
            resp = requests.post(
                f"{self.base_url}/setMyCommands",
                json={"commands": commands},
                timeout=10,
            )
            if resp.ok:
                logger.info(f"✅ {len(commands)} komut Telegram'a kaydedildi.")
            else:
                logger.warning(f"setMyCommands hatası: {resp.text}")
        except Exception as e:
            logger.error(f"register_commands hatası: {e}")

    # ── Temel Gönderici ───────────────────────────────────────────────────────

    def send_message(self, text: str, parse_mode: str = "HTML",
                     chat_id: str = None, disable_preview: bool = True) -> bool:
        if not self.token:
            logger.warning("Telegram Bot Token eksik.")
            return False
        target = str(chat_id or self.chat_id).strip()
        if not target:
            logger.warning("Telegram Chat ID tanımlanmamış.")
            return False

        if ALLOWED_CHAT_IDS and target not in ALLOWED_CHAT_IDS:
            logger.warning(f"İzinsiz chat_id engellendi: {target}")
            return False

        # Telegram mesaj sınırı 4096 karakterdir. Güvenli bölme için 4000 limitini kullanıyoruz.
        def _split_text(full_text: str, chunk_size=4000):
            chunks = []
            while len(full_text) > chunk_size:
                # Sonraki en yakın satır sonundan bölmeye çalış
                split_idx = full_text.rfind("\n", 0, chunk_size)
                if split_idx == -1:
                    split_idx = chunk_size
                chunks.append(full_text[:split_idx])
                full_text = full_text[split_idx:].strip()
            if full_text:
                chunks.append(full_text)
            return chunks

        text_chunks = _split_text(text)
        success_overall = True

        for chunk in text_chunks:
            payload = {
                "chat_id": target, "text": chunk,
                "parse_mode": parse_mode,
                "disable_web_page_preview": disable_preview,
            }
            try:
                resp = requests.post(f"{self.base_url}/sendMessage", json=payload, timeout=10)
                if not resp.ok:
                    logger.error(f"Telegram API hatası: {resp.text}")
                    if "can't parse" in resp.text.lower():
                        payload["parse_mode"] = None
                        # HTML escape & strip tags
                        payload["text"] = _html.unescape(
                            chunk.replace("<b>","").replace("</b>","")
                                .replace("<i>","").replace("</i>","")
                                .replace("<code>","").replace("</code>","")
                        )
                        r2 = requests.post(f"{self.base_url}/sendMessage", json=payload, timeout=5)
                        if not r2.ok:
                            success_overall = False
                    else:
                        success_overall = False
            except Exception as e:
                logger.error(f"Telegram bağlantı hatası: {e}")
                success_overall = False

        return success_overall

    # ── Zamanlı Brifinglar ────────────────────────────────────────────────────

    def send_morning_briefing(self):
        """09:00 — Önceki günün top10 yükselen/düşen + bugün beklentiler + günlük alım önerileri."""
        logger.info("Sabah brifingi gönderiliyor...")
        try:
            quotes  = self._get_key_quotes()
            world   = self._get_world_indices()
            news    = self._get_news_with_links(limit=5)
            fund    = self._get_fundamental_summary()
            katilim = self._get_katilim_top(n=5)
            gainers_yesterday, losers_yesterday = self._get_bist_movers(top_n=10)
            firsat  = self._get_gunun_firsati()
            signal  = self._get_action_signal(firsat["kod"] if firsat else None)

            fund_text = ""
            if fund:
                stale_note = (f"  <i>⚠️ Temel veri {fund.get('data_date','?')} tarihli — bugün güncellenmedi</i>\n"
                              if fund.get("data_stale") else "")
                fund_text = (
                    "\n<b>📊 Temel Analiz Özeti (İş Yatırım)</b>\n"
                    + stale_note
                    + f"  AL önerisi: <b>{fund.get('al_count',0)}</b> hisse  |  "
                    f"Ort. getiri pot.: <b>%{fund.get('avg_pot',0):.1f}</b>\n"
                    f"  En cazip 5: <b>{fund.get('top3','')}</b>\n"
                )

            katilim_text = ""
            if katilim:
                def _kat_row_morning(k):
                    f = k.get("fiyat", 0)
                    h = k.get("hedef", 0)
                    s = k.get("stop", 0)
                    fiyat_str = f"  {f:.2f}₺ → {h:.2f}₺  (stop: {s:.2f}₺)" if f > 0 else ""
                    return (f"  • <code>{k['kod']}</code> {k['ad'][:20]} — "
                            f"Pot: <b>%{k['pot']:.1f}</b>  [{k['oneri']}]{fiyat_str}")
                katilim_text = (
                    "\n<b>☪️ Katılım Hisseleri — Günün Öne Çıkanları</b>\n"
                    + "\n".join(_kat_row_morning(k) for k in katilim[:5])
                    + "\n"
                )

            volatile = self._is_volatile_market()
            vol_note = "PIYASA VOLATİL — defansif mod aktif. " if volatile else ""
            data_warn = f"NOT: Temel veri {fund.get('data_date','?')} tarihli, bugün güncellenmedi. " if fund.get("data_stale") else ""
            kat_fiyat_str = "; ".join(
                f"{k['kod']} şu an {k['fiyat']:.2f}₺ hedef {k['hedef']:.2f}₺ stop {k['stop']:.2f}₺"
                if k.get("fiyat", 0) > 0
                else f"{k['kod']} (fiyat alınamadı, pot %{k['pot']:.0f})"
                for k in katilim
            )
            prompt = (
                f"FinSentinel SABAH brifingi — katılım yatırımcısı odaklı. {vol_note}{data_warn}"
                f"Dün kapanış: {quotes}. "
                f"Dün yükselen (XKTUM): {gainers_yesterday}. Dün düşen (XKTUM): {losers_yesterday}. "
                f"İş Yatırım (AL:{fund.get('al_count',0)}, Ort.pot:%{fund.get('avg_pot',0):.1f}, top5:{fund.get('top3','')}). "
                f"XKTUM katılım hisseleri GERÇEK FİYATLAR: {kat_fiyat_str}. "
                + ("Piyasa sert düştü; öncelik zararı kesmek, defansif pozisyon. " if volatile else "")
                + "SADECE TÜRKÇE yaz. SADECE XKTUM listesindeki katılım uyumlu hisseleri öner.\n"
                "Şunları ver:\n"
                "1) Bugün piyasada ne bekleniyor — XK030/XKTUM açısından (2 cümle)\n"
                "2) GÜNLÜK: 3 somut XKTUM hissesi — sembol + GERÇEK alım seviyesi + stop + hedef + kısa gerekçe\n"
                "3) ALTIN & KUR: Bugün altın/dolar için kısa not (1 cümle)\n"
                "4) HAFTALIK: 2 XKTUM hissesi için haftalık strateji\n"
                "5) Katılım yatırımcısı için özel not\n"
                "6) 1 kritik risk\n"
                "Verilen fiyatların DIŞINDA fiyat UYDURMA.\n"
                "ÖNEMLİ: Yanıtını ASLA yarım bırakma, en fazla 3500 karakterde tamamla."
            )
            ai_text = self._ai_text(prompt, max_tokens=1000)

            volatile_banner = (
                "\n⚠️ <b>VOLATİLİTE MODU AKTİF</b> — Piyasa -%2'nin altında."
                " İşlem hacmini azaltın, stop-loss'larınızı kontrol edin.\n"
            ) if volatile else ""

            msg = (
                self._header("☀️", "Günaydın — Sabah Brifingi",
                             datetime.now().strftime("%d %b %Y — %A"))
                + volatile_banner
                + "\n"
                + self._quotes_block(quotes)
                + "\n\n<b>🌍 Dünya Piyasaları</b>\n"
                + "\n".join(f"  {w}" for w in world)
                + "\n"
                + self._movers_block(gainers_yesterday, losers_yesterday, top_n=10)
                + fund_text
                + katilim_text
                + self._firsat_block(firsat)
                + self._action_signal_block(signal)
                + "\n<b>🤖 AI Piyasa Yorumu & Günlük Alım Önerileri</b>\n"
                + ai_text
                + "\n\n<b>📰 Öne Çıkan Haberler</b>\n"
                + self._news_block(news[:5])
                + self._footer("Borsa 10:00'da açılıyor — sonraki brifing 10:00")
            )
            self.send_message(msg)
            self._save_last_briefing("morning")
        except Exception as e:
            logger.error(f"Sabah brifingi hatası: {e}")

    def send_market_open(self):
        """10:00 — Borsa açılışı: ilk hareket + temel analiz + AI tavsiyesi."""
        if not self._is_trading_day():
            return
        logger.info("Piyasa açılış mesajı gönderiliyor...")
        try:
            quotes  = self._get_key_quotes()
            gainers, losers = self._get_bist_movers(top_n=10)
            fund    = self._get_fundamental_summary()
            katilim = self._get_katilim_top(n=3)
            news    = self._get_news_with_links(limit=3)

            katilim_text = ""
            if katilim:
                def _kat_row(k):
                    f = k.get("fiyat", 0)
                    h = k.get("hedef", 0)
                    fiyat_str = f"  Fiyat: {f:.2f}₺  →  Hedef: {h:.2f}₺" if f > 0 else ""
                    return (f"  • <code>{k['kod']}</code>  Pot: %{k['pot']:.1f}  [{k['oneri']}]{fiyat_str}")
                katilim_text = (
                    "\n<b>☪️ Katılım Radarı</b>\n"
                    + "\n".join(_kat_row(k) for k in katilim)
                    + "\n"
                )

            data_warn = f"NOT: Temel veri {fund.get('data_date','?')} tarihli. " if fund.get("data_stale") else ""
            # Gerçek fiyat/hedef bilgilerini prompta ekle — AI uydurmasın
            kat_fiyat_str = "; ".join(
                f"{k['kod']} şu an {k['fiyat']:.2f}₺ hedef {k['hedef']:.2f}₺ (%{k['pot']:.0f} pot)"
                if k.get("fiyat", 0) > 0
                else f"{k['kod']} (fiyat alınamadı, pot %{k['pot']:.0f})"
                for k in katilim
            )
            prompt = (
                f"BIST 10:00'da açıldı. {data_warn}"
                f"Göstergeler: {quotes}. "
                f"Açılışta yükselen: {gainers[:5]}. Düşen: {losers[:5]}. "
                f"Temel analiz (top5:{fund.get('top3','')}). "
                f"Katılım hisseleri GERÇEK FİYATLAR: {kat_fiyat_str}. "
                "SADECE TÜRKÇE yaz. SADECE katılım uyumlu hisseleri öner (banka/sigorta/GYO yok).\n"
                "Şunları ver:\n"
                "1) Açılış yorumu — momentum güçlü mü zayıf mı? (2 cümle)\n"
                "2) BUGÜN takip edilecek 2 hisse: Sembol — neden — GERÇEK alım seviyesi (yukarıdaki fiyatları kullan) — hedef — stop (%7 aşağısı)\n"
                "3) Katılım yatırımcısı için özel not: hangi katılım hissesini bugün izlemeli, neden\n"
                "BU FİYATLARIN DIŞINDA FİYAT UYDURMA. Kısa ve net tut.\n"
                "ÖNEMLİ: Yanıtını ASLA yarım bırakma, en fazla 3500 karakterde tamamla."
            )
            ai_text = self._ai_text(prompt, max_tokens=600)

            msg = (
                self._header("🔔", "Borsa Açıldı — 10:00  ⏱ veriler ~15dk gecikmeli",
                             datetime.now().strftime("%d %b %Y"))
                + "\n"
                + self._quotes_block(quotes)
                + "\n"
                + self._movers_block(gainers, losers, top_n=10)
                + katilim_text
                + "\n<b>🤖 Açılış Analizi & Tavsiye</b>\n"
                + ai_text
                + "\n\n<b>📰 Son Haberler</b>\n"
                + self._news_block(news)
                + self._footer("2 saatlik brifing: 12:00")
            )
            self.send_message(msg)
            self._save_last_briefing("market_open")
        except Exception as e:
            logger.error(f"Piyasa açılış hatası: {e}")

    def send_hourly_update(self, hour: int = None):
        """10-18 arası çift saatlik güncelleme (10,12,14,16,18) + haber + AI."""
        if not self._is_trading_day():
            return
        now  = datetime.now()
        hour = hour or now.hour
        if hour not in (10, 12, 14, 16, 18):
            return
        logger.info(f"Saatlik güncelleme gönderiliyor ({hour}:00)...")
        try:
            quotes  = self._get_key_quotes()
            gainers, losers = self._get_bist_movers(top_n=10)
            news    = self._get_news_with_links(limit=4)
            fund    = self._get_fundamental_summary()
            katilim = self._get_katilim_top(n=3)

            next_h  = {10:"12:00", 12:"14:00", 14:"16:00", 16:"18:00", 18:"Kapanış"}.get(hour,"—")

            katilim_text = ""
            if katilim:
                def _kat_row_hourly(k):
                    f = k.get("fiyat", 0)
                    h_p = k.get("hedef", 0)
                    s = k.get("stop", 0)
                    # 12 ve 16'da detaylı, diğer saatlerde özet
                    if hour in (12, 16) and f > 0:
                        return (f"  • <code>{k['kod']}</code>  Pot: %{k['pot']:.1f}  [{k['oneri']}]"
                                f"  {f:.2f}₺→{h_p:.2f}₺  stop:{s:.2f}₺")
                    elif f > 0:
                        return f"  • <code>{k['kod']}</code>  {f:.2f}₺→{h_p:.2f}₺  [{k['oneri']}]"
                    else:
                        return f"  • <code>{k['kod']}</code>  Pot: %{k['pot']:.1f}  [{k['oneri']}]"
                katilim_text = (
                    "\n<b>☪️ Katılım Güncel</b>\n"
                    + "\n".join(_kat_row_hourly(k) for k in katilim)
                    + "\n"
                )

            data_warn = f"Temel veri {fund.get('data_date','?')} tarihli. " if fund.get("data_stale") else ""
            kat_fiyat_str = "; ".join(
                f"{k['kod']} {k['fiyat']:.2f}₺→{k['hedef']:.2f}₺"
                if k.get("fiyat", 0) > 0 else k['kod']
                for k in katilim
            ) if katilim else "—"
            prompt = (
                f"BIST saat {hour}:00. {data_warn}Göstergeler: {quotes}. "
                f"Yükselen: {gainers[:5]}. Düşen: {losers[:5]}. "
                f"Temel (top5:{fund.get('top3','')}). "
                f"Katılım GERÇEK FİYATLAR: {kat_fiyat_str}. "
                "SADECE TÜRKÇE yaz. SADECE katılım uyumlu hisseler öner (banka/sigorta/GYO asla önerme).\n"
                "Verilen fiyatların DIŞINDA fiyat UYDURMA. Şunları ver:\n"
                f"1) {hour}:00 piyasa yorumu (1 cümle)\n"
                "2) Şu an aksiyon: 2 katılım hissesi — sembol + AL/TUT + GERÇEK alım/stop seviyeleri + gerekçe\n"
                "3) Gün kapanışına kadar kritik seviyeler\n"
                f"Sonraki brifing: {next_h}.\n"
                "ÖNEMLİ: Yanıtını ASLA yarım bırakma, en fazla 3500 karakterde tamamla."
            )
            ai_text = self._ai_text(prompt, max_tokens=500)

            msg = (
                self._header("📊", f"Piyasa Güncellemesi — {hour}:00",
                             now.strftime("%d %b"))
                + "\n"
                + self._quotes_block(quotes)
                + "\n"
                + self._movers_block(gainers, losers, top_n=10)
                + katilim_text
                + "\n<b>🤖 AI Yorum & Tavsiye</b>\n"
                + ai_text
                + "\n\n<b>📰 Son Haberler</b>\n"
                + self._news_block(news)
                + self._footer(f"Sonraki güncelleme: {next_h}")
            )
            self.send_message(msg)
            self._save_last_briefing(f"hourly_{hour}")
        except Exception as e:
            logger.error(f"Saatlik güncelleme hatası ({hour}): {e}")

    def send_noon_briefing(self):
        """13:30 — Öğlen seansı arası özel brifing."""
        if not self._is_trading_day():
            return
        logger.info("Öğlen seansı brifingi gönderiliyor...")
        try:
            quotes  = self._get_key_quotes()
            gainers, losers = self._get_bist_movers(top_n=10)
            news    = self._get_news_with_links(limit=4)
            fund    = self._get_fundamental_summary()
            katilim = self._get_katilim_top(n=5)

            katilim_text = ""
            if katilim:
                def _kat_row_noon(k):
                    f = k.get("fiyat", 0)
                    h = k.get("hedef", 0)
                    fiyat_str = f"  {f:.2f}₺→{h:.2f}₺" if f > 0 else ""
                    return (f"  • <code>{k['kod']}</code> {k['ad'][:18]}  "
                            f"Pot: <b>%{k['pot']:.1f}</b>  [{k['oneri']}]  "
                            f"F/K: {k.get('fk','—')}{fiyat_str}")
                katilim_text = (
                    "\n<b>☪️ Katılım Hisseleri — Öğlen Değerlendirmesi</b>\n"
                    + "\n".join(_kat_row_noon(k) for k in katilim)
                    + "\n"
                )

            fund_text = ""
            if fund:
                stale_note = (f"  <i>⚠️ Veri {fund.get('data_date','?')} tarihli</i>\n"
                              if fund.get("data_stale") else "")
                fund_text = (
                    "\n<b>📊 Temel Analiz (Günün Yarısı)</b>\n"
                    + stale_note
                    + f"  AL: {fund.get('al_count',0)}  |  TUT: {fund.get('tut_count',0)}  "
                    f"|  SAT: {fund.get('sat_count',0)}\n"
                    f"  Ort. Getiri Pot.: %{fund.get('avg_pot',0):.1f}  |  "
                    f"Smart Money Giriş: {fund.get('smart_giris',0)} hisse (yabancı alım tespit edilen adet)\n"
                )

            data_warn = f"Temel veri {fund.get('data_date','?')} tarihli. " if fund.get("data_stale") else ""
            kat_fiyat_str = "; ".join(
                f"{k['kod']} şu an {k['fiyat']:.2f}₺, hedef {k['hedef']:.2f}₺, stop {k['stop']:.2f}₺"
                if k.get("fiyat", 0) > 0
                else f"{k['kod']} (fiyat alınamadı, pot %{k['pot']:.0f})"
                for k in katilim
            )
            prompt = (
                f"BIST öğlen 13:30 brifingi. {data_warn}"
                f"Sabahtan bu yana: {quotes}. Yükselen: {gainers[:5]}. Düşen: {losers[:5]}. "
                f"İş Yatırım (AL:{fund.get('al_count',0)}, top5:{fund.get('top3','')}). "
                f"Katılım hisseleri GERÇEK FİYATLAR: {kat_fiyat_str}. "
                "SADECE TÜRKÇE yaz. SADECE katılım uyumlu hisseleri öner (banka/sigorta/GYO/AKBNK/GARAN vb. asla önerme).\n"
                "Şunları ver:\n"
                "1) Sabah tezi tuttu mu? (1-2 cümle)\n"
                "2) ÖĞLEDEN SONRA: 2 senaryo (yükseliş/düşüş) — her senaryo için GERÇEK fiyatlarla aksiyon planı\n"
                "3) HAFTALIK görünüm: Bu hafta öne çıkabilecek 2-3 katılım hissesi + gerekçe\n"
                "4) Katılım özel not: öğleden sonra hangi hisse izlenmeli, GERÇEK alım/stop seviyeleri\n"
                "Verilen fiyatların DIŞINDA fiyat UYDURMA.\n"
                "ÖNEMLİ: Yanıtını ASLA yarım bırakma, en fazla 3500 karakterde tamamla."
            )
            ai_text = self._ai_text(prompt, max_tokens=800)

            msg = (
                self._header("🌤️", "Öğlen Seansı Brifingi — 13:30",
                             datetime.now().strftime("%d %b %Y"))
                + "\n"
                + self._quotes_block(quotes)
                + "\n"
                + self._movers_block(gainers, losers, top_n=10)
                + fund_text
                + katilim_text
                + "\n<b>🤖 Öğlen Değerlendirmesi & Öğleden Sonra Stratejisi</b>\n"
                + ai_text
                + "\n\n<b>📰 Öğlen Haberleri</b>\n"
                + self._news_block(news)
                + self._footer("Sonraki güncelleme: 14:00")
            )
            self.send_message(msg)
            self._save_last_briefing("noon")
        except Exception as e:
            logger.error(f"Öğlen brifingi hatası: {e}")

    def send_evening_summary(self):
        """22:00 — Gün sonu özeti + yarın fikirleri + temel analiz."""
        logger.info("Akşam özeti gönderiliyor...")
        try:
            is_trading = self._is_trading_day()
            quotes  = self._get_key_quotes()
            gainers, losers = self._get_bist_movers(top_n=10)
            news    = self._get_news_with_links(limit=5)
            kap     = self._get_kap_corporate_news(limit=4)
            fund    = self._get_fundamental_summary()
            katilim = self._get_katilim_top(n=5)
            firsat  = self._get_gunun_firsati()
            signal  = self._get_action_signal(firsat["kod"] if firsat else None)

            tomorrow_note = ""
            next_trading  = "yarın" if is_trading else "bir sonraki işlem günü"

            katilim_text = ""
            if katilim:
                katilim_text = (
                    "\n<b>☪️ Katılım Portföy Özeti</b>\n"
                    + "\n".join(f"  • <code>{k['kod']}</code> {k['ad'][:20]}  "
                                f"Pot: <b>%{k['pot']:.1f}</b>  [{k['oneri']}]"
                                for k in katilim[:5])
                    + "\n"
                )

            fund_text = ""
            if fund:
                stale_note = (f"  <i>⚠️ Veri {fund.get('data_date','?')} tarihli — taze veri bekleniyor</i>\n"
                              if fund.get("data_stale") else "")
                fund_text = (
                    "\n<b>📊 İş Yatırım Temel Analiz Özeti</b>\n"
                    + stale_note
                    + f"  AL: {fund.get('al_count',0)}  |  "
                    f"Ort. Getiri Pot.: %{fund.get('avg_pot',0):.1f}\n"
                    f"  En cazip 5: <b>{fund.get('top3','—')}</b>\n"
                    f"  Smart Money Giriş: {fund.get('smart_giris',0)} hisse (yabancı alım tespit edilen adet)\n"
                )

            data_warn = f"Temel veri {fund.get('data_date','?')} tarihli, bugün güncellenmedi. " if fund.get("data_stale") else ""
            smart_giris = fund.get('smart_giris', 0)
            kat_fiyat_str = "; ".join(
                f"{k['kod']} şu an {k['fiyat']:.2f}₺ hedef {k['hedef']:.2f}₺ stop {k['stop']:.2f}₺"
                if k.get("fiyat", 0) > 0
                else f"{k['kod']} pot %{k['pot']:.0f}"
                for k in katilim
            )
            prompt = (
                f"{'Hafta içi Türkiye borsası (XKTUM/katılım odaklı)' if is_trading else 'Piyasalar bugün kapalıydı —'} "
                f"GÜN SONU özeti 22:00. {data_warn}"
                f"Kapanış: {quotes}. XKTUM kazananlar: {gainers[:5]}. XKTUM kaybedenler: {losers[:5]}. "
                f"KAP: {kap[:3] if kap else 'yok'}. "
                f"İş Yatırım (AL:{fund.get('al_count',0)}, Ort.pot:%{fund.get('avg_pot',0):.1f}, top5:{fund.get('top3','')}). "
                f"XKTUM katılım GERÇEK FİYATLAR: {kat_fiyat_str}. "
                f"Smart money giriş: {smart_giris} hisse (ADET sayısı, fiyat değil). "
                "SADECE TÜRKÇE yaz. SADECE XKTUM listesindeki katılım uyumlu hisseleri öner.\n"
                "Verilen fiyatların DIŞINDA fiyat UYDURMA. Şunları ver:\n"
                "1) Günün 2 cümle XKTUM özeti\n"
                f"2) YARIN ({next_trading}): 3 XKTUM hissesi — sembol, GERÇEK alım seviyesi, hedef, stop, kısa gerekçe\n"
                "3) ALTIN & KUR: Yarın için altın/dolar beklentisi (1 cümle)\n"
                "4) HAFTALIK: 2 XKTUM hissesi için haftalık strateji\n"
                "5) AYLIK: 2 hisse için aylık yatırım tezi\n"
                "6) Katılım yatırımcısı için özel tavsiye: hisse + vade + GERÇEK giriş seviyesi\n"
                "7) 2 kritik risk senaryosu\n"
                "ÖNEMLİ: Yanıtını ASLA yarım bırakma, en fazla 3500 karakterde tamamla."
            )
            ai_text = self._ai_text(prompt, max_tokens=1200)

            msg = (
                self._header("🌙", "Gün Sonu Brifingi — 22:00",
                             datetime.now().strftime("%d %b %Y"))
                + "\n"
                + self._quotes_block(quotes)
                + "\n"
                + self._movers_block(gainers, losers, top_n=10)
                + fund_text
                + katilim_text
                + self._firsat_block(firsat)
                + self._action_signal_block(signal)
            )

            if kap:
                msg += "\n<b>📋 KAP Kurumsal Haberler</b>\n"
                msg += "\n".join(f"  • {_html.escape(str(k))}" for k in kap[:4]) + "\n"

            msg += (
                "\n<b>🤖 AI Günlük Değerlendirme & Yarına Bakış</b>\n"
                + ai_text
                + "\n\n<b>📰 Günün Haberleri</b>\n"
                + self._news_block(news[:5])
                + self._footer("İyi geceler — FinSentinel yarın 09:00'da burada")
            )
            self.send_message(msg)
            self._save_last_briefing("evening")
        except Exception as e:
            logger.error(f"Akşam özeti hatası: {e}")

    # ── Çok Dönemli Yatırım Planı ─────────────────────────────────────────────

    def send_investment_plan(self, symbol: str = "") -> str:
        """
        /plan [SEMBOL]  — Günlük'ten 5 yıllığa kadar kademeli yatırım planı.
        Sembol verilirse o hisse için, verilmezse en cazip AL önerileri için plan üretir.
        Sonucu Telegram'a gönderir ve string olarak döndürür.
        """
        try:
            quotes  = self._get_key_quotes()
            fund    = self._get_fundamental_summary()
            katilim = self._get_katilim_top(n=5)

            # Hedef hisse: verilen sembol veya top-3 AL önerisi
            if symbol:
                target_info = f"Analiz edilecek hisse: {symbol.upper()}."
                specific_signal = self._get_action_signal(symbol.upper())
                signal_str = ""
                if specific_signal:
                    signal_str = (
                        f" Mevcut fiyat: {specific_signal.get('fiyat',0):.2f}₺, "
                        f"İş Yatırım hedef: {specific_signal.get('hedef',0):.2f}₺, "
                        f"pot: %{specific_signal.get('pot',0):.1f}, "
                        f"öneri: {specific_signal.get('oneri','—')}."
                    )
                target_info += signal_str
            else:
                top_stocks = fund.get("top3", "GWIND, KOTON, THYAO, ULKER, SOKM")
                target_info = f"En cazip AL önerileri: {top_stocks}."

            data_warn = f"Temel veri {fund.get('data_date','?')} tarihli. " if fund.get("data_stale") else ""
            katilim_kodlar = [k["kod"] for k in katilim]

            prompt = (
                f"FinSentinel ÇOK DÖNEMLİ YATIRIM PLANI. {data_warn}"
                f"Güncel piyasa: BIST-100={quotes.get('BIST-100',{}).get('price','?')}, "
                f"USD/TRY={quotes.get('USD/TRY',{}).get('price','?')}, "
                f"Altın={quotes.get('Altın ONS',{}).get('price','?')}. "
                f"İş Yatırım AL sayısı: {fund.get('al_count',0)}, Ort.pot: %{fund.get('avg_pot',0):.1f}. "
                f"Katılım uyumlu öneriler: {katilim_kodlar}. "
                f"{target_info} "
                "SADECE TÜRKÇE yaz. Çok dönemli yatırım planı hazırla:\n\n"
                "📅 GÜNLÜK (bugün-yarın): Giriş/stop/hedef seviyeleri, hangi sinyale bakılacak\n"
                "📅 HAFTALIK (1 hafta): Haftalık strateji ve beklenen hareket\n"
                "📅 AYLIK (1 ay): Aylık pozisyon yönetimi ve hedefler\n"
                "📅 3 AYLIK: Orta vade tez — neden bu hisse, katalizörler neler\n"
                "📅 6 AYLIK: 6 aylık beklenti, sektör ve makro değerlendirme\n"
                "📅 1 YILLIK: 1 yıllık yatırım tezi, temel gerekçe, beklenen getiri %\n"
                "📅 3 YILLIK: Uzun vadeli büyüme tezi, şirketin 3 yıl sonraki konumu\n"
                "📅 5 YILLIK: 5 yıllık vizyon — sektör trendi, rekabet avantajı, değerleme\n\n"
                "Her dönem için: Sembol — Giriş bölgesi (₺) — Hedef (₺) — Beklenen getiri (%) — Ana gerekçe (1 cümle)\n"
                "Katılım yatırımcısı için özel not: Hangi dönemler için hangi katılım hisseleri önerilir?\n"
                "Risk uyarısı: Her dönemin en büyük riski nedir?"
            )
            ai_text = self._ai_text(prompt, max_tokens=900)

            header_sub = symbol.upper() if symbol else "En Cazip AL Önerileri"
            msg = (
                self._header("🗓️", f"Çok Dönemli Yatırım Planı — {header_sub}",
                             datetime.now().strftime("%d %b %Y %H:%M"))
                + "\n"
                + self._quotes_block(quotes)
                + "\n"
            )

            if fund:
                stale_note = f"\n<i>⚠️ Temel veri {fund.get('data_date','?')} tarihli</i>" if fund.get("data_stale") else ""
                msg += (
                    f"\n<b>📊 İş Yatırım Temel Analiz</b>{stale_note}\n"
                    f"  AL: {fund.get('al_count',0)}  |  Ort. Pot.: %{fund.get('avg_pot',0):.1f}\n"
                    f"  En cazip 5: <b>{fund.get('top3','—')}</b>\n"
                )

            if katilim:
                msg += (
                    "\n<b>☪️ Katılım Uyumlu Hisseler</b>\n"
                    + "\n".join(
                        f"  • <code>{k['kod']}</code>  {k['ad'][:18]}  "
                        f"Pot: <b>%{k['pot']:.1f}</b>  [{k['oneri']}]  F/K: {k.get('fk','—')}"
                        for k in katilim
                    )
                    + "\n"
                )

            msg += (
                f"\n<b>🤖 Yatırım Planı</b>\n"
                + ai_text
                + self._footer("Detaylı analiz için /analiz SEMBOL")
            )
            self.send_message(msg)
            return msg
        except Exception as e:
            logger.error(f"send_investment_plan hatası: {e}")
            return ""

    def send_longterm_view(self, symbol: str = "") -> str:
        """
        /uzunvade [SEMBOL]  — 1-5 yıllık derinlemesine uzun vade görüşü.
        """
        try:
            fund    = self._get_fundamental_summary()
            katilim = self._get_katilim_top(n=5)
            quotes  = self._get_key_quotes()

            if symbol:
                specific = self._get_action_signal(symbol.upper())
                target_info = (
                    f"Hisse: {symbol.upper()}. "
                    + (f"Fiyat: {specific.get('fiyat',0):.2f}₺, İY hedef: {specific.get('hedef',0):.2f}₺, "
                       f"öneri: {specific.get('oneri','—')}, pot: %{specific.get('pot',0):.1f}."
                       if specific else "")
                )
            else:
                top = fund.get("top3", "GWIND, KOTON, THYAO")
                target_info = f"Değerlendirilecek hisseler: {top}."

            prompt = (
                f"FinSentinel UZUN VADELİ YATIRIM ANALİZİ. "
                f"BIST-100={quotes.get('BIST-100',{}).get('price','?')}, "
                f"USD/TRY={quotes.get('USD/TRY',{}).get('price','?')}. "
                f"{target_info} "
                f"İş Yatırım önerileri (AL:{fund.get('al_count',0)}, top5:{fund.get('top3','')}). "
                f"Katılım uyumlu: {[k['kod'] for k in katilim]}. "
                "SADECE TÜRKÇE yaz. Şunları hazırla:\n\n"
                "1) MAKRO BAĞLAM: Türkiye ekonomisi 1-5 yıl perspektifi (enflasyon, faiz, büyüme etkisi)\n"
                "2) SEKTÖR ANALİZİ: Önümüzdeki 3-5 yılda hangi sektörler öne çıkar? Gerekçe ver.\n"
                "3) HİSSE ÖNERİLERİ — 1 YILLIK: 3 hisse, her biri için:\n"
                "   - Sembol — Şu an alım bölgesi — 1 yıl hedefi — Beklenen getiri % — Temel gerekçe\n"
                "4) HİSSE ÖNERİLERİ — 3 YILLIK: 2-3 hisse, büyüme tezi ve şirket konumu\n"
                "5) HİSSE ÖNERİLERİ — 5 YILLIK: 2 hisse, sektörel trend ve rekabet avantajı\n"
                "6) KATİLIM PORTFÖYÜ — UZUN VADE: Sadece katılım uyumlu hisselerden 1-3-5 yıllık portföy önerisi\n"
                "7) RİSK FAKTÖRÜ: Her vade için temel risk (kur, faiz, jeopolitik, sektörel)\n"
                "8) GİRİŞ STRATEJİSİ: Tek seferde mi, kademeli mi alınmalı? Hangi fiyat bölgelerinde?"
            )
            ai_text = self._ai_text(prompt, max_tokens=900)

            header_sub = symbol.upper() if symbol else "Genel Piyasa"
            msg = (
                self._header("🔭", f"Uzun Vadeli Yatırım Görüşü — {header_sub}",
                             datetime.now().strftime("%d %b %Y"))
                + "\n"
                + self._quotes_block(quotes)
                + "\n"
                + f"\n<b>🤖 1-5 Yıllık Analiz</b>\n"
                + ai_text
                + self._footer("Günlük plan için /plan | Anlık analiz için /analiz SEMBOL")
            )
            self.send_message(msg)
            return msg
        except Exception as e:
            logger.error(f"send_longterm_view hatası: {e}")
            return ""

    def send_weekend_briefing(self, period: str = "morning"):
        """
        Hafta sonu / tatil günü brifingleri.
        period: morning (10:00) | noon (15:00) | evening (22:00)
        """
        logger.info(f"Hafta sonu/tatil brifing ({period}) gönderiliyor...")
        try:
            period_meta = {
                "morning": ("☀️", "Hafta Sonu Sabah — 10:00", "Geçen Haftanın Özeti & Yeni Haftaya Hazırlık"),
                "noon":    ("🌤️", "Hafta Sonu Öğle — 15:00",  "Genel Piyasalar & Analiz"),
                "evening": ("🌙", "Hafta Sonu Akşam — 22:00",  "Hafta Sonu Özeti & Yeni Hafta Stratejisi"),
            }
            icon, title, subtitle = period_meta.get(period, period_meta["morning"])

            weekly_gainers, weekly_losers = self._get_weekly_movers(top_n=10)
            quotes   = self._get_key_quotes()
            world    = self._get_world_indices()
            news     = self._get_news_with_links(limit=5)
            kap      = self._get_kap_corporate_news(limit=5)
            fund     = self._get_fundamental_summary()
            katilim  = self._get_katilim_top(n=5)

            fund_text = ""
            if fund:
                fund_text = (
                    "\n<b>📊 İş Yatırım — Haftalık Temel Özet</b>\n"
                    f"  AL: {fund.get('al_count',0)}  |  TUT: {fund.get('tut_count',0)}  "
                    f"|  SAT: {fund.get('sat_count',0)}\n"
                    f"  Ort. Getiri Pot.: %{fund.get('avg_pot',0):.1f}\n"
                    f"  Top 5 Fırsat: <b>{fund.get('top3','—')}</b>\n"
                )

            katilim_text = ""
            if katilim:
                katilim_text = (
                    "\n<b>☪️ Katılım Hisseleri — Hafta Sonu Değerlendirmesi</b>\n"
                    + "\n".join(f"  • <code>{k['kod']}</code> {k['ad'][:20]}  "
                                f"Pot: <b>%{k['pot']:.1f}</b>  [{k['oneri']}]  "
                                f"F/K: {k.get('fk','—')}  Değerleme: {k.get('deger','—')}"
                                for k in katilim)
                    + "\n"
                )

            data_warn = f"Temel veri {fund.get('data_date','?')} tarihli. " if fund.get("data_stale") else ""
            prompt = (
                f"Türkiye borsası hafta sonu brifingi ({period}). {data_warn}"
                f"Piyasa: {quotes}. Dünya: {world}. "
                f"Haftanın yükselenleri: {weekly_gainers[:5]}. Düşenleri: {weekly_losers[:5]}. "
                f"KAP: {kap[:3] if kap else 'yok'}. "
                f"İş Yatırım (AL:{fund.get('al_count',0)}, top5:{fund.get('top3','')}). "
                f"Katılım: {[k['kod'] for k in katilim]}. "
                "SADECE TÜRKÇE yaz. Şunları ver:\n"
                "1) Geçen haftanın özeti (2 cümle)\n"
                "2) GELECEK HAFTA planı: 3 izlenecek hisse — sembol + neden + alım seviyesi + hedef\n"
                "3) AYLIK (1 ay): 2 hisse için aylık yatırım planı — giriş/hedef/stop\n"
                "4) 3 AYLIK: Hangi sektör/hisse öne çıkabilir, katalizörler neler\n"
                "5) 6 AYLIK: Makro beklenti ve 2 öne çıkan hisse tezi\n"
                "6) 1 YILLIK: BIST için yıllık beklenti ve 2-3 uzun vadeli hisse önerisi\n"
                "7) 3-5 YILLIK vizyon: Türkiye ekonomisi ve hangi hisseler yapısal büyüme sunar\n"
                "8) Katılım portföyü: Haftalık/aylık/uzun vade için 3 somut katılım hissesi\n"
                "9) Sektör rotasyonu: Hangi sektörden çık, hangi sektöre gir ve neden"
            )
            ai_text = self._ai_text(prompt, max_tokens=700)

            msg = (
                self._header(icon, title, subtitle)
                + "\n"
                + self._quotes_block(quotes)
                + "\n\n<b>🌍 Dünya Piyasaları</b>\n"
                + "\n".join(f"  {w}" for w in world)
                + "\n"
                + self._weekly_movers_block(weekly_gainers, weekly_losers)
                + fund_text
                + katilim_text
            )

            if kap:
                msg += "\n<b>📋 KAP Kurumsal Haberler</b>\n"
                msg += "\n".join(f"  • {_html.escape(str(k))}" for k in kap[:4]) + "\n"

            msg += (
                "\n<b>🤖 AI Haftalık Analiz & Stratejiler</b>\n"
                + ai_text
                + "\n\n<b>📰 Öne Çıkan Haberler</b>\n"
                + self._news_block(news[:5])
                + self._footer("Piyasalar Pazartesi 10:00'da açılıyor")
            )
            self.send_message(msg)
            self._save_last_briefing(f"weekend_{period}")
        except Exception as e:
            logger.error(f"Hafta sonu brifing hatası: {e}")

    def send_catchup_briefing(self):
        """
        Program geç açıldığında çağrılır.
        Son brifingden bu yana geçen süreye ve güncel saate göre
        uygun özet brifingi gönderir.
        """
        now       = datetime.now()
        last_info = self._load_last_briefing()
        last_time = last_info.get("time")
        last_type = last_info.get("type", "")

        if last_time:
            try:
                last_dt  = datetime.fromisoformat(last_time)
                gap_mins = (now - last_dt).total_seconds() / 60
                if gap_mins < 90:     # 90 dakikadan az geçmişse gönderme
                    logger.info(f"Catchup gerekmedi — son brifing {gap_mins:.0f} dk önce.")
                    return
            except Exception:
                pass

        logger.info(f"Catchup brifingi gönderiliyor — saat {now.hour}:{now.minute:02d}...")
        is_trading = self._is_trading_day()
        h = now.hour

        try:
            quotes  = self._get_key_quotes()
            gainers, losers = self._get_bist_movers(top_n=10)
            news    = self._get_news_with_links(limit=5)
            kap     = self._get_kap_corporate_news(limit=3)
            fund    = self._get_fundamental_summary()
            katilim = self._get_katilim_top(n=5)

            if is_trading:
                if h < 10:
                    period_label = "Sabah (Borsa Henüz Açılmadı)"
                elif 10 <= h < 13:
                    period_label = "Sabah Seansı"
                elif 13 <= h < 14:
                    period_label = "Öğlen Arası"
                elif 14 <= h < 18:
                    period_label = "Öğleden Sonra Seansı"
                elif 18 <= h < 22:
                    period_label = "Borsa Kapandı — Akşam"
                else:
                    period_label = "Gece Özeti"
            else:
                period_label = "Hafta Sonu / Tatil Genel Piyasalar"

            fund_text = ""
            if fund:
                fund_text = (
                    "\n<b>📊 İş Yatırım Temel Özet</b>\n"
                    f"  AL: {fund.get('al_count',0)}  |  Ort. Pot.: %{fund.get('avg_pot',0):.1f}\n"
                    f"  Top fırsatlar: <b>{fund.get('top3','—')}</b>\n"
                )

            katilim_text = ""
            if katilim:
                katilim_text = (
                    "\n<b>☪️ Katılım Öne Çıkanlar</b>\n"
                    + "\n".join(f"  • <code>{k['kod']}</code>  Pot: %{k['pot']:.1f}  [{k['oneri']}]"
                                for k in katilim[:5])
                    + "\n"
                )

            data_warn = f"Temel veri {fund.get('data_date','?')} tarihli. " if fund.get("data_stale") else ""
            prompt = (
                f"FinSentinel açıldı. Saat: {now.strftime('%H:%M')}. Dönem: {period_label}. "
                f"{'Borsa işlem günü.' if is_trading else 'Borsa bugün kapalı.'} {data_warn}"
                f"Piyasa: {quotes}. Yükselen: {gainers[:5]}. Düşen: {losers[:5]}. "
                f"İş Yatırım (AL:{fund.get('al_count',0)}, top5:{fund.get('top3','')}). "
                f"Katılım: {[k['kod'] for k in katilim]}. "
                "SADECE TÜRKÇE yaz. Şunları ver:\n"
                "1) Kaçırılan brifinglerin özeti (1-2 cümle)\n"
                "2) ŞU AN için 2-3 somut aksiyon önerisi: sembol + AL/SAT/TUT + gerekçe\n"
                "3) GÜNLÜK plan: Bugün gün bitmeden ne yapılmalı?\n"
                "4) HAFTALIK plan: Bu hafta hangi hisseler izlenmeli (2-3 sembol + strateji)\n"
                "5) Katılım yatırımcısı için özel not\n"
                "smart_giris verisi hisse adedidir, fiyat değildir."
            )
            ai_text = self._ai_text(prompt, max_tokens=600)

            msg = (
                self._header("🔄", f"Program Açıldı — Catchup Brifingi",
                             f"{now.strftime('%d %b %Y %H:%M')} | {period_label}")
                + "\n"
                + self._quotes_block(quotes)
                + "\n"
                + self._movers_block(gainers, losers, top_n=10)
                + fund_text
                + katilim_text
            )

            if kap:
                msg += "\n<b>📋 KAP Haberleri</b>\n"
                msg += "\n".join(f"  • {_html.escape(str(k))}" for k in kap[:3]) + "\n"

            msg += (
                "\n<b>🤖 Durum Özeti & Tavsiyeler</b>\n"
                + ai_text
                + "\n\n<b>📰 Güncel Haberler</b>\n"
                + self._news_block(news[:5])
                + self._footer("FinSentinel aktif — brifinglar devam ediyor")
            )
            self.send_message(msg)
            self._save_last_briefing("catchup")
        except Exception as e:
            logger.error(f"Catchup brifing hatası: {e}")

    # ── Anlık Alarm Mesajları ─────────────────────────────────────────────────

    def send_market_alert(self, title: str, body: str, severity: str = "info"):
        icons = {"info": "ℹ️", "success": "✅", "warning": "⚠️", "danger": "🚨"}
        icon  = icons.get(severity, "🔔")
        ai_hint = ""
        try:
            ai_hint = self._ai_text(
                f"Yatırımcıya şu alarm hakkında 2 cümle tavsiye ver: {title} — {body}",
                max_tokens=120,
            )
        except Exception:
            pass
        msg = (
            f"{icon} <b>{_html.escape(title)}</b>\n\n"
            f"{_html.escape(body)}"
            + (f"\n\n<b>🤖 AI Tavsiyesi:</b> {ai_hint}" if ai_hint else "")
            + "\n" + self._footer("FinSentinel")
        )
        self.send_message(msg)

    def send_portfolio_alert(self, symbol: str, risk_level: str, detail: str):
        severity_map = {"kritik": "danger", "yüksek": "warning", "orta": "info"}
        severity = severity_map.get(risk_level.lower(), "info")
        ai_hint = ""
        try:
            ai_hint = self._ai_text(
                f"{symbol} hissesinde {risk_level} risk. Detay: {detail}. "
                "Stop-loss veya pozisyon yönetimi konusunda 2 cümle tavsiye ver.",
                max_tokens=130,
            )
        except Exception:
            pass
        title = f"Portföy Uyarısı: {symbol} [{risk_level.upper()}]"
        body  = detail + (f"\n\n<b>🤖 AI Tavsiyesi:</b> {ai_hint}" if ai_hint else "")
        self.send_market_alert(title, body, severity)

    def send_ai_summary(self, topic: str, content: str):
        msg = (
            f"🤖 <b>AI Analiz: {_html.escape(topic)}</b>\n\n"
            f"{content}\n\n"
            f"<i>Detaylar için FinSentinel Dashboard'u ziyaret edin.</i>"
        )
        self.send_message(msg)

    # ── Veri Yardımcıları ─────────────────────────────────────────────────────

    def _get_key_quotes(self) -> dict:
        """Her sembolü ayrı ayrı çek — toplu çekimde yanlış kolon eşleşmesini önler.

        yfinance tek sembol için bile bazen DataFrame/MultiIndex döndürebiliyor.
        Bu nedenle kolon Series, DataFrame veya skaler olabilir — hepsi ele alınır.
        Ek olarak fast_info fallback'i kullanılır.
        """
        import yfinance as yf
        import pandas as pd
        labels = {
            "XU100.IS": "BIST-100",
            "USDTRY=X": "USD/TRY",
            "EURTRY=X": "EUR/TRY",
            "GC=F":     "Altın ONS",
            "BTC-USD":  "BTC",
        }
        # Geniş aralıklar — veri kalitesi filtresi, kur hareketlerine toleranslı
        # 2026 gerçek seviyelere göre güncellendi
        _valid_ranges = {
            "XU100.IS": (1,        500_000),   # endeks normalize edilmiş olabilir
            "USDTRY=X": (1,        2_000),     # TRY/USD her seviyeye toleranslı
            "EURTRY=X": (1,        3_000),
            "GC=F":     (100,      30_000),    # altın geniş aralık
            "BTC-USD":  (100,      2_000_000), # BTC 100k+ seviyelerinde
        }
        _pct_limits = {
            "XU100.IS": 10.0, "USDTRY=X": 12.0, "EURTRY=X": 12.0,
            "GC=F": 12.0, "BTC-USD": 20.0,
        }

        def _fast_info_fallback(symbol: str):
            """fast_info üzerinden (last_price, previous_close) döner — olmazsa (None, None)."""
            try:
                fi = yf.Ticker(symbol).fast_info
                last = fi.get("last_price") if hasattr(fi, "get") else getattr(fi, "last_price", None)
                prev = fi.get("previous_close") if hasattr(fi, "get") else getattr(fi, "previous_close", None)
                return (float(last) if last else None, float(prev) if prev else None)
            except Exception:
                return (None, None)

        result = {}
        for sym, lbl in labels.items():
            try:
                close = None
                prev = None

                # 1) yf.download — ana yol
                try:
                    raw = yf.download(
                        sym, period="5d", interval="1d",
                        auto_adjust=True, progress=False, multi_level_index=False,
                    )
                except Exception as dl_err:
                    logger.exception(f"_get_key_quotes {sym} yf.download hatası: {dl_err}")
                    raw = None

                if raw is not None and not getattr(raw, "empty", True) and "Close" in getattr(raw, "columns", []):
                    close_col = raw["Close"]
                    # DataFrame ise ilk kolonu Series olarak al (MultiIndex artığı)
                    if isinstance(close_col, pd.DataFrame):
                        if close_col.shape[1] >= 1:
                            close_col = close_col.iloc[:, 0]
                    # Hâlâ DataFrame/2B ise squeeze ile sıkıştır
                    if hasattr(close_col, "squeeze"):
                        close_col = close_col.squeeze()

                    # Squeeze sonrası skaler dönebiliyor (tek değerli seri)
                    if isinstance(close_col, (int, float)):
                        close = float(close_col)
                        prev = close
                    elif isinstance(close_col, pd.Series):
                        closes = close_col.dropna()
                        if len(closes) >= 1:
                            close = float(closes.iloc[-1])
                            prev = float(closes.iloc[-2]) if len(closes) >= 2 else None

                # 2) fast_info fallback — close yoksa veya prev eksikse
                if close is None or prev is None:
                    fi_last, fi_prev = _fast_info_fallback(sym)
                    if close is None and fi_last is not None:
                        close = fi_last
                    if prev is None and fi_prev is not None:
                        prev = fi_prev
                    # Hâlâ prev yoksa close'u prev olarak kullan (sıfır değişim)
                    if prev is None and close is not None:
                        prev = close

                if close is None:
                    logger.warning(f"_get_key_quotes: {sym} için fiyat alınamadı (tüm yollar başarısız)")
                    continue

                lo, hi = _valid_ranges.get(sym, (0, float("inf")))
                if not (lo <= close <= hi):
                    logger.warning(f"_get_key_quotes: {sym} fiyatı ({close:.2f}) aralık dışı — atlandı")
                    continue

                pct = round((close - prev) / prev * 100, 2) if prev else 0
                if abs(pct) > _pct_limits.get(sym, 10.0):
                    logger.warning(
                        f"_get_key_quotes: {sym} için aşırı değişim %{pct:.2f} — "
                        f"veri şüpheli, atlandı (close={close:.2f}, prev={prev:.2f})"
                    )
                    continue
                result[lbl] = {"price": round(close, 4), "pct": pct}
            except Exception as e:
                logger.exception(f"_get_key_quotes {sym} hatası: {e}")
        return result

    @staticmethod
    def _extract_close(raw) -> "pd.DataFrame":
        """
        yfinance toplu indirmede multi-level veya flat kolon yapısından
        Close verilerini güvenli şekilde çıkarır.
        yfinance >=1.2 multi_level_index=False parametresini yok sayabiliyor.
        """
        import pandas as pd
        if raw is None or raw.empty:
            return pd.DataFrame()
        cols = raw.columns
        # Multi-level tuple colonlar: ('Close', 'THYAO.IS'), ('Close', 'GARAN.IS') ...
        if isinstance(cols[0], tuple):
            close_cols = [c for c in cols if c[0] == "Close"]
            if close_cols:
                close_df = raw[close_cols].copy()
                close_df.columns = [c[1] for c in close_cols]  # sadece sembol adı
                return close_df.dropna(how="all")
        # Flat colonlar: "Close" tek kolon (tek sembol) veya "Close" DataFrame
        if "Close" in cols:
            close_data = raw["Close"]
            if isinstance(close_data, pd.Series):
                return close_data.to_frame()
            return close_data.dropna(how="all")
        return pd.DataFrame()

    def _get_bist_movers(self, top_n: int = 10) -> tuple[list, list]:
        # 1. live_feed dene
        try:
            from core.live_feed import get_live_manager
            mgr  = get_live_manager()
            data = mgr.get_bist_data()
            if data:
                sorted_data = sorted(data.items(), key=lambda x: x[1].get("change_pct", 0) or 0, reverse=True)
                gainers = [(s, d.get("change_pct", 0)) for s, d in sorted_data[:top_n]]
                losers  = [(s, d.get("change_pct", 0)) for s, d in sorted_data[-top_n:]]
                if gainers or losers:
                    return gainers, losers
        except Exception as e:
            logger.debug(f"_get_bist_movers live_feed hatası: {e}")

        # 2. yfinance fallback — BIST_SYMBOLS listesinden günlük değişim hesapla
        try:
            import yfinance as yf
            from config.settings import BIST_SYMBOLS
            syms = (BIST_SYMBOLS or [])[:80]
            if not syms:
                return [], []
            raw = yf.download(syms, period="5d", auto_adjust=True, progress=False)
            close = self._extract_close(raw)
            if close.empty or len(close) < 2:
                return [], []
            pct = ((close.iloc[-1] - close.iloc[-2]) / close.iloc[-2] * 100).dropna()
            pct_sorted = pct.sort_values(ascending=False)
            gainers = [(s.replace(".IS",""), round(float(v), 2)) for s, v in pct_sorted.head(top_n).items()]
            losers  = [(s.replace(".IS",""), round(float(v), 2)) for s, v in pct_sorted.tail(top_n).items()]
            losers.reverse()  # en çok düşen başa gelsin
            return gainers, losers
        except Exception as e:
            logger.debug(f"_get_bist_movers yfinance fallback hatası: {e}")
            return [], []

    def _get_world_indices(self) -> list[str]:
        try:
            from core.fetcher import PriceFetcher
            symbols = ["^GSPC", "^GDAXI", "^N225", "^FTSE"]
            labels  = {"^GSPC":"S&P 500","^GDAXI":"DAX","^N225":"Nikkei","^FTSE":"FTSE 100"}
            raw     = PriceFetcher.get_bulk_quotes(symbols)
            rows    = []
            for sym, lbl in labels.items():
                q = raw.get(sym, {})
                if q and "price" in q:
                    pct   = q.get("change_pct", 0) or 0
                    arrow = "▲" if pct >= 0 else "▼"
                    rows.append(f"{arrow} {lbl}: {q['price']:,.0f}  ({pct:+.2f}%)")
            return rows
        except Exception as e:
            logger.debug(f"_get_world_indices hatası: {e}")
            return []

    def _get_weekly_movers(self, top_n: int = 10) -> tuple[list, list]:
        try:
            import yfinance as yf
            from config.settings import BIST_SYMBOLS
            syms = (BIST_SYMBOLS or [])[:60]
            if not syms:
                return [], []
            data = yf.download(syms, period="5d", auto_adjust=True, progress=False)
            close = self._extract_close(data)
            if close.empty or len(close) < 2:
                return [], []
            wr = ((close.iloc[-1] - close.iloc[0]) / close.iloc[0] * 100).dropna().sort_values(ascending=False)
            gainers = [(s.replace(".IS",""), round(v,2)) for s,v in wr.head(top_n).items()]
            losers  = [(s.replace(".IS",""), round(v,2)) for s,v in wr.tail(top_n).items()]
            return gainers, losers
        except Exception as e:
            logger.debug(f"_get_weekly_movers hatası: {e}")
            return [], []

    def _get_kap_corporate_news(self, limit: int = 5) -> list[str]:
        try:
            from core.kap_fetcher import get_kap_disclosures
            discs = get_kap_disclosures(limit=30)
            keywords = ["temettü","bölünme","birleşme","satın alma","anlaşma",
                        "sözleşme","iştirak","halka arz","sermaye","ihale"]
            results = []
            for d in discs:
                t = d.get("title","").lower()
                if any(kw in t for kw in keywords):
                    co  = d.get("company","")
                    ttl = d.get("title","")[:80]
                    results.append(f"{co}: {ttl}" if co else ttl)
            return results[:limit]
        except Exception as e:
            logger.debug(f"_get_kap_corporate_news hatası: {e}")
            return []

    def _get_news_with_links(self, limit: int = 5) -> list[dict]:
        """
        Haber başlığı + URL döndürür.
        İş Yatırım Araştırma haberleri öncelikli olarak listenin başına alınır.
        """
        try:
            from core.fetcher import NewsFetcher
            result = []

            # 1. İş Yatırım Araştırma — öncelikli (ilk 3 slot)
            iy_items = NewsFetcher.get_isyatirim_research(limit=3)
            for n in iy_items:
                result.append({
                    "title":  f"[İY Araştırma] {n.get('title','')}",
                    "url":    n.get("url",""),
                    "source": "İş Yatırım Araştırma",
                })

            # Türkçe kaynak alan adları — bu domainler öncelikli, İngilizce domainler etiketlenir
            _TURKISH_DOMAINS = {
                "isyatirim.com.tr", "bloomberght.com", "paraanaliz.com",
                "tr.investing.com", "doviz.com", "bigpara.com",
                "haberturk.com", "sabah.com.tr", "hurriyet.com.tr",
                "milliyet.com.tr", "ekonomim.com", "borsagundem.com",
                "borsa.ansiklopedi.org", "kap.org.tr",
            }

            def _is_english_source(url: str) -> bool:
                """URL'den domain al, Türkçe listesinde yoksa İngilizce kaynak say."""
                try:
                    from urllib.parse import urlparse
                    domain = urlparse(url).netloc.lower().lstrip("www.")
                    return not any(td in domain for td in _TURKISH_DOMAINS)
                except Exception:
                    return False

            # 2. Genel haberler — kalan slotları doldur
            remaining = limit - len(result)
            if remaining > 0:
                general = NewsFetcher.get_latest(limit=remaining + 10)
                turkish_news = []
                for n in general:
                    if isinstance(n, dict):
                        url = n.get("url", "")
                        if "isyatirim.com.tr" in url:
                            continue  # zaten eklendi
                        title = n.get("title", "")
                        
                        # Eğer İngilizce (yabancı) kaynak ise tamamen yoksay
                        if _is_english_source(url):
                            continue
                            
                        # Türkiye dışı hisseler/şirketler ile ilgili investing.com haberlerini filtrele
                        if "investing.com" in url.lower() and any(k in title.lower() for k in ["hissesi", "wall street", "nasdaq", "dow", "s&p"]):
                            continue

                        turkish_news.append({"title": title, "url": url})
                    else:
                        turkish_news.append({"title": str(n), "url": ""})

                # Sadece Türkçe kaynakları ekle
                for item in turkish_news:
                    if len(result) >= limit:
                        break
                    result.append(item)

            return result[:limit]
        except Exception as e:
            logger.debug(f"_get_news_with_links hatası: {e}")
            return []

    def _get_fundamental_summary(self) -> dict:
        """
        data/isyatirim/YYYY_MM_DD/ klasöründen en güncel İş Yatırım verilerini
        okuyup özet dict döndürür.
        """
        try:
            import pandas as pd

            data_dir = self._latest_data_dir()
            if not data_dir:
                return {}

            def _read_xlsx(name: str):
                for ext in (".xlsx", ".xls"):
                    p = data_dir / (name + ext)
                    if p.exists():
                        try:
                            df = pd.read_excel(p, sheet_name=0)
                            df.columns = df.columns.str.strip()
                            return df.dropna(how="all").reset_index(drop=True)
                        except Exception:
                            pass
                return None

            def _num(s):
                import re
                return pd.to_numeric(
                    s.astype(str).str.replace(",",".",regex=False)
                              .str.replace(" ","",regex=False)
                              .str.replace("%","",regex=False),
                    errors="coerce"
                )

            df_takip = _read_xlsx("takipozet")
            df_fin   = _read_xlsx("temelfinansal")

            if df_takip is None:
                return {}

            result = {}

            # Veri tarihi — klasör adından al (YYYY_MM_DD)
            dir_name = data_dir.name
            if len(dir_name) == 10 and dir_name[4] == "_":
                result["data_date"] = dir_name.replace("_", "-")
                today_str = datetime.now().strftime("%Y-%m-%d")
                result["data_stale"] = result["data_date"] != today_str
            else:
                result["data_date"] = "?"
                result["data_stale"] = True

            # Öneri dağılımı
            if "Öneri" in df_takip.columns:
                oneri_s = df_takip["Öneri"].astype(str).str.upper()
                result["al_count"]  = int(oneri_s.str.contains("AL",na=False).sum())
                result["tut_count"] = int(oneri_s.str.contains("TUT",na=False).sum())
                result["sat_count"] = int(oneri_s.str.contains("SAT",na=False).sum())

            # Getiri potansiyeli
            if "Getiri Potansiyeli (%)" in df_takip.columns:
                pot_s = _num(df_takip["Getiri Potansiyeli (%)"])
                result["avg_pot"] = round(float(pot_s.mean()), 1) if pot_s.notna().any() else 0

                # Top 5 AL hisse (potansiyele göre)
                df_al = df_takip[df_takip["Öneri"].astype(str).str.upper().str.contains("AL",na=False)].copy()
                df_al["_pot"] = pot_s
                top5  = df_al.nlargest(5, "_pot")
                if "Kod" in top5.columns:
                    result["top3"] = ", ".join(top5["Kod"].astype(str).tolist())

            # Smart money (temelyabancioran'dan)
            df_yab = _read_xlsx("temelyabancioran")
            if df_yab is not None:
                degisim_col = next((c for c in df_yab.columns if "Değişim" in c and "Baz" in c), None)
                if degisim_col:
                    smart = _num(df_yab[degisim_col])
                    result["smart_giris"] = int((smart > 0).sum())
                    result["smart_cikis"] = int((smart < 0).sum())

            return result

        except Exception as e:
            logger.debug(f"_get_fundamental_summary hatası: {e}")
            return {}

    def _get_katilim_top(self, n: int = 5) -> list[dict]:
        """
        Resmi XKTUM listesinden (228 hisse) en iyi n katılım hissesini döndürür.
        Önce İş Yatırım Excel verisini dener (≤3 gün eski), yoksa dinamik yfinance skoru kullanır.
        """
        try:
            import pandas as pd

            # ── 1. Excel tabanlı veri (İş Yatırım) ──────────────────────────
            data_dir = self._latest_data_dir()
            data_stale = True
            if data_dir:
                try:
                    dir_date = datetime.strptime(data_dir.name[:10], "%Y_%m_%d").date()
                    data_stale = (datetime.now().date() - dir_date).days > 3
                except Exception:
                    pass

            if data_dir and not data_stale:
                result = self._get_katilim_top_excel(data_dir, n)
                if result:
                    return result

            # ── 2. Dinamik yfinance skoru (fallback) ─────────────────────────
            return self._get_katilim_top_dynamic(n)

        except Exception as e:
            logger.debug(f"_get_katilim_top hatası: {e}")
            return []

    def _get_katilim_top_excel(self, data_dir: Path, n: int) -> list[dict]:
        """İş Yatırım Excel'den XKTUM filtreli top-n katılım hissesi."""
        try:
            import pandas as pd

            def _read_xlsx(name: str):
                for ext in (".xlsx", ".xls"):
                    p = data_dir / (name + ext)
                    if p.exists():
                        try:
                            df = pd.read_excel(p, sheet_name=0)
                            df.columns = df.columns.str.strip()
                            return df.dropna(how="all").reset_index(drop=True)
                        except Exception:
                            pass
                return None

            def _num(s):
                return pd.to_numeric(
                    s.astype(str).str.replace(",",".",regex=False)
                              .str.replace(" ","",regex=False)
                              .str.replace("%","",regex=False),
                    errors="coerce"
                )

            df_takip = _read_xlsx("takipozet")
            df_fin   = _read_xlsx("temelfinansal")
            df_ozet  = _read_xlsx("temelozet")

            if df_takip is None or "Kod" not in df_takip.columns:
                return []

            df = df_takip.copy()
            df["Kod"] = df["Kod"].astype(str).str.strip().str.upper()

            # Sektör & ad bilgisi ekle
            if df_ozet is not None and "Kod" in df_ozet.columns:
                sek_col = next((c for c in df_ozet.columns
                                if c.lower().replace("ö","o").replace("ü","u") in ("sektor","sektör","sector")), None)
                if sek_col:
                    cols = ["Kod", sek_col] + (["Hisse Adı"] if "Hisse Adı" in df_ozet.columns else [])
                    ds = df_ozet[cols].copy()
                    ds["Kod"] = ds["Kod"].astype(str).str.strip().str.upper()
                    df = df.merge(ds, on="Kod", how="left")

            # F/K ekle
            if df_fin is not None and "Kod" in df_fin.columns and "F/K" in df_fin.columns:
                df_fin2 = df_fin[["Kod","F/K"]].copy()
                df_fin2["Kod"] = df_fin2["Kod"].astype(str).str.strip().str.upper()
                df = df.merge(df_fin2, on="Kod", how="left")

            # XKTUM inclusion filtresi (228 resmi sembol)
            if _XKTUM_SET:
                df = df[df["Kod"].isin(_XKTUM_SET)].copy()

            ad_col = next((c for c in df.columns if "Hisse Adı" in c), None)

            if "Getiri Potansiyeli (%)" not in df.columns:
                return []

            df["_pot"] = _num(df["Getiri Potansiyeli (%)"])

            al_mask = (
                df["Öneri"].astype(str).str.upper().str.contains("AL", na=False)
                & (df["_pot"] > 0)
            )
            df_k = df[al_mask].nlargest(n, "_pot")

            # Anlık fiyatları yfinance'ten çek
            kodlar = [str(r["Kod"]) for _, r in df_k.iterrows()]
            live_prices = self._fetch_live_prices(kodlar)

            result = []
            for _, r in df_k.iterrows():
                kod = str(r["Kod"])
                fiyat = live_prices.get(kod, 0)
                pot_v = round(float(r["_pot"]), 1)
                hedef = round(fiyat * (1 + pot_v / 100), 2) if fiyat > 0 else 0
                stop  = round(fiyat * 0.93, 2) if fiyat > 0 else 0
                result.append({
                    "kod":   kod,
                    "ad":    str(r.get(ad_col, kod)) if ad_col else kod,
                    "oneri": str(r.get("Öneri", "AL")),
                    "pot":   pot_v,
                    "fk":    str(r["F/K"]) if "F/K" in r.index else "—",
                    "deger": "—",
                    "fiyat": fiyat,
                    "hedef": hedef,
                    "stop":  stop,
                    "kaynak": "İş Yatırım",
                })
            return result
        except Exception as e:
            logger.debug(f"_get_katilim_top_excel hatası: {e}")
            return []

    def _get_katilim_top_dynamic(self, n: int) -> list[dict]:
        """Dinamik: XKTUM sembollerini yfinance'ten çekerek RSI+momentum skoru hesaplar."""
        try:
            import yfinance as yf
            import pandas as pd

            semboller = list(_XKTUM_SET) if _XKTUM_SET else []
            if not semboller:
                return []

            syms = [s + ".IS" for s in semboller]
            raw = yf.download(syms, period="60d", interval="1d",
                              auto_adjust=True, progress=False)
            if raw is None or raw.empty:
                return []

            close = raw["Close"] if "Close" in raw.columns else None
            volume = raw["Volume"] if "Volume" in raw.columns else None
            if close is None or close.empty:
                return []

            scores = []
            for sym in syms:
                if sym not in close.columns:
                    continue
                s = close[sym].dropna()
                if len(s) < 20:
                    continue
                kod = sym.replace(".IS", "")
                fiyat = float(s.iloc[-1])
                # RSI(14)
                delta = s.diff()
                gain = delta.clip(lower=0).rolling(14).mean()
                loss = (-delta.clip(upper=0)).rolling(14).mean()
                rs = gain / loss.replace(0, float("nan"))
                rsi = float((100 - 100 / (1 + rs)).iloc[-1])
                # Momentum: 20 günlük getiri %
                mom = float((s.iloc[-1] / s.iloc[-20] - 1) * 100) if len(s) >= 20 else 0
                # Hacim artışı
                if volume is not None and sym in volume.columns:
                    v = volume[sym].dropna()
                    vol_ratio = float(v.iloc[-1] / v.rolling(20).mean().iloc[-1]) if len(v) >= 20 else 1
                else:
                    vol_ratio = 1
                # Skor: momentum + hacim etkisi (RSI 30-60 arası bonus)
                rsi_bonus = max(0, (60 - rsi) * 0.3) if rsi < 60 else 0
                skor = mom + vol_ratio * 2 + rsi_bonus
                scores.append({"kod": kod, "fiyat": fiyat, "rsi": rsi, "mom": mom, "skor": skor})

            scores.sort(key=lambda x: x["skor"], reverse=True)
            top = scores[:n]

            result = []
            for item in top:
                fiyat = item["fiyat"]
                pot = max(item["mom"], 5.0)
                result.append({
                    "kod":    item["kod"],
                    "ad":     item["kod"],
                    "oneri":  "AL" if item["rsi"] < 65 else "TUT",
                    "pot":    round(pot, 1),
                    "fk":     "—",
                    "deger":  "—",
                    "fiyat":  round(fiyat, 2),
                    "hedef":  round(fiyat * (1 + pot / 100), 2),
                    "stop":   round(fiyat * 0.93, 2),
                    "kaynak": "teknik",
                })
            return result
        except Exception as e:
            logger.debug(f"_get_katilim_top_dynamic hatası: {e}")
            return []

    def _fetch_live_prices(self, kodlar: list[str]) -> dict[str, float]:
        """Verilen BIST sembol listesi için anlık fiyatları yfinance'ten çeker."""
        live: dict[str, float] = {}
        try:
            import yfinance as yf
            syms = [k + ".IS" for k in kodlar]
            raw = yf.download(syms, period="2d", auto_adjust=True,
                              progress=False, multi_level_index=False)
            if not raw.empty and "Close" in raw.columns:
                last_row = raw["Close"].dropna().iloc[-1]
                for sym in syms:
                    if sym in last_row.index:
                        v = float(last_row[sym])
                        if v > 0:
                            live[sym.replace(".IS", "")] = round(v, 2)
        except Exception:
            pass
        return live

    def _latest_data_dir(self) -> Path | None:
        if not _DATA_ROOT.exists():
            return None
        dated = sorted(
            [d for d in _DATA_ROOT.iterdir() if d.is_dir() and len(d.name) == 10 and d.name[4] == "_"],
            reverse=True,
        )
        if dated:
            return dated[0]
        if any(_DATA_ROOT.glob("*.xlsx")):
            return _DATA_ROOT
        return None

    def _is_trading_day(self) -> bool:
        """Bugün borsa işlem günü mü? (hafta sonu + resmi tatil kontrolü)"""
        today = datetime.now()
        if today.weekday() >= 5:    # Cumartesi=5, Pazar=6
            return False
        if today.strftime("%Y-%m-%d") in _RESMI_TATILLER:
            return False
        return True

    def _save_last_briefing(self, brifing_type: str):
        try:
            _LAST_BRIFING_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(_LAST_BRIFING_FILE, "w", encoding="utf-8") as f:
                json.dump({"type": brifing_type, "time": datetime.now().isoformat()}, f)
        except Exception as e:
            logger.debug(f"Son brifing kaydedilemedi: {e}")

    def _load_last_briefing(self) -> dict:
        try:
            if _LAST_BRIFING_FILE.exists():
                with open(_LAST_BRIFING_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass
        return {}

    _AI_KURALLAR = (
        "\n\nKURALLAR — KESİNLİKLE UYULACAK:\n"
        "- SADECE Türkçe yaz. İngilizce/Almanca/Çince/Çekçe hiçbir kelime kullanma. "
        "Teknik terimleri bile Türkçeleştir (ör. 'support' yerine 'destek', 'trend' yerine 'eğilim').\n"
        "- Belirsiz ifadelerden kaçın: 'olabilir, görünüyor, dikkat edilmeli' yerine net karar: "
        "'AL', 'SAT', 'TUT', 'BEKLE'.\n"
        "- Her tavsiye için: Sembol | Karar (AL/SAT/TUT) | Giriş fiyatı | Stop-loss (%-X) | "
        "Hedef fiyat | Tutma süresi | Tek cümle gerekçe.\n"
        "- Kararın ardında dur: Risk seviyesi (DÜŞÜK/ORTA/YÜKSEK) belirt.\n"
        "- Kısa vade (gün içi), orta vade (haftalık), uzun vade (aylık/3 aylık) ayrı başlıklarla verilecek.\n"
        "- 'Yatırım tavsiyesi değildir' ibaresi en sona bir satırda.\n"
        "- FİLTRELEME ZORUNLU: Eğer 5'ten fazla AL sinyali varsa, SADECE EN İYİ 1 TANESİNİ seç. Diğerlerini neden elemek zorunda kaldığını TEK CÜMLEYLE yaz. Liste halinde 10 hisse önermek YASAK — kullanıcı karar alamıyor.\n"
        "- Önerilen tek hissenin Alpha Skoru, getiri potansiyeli, yabancı akımı, teknik görünüm verilerinden HANGİLERİ onu diğerlerinden ayırdığını açıkça belirt.\n"
        "- 'İzlenmeli', 'dikkat edilmeli', 'takip edilebilir' gibi pasif ifadeler YASAK. Her cümle ya bir karar ya bir rakam içermeli.\n"
    )

    def _ai_text(self, prompt: str, max_tokens: int = 300) -> str:
        try:
            from core.ai_engine import _call_best_ai
            # Her prompt'a standart kuralları ekle (yabancı dil sızıntısı ve muğlak tavsiye engeli)
            if self._AI_KURALLAR.strip().split("\n")[0] not in prompt:
                prompt = prompt + self._AI_KURALLAR
            sys_prompt = (
                "Sen profesyonel bir Türk finans analistisin. Sadece Türkçe yanıt verirsin. "
                "Net AL/SAT/TUT kararları verirsin, muğlak konuşmazsın. "
                "İngilizce/Almanca/Çince/Çekçe/İspanyolca HİÇBİR yabancı kelime kullanma "
                "('wichtig', 'crucial', 'posición', 'vhodné', 'attractive', 'together', 'unterstützt', '一起' vb. YASAK). "
                "Teknik terimleri bile Türkçeleştir: support→destek, resistance→direnç, trend→eğilim, volume→hacim. "
                "Belirsiz ifadelerden kaçın: 'olabilir, görünüyor, dikkat edilmeli' yerine net karar ver. "
                "Yanıtların tam olsun, asla yarım kesilmesin."
            )
            full_prompt = f"{sys_prompt}\n\nGÖREV:\n{prompt}"
            return _call_best_ai(full_prompt, max_tokens=max_tokens) or ""
        except Exception as e:
            logger.debug(f"_ai_text hatası: {e}")
            return ""

    # ── Formatlama Yardımcıları ───────────────────────────────────────────────

    def _header(self, icon: str, title: str, subtitle: str = "") -> str:
        line = "─" * 32
        sub  = f"\n<i>{_html.escape(subtitle)}</i>" if subtitle else ""
        return f"{icon} <b>{_html.escape(title)}</b>{sub}\n{line}"

    def _quotes_block(self, quotes: dict) -> str:
        if not quotes:
            return ""
        # Sembol bazlı format: BIST nokta yok, BTC binlerce
        _fmt = {
            "BIST-100":  lambda p: f"{p:,.0f}",
            "USD/TRY":   lambda p: f"{p:,.4f}",
            "EUR/TRY":   lambda p: f"{p:,.4f}",
            "Altın ONS": lambda p: f"${p:,.2f}",
            "BTC":       lambda p: f"${p:,.0f}",
        }
        rows = []
        for lbl, q in quotes.items():
            price = q.get("price", 0)
            pct   = q.get("pct", 0) or 0
            arrow = "▲" if pct >= 0 else "▼"
            fmt   = _fmt.get(lbl, lambda p: f"{p:,.2f}")
            rows.append(f"  {arrow} <b>{lbl}</b>: {fmt(price)}  ({pct:+.2f}%)")
        h = datetime.now().hour
        delay_note = "\n<i>  ⏱ ~15 dk gecikmeli</i>" if 10 <= h <= 18 else ""
        return "<b>📈 Piyasa Göstergeleri</b>\n" + "\n".join(rows) + delay_note

    def _movers_block(self, gainers: list, losers: list, top_n: int = 10) -> str:
        if not gainers and not losers:
            return ""  # Veri yoksa bölümü tamamen atla
        def fmt_list(items):
            out = []
            for i, (sym, pct) in enumerate(items, 1):
                pct   = pct or 0
                arrow = "▲" if pct >= 0 else "▼"
                out.append(f"  {i:2}. {arrow} <code>{sym:<10}</code> {pct:+.2f}%")
            return "\n".join(out) if out else "  — veri yok"
        g_cnt = min(len(gainers), top_n)
        r_cnt = min(len(losers), top_n)
        g_t = f"🟢 En Çok Yükselen (Top {g_cnt})"
        r_t = f"🔴 En Çok Düşen (Top {r_cnt})"
        return (
            f"\n<b>{g_t}</b>\n{fmt_list(gainers[:top_n])}\n\n"
            f"<b>{r_t}</b>\n{fmt_list(losers[:top_n])}\n"
        )

    def _weekly_movers_block(self, gainers: list, losers: list) -> str:
        if not gainers and not losers:
            return ""
        return self._movers_block(gainers, losers, top_n=10).replace(
            "En Çok Yükselen", "Haftanın Yükselenleri"
        ).replace("En Çok Düşen", "Haftanın Düşenleri")

    def _news_block(self, news: list[dict]) -> str:
        """Haber listesini title + link formatında yazar."""
        if not news:
            return "  — haber yok\n"
        lines = []
        for n in news:
            title = _html.escape(str(n.get("title", ""))[:100])
            url   = str(n.get("url", "")).strip()
            if url:
                lines.append(f'  • <a href="{url}">{title}</a>')
            else:
                lines.append(f"  • {title}")
        return "\n".join(lines) + "\n"

    def _footer(self, cta: str = "") -> str:
        line  = "─" * 32
        ts    = datetime.now().strftime("%H:%M")
        note  = f"\n💡 {_html.escape(cta)}" if cta else ""
        return f"\n{line}{note}\n<i>⏱ Piyasa verileri ~15 dk gecikmeli (Yahoo Finance)</i>\n<i>🤖 FinSentinel  •  {ts}</i>"

    # ── Aksiyon Sinyali ───────────────────────────────────────────────────────

    def _get_action_signal(self, symbol: str = None) -> dict | None:
        """
        En cazip AL hissesi (veya verilen sembol) için aksiyon sinyali üretir.
        Dönen dict: kod, ad, oneri, pot, fiyat, hedef, stop, guvenskor, gerekce
        """
        try:
            import pandas as pd

            data_dir = self._latest_data_dir()
            if not data_dir:
                return None

            def _read_xlsx(name):
                for ext in (".xlsx", ".xls"):
                    p = data_dir / (name + ext)
                    if p.exists():
                        try:
                            df = pd.read_excel(p, sheet_name=0)
                            df.columns = df.columns.str.strip()
                            return df.dropna(how="all").reset_index(drop=True)
                        except Exception:
                            pass
                return None

            def _num(s):
                return pd.to_numeric(
                    s.astype(str).str.replace(",", ".", regex=False)
                                 .str.replace(" ", "", regex=False)
                                 .str.replace("%", "", regex=False),
                    errors="coerce",
                )

            df_takip = _read_xlsx("takipozet")
            df_fin   = _read_xlsx("temelfinansal")
            df_yab   = _read_xlsx("temelyabancioran")
            if df_takip is None:
                return None

            df = df_takip.copy()
            df["Kod"] = df["Kod"].astype(str).str.strip().str.upper()

            if symbol:
                df = df[df["Kod"] == symbol.upper().strip()]
                if df.empty:
                    return None
            else:
                if "Öneri" not in df.columns or "Getiri Potansiyeli (%)" not in df.columns:
                    return None
                al_mask = df["Öneri"].astype(str).str.upper().str.contains("AL", na=False)
                df = df[al_mask].copy()
                df["_pot"] = _num(df["Getiri Potansiyeli (%)"])
                df = df[df["_pot"] > 0].nlargest(1, "_pot")
                if df.empty:
                    return None

            row = df.iloc[0]
            kod   = str(row["Kod"])
            ad    = str(row.get("Hisse Adı", kod))
            oneri = str(row.get("Öneri", "—"))
            pot   = float(_num(pd.Series([row.get("Getiri Potansiyeli (%)", 0)])).iloc[0] or 0)

            # Fiyat ve hedef bilgisi
            fiyat_col  = next((c for c in df_takip.columns if "Fiyat" in c and "Hedef" not in c), None)
            hedef_col  = next((c for c in df_takip.columns if "Hedef" in c and "Fiyat" in c), None)
            fiyat = float(_num(pd.Series([row.get(fiyat_col, 0)])).iloc[0] or 0) if fiyat_col else 0
            hedef = float(_num(pd.Series([row.get(hedef_col, 0)])).iloc[0] or 0) if hedef_col else 0

            if fiyat > 0 and hedef == 0 and pot > 0:
                hedef = round(fiyat * (1 + pot / 100), 2)
            stop = round(fiyat * 0.93, 2) if fiyat > 0 else 0   # %7 stop-loss

            # Güven skoru: kaç sinyal aynı yönde?
            score_pts = 0
            score_max = 0
            gerekce_parts = []

            # 1. Öneri
            score_max += 30
            if "AL" in oneri.upper():
                score_pts += 30
                gerekce_parts.append("Analist AL önerisi")

            # 2. Getiri potansiyeli
            score_max += 25
            if pot >= 30:
                score_pts += 25
                gerekce_parts.append(f"Getiri pot. %{pot:.0f}")
            elif pot >= 15:
                score_pts += 15
                gerekce_parts.append(f"Getiri pot. %{pot:.0f}")

            # 3. F/K
            if df_fin is not None and "Kod" in df_fin.columns and "F/K" in df_fin.columns:
                score_max += 20
                fk_row = df_fin[df_fin["Kod"].astype(str).str.upper().str.strip() == kod]
                if not fk_row.empty:
                    fk = float(_num(fk_row["F/K"]).iloc[0] or 999)
                    if 0 < fk < 10:
                        score_pts += 20
                        gerekce_parts.append(f"F/K={fk:.1f} (ucuz)")
                    elif 0 < fk < 20:
                        score_pts += 10
                        gerekce_parts.append(f"F/K={fk:.1f}")

            # 4. Yabancı alım
            if df_yab is not None and "Kod" in df_yab.columns:
                score_max += 25
                yab_row = df_yab[df_yab["Kod"].astype(str).str.upper().str.strip() == kod]
                if not yab_row.empty:
                    deg_col = next((c for c in df_yab.columns if "Değişim" in c), None)
                    if deg_col:
                        yab_deg = float(_num(yab_row[deg_col]).iloc[0] or 0)
                        if yab_deg > 0:
                            score_pts += 25
                            gerekce_parts.append(f"Yabancı alım +{yab_deg:.2f}%")
                        elif yab_deg > -1:
                            score_pts += 10

            guvenskor = round(score_pts / score_max * 100) if score_max > 0 else 50

            return {
                "kod":       kod,
                "ad":        ad,
                "oneri":     oneri,
                "pot":       pot,
                "fiyat":     fiyat,
                "hedef":     hedef,
                "stop":      stop,
                "guvenskor": guvenskor,
                "gerekce":   " | ".join(gerekce_parts) or "Temel analiz sinyali",
            }
        except Exception as e:
            logger.debug(f"_get_action_signal hatası: {e}")
            return None

    def _get_gunun_firsati(self) -> dict | None:
        """Alpha skoru + AL önerisi + katılım uyumu en yüksek tek hisseyi seçer."""
        try:
            import pandas as pd

            data_dir = self._latest_data_dir()
            if not data_dir:
                return None

            def _read_xlsx(name):
                for ext in (".xlsx", ".xls"):
                    p = data_dir / (name + ext)
                    if p.exists():
                        try:
                            df = pd.read_excel(p, sheet_name=0)
                            df.columns = df.columns.str.strip()
                            return df.dropna(how="all").reset_index(drop=True)
                        except Exception:
                            pass
                return None

            def _num(s):
                return pd.to_numeric(
                    s.astype(str).str.replace(",", ".", regex=False)
                                 .str.replace(" ", "", regex=False)
                                 .str.replace("%", "", regex=False),
                    errors="coerce",
                )

            df = _read_xlsx("takipozet")
            df_fin = _read_xlsx("temelfinansal")
            df_yab = _read_xlsx("temelyabancioran")
            if df is None or "Kod" not in df.columns:
                return None

            df["Kod"] = df["Kod"].astype(str).str.strip().str.upper()

            al_mask = df.get("Öneri", pd.Series(dtype=str)).astype(str).str.upper().str.contains("AL", na=False)
            df = df[al_mask].copy()
            if df.empty:
                return None

            # Basit alpha skoru: potansiyel percentile rank
            pot_col = "Getiri Potansiyeli (%)"
            if pot_col not in df.columns:
                return None
            df["_pot"]   = _num(df[pot_col])
            df["_alpha"] = df["_pot"].rank(pct=True) * 100

            # F/K bonusu
            if df_fin is not None and "Kod" in df_fin.columns and "F/K" in df_fin.columns:
                df_fin2 = df_fin[["Kod","F/K"]].copy()
                df_fin2["Kod"] = df_fin2["Kod"].astype(str).str.strip().str.upper()
                df = df.merge(df_fin2, on="Kod", how="left")
                fk = _num(df["F/K"])
                df["_alpha"] += (fk < 10).fillna(False).astype(int) * 10

            # Yabancı alım bonusu
            if df_yab is not None and "Kod" in df_yab.columns:
                deg_col = next((c for c in df_yab.columns if "Değişim" in c), None)
                if deg_col:
                    df_yab2 = df_yab[["Kod", deg_col]].copy()
                    df_yab2["Kod"] = df_yab2["Kod"].astype(str).str.strip().str.upper()
                    df = df.merge(df_yab2, on="Kod", how="left", suffixes=("","_y"))
                    yab = _num(df[deg_col])
                    df["_alpha"] += (yab > 0).fillna(False).astype(int) * 15

            best = df.nlargest(1, "_alpha")
            if best.empty:
                return None
            row = best.iloc[0]
            return {
                "kod":   str(row["Kod"]),
                "ad":    str(row.get("Hisse Adı", row["Kod"])),
                "alpha": round(float(row["_alpha"]), 1),
                "pot":   round(float(row["_pot"]), 1),
                "oneri": str(row.get("Öneri","AL")),
            }
        except Exception as e:
            logger.debug(f"_get_gunun_firsati hatası: {e}")
            return None

    def _get_whale_signals(self, top_n: int = 5, yab_threshold: float = 0.5,
                           hacim_x_threshold: float = 2.0) -> list[dict]:
        """
        Yabancı oranı > +yab_threshold% VE hacim > hacim_x_threshold × ortalama
        olan hisseleri listeler.
        """
        try:
            import pandas as pd

            data_dir = self._latest_data_dir()
            if not data_dir:
                return []

            def _read_xlsx(name):
                for ext in (".xlsx", ".xls"):
                    p = data_dir / (name + ext)
                    if p.exists():
                        try:
                            df = pd.read_excel(p, sheet_name=0)
                            df.columns = df.columns.str.strip()
                            return df.dropna(how="all").reset_index(drop=True)
                        except Exception:
                            pass
                return None

            def _num(s):
                return pd.to_numeric(
                    s.astype(str).str.replace(",", ".", regex=False)
                                 .str.replace(" ", "", regex=False)
                                 .str.replace("%", "", regex=False),
                    errors="coerce",
                )

            df_yab  = _read_xlsx("temelyabancioran")
            df_ozet = _read_xlsx("temelozet")

            if df_yab is None or "Kod" not in df_yab.columns:
                return []

            df_yab["Kod"] = df_yab["Kod"].astype(str).str.strip().str.upper()

            # Sütun adı: "Değişim (Baz Puan)" — değerler baz puan (100 baz = 1 pp)
            deg_col = next((c for c in df_yab.columns if "De" in c and ("i" in c.lower() or "ğ" in c.lower())), None)
            if not deg_col:
                # fallback: sayısal kolonlardan son ikisi yabancı oranı, aralarındaki fark kullan
                num_cols = [c for c in df_yab.columns if c != "Kod" and _num(df_yab[[c]].iloc[:, 0]).notna().mean() > 0.5]
                if len(num_cols) >= 3:
                    # son iki kolon = iki günün oranı, farkları = değişim
                    df_yab["_yab_bp"] = _num(df_yab[num_cols[-1]]) - _num(df_yab[num_cols[-2]])
                else:
                    return []
            else:
                df_yab["_yab_bp"] = _num(df_yab[deg_col])   # baz puan

            # Baz puanı → yüzde puana çevir (100 baz puan = 1 yüzde puan)
            # Gerçekçi aralık: yabancı oranı günlük en fazla ±30 pp değişebilir.
            # >50 pp değer = kolon yanlış eşleşti (% değeri baz puan olarak okundu) → at.
            df_yab["_yab_bp"] = df_yab["_yab_bp"].clip(-3000, 3000)
            df_yab["_yab"] = df_yab["_yab_bp"] / 100.0

            # Eşik: yab_threshold = yüzde puan (ör. 0.5 = yabancı oranı 0.5 pp artmış)
            # Minimum anlam eşiği: 0.5 pp + en az 50 baz puanı sinyal gücü
            df_whale = df_yab[df_yab["_yab"] >= yab_threshold].copy()

            # Hacim verisi: temelozet'te yoksa yfinance'ten anlık hacim/ortalama hacim al
            df_whale["_hx"] = None
            try:
                import yfinance as yf
                for idx, row in df_whale.iterrows():
                    sym = row["Kod"] + ".IS"
                    try:
                        tk = yf.Ticker(sym)
                        info = tk.fast_info
                        vol  = getattr(info, "three_month_average_volume", None) or 0
                        last = getattr(info, "last_volume", None) or 0
                        if vol > 0 and last > 0:
                            df_whale.at[idx, "_hx"] = last / vol
                    except Exception:
                        pass
            except Exception:
                pass

            # Hacim verisi yoksa filtreleme yapma ama göstermede "N/A" yaz
            has_hacim = df_whale["_hx"].notna().any()
            if has_hacim:
                df_whale = df_whale[df_whale["_hx"].isna() | (df_whale["_hx"] >= hacim_x_threshold)]

            df_whale = df_whale.nlargest(top_n, "_yab")

            result = []
            for _, r in df_whale.iterrows():
                yab_d = float(r["_yab"])           # yüzde puan
                yab_bp = float(r["_yab_bp"])       # baz puan (orijinal)
                hx_raw = r.get("_hx")
                hx     = float(hx_raw) if pd.notna(hx_raw) else None
                sinyal = "🔥 Güçlü Giriş" if yab_d >= 1.0 and (hx or 0) >= 3 else "📈 Balina Hareketi"
                result.append({
                    "kod":     str(r["Kod"]),
                    "yab_deg": yab_d,     # pp
                    "yab_bp":  yab_bp,    # baz puan
                    "hacim_x": hx,        # None = veri yok
                    "sinyal":  sinyal,
                })
            return result
        except Exception as e:
            logger.debug(f"_get_whale_signals hatası: {e}")
            return []

    def _get_sector_rotation(self) -> list[dict]:
        """
        Sektör bazında AL/TUT/SAT sayısı + ort. potansiyel → güç skoru.
        En yüksek skora sahip sektörler rotasyon sinyali verir.
        """
        try:
            import pandas as pd

            data_dir = self._latest_data_dir()
            if not data_dir:
                return []

            def _read_xlsx(name):
                for ext in (".xlsx", ".xls"):
                    p = data_dir / (name + ext)
                    if p.exists():
                        try:
                            df = pd.read_excel(p, sheet_name=0)
                            df.columns = df.columns.str.strip()
                            return df.dropna(how="all").reset_index(drop=True)
                        except Exception:
                            pass
                return None

            def _num(s):
                return pd.to_numeric(
                    s.astype(str).str.replace(",", ".", regex=False)
                                 .str.replace(" ", "", regex=False)
                                 .str.replace("%", "", regex=False),
                    errors="coerce",
                )

            df_takip = _read_xlsx("takipozet")
            df_ozet  = _read_xlsx("temelozet")

            if df_takip is None or df_ozet is None:
                return []

            df_takip["Kod"] = df_takip["Kod"].astype(str).str.strip().str.upper()
            df_ozet["Kod"]  = df_ozet["Kod"].astype(str).str.strip().str.upper()

            sek_col = next((c for c in df_ozet.columns
                            if c.lower().replace("ö","o").replace("ü","u") in ("sektor","sektör","sector")), None)
            if not sek_col:
                return []

            df = df_takip.merge(df_ozet[["Kod", sek_col]], on="Kod", how="left")
            df["_sektor"] = df[sek_col].fillna("Diğer").astype(str)

            if "Öneri" in df.columns:
                df["_oneri"] = df["Öneri"].astype(str).str.upper()
            else:
                return []

            if "Getiri Potansiyeli (%)" in df.columns:
                df["_pot"] = _num(df["Getiri Potansiyeli (%)"])
            else:
                df["_pot"] = 0

            result = []
            for sek, grp in df.groupby("_sektor"):
                al  = int(grp["_oneri"].str.contains("AL",  na=False).sum())
                tut = int(grp["_oneri"].str.contains("TUT", na=False).sum())
                sat = int(grp["_oneri"].str.contains("SAT", na=False).sum())
                total    = max(len(grp), 1)
                avg_pot  = float(grp["_pot"].mean() or 0)
                # Güç skoru: AL oranı ağırlıklı + ortalama potansiyel
                skor = (al / total * 60) + min(avg_pot / 2, 40)
                net  = al - sat
                result.append({
                    "sektor":  sek,
                    "al": al, "tut": tut, "sat": sat,
                    "avg_pot": round(avg_pot, 1),
                    "skor":    round(skor, 1),
                    "net":     net,
                })

            result.sort(key=lambda x: x["skor"], reverse=True)
            return result
        except Exception as e:
            logger.debug(f"_get_sector_rotation hatası: {e}")
            return []

    def _get_news_sentiment_alerts(self, threshold: int = 60) -> list[dict]:
        """
        İY araştırma haberlerini Türkçe keyword ile puanlar.
        threshold% negatif olan hisseler kırmızı listeye alınır.
        Dönen liste: [{kod, neg_pct, titles}]
        """
        _NEG = [
            "düşüş","zarar","kayıp","risk","endişe","çöküş","baskı","kriz","daralma",
            "olumsuz","negatif","zayıf","satış baskısı","hedef fiyat düşürüldü",
            "öneri düşürüldü","sat","revize aşağı","uyarı","tehlike",
        ]
        _POS = [
            "yükseliş","kâr","büyüme","güçlü","pozitif","al","revize yukarı",
            "hedef fiyat artırıldı","öneri yükseltildi","fırsat","rekor","ivme",
        ]
        try:
            from core.fetcher import NewsFetcher
            articles = NewsFetcher.get_isyatirim_research(limit=30)
        except Exception:
            return []

        # Bilinen BIST dışı kelimeler — kategori ayrıştırıcı bunları sembol kabul etmemeli
        _NOT_TICKERS = {
            "GENEL","SEKTÖR","SEKTOR","RAPOR","BULTEN","BORSA","HISSE","ENDEKS",
            "TAKIP","HAFTA","GUNLUK","GUNUN","SIRKET","AYDEM","ENERJI","ENFLASYON",
            "TEMETU","BEDEL","BEDELSIZ","BIST100","BIST50","BIST30","KUPON","MOGAN",
            "ENTRA","FAIZ","DOLAR","DOVIZ","ALTIN","GUMUS","EMTIA","MAKRO","GLOBAL",
            "TEKNIK","TEMEL","YATIRIM","PIYASA","KAPANIS","ACILIS","INCELEME",
        }

        from collections import defaultdict
        stock_scores: dict = defaultdict(lambda: {"pos": 0, "neg": 0, "titles": []})

        for art in articles:
            title   = art.get("title", "").lower()
            cats    = art.get("categories", [])
            summary = art.get("summary", "").lower()
            text    = title + " " + summary

            pos = sum(1 for w in _POS if w in text)
            neg = sum(1 for w in _NEG if w in text)
            if pos == 0 and neg == 0:
                continue

            for cat in cats:
                # Gerçek BIST kodları kategoride zaten BÜYÜK harf gelir (ör. "GWIND", "ENJSA")
                # Türkçe kelimeler başlık case'i veya küçük harf gelir (ör. "Takip", "elektrik")
                # Sadece orijinalde tamamen büyük harf olan kısa tokenleri al
                for tok in cat.split():
                    tok_clean = tok.strip(".,;:!?/()[]")
                    if (
                        4 <= len(tok_clean) <= 6
                        and tok_clean.isupper()          # orijinalde büyük harf
                        and tok_clean.isalpha()          # sadece harf
                        and tok_clean not in _NOT_TICKERS
                        and not tok_clean.startswith("BIST")
                    ):
                        stock_scores[tok_clean]["pos"]    += pos
                        stock_scores[tok_clean]["neg"]    += neg
                        stock_scores[tok_clean]["titles"].append(art.get("title","")[:60])

        alerts = []
        for kod, sc in stock_scores.items():
            total = sc["pos"] + sc["neg"]
            if total == 0:
                continue
            # En az 2 farklı makale VE toplam sinyal ≥ 3 olmadıkça listeye alma
            # (tek bir makaledeki keyword eşleşmesi güvenilir sinyal sayılmaz)
            unique_titles = list(dict.fromkeys(sc["titles"]))  # sırayı koru, tekrarları kaldır
            if len(unique_titles) < 2 or total < 3:
                continue
            neg_pct = round(sc["neg"] / total * 100)
            if neg_pct >= threshold:
                alerts.append({"kod": kod, "neg_pct": neg_pct, "titles": unique_titles[:2]})

        alerts.sort(key=lambda x: x["neg_pct"], reverse=True)
        return alerts[:5]

    def _is_volatile_market(self) -> bool:
        """BIST-100 günlük değişimi -%2'nin altındaysa True döner."""
        try:
            quotes = self._get_key_quotes()
            bist_pct = quotes.get("BIST-100", {}).get("pct", 0) or 0
            return bist_pct <= -2.0
        except Exception:
            return False

    def send_trade_alerts(self):
        """Scheduler tarafından her 5 dk çağrılır. Stop/hedef uyarıları gönderir."""
        from core.trade_manager import check_all_trades
        try:
            alerts = check_all_trades()
            for a in alerts:
                sym  = a["symbol"]
                pct  = a["pct"]
                kind = a["type"]
                cid  = a.get("chat_id") or str(self.chat_id)
                if kind == "STOP":
                    msg = (
                        f"🚨 <b>STOP-LOSS ALARM — {sym}</b>\n"
                        f"Fiyat stop seviyesine indi! (<b>{pct:+.2f}%</b>)\n\n"
                        f"⚡ <b>HEMEN SAT!</b> Zararı kes, pozisyonu kapat.\n"
                        f"  Güncel: {a['price']:,.2f} ₺  |  Stop: {a['trade']['stop']:,.2f} ₺\n"
                        f"/kapat {sym}"
                    )
                else:
                    msg = (
                        f"🎯 <b>HEDEF ULAŞILDI — {sym}</b>\n"
                        f"Fiyat hedefe ulaştı! (<b>{pct:+.2f}%</b>)\n\n"
                        f"💰 <b>KAR AL!</b> Pozisyonu değerlendir.\n"
                        f"  Güncel: {a['price']:,.2f} ₺  |  Hedef: {a['trade']['target']:,.2f} ₺\n"
                        f"/kapat {sym}"
                    )
                self.send_message(msg, chat_id=cid)
        except Exception as e:
            logger.error(f"send_trade_alerts hatası: {e}")

    def send_whale_alert(self):
        """
        Scheduler tarafından her 30 dk çağrılır (sadece işlem saatlerinde).
        Balina hareketi varsa uyarı gönderir. Cooldown ve hacim artışı kontrolü yapar (spam engelleme).
        """
        if not self._is_trading_day():
            return
        h = datetime.now().hour
        if not (10 <= h <= 18):
            return
        try:
            signals = self._get_whale_signals(top_n=3, yab_threshold=0.5, hacim_x_threshold=2.0)
            if not signals:
                return

            # Spam engelleme: data/whale_state.json
            whale_state_file = Path("data/whale_state.json")
            state = {}
            if whale_state_file.exists():
                try:
                    with open(whale_state_file, "r", encoding="utf-8") as f:
                        state = json.load(f)
                except Exception:
                    pass
            
            now = datetime.now()
            today_str = now.strftime("%Y-%m-%d")
            
            # Reset state on new day
            if state.get("_date") != today_str:
                state = {"_date": today_str}

            filtered_signals = []
            for s in signals:
                kod = s['kod']
                hx = s.get('hacim_x') or 0
                
                prev_info = state.get(kod)
                should_alert = False
                
                if not prev_info:
                    should_alert = True
                else:
                    try:
                        last_time = datetime.fromisoformat(prev_info["time"])
                        last_hx = prev_info["hacim_x"]
                        hours_passed = (now - last_time).total_seconds() / 3600
                        
                        # Tekrar alarm şartı: Ya 4 saat geçmeli ya da hacim x çarpanı en az 1.0 artmalı
                        if hours_passed >= 4:
                            should_alert = True
                        elif hx > last_hx + 1.0:
                            should_alert = True
                    except Exception:
                        should_alert = True
                
                if should_alert:
                    filtered_signals.append(s)
                    state[kod] = {
                        "time": now.isoformat(),
                        "hacim_x": hx
                    }

            if not filtered_signals:
                return

            # Update state file
            try:
                whale_state_file.parent.mkdir(parents=True, exist_ok=True)
                with open(whale_state_file, "w", encoding="utf-8") as f:
                    json.dump(state, f)
            except Exception:
                pass

            has_any_hacim = any(s.get("hacim_x") is not None for s in filtered_signals)
            def _whale_row(s):
                yab_str = f"Yab: <b>{s['yab_deg']:+.2f} pp</b> ({s['yab_bp']:+.0f} baz)"
                hx = s.get("hacim_x")
                hx_str = f"  Hacim: <b>{hx:.1f}x</b>" if hx is not None else "  Hacim: <i>veri yok</i>"
                return f"  🐋 <code>{s['kod']}</code>  {yab_str}{hx_str}  {s['sinyal']}"
            
            rows = "\n".join(_whale_row(s) for s in filtered_signals)
            if has_any_hacim:
                footer_note = "<i>Yabancı oranı artışı + anormal hacim tespit edildi.</i>"
            else:
                footer_note = "<i>Yabancı oranı artışı tespit edildi. Hacim verisi şu an alınamıyor.</i>"
            msg = (
                "🐋 <b>BALINA ALARMI</b> — Anormal Para Hareketi\n"
                "─────────────────────────────\n"
                + rows
                + f"\n\n{footer_note}"
                + self._footer()
            )
            self.send_message(msg)
        except Exception as e:
            logger.debug(f"send_whale_alert hatası: {e}")

    def send_sentiment_redlist(self):
        """
        Günde bir kez (09:30) negatif haberleri olan hisseleri raporlar.
        """
        try:
            alerts = self._get_news_sentiment_alerts(threshold=60)
            if not alerts:
                return
            rows = "\n".join(
                f"  🔴 <code>{a['kod']}</code>  Negatif: <b>%{a['neg_pct']}</b>  "
                f"— {_html.escape(a['titles'][0][:55]) if a['titles'] else ''}"
                for a in alerts
            )
            msg = (
                "🔴 <b>Haber Sentiment Kırmızı Liste</b>\n"
                "─────────────────────────────\n"
                + rows
                + "\n\n<i>Bu hisseler hakkında son İY araştırma notları ağırlıklı negatif.</i>"
                + self._footer()
            )
            self.send_message(msg)
        except Exception as e:
            logger.debug(f"send_sentiment_redlist hatası: {e}")

    def _action_signal_block(self, signal: dict) -> str:
        if not signal:
            return ""
        oneri = signal.get("oneri","—").upper()
        emoji = "🟢" if "AL" in oneri else ("🔴" if "SAT" in oneri else "🟡")
        fiyat = signal.get("fiyat", 0)
        hedef = signal.get("hedef", 0)
        stop  = signal.get("stop",  0)
        gsk   = signal.get("guvenskor", 0)
        gerek = _html.escape(signal.get("gerekce",""))
        fiyat_str = f"  Mevcut: <b>{fiyat:,.2f} ₺</b>\n" if fiyat > 0 else ""
        hedef_str = f"  Hedef : <b>{hedef:,.2f} ₺</b>\n" if hedef > 0 else ""
        stop_str  = f"  Stop  : <b>{stop:,.2f} ₺</b>\n"  if stop  > 0 else ""
        conf_bar  = "▓" * (gsk // 10) + "░" * (10 - gsk // 10)
        return (
            f"\n<b>🎯 Aksiyon Sinyali</b>\n"
            f"  {emoji} <code>{signal['kod']}</code>  →  <b>{oneri}</b>\n"
            f"{fiyat_str}{hedef_str}{stop_str}"
            f"  Pot. : <b>%{signal.get('pot',0):.1f}</b>\n"
            f"  Güven: [{conf_bar}] {gsk}%\n"
            f"  <i>{gerek}</i>\n"
        )

    def _firsat_block(self, firsat: dict) -> str:
        if not firsat:
            return ""
        return (
            f"\n<b>🔥 Günün Tek Fırsatı</b>\n"
            f"  ⭐ <code>{firsat['kod']}</code>  {_html.escape(firsat['ad'][:25])}\n"
            f"  Alpha Skoru: <b>{firsat['alpha']:.0f}/125</b>  |  "
            f"Pot: <b>%{firsat['pot']:.1f}</b>  |  Öneri: <b>{firsat['oneri']}</b>\n"
            f"  <i>Bugün radarınızda OLMALI</i>\n"
        )

    # ── Komut Dinleyici (Polling) ─────────────────────────────────────────────

    def listen_commands(self, poll_interval: int = 3, max_loops: int = None):
        """
        Telegram getUpdates ile komutları dinler.
        Kişisel DM, grup ve süper grup mesajlarını yakalar.
        ALLOWED_CHAT_IDS boşsa herkese açık; doluysa sadece listedeki
        chat ID'lerine (kişisel veya grup) yanıt verilir.
        """
        if not self.token:
            logger.warning("listen_commands: token yok, komut dinleme başlatılamadı.")
            return

        # Başlarken komutları Telegram'a kaydet (picker düzeltmesi)
        self.register_commands()

        offset   = 0
        loops    = 0
        base_url = self.base_url

        logger.info("Telegram komut dinleyici başlatıldı.")

        import time

        while True:
            if max_loops and loops >= max_loops:
                break
            loops += 1
            try:
                resp = requests.get(
                    f"{base_url}/getUpdates",
                    params={"offset": offset, "timeout": poll_interval},
                    timeout=poll_interval + 5,
                )
                if not resp.ok:
                    time.sleep(poll_interval)
                    continue

                updates = resp.json().get("result", [])
                for upd in updates:
                    offset = upd["update_id"] + 1

                    # DM, grup ve süper grup mesajlarını yakala
                    msg = (upd.get("message")
                           or upd.get("edited_message")
                           or upd.get("channel_post")
                           or {})
                    if not msg:
                        continue

                    chat      = msg.get("chat", {})
                    chat_id   = str(chat.get("id", ""))
                    chat_type = chat.get("type", "")   # private | group | supergroup | channel
                    text      = (msg.get("text") or "").strip()

                    if not text.startswith("/"):
                        continue

                    # Güvenlik: ALLOWED_CHAT_IDS doluysa kontrol et
                    if ALLOWED_CHAT_IDS and chat_id not in ALLOWED_CHAT_IDS:
                        # Grupta ilk kez görülen bir chat_id: loga yaz, geç
                        logger.debug(f"Bilinmeyen chat_id ({chat_type}): {chat_id} — mesaj: {text[:30]}")
                        continue

                    parts = text.split()
                    cmd   = parts[0].lower().split("@")[0]   # /analiz@botname → /analiz
                    # Grup mesajlarında argümanlar büyük harf olmalı (THYAO gibi),
                    # ama yardım kategorisi gibi Türkçe kelimeler için lower bırak
                    arg   = parts[1] if len(parts) > 1 else ""
                    arg_upper = arg.upper()

                    try:
                        # ── Piyasa ──────────────────────────────────────
                        if cmd == "/durum":
                            self._cmd_durum(chat_id)
                        elif cmd == "/bist":
                            self._cmd_bist(chat_id)
                        elif cmd == "/doviz":
                            self._cmd_doviz(chat_id)
                        elif cmd == "/altin":
                            self._cmd_altin(chat_id)
                        elif cmd == "/kripto":
                            self._cmd_kripto(chat_id)
                        elif cmd == "/dunyapiyasa":
                            self._cmd_dunyapiyasa(chat_id)
                        elif cmd == "/sektor":
                            self._cmd_sektor(chat_id)
                        elif cmd == "/balinalar":
                            self._cmd_balinalar(chat_id)
                        # ── Analiz ──────────────────────────────────────
                        elif cmd == "/analiz":
                            self._cmd_analiz(chat_id, arg_upper)
                        elif cmd == "/risk":
                            self._cmd_risk(chat_id, arg_upper)
                        elif cmd == "/sorgula":
                            self._cmd_sorgula(chat_id, arg_upper)
                        elif cmd == "/firsat":
                            self._cmd_firsat(chat_id)
                        elif cmd == "/katilim":
                            self.send_message(cmd_katilim_full(), chat_id=chat_id)
                        elif cmd == "/plan":
                            self.send_investment_plan(arg_upper)
                        elif cmd == "/uzunvade":
                            self.send_longterm_view(arg_upper)
                        # ── Temel Analiz ─────────────────────────────────
                        elif cmd == "/oneri":
                            self.send_message(cmd_oneri(arg_upper), chat_id=chat_id)
                        elif cmd == "/al":
                            n = int(arg) if arg.isdigit() else 10
                            self.send_message(cmd_al(n), chat_id=chat_id)
                        elif cmd == "/tut":
                            self.send_message(cmd_tut(), chat_id=chat_id)
                        elif cmd == "/sat":
                            self.send_message(cmd_sat(), chat_id=chat_id)
                        elif cmd == "/alfaskor":
                            n = int(arg) if arg.isdigit() else 10
                            self.send_message(cmd_alfaskor(n), chat_id=chat_id)
                        elif cmd == "/temel":
                            self.send_message(cmd_temel(arg_upper), chat_id=chat_id)
                        elif cmd == "/hedef":
                            self.send_message(cmd_hedef(arg_upper), chat_id=chat_id)
                        elif cmd == "/temettu":
                            n = int(arg) if arg.isdigit() else 10
                            self.send_message(cmd_temettu(n), chat_id=chat_id)
                        elif cmd == "/yabanci":
                            n = int(arg) if arg.isdigit() else 10
                            self.send_message(cmd_yabanci(n), chat_id=chat_id)
                        elif cmd == "/endeks":
                            self.send_message(cmd_endeks(), chat_id=chat_id)
                        # ── Portföy ─────────────────────────────────────
                        elif cmd == "/portfoy":
                            self._cmd_portfoy(chat_id)
                        elif cmd == "/ekle":
                            self._cmd_ekle(chat_id, parts[1:])
                        elif cmd == "/kaldir":
                            self._cmd_kaldir(chat_id, arg_upper)
                        # ── Alarmlar ────────────────────────────────────
                        elif cmd == "/alarm":
                            self._cmd_alarm(chat_id, parts[1:])
                        elif cmd == "/alarmlar":
                            self._cmd_alarmlar(chat_id)
                        elif cmd == "/alarmsil":
                            self._cmd_alarmsil(chat_id, arg_upper)
                        # ── İşlem Takip ─────────────────────────────────
                        elif cmd == "/izle":
                            self._cmd_izle(chat_id, parts[1:])
                        elif cmd == "/kapat":
                            self._cmd_kapat(chat_id, arg_upper)
                        elif cmd == "/acikislemler":
                            self._cmd_acikislemler(chat_id)
                        elif cmd == "/performans":
                            self._cmd_performans(chat_id)
                        # ── Haberler ────────────────────────────────────
                        elif cmd == "/haber":
                            self._cmd_haber(chat_id, arg_upper)
                        elif cmd == "/iyarastirma":
                            self._cmd_iyarastirma(chat_id)
                        elif cmd == "/kap":
                            self._cmd_kap(chat_id)
                        # ── Acil ────────────────────────────────────────
                        elif cmd == "/panic":
                            self._cmd_panic(chat_id)
                        # ── Yardım ──────────────────────────────────────
                        elif cmd in ("/help", "/yardim", "/start"):
                            self._cmd_help(chat_id, arg.lower())
                    except Exception as e:
                        logger.error(f"Komut işleme hatası ({cmd}): {e}")
                        self.send_message(f"⚠️ Komut işlenirken hata: {e}", chat_id=chat_id)

            except Exception as e:
                logger.debug(f"getUpdates hatası: {e}")
            time.sleep(poll_interval)

    # ── Komut Yanıtları ────────────────────────────────────────────────────────

    def _cmd_help(self, chat_id: str, category: str = ""):
        cat = category.lower().strip()

        if cat in ("piyasa", "market"):
            msg = (
                "📊 <b>PİYASA KOMUTLARI</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "/durum       — BIST + döviz + altın anlık özet\n"
                "/bist        — BIST-100 detaylı görünüm\n"
                "/doviz       — USD/TRY EUR/TRY GBP/TRY\n"
                "/altin       — Altın ONS ve gram fiyatı\n"
                "/kripto      — BTC ETH BNB anlık fiyatlar\n"
                "/dunyapiyasa — Küresel endeksler\n"
                "/sektor      — Sektör rotasyon sinyali\n"
                "/balinalar   — Smart money / yabancı hareketleri\n"
                "\n➡️ /yardim [kategori] ile diğer kategorilere bakın"
            )
        elif cat in ("analiz", "analysis"):
            msg = (
                "🔬 <b>ANALİZ KOMUTLARI</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "/analiz THYAO     — Temel + teknik detay analizi\n"
                "/risk THYAO       — Risk notu: Düşük/Orta/Yüksek/Kritik\n"
                "/sorgula THYAO    — Karar öncesi eleştirel ön analiz\n"
                "/firsat           — Günün en yüksek alpha skoru\n"
                "/katilim          — Katılım uyumlu AL hisseleri + detay\n"
                "/sektor           — Sektör rotasyon sinyali\n"
                "/balinalar        — Smart money / yabancı hareketleri\n"
                "\n➡️ Temel analiz tabloları: /yardim temel"
            )
        elif cat in ("temel", "fundamental"):
            msg = (
                "📊 <b>TEMEL ANALİZ KOMUTLARI</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "/oneri            — Genel AL/TUT/SAT dağılımı\n"
                "/oneri THYAO      — Tek hisse öneri kartı\n"
                "/al               — En iyi AL önerileri (potansiyele göre)\n"
                "/tut              — TUT listesi\n"
                "/sat              — SAT listesi + risk uyarısı\n"
                "/alfaskor         — Alpha skor sıralaması top-10\n"
                "/alfaskor 20      — Top-20 alpha skoru\n"
                "/temel THYAO      — Hisse tam temel analiz kartı\n"
                "/hedef THYAO      — Hedef fiyat geçmişi\n"
                "/temettu          — En yüksek temettü verimi listesi\n"
                "/yabanci          — Yabancı yatırımcı giriş/çıkış tablosu\n"
                "/endeks           — BIST endeks bileşenleri özeti\n"
                "/katilim          — Katılım uyumlu AL hisseleri\n"
                "\n<i>Tüm sonuçlar İş Yatırım verileri + AI yorumuyla gelir.</i>"
            )
        elif cat in ("portfoy", "portfolyo", "portfolio"):
            msg = (
                "💼 <b>PORTFÖY KOMUTLARI</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "/portfoy               — Portföy özeti + P&amp;L\n"
                "/ekle THYAO 100 300.50 — Hisse ekle (adet + ortalama fiyat)\n"
                "/kaldir THYAO          — Hisseyi portföyden çıkar\n"
                "\n<i>💾 Portföy program kapatılsa dahi korunur.</i>"
            )
        elif cat in ("alarm", "alarmlar"):
            msg = (
                "🔔 <b>ALARM KOMUTLARI</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "/alarm THYAO 350 yukari — Fiyat alarmı kur\n"
                "/alarm THYAO 280 asagi  — Düşüş alarmı kur\n"
                "/alarmlar               — Aktif alarmlarım\n"
                "/alarmsil THYAO         — Sembolün alarmlarını sil\n"
                "\n<i>🔔 Alarm tetiklendiğinde anında mesaj alırsın.</i>"
            )
        elif cat in ("takip", "trade"):
            msg = (
                "📈 <b>İŞLEM TAKİP KOMUTLARI</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "/izle THYAO 300 280 340 — Stop/hedef ile takip başlat\n"
                "/izle THYAO 300 280 340 50 — (son rakam: adet)\n"
                "/kapat THYAO            — İşlemi kapat, P&amp;L hesapla\n"
                "/acikislemler           — Aktif takip listesi\n"
                "/performans             — Geçmiş işlem istatistikleri\n"
            )
        elif cat in ("haber", "news"):
            msg = (
                "📰 <b>HABER KOMUTLARI</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "/haber           — Son 5 genel haber\n"
                "/haber THYAO     — Bu hisse hakkında son haberler\n"
                "/iyarastirma     — İş Yatırım araştırma notları\n"
                "/kap             — Son KAP özel durum açıklamaları\n"
                "\n<i>Kaynak: İY Araştırma, KAP, Bloomberg HT, Reuters, Yahoo Finance...</i>"
            )
        else:
            msg = (
                "🤖 <b>FinSentinel — Akıllı Yatırım Asistanı</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "\n"
                "📊 <b>Piyasa</b>  →  /yardim piyasa\n"
                "  /durum  /bist  /doviz  /altin  /kripto\n"
                "\n"
                "🔬 <b>Analiz</b>  →  /yardim analiz\n"
                "  /analiz THYAO  /risk THYAO  /sorgula THYAO\n"
                "  /firsat  /katilim  /sektor  /balinalar\n"
                "\n"
                "🗓️ <b>Yatırım Planı</b>\n"
                "  /plan          — Günlük→5 yıllık çok dönemli plan (tüm öneriler)\n"
                "  /plan THYAO    — Belirli hisse için çok dönemli plan\n"
                "  /uzunvade      — 1-5 yıllık derinlemesine uzun vade analizi\n"
                "  /uzunvade GWIND — Belirli hisse için uzun vade görüşü\n"
                "\n"
                "📊 <b>Temel Analiz</b>  →  /yardim temel\n"
                "  /oneri  /al  /tut  /sat  /alfaskor  /temel THYAO\n"
                "  /hedef THYAO  /temettu  /yabanci  /endeks\n"
                "\n"
                "💼 <b>Portföy</b>  →  /yardim portfoy\n"
                "  /portfoy  /ekle THYAO 100 300  /kaldir THYAO\n"
                "\n"
                "🔔 <b>Alarmlar</b>  →  /yardim alarm\n"
                "  /alarm THYAO 350 yukari  /alarmlar  /alarmsil THYAO\n"
                "\n"
                "📈 <b>İşlem Takip</b>  →  /yardim takip\n"
                "  /izle THYAO 300 280 340  /kapat THYAO  /performans\n"
                "\n"
                "📰 <b>Haberler</b>  →  /yardim haber\n"
                "  /haber  /haber THYAO  /iyarastirma  /kap\n"
                "\n"
                "🚨 <b>Acil</b>\n"
                "  /panic — Acil durum raporu\n"
                "\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "<i>Detaylı yardım: /yardim [kategori]</i>\n"
                "<i>Örnek: /yardim analiz</i>"
            )
        self.send_message(msg, chat_id=chat_id)

    def _cmd_durum(self, chat_id: str):
        quotes  = self._get_key_quotes()
        gainers, losers = self._get_bist_movers(top_n=5)
        news    = self._get_news_with_links(limit=3)
        fund    = self._get_fundamental_summary()
        msg = (
            self._header("📊", "Anlık Piyasa Durumu", datetime.now().strftime("%d %b %Y %H:%M"))
            + "\n"
            + self._quotes_block(quotes)
            + "\n"
            + self._movers_block(gainers, losers, top_n=5)
        )
        if fund:
            msg += (
                "\n<b>📈 Temel:</b> "
                f"AL: {fund.get('al_count',0)}  |  Ort. Pot.: %{fund.get('avg_pot',0):.1f}  |  "
                f"Smart Giriş: {fund.get('smart_giris',0)}\n"
            )
        msg += "\n<b>📰 Son Haberler</b>\n" + self._news_block(news)
        msg += self._footer()
        self.send_message(msg, chat_id=chat_id)

    def _cmd_firsat(self, chat_id: str):
        firsat = self._get_gunun_firsati()
        signal = self._get_action_signal(firsat["kod"] if firsat else None)
        if not firsat:
            self.send_message("⚠️ Fırsat verisi bulunamadı.", chat_id=chat_id)
            return
        msg = (
            self._header("🔥", "Günün Tek Fırsatı", datetime.now().strftime("%d %b %Y"))
            + self._firsat_block(firsat)
            + self._action_signal_block(signal)
            + self._footer("Yatırım tavsiyesi değildir.")
        )
        self.send_message(msg, chat_id=chat_id)

    def _cmd_katilim(self, chat_id: str):
        katilim = self._get_katilim_top(n=5)
        if not katilim:
            self.send_message("⚠️ Katılım verisi bulunamadı.", chat_id=chat_id)
            return
        rows = "\n".join(
            f"  {i}. <code>{k['kod']}</code> {_html.escape(k['ad'][:20])}  "
            f"Pot: <b>%{k['pot']:.1f}</b>  [{k['oneri']}]"
            for i, k in enumerate(katilim, 1)
        )
        msg = (
            self._header("☪️", "Katılım Hisseleri — Top 5", datetime.now().strftime("%d %b %Y"))
            + "\n" + rows + "\n"
            + self._footer("Yatırım tavsiyesi değildir.")
        )
        self.send_message(msg, chat_id=chat_id)

    def _cmd_analiz(self, chat_id: str, symbol: str):
        if not symbol:
            self.send_message("❓ Kullanım: /analiz THYAO", chat_id=chat_id)
            return
        signal = self._get_action_signal(symbol)
        if not signal:
            self.send_message(f"⚠️ <code>{symbol}</code> için veri bulunamadı.", chat_id=chat_id)
            return

        news = []
        try:
            from core.fetcher import NewsFetcher
            news = NewsFetcher.get_isyatirim_research_by_symbol(symbol, limit=3)
        except Exception:
            pass

        prompt = (
            f"{symbol} hissesi analizi. Öneri: {signal['oneri']}. "
            f"Getiri pot.: %{signal['pot']:.1f}. Güven: %{signal['guvenskor']}. "
            f"Gerekçe: {signal['gerekce']}. "
            "3 madde: 1) Neden AL/TUT/SAT, 2) Risk, 3) Giriş stratejisi. "
            "Türkçe, net, yönlendirici."
        )
        ai_text = self._ai_text(prompt, max_tokens=350)

        news_block = ""
        if news:
            news_block = "\n<b>📡 İY Araştırma Notları</b>\n" + self._news_block([
                {"title": n.get("title",""), "url": n.get("url","")} for n in news
            ])

        msg = (
            self._header("🔬", f"{symbol} Detay Analizi", datetime.now().strftime("%d %b %Y %H:%M"))
            + self._action_signal_block(signal)
            + "\n<b>🤖 AI Değerlendirmesi</b>\n" + ai_text
            + news_block
            + self._footer("Yatırım tavsiyesi değildir.")
        )
        self.send_message(msg, chat_id=chat_id)

    def _cmd_izle(self, chat_id: str, args: list):
        """
        /izle THYAO 300.50 280 340 [adet]
        args = [SYMBOL, entry, stop, target, (adet)]
        """
        if len(args) < 4:
            self.send_message("❓ Kullanım: /izle THYAO 300.50 280 340 [adet]", chat_id=chat_id)
            return
        try:
            sym    = args[0].upper()
            entry  = float(args[1].replace(",", "."))
            stop   = float(args[2].replace(",", "."))
            target = float(args[3].replace(",", "."))
            adet   = int(args[4]) if len(args) > 4 else 1
        except ValueError:
            self.send_message("❌ Geçersiz değer. Örnek: /izle THYAO 300.50 280 340", chat_id=chat_id)
            return

        from core.trade_manager import add_trade
        t = add_trade(sym, entry, stop, target, adet, chat_id)
        pot_target = round((target - entry) / entry * 100, 1)
        risk_stop  = round((entry  - stop)  / entry * 100, 1)

        msg = (
            self._header("📍", f"{sym} Takibe Alındı", datetime.now().strftime("%d %b %Y %H:%M"))
            + f"\n  Giriş : <b>{entry:,.2f} ₺</b>"
            + f"\n  Stop  : <b>{stop:,.2f} ₺</b>  (-%{risk_stop:.1f})"
            + f"\n  Hedef : <b>{target:,.2f} ₺</b>  (+%{pot_target:.1f})"
            + f"\n  Adet  : {adet}"
            + f"\n\n<i>Stop veya hedefe ulaştığında seni arayacağım.</i>"
            + self._footer()
        )
        self.send_message(msg, chat_id=chat_id)

    def _cmd_kapat(self, chat_id: str, symbol: str):
        if not symbol:
            self.send_message("❓ Kullanım: /kapat THYAO", chat_id=chat_id)
            return
        from core.trade_manager import close_trade
        t = close_trade(symbol)
        if not t:
            self.send_message(f"⚠️ <code>{symbol}</code> açık işlemde bulunamadı.", chat_id=chat_id)
            return
        pnl = t.get("pnl_pct", 0)
        emoji = "✅" if pnl > 0 else "❌"
        msg = (
            self._header("🏁", f"{symbol} Pozisyon Kapatıldı", datetime.now().strftime("%d %b %Y %H:%M"))
            + f"\n  Giriş   : {t['entry']:,.2f} ₺"
            + f"\n  Kapanış : {t.get('close_price', 0):,.2f} ₺"
            + f"\n  Sonuç   : {emoji} <b>{pnl:+.2f}%</b>"
            + self._footer()
        )
        self.send_message(msg, chat_id=chat_id)

    def _cmd_portfoy(self, chat_id: str):
        from core.bot_portfolio import get_portfolio_with_prices
        from core.trade_manager import get_open_trades, performance_report

        # ── Kalıcı portföy ───────────────────────────────────────────────
        items = get_portfolio_with_prices()
        port_rows = ""
        total_mkt = 0.0
        total_pnl = 0.0
        if items:
            for it in items:
                arr = "▲" if it["pnl_pct"] >= 0 else "▼"
                port_rows += (
                    f"\n  {arr} <code>{it['symbol']:<7}</code>"
                    f"  {it['qty']:.0f} adet"
                    f"  Maliyet:{it['avg_price']:,.2f}"
                    f"  Güncel:{it.get('current_price',0):,.2f}"
                    f"  <b>{it['pnl_pct']:+.1f}%</b>"
                    f"  ({it['pnl_try']:+,.0f}₺)"
                )
                total_mkt += it.get("mkt_val", 0)
                total_pnl += it.get("pnl_try", 0)
            port_rows += (
                f"\n  {'─'*38}"
                f"\n  Toplam Değer: <b>{total_mkt:,.0f} ₺</b>"
                f"  Net P&amp;L: <b>{total_pnl:+,.0f} ₺</b>"
            )
        else:
            port_rows = "\n  — Portföyde hisse yok  (/ekle THYAO 100 300)"

        # ── Aktif takip işlemleri ─────────────────────────────────────────
        open_t = get_open_trades()
        trade_rows = ""
        if open_t:
            for t in open_t:
                last = t.get("last_price", t["entry"])
                pct  = (last - t["entry"]) / t["entry"] * 100
                bar  = "▲" if pct >= 0 else "▼"
                trade_rows += (
                    f"\n  {bar} <code>{t['symbol']:<7}</code>"
                    f"  G:{t['entry']:,.1f} → {last:,.1f}"
                    f"  <b>{pct:+.1f}%</b>"
                    f"  Stop:{t['stop']:,.1f}  Hdf:{t['target']:,.1f}"
                )
        else:
            trade_rows = "\n  — Aktif takip işlemi yok"

        # ── Geçmiş performans ─────────────────────────────────────────────
        perf  = performance_report()
        stats = ""
        if perf.get("total", 0) > 0:
            stats = (
                f"\n\n<b>📊 Geçmiş İşlem Performansı</b>"
                f"\n  İşlem: {perf['total']}  Kazanan: {perf['wins']}  Kaybeden: {perf['losses']}"
                f"\n  Başarı Oranı: <b>%{perf['win_rate']}</b>"
                f"\n  Ort. Kazanç: <b>{perf['avg_win']:+.2f}%</b>"
                f"  Ort. Kayıp: {perf['avg_loss']:+.2f}%"
            )

        msg = (
            self._header("💼", "Portföy Durumu", datetime.now().strftime("%d %b %Y %H:%M"))
            + "\n\n<b>📂 Portföyüm</b>"
            + port_rows
            + "\n\n<b>📈 Aktif İşlem Takipleri</b>"
            + trade_rows
            + stats
            + self._footer("/ekle /kaldir /izle /kapat")
        )
        self.send_message(msg, chat_id=chat_id)

    def _cmd_ekle(self, chat_id: str, args: list):
        """
        /ekle THYAO 100 300.50
        args = [SYMBOL, qty, avg_price]
        """
        if len(args) < 3:
            self.send_message("❓ Kullanım: /ekle THYAO 100 300.50", chat_id=chat_id)
            return
        try:
            sym   = args[0].upper().strip()
            qty   = float(args[1].replace(",", "."))
            price = float(args[2].replace(",", "."))
        except ValueError:
            self.send_message("❌ Geçersiz değer. Örnek: /ekle THYAO 100 300.50", chat_id=chat_id)
            return
        from core.bot_portfolio import add_stock
        item = add_stock(sym, qty, price, chat_id)
        mkt  = round(item["qty"] * item["avg_price"], 2)
        msg  = (
            f"✅ <b>{sym}</b> portföye eklendi\n"
            f"  Adet       : {item['qty']:.0f}\n"
            f"  Ort. Maliyet: {item['avg_price']:,.2f} ₺\n"
            f"  Toplam Maliyet: {mkt:,.0f} ₺\n"
            f"<i>💾 Portföy kalıcı olarak kaydedildi.</i>"
        )
        self.send_message(msg, chat_id=chat_id)

    def _cmd_kaldir(self, chat_id: str, symbol: str):
        if not symbol:
            self.send_message("❓ Kullanım: /kaldir THYAO", chat_id=chat_id)
            return
        from core.bot_portfolio import remove_stock
        ok = remove_stock(symbol)
        if ok:
            self.send_message(f"🗑 <b>{symbol.upper()}</b> portföyden çıkarıldı.", chat_id=chat_id)
        else:
            self.send_message(f"⚠️ <code>{symbol.upper()}</code> portföyünüzde bulunamadı.", chat_id=chat_id)

    def _cmd_alarm(self, chat_id: str, args: list):
        """
        /alarm THYAO 350 yukari
        /alarm THYAO 280 asagi
        """
        if len(args) < 3:
            self.send_message(
                "❓ Kullanım:\n"
                "  /alarm THYAO 350 yukari\n"
                "  /alarm THYAO 280 asagi",
                chat_id=chat_id,
            )
            return
        try:
            sym       = args[0].upper().strip()
            threshold = float(args[1].replace(",", "."))
            raw_dir   = args[2].lower().strip()
            direction = "above" if raw_dir in ("yukari","üstü","above","yüksek","up") else "below"
        except ValueError:
            self.send_message("❌ Geçersiz değer. Örnek: /alarm THYAO 350 yukari", chat_id=chat_id)
            return
        from core.bot_portfolio import add_alarm
        add_alarm(sym, threshold, direction, chat_id)
        arrow = "📈 ≥" if direction == "above" else "📉 ≤"
        self.send_message(
            f"🔔 <b>Alarm kuruldu</b>\n"
            f"  <code>{sym}</code>  {arrow}  <b>{threshold:,.2f} ₺</b>\n"
            f"<i>Seviyeye ulaşıldığında seni arayacağım.</i>",
            chat_id=chat_id,
        )

    def _cmd_alarmlar(self, chat_id: str):
        from core.bot_portfolio import get_active_alarms
        items = get_active_alarms()
        if not items:
            self.send_message("🔔 Aktif alarm yok.\n/alarm THYAO 350 yukari ile ekleyebilirsin.", chat_id=chat_id)
            return
        rows = "\n".join(
            f"  {'📈' if a['direction']=='above' else '📉'} "
            f"<code>{a['symbol']}</code>  "
            f"{'≥' if a['direction']=='above' else '≤'}  "
            f"<b>{a['threshold']:,.2f} ₺</b>"
            for a in items
        )
        msg = (
            self._header("🔔", "Aktif Alarmlarım", f"{len(items)} alarm")
            + "\n" + rows
            + self._footer("/alarmsil THYAO ile sil")
        )
        self.send_message(msg, chat_id=chat_id)

    def _cmd_alarmsil(self, chat_id: str, symbol: str):
        if not symbol:
            self.send_message("❓ Kullanım: /alarmsil THYAO", chat_id=chat_id)
            return
        from core.bot_portfolio import remove_alarm
        n = remove_alarm(symbol)
        if n:
            self.send_message(f"🗑 <code>{symbol.upper()}</code> için {n} alarm silindi.", chat_id=chat_id)
        else:
            self.send_message(f"⚠️ <code>{symbol.upper()}</code> için aktif alarm bulunamadı.", chat_id=chat_id)

    def _cmd_haber(self, chat_id: str, symbol: str = ""):
        self.send_message("📰 Haberler çekiliyor...", chat_id=chat_id)
        try:
            from core.fetcher import NewsFetcher
            if symbol:
                # Hisse bazlı: İY araştırma + genel filtreleme
                iy  = NewsFetcher.get_isyatirim_research_by_symbol(symbol, limit=3)
                gen = [n for n in NewsFetcher.get_latest(limit=50)
                       if symbol.lower() in (n.get("title","") if isinstance(n,dict)
                                             else getattr(n,"title","")).lower()][:3]
                news = [{"title": f"[İY] {n.get('title','')}", "url": n.get("url","")} for n in iy] \
                     + [{"title": n.get("title","") if isinstance(n,dict) else getattr(n,"title",""),
                         "url":   n.get("url","")   if isinstance(n,dict) else getattr(n,"url","")}
                        for n in gen]
                header_title = f"{symbol.upper()} Haberleri"
            else:
                raw  = NewsFetcher.get_latest(limit=8)
                iy   = NewsFetcher.get_isyatirim_research(limit=2)
                news = [{"title": f"[İY] {n.get('title','')}", "url": n.get("url","")} for n in iy] \
                     + [{"title": n.get("title","") if isinstance(n,dict) else getattr(n,"title",""),
                         "url":   n.get("url","")   if isinstance(n,dict) else getattr(n,"url","")}
                        for n in raw]
                header_title = "Son Finansal Haberler"

            if not news:
                self.send_message("⚠️ Haber bulunamadı.", chat_id=chat_id)
                return
            msg = (
                self._header("📰", header_title, datetime.now().strftime("%d %b %Y %H:%M"))
                + "\n"
                + self._news_block(news[:8])
                + self._footer()
            )
            self.send_message(msg, chat_id=chat_id)
        except Exception as e:
            self.send_message(f"⚠️ Haber çekme hatası: {e}", chat_id=chat_id)

    def _cmd_iyarastirma(self, chat_id: str):
        self.send_message("📡 İş Yatırım araştırma notları çekiliyor...", chat_id=chat_id)
        try:
            from core.fetcher import NewsFetcher
            items = NewsFetcher.get_isyatirim_research(limit=6)
            if not items:
                self.send_message("⚠️ Araştırma notu bulunamadı.", chat_id=chat_id)
                return
            news = [{"title": n.get("title",""), "url": n.get("url","")} for n in items]
            msg  = (
                self._header("📡", "İş Yatırım Araştırma Notları",
                             datetime.now().strftime("%d %b %Y %H:%M"))
                + "\n"
                + self._news_block(news)
                + self._footer("arastirma.isyatirim.com.tr")
            )
            self.send_message(msg, chat_id=chat_id)
        except Exception as e:
            self.send_message(f"⚠️ Hata: {e}", chat_id=chat_id)

    def _cmd_kap(self, chat_id: str):
        try:
            kap = self._get_kap_corporate_news(limit=6)
            if not kap:
                self.send_message("⚠️ KAP verisi bulunamadı.", chat_id=chat_id)
                return
            rows = "\n".join(f"  • {_html.escape(str(k))}" for k in kap)
            msg  = (
                self._header("📋", "KAP Özel Durum Açıklamaları",
                             datetime.now().strftime("%d %b %Y %H:%M"))
                + "\n" + rows
                + self._footer("kap.org.tr")
            )
            self.send_message(msg, chat_id=chat_id)
        except Exception as e:
            self.send_message(f"⚠️ Hata: {e}", chat_id=chat_id)

    def _cmd_bist(self, chat_id: str):
        quotes  = self._get_key_quotes()
        gainers, losers = self._get_bist_movers(top_n=5)
        bist    = quotes.get("BIST-100", {})
        pct     = bist.get("pct", 0) or 0
        arrow   = "▲" if pct >= 0 else "▼"
        volatile_note = "\n⚠️ <b>Yüksek volatilite!</b>" if abs(pct) >= 2 else ""
        msg = (
            self._header("📊", "BIST-100 Durumu", datetime.now().strftime("%d %b %Y %H:%M"))
            + f"\n  {arrow} BIST-100: <b>{bist.get('price',0):,.2f}</b>  ({pct:+.2f}%)"
            + volatile_note
            + "\n"
            + self._movers_block(gainers, losers, top_n=5)
            + self._footer()
        )
        self.send_message(msg, chat_id=chat_id)

    def _cmd_doviz(self, chat_id: str):
        try:
            from core.fetcher import PriceFetcher
            syms   = ["USDTRY=X","EURTRY=X","GBPTRY=X","JPYTRY=X","CHFTRY=X"]
            labels = {"USDTRY=X":"USD/TRY","EURTRY=X":"EUR/TRY",
                      "GBPTRY=X":"GBP/TRY","JPYTRY=X":"JPY/TRY","CHFTRY=X":"CHF/TRY"}
            raw    = PriceFetcher.get_bulk_quotes(syms)
            rows   = []
            for sym, lbl in labels.items():
                q = raw.get(sym, {})
                if q and "price" in q:
                    pct   = q.get("change_pct", 0) or 0
                    arrow = "▲" if pct >= 0 else "▼"
                    rows.append(f"  {arrow} <b>{lbl}</b>: {q['price']:.4f}  ({pct:+.2f}%)")
            msg = (
                self._header("💱", "Döviz Kurları", datetime.now().strftime("%d %b %Y %H:%M"))
                + "\n" + "\n".join(rows) + "\n"
                + self._footer()
            )
            self.send_message(msg, chat_id=chat_id)
        except Exception as e:
            self.send_message(f"⚠️ Döviz verisi alınamadı: {e}", chat_id=chat_id)

    def _cmd_altin(self, chat_id: str):
        try:
            from core.gold_fetcher import get_gold_prices, GOLD_LABELS
            from core.fetcher import PriceFetcher

            gold = get_gold_prices()
            src  = gold.get("source", "—")

            # ONS ve kur
            raw      = PriceFetcher.get_bulk_quotes(["GC=F", "SI=F", "USDTRY=X"])
            ons_usd  = raw.get("GC=F", {}).get("price", 0) or 0
            ons_pct  = raw.get("GC=F", {}).get("change_pct", 0) or 0
            usd_try  = raw.get("USDTRY=X", {}).get("price", 0) or 0

            rows = []

            # Türk altın fiyatları (TL)
            order = [
                "gram_altin", "ceyrek_altin", "yarim_altin", "tam_altin",
                "cumhuriyet_altin", "bilezik_22", "has_altin", "gumus_gram",
            ]
            for key in order:
                if key not in gold:
                    continue
                v     = gold[key]
                label = GOLD_LABELS.get(key, (key, ""))[0]
                alis  = v.get("alis", 0)
                satis = v.get("satis", 0)
                deg   = v.get("degisim_pct", 0) or 0
                arrow = "▲" if deg >= 0 else "▼"
                deg_s = f"({arrow}{abs(deg):.2f}%)" if deg != 0 else ""
                rows.append(
                    f"  <b>{label}</b>\n"
                    f"    Alış: <code>{alis:>10,.2f} ₺</code>  "
                    f"Satış: <code>{satis:,.2f} ₺</code>  {deg_s}"
                )

            # ONS / Kur bilgisi
            kur_line = ""
            if ons_usd and usd_try:
                arrow = "▲" if ons_pct >= 0 else "▼"
                kur_line = (
                    f"\n<b>🌍 Uluslararası</b>\n"
                    f"  {arrow} Altın ONS: <b>${ons_usd:,.2f}</b>  ({ons_pct:+.2f}%)\n"
                    f"  USD/TRY: <b>{usd_try:.4f} ₺</b>"
                )

            msg = (
                self._header("🥇", "Altın & Gümüş Fiyatları", datetime.now().strftime("%d %b %Y %H:%M"))
                + f"\n<i>Kaynak: {src}</i>\n\n"
                + "\n".join(rows)
                + kur_line
                + self._footer("haremaltin.com · canlidoviz.com")
            )
            self.send_message(msg, chat_id=chat_id)
        except Exception as e:
            self.send_message(f"⚠️ Altın verisi alınamadı: {e}", chat_id=chat_id)

    def _cmd_kripto(self, chat_id: str):
        try:
            from core.fetcher import PriceFetcher
            syms   = ["BTC-USD","ETH-USD","BNB-USD","SOL-USD","XRP-USD"]
            labels = {"BTC-USD":"Bitcoin","ETH-USD":"Ethereum",
                      "BNB-USD":"BNB","SOL-USD":"Solana","XRP-USD":"XRP"}
            raw    = PriceFetcher.get_bulk_quotes(syms)
            rows   = []
            for sym, lbl in labels.items():
                q = raw.get(sym, {})
                if q and "price" in q:
                    pct   = q.get("change_pct", 0) or 0
                    arrow = "▲" if pct >= 0 else "▼"
                    rows.append(f"  {arrow} <b>{lbl}</b>: ${q['price']:,.2f}  ({pct:+.2f}%)")
            msg = (
                self._header("🪙", "Kripto Para", datetime.now().strftime("%d %b %Y %H:%M"))
                + "\n" + ("\n".join(rows) or "  — veri yok") + "\n"
                + self._footer()
            )
            self.send_message(msg, chat_id=chat_id)
        except Exception as e:
            self.send_message(f"⚠️ Kripto verisi alınamadı: {e}", chat_id=chat_id)

    def _cmd_dunyapiyasa(self, chat_id: str):
        world = self._get_world_indices()
        msg = (
            self._header("🌍", "Küresel Piyasalar", datetime.now().strftime("%d %b %Y %H:%M"))
            + "\n" + ("\n".join(f"  {w}" for w in world) or "  — veri yok") + "\n"
            + self._footer()
        )
        self.send_message(msg, chat_id=chat_id)

    def _cmd_acikislemler(self, chat_id: str):
        from core.trade_manager import get_open_trades
        items = get_open_trades()
        if not items:
            self.send_message("📈 Aktif takip işlemi yok.\n/izle THYAO 300 280 340 ile ekle.", chat_id=chat_id)
            return
        rows = "\n".join(
            f"  {'▲' if (t.get('last_price',t['entry'])-t['entry'])>=0 else '▼'}"
            f" <code>{t['symbol']:<7}</code>"
            f"  G:{t['entry']:,.1f}  Şimdi:{t.get('last_price',t['entry']):,.1f}"
            f"  Stop:{t['stop']:,.1f}  Hdf:{t['target']:,.1f}"
            for t in items
        )
        msg = (
            self._header("📈", "Aktif İşlem Takipleri", f"{len(items)} işlem")
            + "\n" + rows
            + self._footer("/kapat THYAO ile kapat")
        )
        self.send_message(msg, chat_id=chat_id)

    def _cmd_performans(self, chat_id: str):
        from core.trade_manager import performance_report
        perf = performance_report()
        if not perf.get("total"):
            self.send_message("📊 Henüz kapatılmış işlem yok.", chat_id=chat_id)
            return
        msg = (
            self._header("📊", "İşlem Performansı", "Kapatılan işlemler")
            + f"\n  Toplam İşlem  : {perf['total']}"
            + f"\n  Kazanan        : ✅ {perf['wins']}"
            + f"\n  Kaybeden       : ❌ {perf['losses']}"
            + f"\n  Başarı Oranı   : <b>%{perf['win_rate']}</b>"
            + f"\n  Ort. Kazanç    : <b>{perf['avg_win']:+.2f}%</b>"
            + f"\n  Ort. Kayıp     : {perf['avg_loss']:+.2f}%"
            + f"\n  Genel Ort. P&amp;L: <b>{perf['bot_pnl']:+.2f}%</b>"
            + self._footer()
        )
        self.send_message(msg, chat_id=chat_id)

    def _cmd_sorgula(self, chat_id: str, symbol: str):
        """
        /sorgula THYAO — Eleştirel Analiz
        Veriye dayalı zayıf noktaları ve dikkat edilmesi gereken
        faktörleri listeler; aceleci kararları engeller.
        """
        if not symbol:
            self.send_message("❓ Kullanım: /sorgula THYAO", chat_id=chat_id)
            return

        signal = self._get_action_signal(symbol)
        fund   = self._get_fundamental_summary()
        sent   = self._get_news_sentiment_alerts(threshold=50)
        sent_m = next((a for a in sent if a["kod"] == symbol.upper()), None)

        context = f"Öneri: {signal.get('oneri','?')}, Pot: %{signal.get('pot',0):.1f}, Güven: %{signal.get('guvenskor',0)}" if signal else ""
        news_ctx = f"Haber sentiment: %{sent_m['neg_pct']} negatif." if sent_m else "Dikkat çekici negatif haber yok."

        prompt = (
            f"{symbol} hissesi için eleştirel ön analiz. {context}. {news_ctx}. "
            f"Piyasa geneli: AL={fund.get('al_count',0)}, Ort.Pot=%{fund.get('avg_pot',0):.1f}. "
            "Yatırımcının aceleci karar vermemesi için somut verilere dayalı "
            "2 önemli soru veya dikkat noktası belirt. "
            "Her madde kısa ve net olsun. Türkçe."
        )
        self.send_message(f"🔍 <code>{symbol}</code> analiz ediliyor...", chat_id=chat_id)
        ai_text = self._ai_text(prompt, max_tokens=260)

        msg = (
            self._header("🔍", f"{symbol} — Eleştirel Ön Analiz",
                         "Karar vermeden önce değerlendirin")
            + "\n\n" + ai_text
            + self._footer("Yatırım tavsiyesi değildir.")
        )
        self.send_message(msg, chat_id=chat_id)

    def _cmd_risk(self, chat_id: str, symbol: str):
        """
        /risk THYAO — Çok boyutlu risk raporu.
        Değerleme · Yabancı · Haber Sentiment · Öneri · Volatilite
        → Risk notu: Düşük / Orta / Yüksek / Kritik
        """
        if not symbol:
            self.send_message("❓ Kullanım: /risk THYAO", chat_id=chat_id)
            return

        self.send_message(f"🔍 <code>{symbol}</code> risk taraması yapılıyor...", chat_id=chat_id)

        try:
            import pandas as pd

            data_dir = self._latest_data_dir()

            def _read_xlsx(name):
                if not data_dir:
                    return None
                for ext in (".xlsx", ".xls"):
                    p = data_dir / (name + ext)
                    if p.exists():
                        try:
                            df = pd.read_excel(p, sheet_name=0)
                            df.columns = df.columns.str.strip()
                            return df.dropna(how="all").reset_index(drop=True)
                        except Exception:
                            pass
                return None

            def _num(s):
                return pd.to_numeric(
                    s.astype(str).str.replace(",",".",regex=False)
                                 .str.replace(" ","",regex=False)
                                 .str.replace("%","",regex=False),
                    errors="coerce",
                )

            sym = symbol.upper().strip()
            df_takip = _read_xlsx("takipozet")
            df_fin   = _read_xlsx("temelfinansal")
            df_yab   = _read_xlsx("temelyabancioran")
            df_ozet  = _read_xlsx("temelozet")

            risk_items   = []   # (emoji, label, detay, puan 0-3)
            total_risk   = 0
            total_weight = 0

            # ── 1. Öneri Durumu ───────────────────────────────────────────
            if df_takip is not None and "Kod" in df_takip.columns:
                row = df_takip[df_takip["Kod"].astype(str).str.strip().str.upper() == sym]
                if not row.empty:
                    oneri = str(row.iloc[0].get("Öneri","")).upper()
                    pot   = float(_num(row.iloc[0:1].get("Getiri Potansiyeli (%)", pd.Series([0]))).iloc[0] or 0)
                    if "SAT" in oneri:
                        risk_items.append(("🔴", "Öneri", f"SAT — Analist satış tavsiyesi veriyor", 3))
                    elif "TUT" in oneri and pot < 10:
                        risk_items.append(("🟡", "Öneri", f"TUT, düşük potansiyel (%{pot:.0f})", 2))
                    elif "AL" in oneri and pot >= 20:
                        risk_items.append(("🟢", "Öneri", f"AL — Pot. %{pot:.0f}", 0))
                    else:
                        risk_items.append(("🟡", "Öneri", f"{oneri}, pot. %{pot:.0f}", 1))
                    total_weight += 3

            # ── 2. Değerleme (F/K sektör kıyası) ─────────────────────────
            if df_fin is not None and "Kod" in df_fin.columns and "F/K" in df_fin.columns:
                row = df_fin[df_fin["Kod"].astype(str).str.strip().str.upper() == sym]
                if not row.empty:
                    fk = float(_num(row["F/K"]).iloc[0] or 0)
                    sek_fk_mean = float(_num(df_fin["F/K"]).mean() or 15)
                    if fk > 0:
                        premium = (fk - sek_fk_mean) / sek_fk_mean * 100
                        if premium > 50:
                            risk_items.append(("🔴", "Değerleme", f"F/K={fk:.1f} — Sektör ort. %{premium:.0f} pahalı", 3))
                        elif premium > 20:
                            risk_items.append(("🟡", "Değerleme", f"F/K={fk:.1f} — %{premium:.0f} prim", 2))
                        elif fk < 8:
                            risk_items.append(("🟢", "Değerleme", f"F/K={fk:.1f} — Ucuz", 0))
                        else:
                            risk_items.append(("🟢", "Değerleme", f"F/K={fk:.1f} — Makul", 1))
                    total_weight += 3

            # ── 3. Yabancı Yatırımcı Değişimi ─────────────────────────────
            if df_yab is not None and "Kod" in df_yab.columns:
                row = df_yab[df_yab["Kod"].astype(str).str.strip().str.upper() == sym]
                deg_col = next((c for c in df_yab.columns if "Değişim" in c), None)
                if not row.empty and deg_col:
                    deg = float(_num(row[deg_col]).iloc[0] or 0)
                    if deg <= -1.0:
                        risk_items.append(("🔴", "Yabancı", f"Güçlü çıkış: {deg:+.2f}%", 3))
                    elif deg < 0:
                        risk_items.append(("🟡", "Yabancı", f"Hafif çıkış: {deg:+.2f}%", 2))
                    elif deg >= 0.5:
                        risk_items.append(("🟢", "Yabancı", f"Güçlü giriş: {deg:+.2f}%", 0))
                    else:
                        risk_items.append(("🟢", "Yabancı", f"Stabil: {deg:+.2f}%", 1))
                    total_weight += 3

            # ── 4. Haber Sentiment ────────────────────────────────────────
            sent_alerts = self._get_news_sentiment_alerts(threshold=50)
            sent_match  = next((a for a in sent_alerts if a["kod"] == sym), None)
            if sent_match:
                np_ = sent_match["neg_pct"]
                risk_items.append(("🔴" if np_ >= 70 else "🟡",
                                   "Haberler",
                                   f"Negatif oran: %{np_} — {sent_match['titles'][0][:45] if sent_match['titles'] else ''}",
                                   3 if np_ >= 70 else 2))
            else:
                risk_items.append(("🟢", "Haberler", "Dikkat çekici negatif haber yok", 0))
            total_weight += 3

            # ── 5. Piyasa Volatilitesi ────────────────────────────────────
            volatile = self._is_volatile_market()
            if volatile:
                risk_items.append(("🟡", "Piyasa", "BIST volatil — genel baskı var", 2))
            else:
                risk_items.append(("🟢", "Piyasa", "Piyasa normal seyirde", 0))
            total_weight += 2

            # ── Risk Skoru Hesapla ────────────────────────────────────────
            total_risk = sum(i[3] for i in risk_items)
            max_risk   = total_weight   # her kategori max 3
            risk_pct   = round(total_risk / max_risk * 100) if max_risk > 0 else 50

            if risk_pct >= 70:
                risk_label, risk_emoji = "KRİTİK", "🔴"
            elif risk_pct >= 45:
                risk_label, risk_emoji = "YÜKSEK", "🟠"
            elif risk_pct >= 20:
                risk_label, risk_emoji = "ORTA", "🟡"
            else:
                risk_label, risk_emoji = "DÜŞÜK", "🟢"

            bar = "▓" * (risk_pct // 10) + "░" * (10 - risk_pct // 10)

            rows = "\n".join(
                f"  {e} <b>{lbl:<12}</b> {_html.escape(det)}"
                for e, lbl, det, _ in risk_items
            )

            # AI özet
            prompt = (
                f"{sym} risk skoru: {risk_pct}/100 ({risk_label}). "
                f"Risk faktörleri: {[(i[1], i[2]) for i in risk_items]}. "
                "2 cümle: Bu riski yönetmek için yatırımcı ne yapmalı? "
                "Somut, Türkçe."
            )
            ai_text = self._ai_text(prompt, max_tokens=180)

            msg = (
                self._header(risk_emoji, f"{sym} — Risk Raporu", datetime.now().strftime("%d %b %Y %H:%M"))
                + f"\n\n<b>Risk Notu: {risk_emoji} {risk_label}</b>  [{bar}]  {risk_pct}/100\n\n"
                + rows
                + (f"\n\n<b>💡 Tavsiye:</b> {ai_text}" if ai_text else "")
                + self._footer("Yatırım tavsiyesi değildir.")
            )
            self.send_message(msg, chat_id=chat_id)

        except Exception as e:
            logger.error(f"_cmd_risk hatası: {e}")
            self.send_message(f"⚠️ Risk analizi hatası: {e}", chat_id=chat_id)

    def _cmd_balinalar(self, chat_id: str):
        signals = self._get_whale_signals(top_n=5)
        if not signals:
            self.send_message("🐋 Şu an dikkat çekici balina hareketi yok.", chat_id=chat_id)
            return
        def _fmt_whale(s):
            yab_str = f"Yab: <b>{s['yab_deg']:+.2f} pp</b> ({s['yab_bp']:+.0f} baz)"
            hx = s.get("hacim_x")
            hx_str = f"  Hacim: <b>{hx:.1f}x</b>" if hx is not None else ""
            return f"  🐋 <code>{s['kod']}</code>  {yab_str}{hx_str}  [{s['sinyal']}]"
        rows = "\n".join(_fmt_whale(s) for s in signals)
        msg = (
            self._header("🐋", "Balina & Smart Money Alarmları",
                         datetime.now().strftime("%d %b %Y %H:%M"))
            + "\n" + rows
            + self._footer("Yabancı oranı artışı + anormal hacim tespit edildi.")
        )
        self.send_message(msg, chat_id=chat_id)

    def _cmd_sektor(self, chat_id: str):
        rot = self._get_sector_rotation()
        if not rot:
            self.send_message("⚠️ Sektör verisi bulunamadı.", chat_id=chat_id)
            return
        rows = "\n".join(
            f"  {'🟢' if s['net']>0 else '🔴'} <b>{s['sektor']}</b>  "
            f"AL:{s['al']} TUT:{s['tut']} SAT:{s['sat']}  "
            f"Pot: %{s['avg_pot']:.1f}  Güç: <b>{s['skor']:.0f}</b>"
            for s in rot[:6]
        )
        top = rot[0] if rot else {}
        msg = (
            self._header("🏭", "Sektör Rotasyon Sinyali",
                         datetime.now().strftime("%d %b %Y %H:%M"))
            + "\n" + rows
            + (f"\n\n💡 <b>Öne çıkan sektör:</b> {top.get('sektor','')}  "
               f"(Güç skoru: {top.get('skor',0):.0f})" if top else "")
            + self._footer()
        )
        self.send_message(msg, chat_id=chat_id)

    def _cmd_panic(self, chat_id: str):
        quotes  = self._get_key_quotes()
        gainers, losers = self._get_bist_movers(top_n=10)
        fund    = self._get_fundamental_summary()
        katilim = self._get_katilim_top(n=3)

        bist = quotes.get("BIST-100", {})
        bist_pct = bist.get("pct", 0) or 0

        prompt = (
            "ACIL DURUM RAPORU. "
            f"BIST-100: {bist_pct:+.2f}%. "
            f"En çok düşenler: {losers[:5]}. "
            f"Katılım: {katilim}. "
            "Şunu ver: 1) Mevcut durumun 1 cümle özeti, "
            "2) Stop-loss dikkate alınması gereken 3 hisse, "
            "3) Dipten alım için beklenen 2 hisse, "
            "4) Genel strateji notu. Türkçe, acil, net."
        )
        ai_text = self._ai_text(prompt, max_tokens=400)

        sat_count = fund.get("sat_count", 0)
        al_count  = fund.get("al_count",  0)

        msg = (
            self._header("🚨", "PANİK MODU — Acil Durum Raporu",
                         datetime.now().strftime("%d %b %Y %H:%M"))
            + "\n"
            + self._quotes_block(quotes)
            + "\n"
            + self._movers_block(gainers, losers, top_n=5)
            + f"\n<b>📊 Temel:</b> AL: {al_count}  |  SAT: {sat_count}  |  "
              f"Ort. Pot.: %{fund.get('avg_pot',0):.1f}\n"
            + "\n<b>🤖 AI Acil Değerlendirme</b>\n" + ai_text
            + self._footer("Yatırım tavsiyesi değildir. Panikle işlem yapmayın.")
        )
        self.send_message(msg, chat_id=chat_id)


# ─── Global Instance ──────────────────────────────────────────────────────────

bot = TelegramBot()


if __name__ == "__main__":
    bot.send_message("🚀 <b>FinSentinel Akıllı Bot Servisi Başlatıldı.</b>")
