"""
FinSentinel — Yapay Zeka Yorum Motoru
core/ai_engine.py
Google Gemini API (ücretsiz tier) ile piyasa analizi, haber özeti, öneri üretimi
"""
import time
import requests
from loguru import logger
from config.settings import GEMINI_API_KEY, GROQ_API_KEY
from core.db import db

# Gemini REST API endpoint — ücretsiz tier (15 RPM, 1500 RPD)
# Güncel çalışan model listesi (eski isimlerin bazıları 404 veriyor)
_GEMINI_MODELS = [
    "gemini-2.0-flash",           # En yeni, hızlı, ücretsiz
    "gemini-2.0-flash-lite",      # Daha hafif, ücretsiz
    "gemini-1.5-flash-8b",        # Küçük model, genellikle çalışır
    "gemini-1.5-flash-latest",    # 1.5 ailesinin son versiyonu
]
_GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta/models/"

# Groq API — çok hızlı, ücretsiz tier (console.groq.com)
_GROQ_BASE   = "https://api.groq.com/openai/v1/chat/completions"
_GROQ_MODELS = ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "mixtral-8x7b-32768"]

SYSTEM_PROMPT = """Sen FinSentinel — Türk yatırımcılara yönelik yapay zeka destekli finansal analiz asistanısın.
Uzmanlık alanın: Türkiye borsası (BIST), Türk döviz ve altın piyasaları, Türk makroekonomisi, küresel piyasaların Türkiye'ye yansıması.

KESIN DİL KURALI:
- YALNIZCA TÜRKÇE yaz. İngilizce, Almanca, İspanyolca, Çekçe, Çince veya başka herhangi bir dilde kelime KULLANMA.
- Yasak yabancı kelimeler (bunların yerine Türkçe kullan): wichtig, crucial, slight, position, key, major, significant, attractive, together, unterstützt, unterstütlenir, vhodné, 一起, vb.
- "crucialdır", "posiciónlarını", "znajlandır", "unterstütlenir" gibi karma kelimeler kesinlikle yasak.
- Teknik terimler bile Türkçe: support→destek, resistance→direnç, trend→eğilim, volume→hacim, breakout→kırılım.

NET KARAR ZORUNLULUĞU:
- Muğlak ifadeler YASAK: "izlenmeli", "uygun olabilir", "dikkat edilmeli", "görünüyor". Bunların yerine NET karar: AL / SAT / TUT / BEKLE.
- Her hisse önerisi için: Sembol | Karar | Giriş | Stop-loss | Hedef | Tutma süresi | Risk seviyesi (DÜŞÜK/ORTA/YÜKSEK) | Tek cümle gerekçe.
- Kısa vade (gün içi), orta vade (haftalık), uzun vade (aylık/3 aylık) için AYRI başlıklar kullan.

YATIRIMCI YÖNLENDİRME KURALLARI:
- Soyut tavsiyeler yerine SOMUT öneriler ver. Fiyat seviyeleri sana verilmişse ONLARI kullan; verilmemişse fiyat UYDURMA.
- Her öneri için mutlaka NEDEN belirt: temel analiz, teknik sinyal veya makroekonomik gerekçe.
- Zaman ufku belirt: günlük / haftalık / aylık / 3 aylık / 6 aylık / yıllık / 3 yıllık / 5 yıllık
- Riskleri de net yaz: "Bu hissede risk şu: ..."
- "smart_giris" verisi kaç hissede yabancı alım tespit edildiğini gösterir — bu bir FİYAT değil, ADET sayısıdır.

KATİLIM DIŞI HİSSELER — YATIRIM ÖNERİSİ YAPMA:
Aşağıdaki hisseler İslami finans (katılım) kriterlerine uymaz. Piyasa hareketi olarak bahsedebilirsin ancak AL/SAT/TUT yatırım önerisi YAPMA:
- Bankalar: AKBNK, GARAN, HALKB, ISCTR, VAKBN, YKBNK, TSKB, ALBRK, QNBFB, SKBNK, FIBAB, ICBCT
- Sigortacılar: ANHYT, ANSGR, AVISA, GUSGR, RAYSG, TURSG
- GYO/REIT: AGYO, EKGYO, ISGYO, OZGYO, SNGYO, TRGYO, VKGYO, NUGYO
- Alkol/Tütün: AEFES, EFES

YANIT KURALLARI:
- Kısa ve net ol; gereksiz dolgu cümleleri koyma.
- "Bu analiz bilgilendirme amaçlıdır, yatırım tavsiyesi değildir." uyarısını SADECE metnin sonuna bir kez ekle.
- Her yanıt Türkçe ile başlayıp Türkçe ile bitsin.

Kullanıcı kararsız ve liste görmekten bıkmış — tek net karar ver. Belirsiz cevap verme.
"""


