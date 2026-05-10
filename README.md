# 📊 FinSentinel — AI-Powered Financial Intelligence Platform

> Türkiye piyasalarına odaklı, yapay zeka destekli kapsamlı finansal izleme ve analiz platformu.
> Built with Python · Streamlit · Google Gemini AI · TCMB EVDS API · yfinance · TEFAS

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat&logo=python&logoColor=white)](https://python.org)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.x-FF4B4B?style=flat&logo=streamlit&logoColor=white)](https://streamlit.io)
[![License](https://img.shields.io/badge/License-Personal%20Use-lightgrey)](LICENSE)

---

## 🖼️ Ekran Görüntüleri

> *Dashboard ekran görüntüleri yakında eklenecek.*

---

## ✨ Özellikler

| Modül | Açıklama | Durum |
|-------|----------|-------|
| 📈 **Piyasa Özeti** | BIST, Forex, Kripto — tek ekranda anlık tablo | ✅ |
| 🏦 **BIST Analizi** | Hisse senedi detay, teknik göstergeler (RSI, MACD, Bollinger) | ✅ |
| 💱 **Forex / Pariteler** | USD/TRY, EUR/TRY ve dünya pariteleri | ✅ |
| 🪙 **Kripto** | CoinGecko entegrasyonu, top 100 + özel takip listesi | ✅ |
| 🥇 **Emtia** | Altın, gümüş, petrol, bakır gerçek zamanlı | ✅ |
| 🌍 **Dünya Borsaları** | NYSE, NASDAQ, DAX, FTSE ve diğerleri | ✅ |
| 📉 **Teknik Analiz** | Grafik motoru: SMA, EMA, RSI, MACD, BB, hacim | ✅ |
| 🏛️ **TCMB Makro** | EVDS API — enflasyon, faiz, rezervler, döviz kuru | ✅ |
| 📰 **Haberler** | RSS akışları — Borsa İstanbul, Reuters TR | ✅ |
| 🤖 **AI Asistan** | Google Gemini API ile doğal dil finansal analiz | ✅ |
| 💼 **Portföy Takip** | Maliyet bazlı P&L, çeşitlendirme analizi | 🔨 |
| 🔔 **Alarmlar** | Fiyat/gösterge bazlı alarm + Telegram bildirimi | ✅ |
| 📚 **Eğitim** | Kavram sözlüğü, strateji rehberleri | 🔨 |

---

## 🏗️ Mimari

```
finsentinel/
├── app.py                    # Ana giriş noktası (Streamlit)
├── config/
│   └── settings.py           # Merkezi konfigürasyon
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
    ├── finsentinel.db         # SQLite (otomatik oluşur)
    └── processed/
```

---

## 🚀 Kurulum

### Gereksinimler
- Python 3.10+
- pip

### 1. Repoyu klonla
```bash
git clone https://github.com/hasansaldiran/finsentinel.git
cd finsentinel
```

### 2. Sanal ortam oluştur
```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux / macOS
source venv/bin/activate
```

### 3. Bağımlılıkları yükle
```bash
pip install -r requirements.txt
```

### 4. API anahtarlarını ayarla
```bash
cp .env.example .env
# .env dosyasını düzenle
```

| Değişken | Servis | Ücret |
|----------|--------|-------|
| `GEMINI_API_KEY` | [Google AI Studio](https://aistudio.google.com) | Ücretsiz tier |
| `TCMB_API_KEY` | [TCMB EVDS](https://evds2.tcmb.gov.tr) | Ücretsiz |
| `COINGECKO_API_KEY` | [CoinGecko](https://www.coingecko.com/api) | Ücretsiz tier |
| `TELEGRAM_BOT_TOKEN` | @BotFather | Ücretsiz |

> **Not:** API anahtarları olmadan da temel özellikler çalışır (`yfinance` + CoinGecko ücretsiz tier).

### 5. Uygulamayı başlat
```bash
streamlit run app.py
```
Tarayıcıda → `http://localhost:8501`

---

## 🛡️ Güvenlik

- `.env` dosyasını **asla** git'e ekleme — `.gitignore`'da zaten mevcut
- Dışarıya açarken `APP_PASSWORD` ile şifre koruması aktif et
- Ngrok / Cloudflare URL'ini yalnızca güvendiğin kişilerle paylaş

---

## ⚠️ Yasal Uyarı

Bu platform kişisel kullanım ve eğitim amaçlıdır. Sağlanan analizler ve yapay zeka yorumları **yatırım tavsiyesi değildir**. Yatırım kararlarınızda lisanslı bir finansal danışmana başvurun.

---

## 👤 Geliştirici

**Hasan Saldıran** — BT Sistemleri & Güvenlik Uzmanı

[![LinkedIn](https://img.shields.io/badge/LinkedIn-hasansaldiran-0A66C2?style=flat&logo=linkedin)](https://linkedin.com/in/hasansaldiran)
[![Portfolio](https://img.shields.io/badge/Portfolio-hasansaldiran.github.io-222?style=flat&logo=github)](https://hasansaldiran.github.io)
[![GitHub](https://img.shields.io/badge/GitHub-hasansaldiran-181717?style=flat&logo=github)](https://github.com/hasansaldiran)
