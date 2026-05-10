"""
FinSentinel — Şirket Gelecek Projeleri & Stratejik Hedefler
utils/company_projects.py

Her kayıt:
  name        : Proje adı
  desc        : Açıklama
  horizon     : "Kısa" (<1 yıl) | "Orta" (1-3 yıl) | "Uzun" (3+ yıl)
  category    : "Kapasite" | "Yatırım" | "İhracat" | "Dijital" | "Enerji" |
                "AR-GE" | "M&A" | "Sürdürülebilirlik" | "Altyapı"
  status      : "Planlama" | "Devam Ediyor" | "Tamamlandı"
  source      : Kaynak (KAP, yıllık rapor, şirket açıklaması vb.)
  year        : Hedef yıl (int veya None)
"""
from __future__ import annotations

PROJECTS: dict[str, list[dict]] = {

    # ── Havacılık ─────────────────────────────────────────────────────────────

    "THYAO": [
        {
            "name":     "Yeni Hat Genişlemesi — 400+ Destinasyon",
            "desc":     "2025-2026 dönemi uçuş ağını 400 destinasyonun üzerine taşıma hedefi. "
                        "Afrika ve Güneydoğu Asya'da yeni noktalar öncelikli.",
            "horizon":  "Kısa",
            "category": "Kapasite",
            "status":   "Devam Ediyor",
            "source":   "THY Yıllık Rapor 2024",
            "year":     2026,
        },
        {
            "name":     "Yeni Nesil Uçak Alımı (350+ Adet)",
            "desc":     "Boeing 787, Airbus A350 ve A320neo ailesiyle filo gençleştirme. "
                        "2033'e kadar 350'den fazla uçak teslimatı planlanıyor.",
            "horizon":  "Uzun",
            "category": "Kapasite",
            "status":   "Devam Ediyor",
            "source":   "KAP Açıklaması 2024",
            "year":     2033,
        },
        {
            "name":     "THY Teknik Uluslararası MRO Genişlemesi",
            "desc":     "THY Teknik'in dünya çapında MRO (bakım-onarım-revizyon) kapasitesini "
                        "artırarak üçüncü taraf havayollarına daha fazla hizmet vermesi.",
            "horizon":  "Orta",
            "category": "İhracat",
            "status":   "Devam Ediyor",
            "source":   "THY Strateji Belgesi",
            "year":     2027,
        },
        {
            "name":     "Sürdürülebilir Uçak Yakıtı (SAF) Programı",
            "desc":     "2030'a kadar yakıt tüketiminin %10'unu SAF'tan karşılama taahhüdü. "
                        "Karbon salımını azaltmaya yönelik net sıfır yol haritası.",
            "horizon":  "Uzun",
            "category": "Sürdürülebilirlik",
            "status":   "Planlama",
            "source":   "THY ESG Raporu",
            "year":     2030,
        },
    ],

    "PGSUS": [
        {
            "name":     "Filo Büyümesi — 150+ Uçak",
            "desc":     "2026 sonuna kadar filonun 150 uçağın üzerine çıkarılması. "
                        "A320neo ve A321neo teslimatlarıyla yakıt verimliliği artacak.",
            "horizon":  "Kısa",
            "category": "Kapasite",
            "status":   "Devam Ediyor",
            "source":   "Pegasus Yatırımcı Sunumu 2024",
            "year":     2026,
        },
        {
            "name":     "Orta Doğu ve Afrika Hat Açılımı",
            "desc":     "Sabiha Gökçen üssünden Körfez, Kuzey Afrika ve Doğu Afrika'ya yeni "
                        "hatlar açarak yolcu sayısını 30 milyonun üzerine taşıma hedefi.",
            "horizon":  "Orta",
            "category": "İhracat",
            "status":   "Devam Ediyor",
            "source":   "KAP Açıklaması",
            "year":     2027,
        },
    ],

    # ── Enerji ────────────────────────────────────────────────────────────────

    "TUPRS": [
        {
            "name":     "STAR Rafineri Entegrasyonu & Kapasite Artışı",
            "desc":     "SOCAR STAR rafineriyle hammadde ve ürün entegrasyonunu derinleştirerek "
                        "marj optimizasyonu. Lube oil ve özel ürünler kapasitesi genişletiliyor.",
            "horizon":  "Kısa",
            "category": "Kapasite",
            "status":   "Devam Ediyor",
            "source":   "Tüpraş Yatırımcı Günü 2024",
            "year":     2026,
        },
        {
            "name":     "Yeşil Hidrojen & Sürdürülebilir Yakıt Yatırımı",
            "desc":     "2030'a kadar yeşil hidrojen üretim tesisi kurulumu. SAF (sürdürülebilir "
                        "uçak yakıtı) üretim kapasitesi oluşturma hedefi.",
            "horizon":  "Uzun",
            "category": "Sürdürülebilirlik",
            "status":   "Planlama",
            "source":   "Tüpraş ESG & Strateji Belgesi",
            "year":     2030,
        },
        {
            "name":     "Dijital Rafineri Dönüşümü",
            "desc":     "Yapay zeka ve dijital ikiz teknolojileriyle rafineri operasyonlarını "
                        "optimize etme; enerji tasarrufu ve verimlilik hedefleri.",
            "horizon":  "Orta",
            "category": "Dijital",
            "status":   "Devam Ediyor",
            "source":   "Tüpraş Yıllık Rapor",
            "year":     2027,
        },
    ],

    "AKSEN": [
        {
            "name":     "Afrika Enerji Genişlemesi",
            "desc":     "Gana, Senegal ve diğer Afrika ülkelerinde yeni enerji üretim tesisleri. "
                        "Toplam uluslararası kurulu güç kapasitesini 2.000 MW'a çıkarma hedefi.",
            "horizon":  "Orta",
            "category": "Yatırım",
            "status":   "Devam Ediyor",
            "source":   "Aksa Enerji Yatırımcı Sunumu",
            "year":     2027,
        },
        {
            "name":     "Yenilenebilir Enerji Portföyü Oluşturma",
            "desc":     "Türkiye'de güneş ve rüzgar santrallerine yatırım yaparak portföy "
                        "çeşitlendirmesi. 2030'a kadar 500 MW yenilenebilir kapasite hedefi.",
            "horizon":  "Uzun",
            "category": "Enerji",
            "status":   "Planlama",
            "source":   "KAP Açıklaması",
            "year":     2030,
        },
    ],

    "ZOREN": [
        {
            "name":     "Jeotermal Kapasite Genişlemesi",
            "desc":     "Zorlu Jeotermal bünyesinde toplam kurulu gücü 700 MW'ın üzerine "
                        "taşıma yatırımları. Yeni jeotermal saha araştırmaları sürüyor.",
            "horizon":  "Orta",
            "category": "Enerji",
            "status":   "Devam Ediyor",
            "source":   "Zorlu Enerji Yıllık Raporu",
            "year":     2027,
        },
    ],

    # ── Teknoloji ─────────────────────────────────────────────────────────────

    "ASELS": [
        {
            "name":     "KAAN Savaş Uçağı Aviyonik Sistemleri",
            "desc":     "Türkiye'nin yerli muharip uçağı KAAN için radar, elektronik harp ve "
                        "silah yönetim sistemlerinin geliştirilmesi. Seri üretim 2028 hedefi.",
            "horizon":  "Orta",
            "category": "AR-GE",
            "status":   "Devam Ediyor",
            "source":   "Savunma Sanayii Başkanlığı",
            "year":     2028,
        },
        {
            "name":     "İhracat Gelirlerini 1 Milyar Dolar'a Çıkarma",
            "desc":     "Elektronik harp, radar ve iletişim sistemlerinde uluslararası pazarı "
                        "genişleterek yıllık ihracat gelirini 1 Milyar USD hedefi.",
            "horizon":  "Orta",
            "category": "İhracat",
            "status":   "Devam Ediyor",
            "source":   "Aselsan Strateji Belgesi",
            "year":     2027,
        },
        {
            "name":     "Tıbbi Teknoloji İş Kolu Büyümesi",
            "desc":     "Ultrason, MR ve tıbbi görüntüleme cihazları üretimiyle sağlık "
                        "teknolojileri segmentinde ciddi büyüme hedefleniyor.",
            "horizon":  "Orta",
            "category": "Kapasite",
            "status":   "Devam Ediyor",
            "source":   "Aselsan Yıllık Rapor",
            "year":     2027,
        },
    ],

    "TCELL": [
        {
            "name":     "5G Altyapı Yatırımı",
            "desc":     "Türkiye'de 5G lisans ihalesine hazırlık; 5G baz istasyonu kurulumları "
                        "ve spektrum yatırımları. Tam kapsama 2026-2027 hedefi.",
            "horizon":  "Kısa",
            "category": "Altyapı",
            "status":   "Planlama",
            "source":   "Turkcell Yatırımcı Günü",
            "year":     2027,
        },
        {
            "name":     "Paycell Fintech Büyümesi",
            "desc":     "Paycell'i bağımsız bir fintech markası olarak konumlandırma. "
                        "Dijital cüzdan, BNPL ve uluslararası ödeme çözümleri genişletiliyor.",
            "horizon":  "Orta",
            "category": "Dijital",
            "status":   "Devam Ediyor",
            "source":   "Turkcell Strateji Belgesi",
            "year":     2027,
        },
        {
            "name":     "Bulut & Siber Güvenlik Hizmetleri",
            "desc":     "Turkcell Bulut ve siber güvenlik hizmetlerini kurumsal segmentte "
                        "büyütme. Veri merkezi kapasitesi genişletiliyor.",
            "horizon":  "Orta",
            "category": "Dijital",
            "status":   "Devam Ediyor",
            "source":   "Turkcell Yıllık Rapor",
            "year":     2027,
        },
    ],

    "TTKOM": [
        {
            "name":     "Fiber Altyapı 25 Milyon Eve Genişleme",
            "desc":     "2026 sonuna kadar fiber ağı 25 milyon haneye taşıma yatırımı. "
                        "FTTH altyapısıyla internet hız ve kalitesini artırma.",
            "horizon":  "Kısa",
            "category": "Altyapı",
            "status":   "Devam Ediyor",
            "source":   "Türk Telekom Yatırımcı Sunumu",
            "year":     2026,
        },
        {
            "name":     "Kurumsal Bulut & Veri Merkezi",
            "desc":     "Türkiye'nin en büyük veri merkezi operatörü olma hedefi. "
                        "Kamu dijital dönüşümünde stratejik tedarikçi konumu.",
            "horizon":  "Orta",
            "category": "Dijital",
            "status":   "Devam Ediyor",
            "source":   "Türk Telekom Strateji Belgesi",
            "year":     2028,
        },
    ],

    # ── Otomotiv ─────────────────────────────────────────────────────────────

    "FROTO": [
        {
            "name":     "Ford Transit Elektrikli Versiyonu Üretimi",
            "desc":     "İzmit fabrikasında E-Transit ve elektrikli Transit Custom modellerinin "
                        "üretimine geçiş. Avrupa'nın elektrikli ticari araç talebine yönelik.",
            "horizon":  "Kısa",
            "category": "Kapasite",
            "status":   "Devam Ediyor",
            "source":   "Ford Otosan Yatırımcı Sunumu 2024",
            "year":     2026,
        },
        {
            "name":     "Gölcük Tesisi EV Dönüşümü — 12 Milyar TL Yatırım",
            "desc":     "Gölcük fabrikasının tamamen elektrikli araç üretimine dönüştürülmesi. "
                        "Türkiye'nin en büyük EV yatırımlarından biri.",
            "horizon":  "Orta",
            "category": "Yatırım",
            "status":   "Devam Ediyor",
            "source":   "Ford Otosan KAP Açıklaması",
            "year":     2027,
        },
        {
            "name":     "Yerli Elektrikli Ticari Araç Markası",
            "desc":     "Ford Otosan'ın kendi marka elektrikli ticari araç geliştirme projesi. "
                        "Avrupa ve gelişmekte olan pazarlar hedefleniyor.",
            "horizon":  "Uzun",
            "category": "AR-GE",
            "status":   "Devam Ediyor",
            "source":   "Ford Otosan Strateji Belgesi",
            "year":     2030,
        },
    ],

    "TOASO": [
        {
            "name":     "Elektrikli Araç Üretimi (Fiat 500e & Alfa Romeo)",
            "desc":     "Bursa fabrikasında Stellantis grubu için elektrikli modellerin üretimine "
                        "geçiş. Fiat 500e ve diğer EV platformları için kapasite hazırlığı.",
            "horizon":  "Orta",
            "category": "Kapasite",
            "status":   "Devam Ediyor",
            "source":   "Tofaş Yatırımcı Günü 2024",
            "year":     2027,
        },
    ],

    "ARCLK": [
        {
            "name":     "Whirlpool EMEA Entegrasyonu",
            "desc":     "Whirlpool'un Avrupa, Orta Doğu ve Afrika operasyonlarının Arçelik "
                        "bünyesine entegrasyonu. Yeni markaların portföye eklenmesiyle küresel "
                        "pazar payı hedefleniyor.",
            "horizon":  "Kısa",
            "category": "M&A",
            "status":   "Devam Ediyor",
            "source":   "Arçelik KAP Açıklaması 2024",
            "year":     2026,
        },
        {
            "name":     "Enerji Verimli Ürün Portföyü Genişlemesi",
            "desc":     "A+++ enerji sınıfı ürünlerin toplam portföydeki payını artırma. "
                        "AB'nin enerji verimliliği direktiflerine uyumlu ürün geliştirme.",
            "horizon":  "Orta",
            "category": "Sürdürülebilirlik",
            "status":   "Devam Ediyor",
            "source":   "Arçelik ESG Raporu",
            "year":     2028,
        },
    ],

    # ── Metal & Demir-Çelik ───────────────────────────────────────────────────

    "EREGL": [
        {
            "name":     "Karbon Azaltım & Yeşil Çelik Yol Haritası",
            "desc":     "2050 net sıfır karbon hedefi. Elektrik ark ocağı (EAO) teknolojisine "
                        "geçiş ve doğalgaz tüketimini azaltma yatırımları.",
            "horizon":  "Uzun",
            "category": "Sürdürülebilirlik",
            "status":   "Planlama",
            "source":   "Erdemir ESG Raporu",
            "year":     2050,
        },
        {
            "name":     "Yüksek Katma Değerli Çelik Ürün Kapasitesi",
            "desc":     "Otomotiv ve enerji sektörlerine yönelik yüksek mukavemetli çelik "
                        "ve özel alaşım sac kapasitesinin artırılması.",
            "horizon":  "Orta",
            "category": "Kapasite",
            "status":   "Devam Ediyor",
            "source":   "Erdemir Yıllık Rapor",
            "year":     2027,
        },
    ],

    "KRDMD": [
        {
            "name":     "Demiryolu Rayı İhracatını Artırma",
            "desc":     "Türkiye'nin hızlı tren projelerinin yanı sıra Avrupa ve Orta Doğu "
                        "demiryolu projelerine ray ihracatını büyütme.",
            "horizon":  "Orta",
            "category": "İhracat",
            "status":   "Devam Ediyor",
            "source":   "Kardemir Yatırımcı Sunumu",
            "year":     2027,
        },
    ],

    # ── Kimya ─────────────────────────────────────────────────────────────────

    "SASA": [
        {
            "name":     "Entegre Petrokimya Kompleksi — Faz 2",
            "desc":     "Adana'daki PTA-PET-polyester entegrasyon projesinin ikinci fazı. "
                        "2026'ya kadar toplam kapasitenin 5 milyon ton/yıla çıkarılması hedefi.",
            "horizon":  "Kısa",
            "category": "Kapasite",
            "status":   "Devam Ediyor",
            "source":   "SASA KAP Açıklaması 2024",
            "year":     2026,
        },
        {
            "name":     "Avrupa'nın En Büyük Polyester Kompleksi",
            "desc":     "Tam entegrasyon tamamlandığında Avrupa'nın en büyük entegre polyester "
                        "tesisi olma hedefi. Dikey entegrasyon marj avantajı sağlayacak.",
            "horizon":  "Orta",
            "category": "Yatırım",
            "status":   "Devam Ediyor",
            "source":   "SASA Strateji Belgesi",
            "year":     2028,
        },
        {
            "name":     "Geri Dönüştürülmüş Polyester (rPET) Üretimi",
            "desc":     "Döngüsel ekonomi kapsamında geri dönüştürülmüş PET şişelerden "
                        "polyester elyaf üretim kapasitesi kurulumu.",
            "horizon":  "Orta",
            "category": "Sürdürülebilirlik",
            "status":   "Planlama",
            "source":   "SASA ESG Belgesi",
            "year":     2027,
        },
    ],

    # ── Holding ───────────────────────────────────────────────────────────────

    "KCHOL": [
        {
            "name":     "Koç Enerji — Yenilenebilir Güç Kapasitesi",
            "desc":     "Koç Holding enerji şirketleri aracılığıyla 2030'a kadar 3.000 MW "
                        "yenilenebilir enerji kapasitesi hedefi.",
            "horizon":  "Uzun",
            "category": "Enerji",
            "status":   "Devam Ediyor",
            "source":   "Koç Holding Strateji Belgesi",
            "year":     2030,
        },
        {
            "name":     "Dijital & Teknoloji Yatırımları",
            "desc":     "KoçSistem, KoçDigital ve fintech girişimlerine yönelik büyük ölçekli "
                        "yatırımlar. Grup şirketlerinin dijital dönüşümü.",
            "horizon":  "Orta",
            "category": "Dijital",
            "status":   "Devam Ediyor",
            "source":   "Koç Holding Yıllık Raporu",
            "year":     2027,
        },
    ],

    "SAHOL": [
        {
            "name":     "Enerjisa Yenilenebilir Büyüme",
            "desc":     "Sabancı'nın enerji kolu Enerjisa aracılığıyla güneş ve rüzgar "
                        "santrallerine yönelik büyük ölçekli yatırım programı.",
            "horizon":  "Orta",
            "category": "Enerji",
            "status":   "Devam Ediyor",
            "source":   "Sabancı Holding Yıllık Raporu",
            "year":     2028,
        },
        {
            "name":     "Agesa & Aksigorta Dijital Sigorta",
            "desc":     "Sigorta ve emeklilik ürünlerinin dijital kanallara taşınması; "
                        "yapay zeka destekli hasar yönetimi.",
            "horizon":  "Kısa",
            "category": "Dijital",
            "status":   "Devam Ediyor",
            "source":   "Sabancı Holding Strateji",
            "year":     2026,
        },
    ],

    # ── Bankacılık ───────────────────────────────────────────────────────────

    "GARAN": [
        {
            "name":     "Yapay Zeka Destekli Bankacılık Platformu",
            "desc":     "Garanti BBVA'nın müşteri deneyimi, kredi skorlama ve dolandırıcılık "
                        "tespitinde yapay zeka kullanımını artırma yatırımı.",
            "horizon":  "Kısa",
            "category": "Dijital",
            "status":   "Devam Ediyor",
            "source":   "Garanti BBVA Yatırımcı Günü",
            "year":     2026,
        },
        {
            "name":     "Sürdürülebilir Finans Portföyü",
            "desc":     "2030'a kadar yeşil ve sürdürülebilir kredi portföyünü toplam "
                        "kredilerin %20'sine çıkarma taahhüdü.",
            "horizon":  "Uzun",
            "category": "Sürdürülebilirlik",
            "status":   "Devam Ediyor",
            "source":   "Garanti BBVA ESG Raporu",
            "year":     2030,
        },
    ],

    "AKBNK": [
        {
            "name":     "Akbank Dijital Bankacılık Büyümesi",
            "desc":     "Dijital müşteri sayısını 10 milyonun üzerine taşıma ve işlemlerin "
                        "%80'ini dijital kanaldan gerçekleştirme hedefi.",
            "horizon":  "Kısa",
            "category": "Dijital",
            "status":   "Devam Ediyor",
            "source":   "Akbank Yatırımcı Sunumu",
            "year":     2026,
        },
    ],

    # ── Perakende ─────────────────────────────────────────────────────────────

    "BIMAS": [
        {
            "name":     "Mağaza Ağını 15.000'e Genişletme",
            "desc":     "Türkiye'de mağaza sayısını 15.000'e taşıma hedefi. Anadolu'nun "
                        "küçük ilçe ve köylerine ulaşım öncelikli.",
            "horizon":  "Orta",
            "category": "Kapasite",
            "status":   "Devam Ediyor",
            "source":   "BİM Yatırımcı Sunumu",
            "year":     2027,
        },
        {
            "name":     "Fas ve Mısır Operasyonlarını Büyütme",
            "desc":     "Kuzey Afrika'daki mağaza sayısını artırarak uluslararası büyümeyi "
                        "hızlandırma. Fas'ta 1.000+ mağaza hedefi.",
            "horizon":  "Orta",
            "category": "İhracat",
            "status":   "Devam Ediyor",
            "source":   "BİM Yıllık Raporu",
            "year":     2028,
        },
    ],

    "MGROS": [
        {
            "name":     "Sanal Market & e-Ticaret Büyümesi",
            "desc":     "Dijital satışların toplam gelir içindeki payını %15'in üzerine "
                        "taşıma. Hızlı teslimat (30 dakika) altyapısının genişletilmesi.",
            "horizon":  "Kısa",
            "category": "Dijital",
            "status":   "Devam Ediyor",
            "source":   "Migros Yatırımcı Günü",
            "year":     2026,
        },
    ],

    # ── GYO ──────────────────────────────────────────────────────────────────

    "EKGYO": [
        {
            "name":     "Kentsel Dönüşüm Projeleri Portföyü",
            "desc":     "TOKİ ile koordineli büyük ölçekli kentsel dönüşüm konut projeleri. "
                        "İstanbul'da 100.000+ konut üretim hedefi.",
            "horizon":  "Uzun",
            "category": "Yatırım",
            "status":   "Devam Ediyor",
            "source":   "Emlak Konut Yıllık Raporu",
            "year":     2030,
        },
    ],
}