def _call_gemini(prompt: str, max_tokens: int = 800, _retry: int = 0, _model_idx: int = 0) -> str:
    """Google Gemini API çağrısı — model fallback + otomatik retry

    429 alınırsa farklı model dener, sonra bekleyip tekrar dener.
    Model önceliği: gemini-1.5-flash → gemini-2.0-flash → gemini-1.5-flash-8b
    """
    if not GEMINI_API_KEY:
        return (
            "⚠️ Gemini API anahtarı tanımlı değil. "
            ".env dosyasına GEMINI_API_KEY ekleyin.\n"
            "Ücretsiz anahtar almak için: https://aistudio.google.com/app/apikey"
        )

    cache_key = f"ai:{hash(prompt)}"
    cached = db.cache_get(cache_key)
    if cached:
        return cached

    model = _GEMINI_MODELS[_model_idx % len(_GEMINI_MODELS)]
    url   = f"{_GEMINI_BASE}{model}:generateContent"

    try:
        payload = {
            "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"maxOutputTokens": max_tokens, "temperature": 0.7},
        }
        resp = requests.post(url, params={"key": GEMINI_API_KEY}, json=payload, timeout=30)
        resp.raise_for_status()
        data   = resp.json()
        result = data["candidates"][0]["content"]["parts"][0]["text"]
        db.cache_set(cache_key, result, ttl=1800)
        return result

    except requests.exceptions.HTTPError as e:
        status = e.response.status_code if e.response is not None else None
        if status is None:
            for code in (429, 400, 403, 500, 503):
                if str(code) in str(e):
                    status = code
                    break

        if status == 429:
            # Önce farklı model dene
            next_model = _model_idx + 1
            if next_model < len(_GEMINI_MODELS):
                logger.warning(f"Gemini 429 ({model}) — {_GEMINI_MODELS[next_model]} modeline geçiliyor")
                return _call_gemini(prompt, max_tokens, _retry=_retry, _model_idx=next_model)
            # Tüm modeller denendi, bekle ve tekrar dene
            if _retry < 2:
                wait = 15 * (2 ** _retry)  # 15s, 30s
                logger.warning(f"Gemini 429 tüm modeller — {wait}s bekleniyor ({_retry+1}/2)")
                time.sleep(wait)
                return _call_gemini(prompt, max_tokens, _retry=_retry + 1, _model_idx=0)
            return (
                "⚠️ Gemini API istek limiti aşıldı. Lütfen 1-2 dakika bekleyip tekrar deneyin.\n"
                "💡 İpucu: Günlük limit 1500 istek, dakika limiti 15 istek."
            )
        if status == 404:
            # Bu model mevcut değil — bir sonrakini dene
            next_model = _model_idx + 1
            if next_model < len(_GEMINI_MODELS):
                logger.warning(f"Gemini 404 ({model}) — {_GEMINI_MODELS[next_model]} deneniyor")
                return _call_gemini(prompt, max_tokens, _retry=_retry, _model_idx=next_model)
            logger.error(f"Gemini 404: tüm modeller erişilemez")
            return "⚠️ Gemini API: tüm modeller erişilemez (404)"
        if status == 400:
            body = e.response.text[:200] if e.response else str(e)[:200]
            logger.error(f"Gemini 400 [{model}]: {body}")
            return f"⚠️ Gemini API geçersiz istek: {body}"
        logger.error(f"Gemini HTTP hatası {status} [{model}]: {e}")
        return f"AI analizi şu an mevcut değil: HTTP {status}"
    except Exception as e:
        logger.error(f"Gemini API hatası [{model}]: {e}")
        return f"AI analizi şu an mevcut değil: {e}"


