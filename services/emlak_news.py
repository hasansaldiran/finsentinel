"""Em­lak Haberleri — Canlı Veri Çekimi (RSS)

Bu modül, Türkiye'nin önde gelen emlak haber platformalarından 
(Emlak Kulisi, Emlak Haberi, Emlak Medya vb.) 
güncel haberleri çeker ve konsolide eder.
"""
import feedparser
import requests
import re
from datetime import datetime
import time
from typing import List, Dict

# Haber kaynaklarının RSS adresleri
RSS_FEEDS = {
    "Emlak Kulisi": "https://emlakkulisi.com/feed",
    "Emlak Haberi": "https://www.emlakhaberi.com/rss",
    "Emlak Medya": "https://www.emlakmedya.com/feed",
    "Emlak Dream": "https://emlakdream.com/feed",
    "Gayrimenkul Haber": "https://www.gayrimenkulhaber.com/feed"
}

# In-memory cache
_NEWS_CACHE = {"data": [], "expires": 0}

def clean_html(raw_html: str) -> str:
    """HTML etiketlerini temizler ve kısa bir özet çıkarır."""
    if not raw_html:
        return ""
    clean_text = re.sub('<[^<]+>', '', raw_html)
    clean_text = clean_text.replace('\n', ' ').replace('\r', '').replace('&nbsp;', ' ').strip()
    return clean_text[:140] + ("..." if len(clean_text) > 140 else "")

def fetch_news(limit: int = 12, force_refresh: bool = False) -> List[Dict]:
    """Tüm kaynaklardan haberleri çeker, tarihe göre sıralar ve döndürür.
    
    Önbellek (Cache) mekanizması ile 15 dakikada bir güncellenir.
    force_refresh=True ise önbelleği atlar.
    """
    global _NEWS_CACHE
    now = time.time()
    
    if not force_refresh and _NEWS_CACHE["data"] and now < _NEWS_CACHE["expires"]:
        return _NEWS_CACHE["data"][:limit]
        
    all_news = []
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)"
    }
    
    for source_name, url in RSS_FEEDS.items():
        try:
            # Bazı siteler feedparser'ı engelleyebildiği için requests ile çekiyoruz
            resp = requests.get(url, headers=headers, timeout=5)
            if resp.status_code == 200:
                feed = feedparser.parse(resp.content)
                for entry in feed.entries[:5]: # Her kaynaktan en fazla 5 haber
                    
                    # Tarih okuma
                    published_parsed = entry.get("published_parsed", None)
                    if published_parsed:
                        dt = datetime.fromtimestamp(time.mktime(published_parsed))
                    else:
                        dt = datetime.now()
                        
                    # Özet çıkarma (summary veya description)
                    summary = entry.get("summary", entry.get("description", ""))
                    clean_summary = clean_html(summary)
                    
                    if not clean_summary:
                        clean_summary = "Detaylı haber içeriği için tıklayınız."
                    
                    all_news.append({
                        "title": entry.get("title", ""),
                        "source": source_name,
                        "url": entry.get("link", url),
                        "summary": clean_summary,
                        "timestamp": dt.timestamp(),
                        "date_str": dt.strftime("%d.%m.%Y %H:%M")
                    })
        except Exception as e:
            print(f"Haber çekme hatası ({source_name}): {e}")
            pass

    # Haberleri en yeniden eskiye sıralama
    all_news.sort(key=lambda x: x["timestamp"], reverse=True)
    
    # Cache kaydet
    _NEWS_CACHE["data"] = all_news
    _NEWS_CACHE["expires"] = now + 900 # 15 dakika sakla
    
    # Çekim başarısızsa önlem
    if not all_news:
        return [{
            "title": "Şu anda haber servislerine ulaşılamıyor.",
            "source": "Sistem Mesajı",
            "url": "#",
            "summary": "İnternet bağlantınızı kontrol edin veya daha sonra tekrar deneyin."
        }]
        
    return all_news[:limit]
