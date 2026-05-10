# 📊 FinSentinel — AI-Powered Financial Intelligence Platform

> Türkiye piyasalarına odaklı, yapay zeka destekli kapsamlı finansal izleme ve analiz platformu.
> Python · Streamlit · Google Gemini AI · TCMB EVDS API · yfinance · CoinGecko

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat&logo=python&logoColor=white)](https://python.org)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.x-FF4B4B?style=flat&logo=streamlit&logoColor=white)](https://streamlit.io)
[![Gemini](https://img.shields.io/badge/Google-Gemini%20AI-4285F4?style=flat&logo=google&logoColor=white)](https://aistudio.google.com)

---

## ✨ Özellikler

| Modül | Açıklama | Durum |
|-------|----------|-------|
| 📈 **Piyasa Özeti** | BIST, Forex, Kripto — tek ekranda anlık tablo | ✅ |
| 🏦 **BIST Analizi** | Hisse senedi detay, teknik göstergeler (RSI, MACD, Bollinger) | ✅ |
| 💱 **Forex / Pariteler** | USD/TRY, EUR/TRY ve dünya pariteleri | ✅ |
| 🪙 **Kripto** | CoinGecko entegrasyonu, top 100 + özel takip listesi | ✅ |
| 🥇 **Emtia** | Altın, gümüş, petrol gerçek zamanlı | ✅ |
| 🌍 **Dünya Borsaları** | NYSE, NASDAQ, DAX, FTSE ve diğerleri | ✅ |
| 📉 **Teknik Analiz** | SMA, EMA, RSI, MACD, Bollinger Bands, hacim | ✅ |
| 🏛️ **TCMB Makro** | EVDS API — enflasyon, faiz, rezervler, döviz kuru | ✅ |
| 📰 **Haberler** | RSS akışları — Borsa İstanbul, Reuters TR | ✅ |
| 🤖 **AI Asistan** | Google Gemini ile doğal dil finansal analiz | ✅ |
| 💼 **Portföy Takip** | Maliyet bazlı P&L, çeşitlendirme analizi | 🔨 |
| 🔔 **Alarmlar** | Fiyat/gösterge bazlı alarm + Telegram bildirimi | ✅ |

---

## 🏗️ Mimari

```
finsentinel/
├── app.py                    # Streamlit giriş noktası
├── config/
│   └── settings.py           # Merkezi konfigürasyon (.env tabanlı)
├── core/
│   ├── db.py                 # SQLite veritabanı katmanı
│   ├── fetcher.py            # Veri çekici (yfinance, CoinGecko, TCMB EVDS)
│   ├── scheduler.py          # APScheduler — arka plan görevleri
│   └── ai_engine.py          # Gemini AI entegrasyonu
├── pages/
│   ├── 01_market_overview.py
│   ├── 02_bist.py
│   ├── 03_forex.py
│   ├── 04_crypto.py
│   ├── 05_commodities.py
│   ├── 06_world_markets.py
│   ├── 07_chart_analysis.py
│   ├── 08_macro.py            # TCMB EVDS entegrasyonu
│   ├── 09_news.py
│   ├── 10_ai_assistant.py
│   ├── 11_portfolio.py
│   ├── 12_alerts.py
│   ├── 13_education.py
│   └── 14_settings.py
├── utils/
│   └── ui.py                 # Paylaşılan Plotly grafik bileşenleri
└── data/
    └── finsentinel.db         # SQLite (otomatik oluşur, git'e eklenmez)
```

---

## 🚀 Kurulum

```bash
git clone https://github.com/hasansaldiran/finsentinel.git
cd finsentinel
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
streamlit run app.py
```

---

## 🔑 API Anahtarları

| Servis | Kaynak | Ücret |
|--------|--------|-------|
| Google Gemini | [aistudio.google.com](https://aistudio.google.com/app/apikey) | Ücretsiz tier |
| TCMB EVDS | [evds2.tcmb.gov.tr](https://evds2.tcmb.gov.tr) | Ücretsiz |
| CoinGecko | [coingecko.com/api](https://www.coingecko.com/api) | Ücretsiz tier |
| Telegram Bot | @BotFather | Ücretsiz |

> Tüm anahtarlar `.env` dosyasına yazılır — kaynak koda ve git geçmişine **asla** eklenmez.

---

## 🛡️ Güvenlik

- `.env` dosyası `.gitignore`'da — tüm gizli anahtarlar orada kalır
- Şifreler kaynak kodda plaintext değil, SHA-256 hash olarak işlenir
- Dışarıya açılırken `APP_PASSWORD` ile oturum koruması aktif edilebilir

---

## ⚠️ Yasal Uyarı

Kişisel kullanım ve eğitim amaçlıdır. Sağlanan analizler ve yapay zeka yorumları **yatırım tavsiyesi değildir**.

---

## 👤 Geliştirici

**Hasan Saldıran** — IT Sistemleri & Güvenlik Uzmanı

[![LinkedIn](https://img.shields.io/badge/LinkedIn-hasansaldiran-0A66C2?style=flat&logo=linkedin)](https://linkedin.com/in/hasansaldiran)
[![Portfolio](https://img.shields.io/badge/Portfolio-hasansaldiran.github.io-222?style=flat&logo=github)](https://hasansaldiran.github.io)