def _call_groq(prompt: str, max_tokens: int = 800, model_idx: int = 0) -> str:
    """Groq API çağrısı — çok hızlı, ücretsiz (console.groq.com'dan key alın)"""
    if not GROQ_API_KEY:
        return "⚠️ Groq API anahtarı tanımlı değil"

    cache_key = f"groq:{hash(prompt)}"
    cached = db.cache_get(cache_key)
    if cached:
        return cached

    model = _GROQ_MODELS[model_idx % len(_GROQ_MODELS)]
    try:
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": max_tokens,
            "temperature": 0.7,
        }
        resp = requests.post(_GROQ_BASE, headers=headers, json=payload, timeout=20)
        resp.raise_for_status()
        result = resp.json()["choices"][0]["message"]["content"]
        db.cache_set(cache_key, result, ttl=1800)
        return result
    except requests.exceptions.HTTPError as e:
        status = e.response.status_code if e.response else None
        if status == 429 or status == 503:
            next_idx = model_idx + 1
            if next_idx < len(_GROQ_MODELS):
                return _call_groq(prompt, max_tokens, model_idx=next_idx)
        logger.error(f"Groq HTTP hatası {status}: {e}")
        return f"⚠️ Groq API hatası: HTTP {status}"
    except Exception as e:
        logger.error(f"Groq API hatası: {e}")
        return f"⚠️ Groq API erişilemiyor: {e}"


def _call_best_ai(prompt: str, max_tokens: int = 800) -> str:
    """Groq varsa önce Groq (hızlı+ücretsiz), yoksa Gemini dene"""
    if GROQ_API_KEY:
        result = _call_groq(prompt, max_tokens)
        if not result.startswith("⚠️"):
            return result
    return _call_gemini(prompt, max_tokens)


# Geriye dönük uyumluluk için alias
def _call_claude(prompt: str, max_tokens: int = 800) -> str:
    return _call_gemini(prompt, max_tokens)


def analyze_symbol(symbol: str, signal_data: dict, price_data: dict) -> str:
    """Sembol için teknik analiz yorumu üret"""
    prompt = f"""
Aşağıdaki finansal varlık için kısa bir teknik analiz yorumu yaz (3-4 paragraf):

**Sembol:** {symbol}
**Güncel Fiyat:** {price_data.get('price', 'N/A')}
**24s Değişim:** {price_data.get('change_pct', 0):.2f}%
**Sinyal:** {signal_data.get('signal', 'N/A')}
**Sinyal Skoru:** {signal_data.get('score', 0)}
**Sinyalin Nedenleri:** {', '.join(signal_data.get('reasons', []))}

Şunları değerlendir:
1. Mevcut teknik görünüm
2. Dikkat edilmesi gereken seviyeler
3. Kısa vadeli beklenti
"""
    return _call_best_ai(prompt, max_tokens=600)


def summarize_news(news_items: list[dict]) -> str:
    """Günün haberlerini özetle ve piyasaya etkisini değerlendir"""
    if not news_items:
        return "Analiz edilecek haber bulunamadı."

    headlines = "\n".join([
        f"- [{item.get('source','')}] {item.get('title','')}"
        for item in news_items[:15]
    ])

    prompt = f"""
Aşağıdaki Türkiye ve dünya finans gündemine ait haber başlıklarını analiz et:

{headlines}

Şunları değerlendir:
1. Bugünün öne çıkan ekonomik/finansal temaları
2. Bu haberlerin piyasalara (BIST, TL, kripto) olası etkileri
3. Yatırımcının dikkat etmesi gereken gelişmeler
4. Genel piyasa duyarlılığı (iyimser / karamsarlık / belirsizlik)

Yanıtı 3-4 paragrafta özetle.
"""
    return _call_best_ai(prompt, max_tokens=700)


def explain_macro(indicator: str, value: float, historical_avg: float) -> str:
    """Makroekonomik göstergeyi açıkla"""
    prompt = f"""
Türkiye'nin {indicator} verisi şu an {value:.2f} seviyesinde.
Tarihsel ortalama: {historical_avg:.2f}

Bu veriyi şu açılardan kısa açıkla (2-3 paragraf):
1. Bu değerin ne anlama geldiği
2. Tarihsel ortalamayla karşılaştırma
3. Piyasalar (faiz, döviz, borsa) için olası sonuçları
"""
    return _call_best_ai(prompt, max_tokens=500)