# ─────────────────────────────────────────────────────────────────────────────
# Yardımcı fonksiyonlar
# ─────────────────────────────────────────────────────────────────────────────

HORIZON_ORDER = {"Kısa": 0, "Orta": 1, "Uzun": 2}
STATUS_COLOR  = {
    "Devam Ediyor": "#10b981",
    "Planlama":     "#f59e0b",
    "Tamamlandı":   "#6366f1",
}
CATEGORY_ICON = {
    "Kapasite":          "🏭",
    "Yatırım":           "💰",
    "İhracat":           "🌍",
    "Dijital":           "💻",
    "Enerji":            "⚡",
    "AR-GE":             "🔬",
    "M&A":               "🤝",
    "Sürdürülebilirlik": "🌱",
    "Altyapı":           "🔧",
}


def get_projects(ticker: str) -> list[dict]:
    """Ticker için proje listesi döner. Bulunamazsa boş liste."""
    return PROJECTS.get(ticker.replace(".IS", "").upper(), [])


def all_tickers_with_projects() -> list[str]:
    """Proje verisi olan tüm ticker'ları döner."""
    return sorted(PROJECTS.keys())


def filter_projects(
    tickers: list[str] | None = None,
    horizon: str | None = None,
    category: str | None = None,
    status: str | None = None,
) -> list[dict]:
    """
    Filtrelenmiş proje listesi döner.
    Her kayıtta 'ticker' anahtarı da eklenir.
    """
    result = []
    src = tickers if tickers else list(PROJECTS.keys())
    for t in src:
        for p in PROJECTS.get(t, []):
            if horizon  and p["horizon"]  != horizon:  continue
            if category and p["category"] != category: continue
            if status   and p["status"]   != status:   continue
            result.append({**p, "ticker": t})
    return result