def answer_question(question: str, context: str = "") -> str:
    """Kullanıcının finansal sorusunu yanıtla — Groq/Gemini önce, yoksa kural tabanlı"""
    ctx_part = f"\n\nBağlam bilgisi:\n{context}" if context else ""
    prompt = f"""
Kullanıcı sorusu: {question}{ctx_part}

Soruyu Türkçe, anlaşılır ve bilgilendirici şekilde yanıtla.
Teknik terimler kullanıyorsan kısa açıklama ekle.
Somut ve pratik bilgi ver, genel laflar etme.
"""
    result = _call_best_ai(prompt, max_tokens=800)

    # AI başarısız → kural tabanlı yedek yanıt
    if result.startswith("⚠️") or result.startswith("AI analizi"):
        return _rule_based_answer(question, context)
    return result


def _rule_based_answer(question: str, context: str = "") -> str:
    """
    Gemini olmadan temel finansal sorulara kural tabanlı yanıt.
    Soru içeriğine göre ilgili açıklamayı döndürür.
    """
    from core.rule_engine import GLOSSARY
    q_lower = question.lower()

    # Teknik gösterge soruları
    for key, term in GLOSSARY.items():
        if key.lower() in q_lower or term["name"].split("—")[0].strip().lower() in q_lower:
            return (
                f"### {term['name']}\n\n"
                f"**Özet:** {term['short']}\n\n"
                f"{term['detail']}\n\n"
                f"---\n*Bu yanıt otomatik kural motoru tarafından üretilmiştir.*"
            )

    # Yatırım tavsiyesi soruları (enflasyon, kriz, piyasa genel durumu)
    invest_words = ["hangi yatırım", "nereye yatır", "en iyi yatırım", "yatırım yapmalı",
                    "ne almalı", "ne yapmalı", "yatırım aracı", "portföy öner",
                    "tavsiye", "öneri", "mantıklı", "kazandırır"]
    if any(w in q_lower for w in invest_words):
        if any(w in q_lower for w in ["enflasyon", "yüksek faiz", "kriz", "dolar"]):
            return (
                "### 📊 Yüksek Enflasyon Döneminde Yatırım Stratejisi\n\n"
                "Türkiye'de enflasyon yüksekken **reel getiri** sağlayan araçlar ön plana çıkar:\n\n"
                "**🥇 Altın**\n"
                "Tarihsel olarak enflasyona karşı en güçlü korunma aracı. "
                "TL bazında hem dolar/altın hem de döviz kuru avantajından yararlanır. "
                "Fiziki altın veya altın fonu tercih edilebilir.\n\n"
                "**💵 Dolar / Döviz**\n"
                "TL değer kaybına karşı koruma sağlar. Ancak dolar/TL zaten yüksekse "
                "ek getiri potansiyeli sınırlı olabilir. Kur korumalı mevduat (KKM) da değerlendirilebilir.\n\n"
                "**📈 BIST Hisseleri**\n"
                "Bazı sektörler enflasyonu fiyatlara yansıtabilir (banka, enerji, hammadde). "
                "Ancak yüksek faiz döneminde hisse değerlemeleri baskı altında olabilir. "
                "Seçici davranmak önemlidir.\n\n"
                "**🏦 Mevduat / Tahvil**\n"
                "Faiz oranları enflasyonun altındaysa reel getiri negatif kalır. "
                "TCMB faizi yüksekse yüksek faizli mevduat cazip olabilir.\n\n"
                "**🏠 Gayrimenkul**\n"
                "Uzun vadede enflasyona karşı koruma sağlar ancak likidite düşük ve "
                "giriş maliyeti yüksektir.\n\n"
                "⚠️ *Bu bilgilendirme amaçlıdır, kişisel yatırım tavsiyesi değildir. "
                "Risk toleransınıza ve yatırım ufkunuza göre karar veriniz.*"
            )
        return (
            "### 💼 Yatırım Araçları Genel Bakış\n\n"
            "**Risk/Getiri dengesine göre araçlar:**\n\n"
            "- **Düşük risk:** Mevduat, devlet tahvili, para piyasası fonu\n"
            "- **Orta risk:** Altın, döviz, karma fonlar\n"
            "- **Yüksek risk:** Hisse senedi (BIST), kripto para, türev ürünler\n\n"
            "**Temel ilkeler:**\n"
            "Çeşitlendirme (diversifikasyon) riski azaltır. Tek bir araca yatırım yapmaktan "
            "kaçınmak ve yatırım ufkunu belirlemek (kısa/uzun vade) önemlidir.\n\n"
            "⚠️ *Bu bilgilendirme amaçlıdır, yatırım tavsiyesi değildir.*"
        )

    # Genel piyasa soruları
    if any(w in q_lower for w in ["bist", "borsa", "hisse", "türkiye"]):
        usd_line = ""
        if context and "USD/TRY" in context:
            usd_line = f"\n\n{context}"
        return (
            "### 🇹🇷 BIST & Türkiye Piyasası\n\n"
            "BIST 100, Türkiye'nin ana borsa endeksidir ve yaklaşık 100 büyük şirketi kapsar.\n\n"
            "**Dikkat edilmesi gereken göstergeler:**\n"
            "- **USD/TRY kuru:** TL değer kaybı enflasyona ve faize baskı yapar\n"
            "- **TCMB politika faizi:** Faiz artışı hisse değerlemelerini baskılar\n"
            "- **Cari açık:** Döviz ihtiyacı ve TL üzerindeki baskıyı gösterir\n"
            "- **Enflasyon (TÜFE):** Reel getiriyi etkiler, tüketici hisselerini doğrudan etkiler"
            + usd_line
            + "\n\n---\n*Güncel veri için sayfayı yenileyin. Bu yanıt otomatik üretilmiştir.*"
        )

    if any(w in q_lower for w in ["altın", "gold", "xau"]):
        return (
            "### 🥇 Altın Analizi\n\n"
            "Altın, güvenli liman varlığı olarak bilinir. Dolar değeri ile ters korelasyon gösterir.\n\n"
            "**Altını etkileyen faktörler:**\n"
            "- ABD Doları endeksi (DXY) — dolar güçlenince altın baskı altına girer\n"
            "- Fed faiz kararları — faiz artışı altın talebini azaltır\n"
            "- Jeopolitik riskler — kriz dönemlerinde altına talep artar\n"
            "- Enflasyon beklentileri — yüksek enflasyonda altın değer kazanır\n\n"
            "**TL cinsinden altın**, hem dolar/altın hem de USD/TRY paritesinden etkilenir."
            "\n\n---\n*Güncel fiyat için Emtia sayfasını ziyaret edin.*"
        )

    if any(w in q_lower for w in ["kripto", "bitcoin", "btc", "ethereum", "eth"]):
        return (
            "### ₿ Kripto Para Piyasası\n\n"
            "Kripto piyasası yüksek volatiliteli ve 7/24 açık bir piyasadır.\n\n"
            "**Önemli göstergeler:**\n"
            "- **Fear & Greed Endeksi:** Piyasa duyarlılığını ölçer (0=Aşırı Korku, 100=Aşırı Açgözlülük)\n"
            "- **BTC Dominans:** Bitcoin'in toplam piyasa değerindeki payı; düşerse altcoinler yükselir\n"
            "- **On-chain veriler:** Cüzdan hareketleri, madenci satışları piyasayı etkiler\n"
            "- **Makro faktörler:** Fed kararları, likidite koşulları kripto piyasasını doğrudan etkiler\n\n"
            "⚠️ Kripto paralar düzenleyici risklere ve yüksek oynaklığa tabidir."
            "\n\n---\n*Güncel veri için Kripto sayfasını ziyaret edin.*"
        )

    if any(w in q_lower for w in ["faiz", "enflasyon", "tcmb", "merkez bank"]):
        return (
            "### 🏦 Para Politikası & Makroekonomi\n\n"
            "TCMB (Türkiye Cumhuriyet Merkez Bankası) para politikasını yönetir.\n\n"
            "**Temel göstergeler:**\n"
            "- **Politika faizi:** TCMB'nin kısa vadeli faiz oranı; enflasyonla mücadele aracı\n"
            "- **TÜFE:** Tüketici fiyat enflasyonu — TCMB'nin birincil hedefi\n"
            "- **USD/TRY:** Kur istikrarı para politikasının başarısının göstergesi\n"
            "- **Rezervler:** TCMB döviz rezervleri kur müdahale kapasitesini gösterir"
            "\n\n---\n*Makro sayfasında tüm göstergelere bakabilirsiniz.*"
        )

    # Genel fallback
    return (
        "### 💬 Finansal Asistan\n\n"
        "Sorunuzu aldım, ancak Gemini API şu an erişilemiyor.\n\n"
        "**Yardımcı olabileceğim konular:**\n"
        "- RSI, MACD, SMA gibi teknik gösterge açıklamaları\n"
        "- BIST ve Türkiye piyasası hakkında genel bilgi\n"
        "- Altın, kripto, forex piyasaları hakkında temel analiz\n"
        "- Makroekonomi ve TCMB politikaları\n\n"
        "💡 **İpucu:** Daha spesifik sorular (ör. 'RSI nedir?', 'Altın neden yükseliyor?') "
        "için daha iyi yanıt alabilirsiniz.\n\n"
        f"📌 *Sorgunuz: \"{question}\"*"
        "\n\n---\n*Gemini API erişilebilir olduğunda daha kapsamlı yanıt üretilecektir.*"
    )


def analyze_with_hub_data(ticker: str, current_price: float = 0.0, extra_context: str = "") -> str:
    """
    Data Hub'dan yüklenen finansal tablolar (bilanço, gelir, karlılık, analist)
    ve büyüme trendlerini harmanlayarak ileri görüşlü (forward-looking) projeksiyon üretir.

    Çıktı: 1A / 3A / 6A ve 1Y / 3Y / 5Y projeksiyonları + Al/Tut/Sat/Zarar Kes tavsiyesi
    """
    try:
        from core.data_processor import parse_financials_to_context, get_growth_trends
        fin_data = parse_financials_to_context(ticker)
        growth_text = get_growth_trends(ticker)
    except Exception as e:
        return f"⚠️ Finansal veri yüklenemedi: {e}"

    if not fin_data["available_tables"]:
        return (
            f"⚠️ **{ticker}** için Data Hub'da veri bulunamadı.\n"
            "Lütfen önce **Veri Havuzu** sayfasından finansal tabloları yükleyin."
        )

    tables_info = ", ".join(fin_data["available_tables"])
    price_line = f"**Güncel Fiyat:** {current_price:.2f} TL\n" if current_price else ""
    extra_line = f"\n**Ek Bağlam:**\n{extra_context}\n" if extra_context else ""

    prompt = f"""
Sen FinSentinel'in ileri görüşlü (forward-looking) finansal analiz motorusun.
Aşağıda {ticker} hissesine ait gerçek finansal veriler bulunmaktadır.
Bu verileri derinlemesine analiz ederek somut projeksiyonlar ve net aksiyon tavsiyesi üret.

{price_line}
**Kullanılabilir Veri Setleri:** {tables_info}

---
{fin_data['context_string']}

---
{growth_text}
{extra_line}

---
## İSTENEN ÇIKTI FORMATI (bu başlıkları aynen kullan):

### 📊 Temel Analiz Özeti
- Şirketin finansal sağlığını 3-4 cümlede değerlendir (büyüme, karlılık, borçluluk)
- En güçlü ve en zayıf finansal metrik nedir?

### 🔮 Kısa Vadeli Projeksiyonlar
- **1 Ay:** Teknik ve fundamental beklenti, olası fiyat aralığı
- **3 Ay:** Bir sonraki bilanço/açıklamaya kadar beklenti
- **6 Ay:** Orta vadeli büyüme ivmesi

### 📅 Uzun Vadeli Projeksiyonlar
- **1 Yıl:** Yıl sonu hedef aralığı ve temel senaryo
- **3 Yıl:** Büyüme trendinin sürdürülebilirliği
- **5 Yıl:** Sektör ve makro riskler dahil iyimser/kötümser/baz senaryo

### ⚡ Aksiyon Tavsiyesi
**[AL / TUT / SAT / ZARAR KES]** — Net kararını yaz ve 2-3 cümle gerekçe ekle.
- Giriş fiyatı / Hedef fiyat / Stop-loss seviyesi (verilerden tahmin et)
- Risk faktörleri (bu tavsiyeyi geçersiz kılacak senaryolar)

### ⚠️ Uyarı
Bu analiz yüklenen finansal veriler bazındadır. Yatırım kararı vermeden bağımsız araştırma yapınız.
"""
    return _call_best_ai(prompt, max_tokens=1200)


def generate_portfolio_insight(positions: list[dict]) -> str:
    """Portföy analizi ve aksiyon odaklı öneri üret (Copilot Persona)"""
    if not positions:
        return "Portföyde pozisyon bulunamadı. Analiz için lütfen işlem girin."

    pos_text = "\n".join([
        f"- {p.get('Sembol')}: {p.get('Adet')} adet, "
        f"Maliyet: {p.get('Maliyet'):.2f}, Değer: {p.get('Değer'):.2f}, "
        f"Durum: %{p.get('K/Z %',0):.1f}"
        for p in positions
    ])

    prompt = f"""
Sen bir 'Smart Portfolio Copilot' AI asistanısın. Kullanıcının portföyünü analiz et ve pasif bir 'yorumcu' değil, 'karar verici' bir yardımcı gibi davran.

Kullanıcı Portföyü:
{pos_text}

Senden beklenenler:
1. **📊 Genel Sağlık:** Portföyün risk dağılımı (Sektörel veya Asset bazlı öngörü)
2. **⚖️ Rebalancing:** Hangi varlık çok fazla ağırlık kazanmış veya hangisi aşırı düşmüş? Ne yapılmalı? (Örn: "THYAO ağırlığını %20'ye çekmek için kâr realizasyonu yap")
3. **⚠️ Risk Uyarısı:** Portföydeki en kırılgan nokta neresi?
4. **💡 Stratejik Hamle:** Bugünün piyasa koşullarında (varsayalım BIST dalgalı) kullanıcıya tek bir net tavsiye ver.

Format:
- Başlıklar net (Emoji kullanarak)
- Cümleler kısa ve emir kipi/aksiyon odaklı olsun.
- "Sadece veri verme, karar ver."
"""
    return _call_best_ai(prompt, max_tokens=800)

def get_morning_briefing(quotes: dict, news: list, portfolio_summary: str = "") -> str:
    """Yatırımcı için sabah brifingi üret (Piyasa özeti + Haberler + Portföy Durumu)"""
    market_lines = []
    for label, sym in [("BIST 100", "XU100.IS"), ("USD/TRY", "USDTRY=X"), ("Altın", "GC=F"), ("BTC", "BTC-USD")]:
        q = quotes.get(sym, {})
        if q and "price" in q:
            change = q.get("change_pct", 0)
            market_lines.append(f"- {label}: {q['price']:,.2f} (%{change:+.2f})")
    
    market_ctx = "\n".join(market_lines)
    news_ctx = "\n".join([f"- {n.get('title','')}" for n in news[:5]])
    
    port_ctx = f"\n**Portföy Durumu:**\n{portfolio_summary}" if portfolio_summary else ""
    
    prompt = f"""
Bugün piyasalar için özel bir 'Sabah Brifingi' hazırla. 
Aşağıdaki verilere dayanarak kısa, etkili ve eyleme dökülebilir bir özet sun:

**Piyasa Durumu:**
{market_ctx}

**Günün Kritik Haberleri:**
{news_ctx}
{port_ctx}

İstediğim Format:
1. ☀️ **Güne Bakış:** (Genel atmosfer)
2. 🚨 **Kritik Gelişme:** (Bugün en çok neye dikkat edilmeli)
3. 💼 **Strateji Notu:** (Yatırımcı bugün nasıl bir duruş sergilemeli)

Yanıtı samimi ama profesyonel bir finans danışmanı tonunda yaz.
"""
    return _call_best_ai(prompt, max_tokens=800)
