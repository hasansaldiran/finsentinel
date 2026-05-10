"""
FinSentinel — Şirket Bilgi Modülü
utils/company_info.py

Her ticker için: tam ad, sektör, kısa açıklama.
Bilinmeyenler için yfinance fallback kullanılır.

Batch planı:
  v1 (mevcut) : BIST 30
  v2           : BIST 100 (31-100 arası)
  v3           : XKTUM batch 1 (1-50)
  v4           : XKTUM batch 2 (51-100)
  v5           : XKTUM batch 3 (101-150)
  v6           : XKTUM batch 4 (151-228)
"""
from __future__ import annotations
import streamlit as st

# ─────────────────────────────────────────────────────────────────────────────
# Statik şirket veritabanı
# Anahtar: ".IS" eki YOK  (ör. "THYAO")
# ─────────────────────────────────────────────────────────────────────────────
COMPANY_DB: dict[str, dict] = {

    # ── BIST 30 ──────────────────────────────────────────────────────────────

    "GARAN": {
        "name":    "Türkiye Garanti Bankası A.Ş.",
        "sector":  "Bankacılık",
        "desc":    "Türkiye'nin en büyük özel bankalarından biri. Bireysel, KOBİ ve kurumsal bankacılık, "
                   "dijital bankacılık ve uluslararası finansman hizmetleri sunar. BBVA ortaklığıyla "
                   "güçlü dijital dönüşüm altyapısına sahiptir.",
    },
    "AKBNK": {
        "name":    "Akbank T.A.Ş.",
        "sector":  "Bankacılık",
        "desc":    "Sabancı Grubu bünyesindeki köklü özel banka. Kurumsal, ticari, bireysel ve özel "
                   "bankacılık ile yatırım bankacılığı hizmetleri sunar. Güçlü dijital altyapısıyla "
                   "Türkiye'nin önde gelen bankalarından biridir.",
    },
    "THYAO": {
        "name":    "Türk Hava Yolları A.O.",
        "sector":  "Havacılık",
        "desc":    "Türkiye'nin ulusal havayolu şirketi. 120'den fazla ülkeye 340+ destinasyonda uçuş "
                   "gerçekleştirir. Kargo, teknik bakım (THY Teknik) ve uçuş okulu (Türkiye Uçuş "
                   "Akademisi) alanlarında da faaliyet gösterir.",
    },
    "KCHOL": {
        "name":    "Koç Holding A.Ş.",
        "sector":  "Holding",
        "desc":    "Türkiye'nin en büyük sanayi ve hizmet holdinglerinden biri. Enerji, otomotiv "
                   "(Ford, Fiat), dayanıklı tüketim (Arçelik), finans (Yapı Kredi) ve perakende "
                   "sektörlerinde faaliyet gösterir.",
    },
    "SAHOL": {
        "name":    "Hacı Ömer Sabancı Holding A.Ş.",
        "sector":  "Holding",
        "desc":    "Türkiye'nin önde gelen holdinglerinden. Bankacılık (Akbank), enerji, çimento, "
                   "tekstil (Sabancı Tekstil), perakende ve dijital teknoloji alanlarında geniş "
                   "portföye sahiptir.",
    },
    "TUPRS": {
        "name":    "Tüpraş — Türkiye Petrol Rafinerileri A.Ş.",
        "sector":  "Enerji",
        "desc":    "Türkiye'nin tek entegre petrol rafinerisini işleten şirket. İzmit, İzmir, Kırıkkale "
                   "ve Batman rafinerilerinde ham petrol işler; benzin, motorin, jet yakıtı, fuel oil "
                   "ve petrokimyasal ürünler üretir.",
    },
    "ISCTR": {
        "name":    "Türkiye İş Bankası A.Ş.",
        "sector":  "Bankacılık",
        "desc":    "Türkiye Cumhuriyeti'nin ilk ulusal bankası. Bireysel, ticari ve kurumsal bankacılık "
                   "ile sigorta, yatırım ve portföy yönetimi hizmetleri sunar. CHP hissedarlığıyla "
                   "kamuoyunda tanınan köklü bir kurumdur.",
    },
    "YKBNK": {
        "name":    "Yapı ve Kredi Bankası A.Ş.",
        "sector":  "Bankacılık",
        "desc":    "Koç Holding ve UniCredit ortaklığıyla yönetilen büyük özel banka. Bireysel, "
                   "kurumsal ve ticari bankacılık, kredi kartı (World Card) ve dijital bankacılık "
                   "hizmetleri sunar.",
    },
    "BIMAS": {
        "name":    "BİM Birleşik Mağazalar A.Ş.",
        "sector":  "Perakende",
        "desc":    "Türkiye'nin en büyük indirimli gıda perakendecisi. 10.000'i aşkın mağazasıyla "
                   "Türkiye, Fas ve Mısır'da faaliyet gösterir. Sınırlı ürün yelpazesi ve düşük "
                   "maliyet modeli temel rekabet avantajıdır.",
    },
    "SISE": {
        "name":    "Türkiye Şişe ve Cam Fabrikaları A.Ş.",
        "sector":  "Holding",
        "desc":    "Cam sektöründe Türkiye'nin lider holdinglerinden. Düzcam (Trakya Cam), cam "
                   "ambalaj, ev eşyası ve kimyasal ürünler (Şişecam Kimyasallar) üretir. "
                   "Avrupa, CIS ve Asya'da uluslararası üretim tesisleri bulunmaktadır.",
    },
    "TOASO": {
        "name":    "Tofaş Türk Otomobil Fabrikası A.Ş.",
        "sector":  "Otomotiv",
        "desc":    "Koç Holding ve Stellantis (eski Fiat Chrysler) ortaklığıyla Bursa'da faaliyet "
                   "gösteren otomobil üreticisi. Fiat, Alfa Romeo ve Jeep markalı araç üretir; "
                   "ihracatı iç satışları önemli ölçüde geçmektedir.",
    },
    "FROTO": {
        "name":    "Ford Otomotiv Sanayi A.Ş.",
        "sector":  "Otomotiv",
        "desc":    "Koç Holding ve Ford Motor Company ortaklığıyla İzmit'te kurulu. Transit, "
                   "Ranger ve Kuga modellerini üretir. Türkiye'nin en büyük ihracatçı "
                   "firmalarından biri olup üretiminin büyük bölümünü Avrupa'ya ihraç eder.",
    },
    "ARCLK": {
        "name":    "Arçelik A.Ş.",
        "sector":  "Otomotiv",
        "desc":    "Koç Holding bünyesinde faaliyet gösteren küresel beyaz eşya ve tüketici "
                   "elektroniği üreticisi. Arçelik, Beko, Grundig, Blomberg gibi markalarla "
                   "Avrupa, Afrika ve Asya'da satış yapar.",
    },
    "TCELL": {
        "name":    "Turkcell İletişim Hizmetleri A.Ş.",
        "sector":  "Teknoloji",
        "desc":    "Türkiye'nin lider mobil operatörü. Mobil ses ve veri, fiber internet (Superonline), "
                   "dijital TV, bulut ve fintech (Paycell) hizmetleri sunar. Ukrayna ve diğer "
                   "ülkelerde de operasyonları bulunmaktadır.",
    },
    "TTKOM": {
        "name":    "Türk Telekomunikasyon A.Ş.",
        "sector":  "Teknoloji",
        "desc":    "Türkiye'nin sabit hat ve geniş bant altyapısını yöneten telekom devi. "
                   "ADSL/fiber internet, IP-TV, kurumsal veri merkezi ve bulut hizmetleri "
                   "ile siber güvenlik çözümleri sunar.",
    },
    "ASELS": {
        "name":    "Aselsan Elektronik Sanayi ve Ticaret A.Ş.",
        "sector":  "Teknoloji",
        "desc":    "Türkiye'nin lider savunma elektroniği şirketi. Radar, elektronik harp, "
                   "haberleşme sistemleri, optik ve tıbbi cihazlar üretir. OYAK bünyesinde "
                   "olup TSK'nın kritik tedarikçisidir.",
    },
    "PGSUS": {
        "name":    "Pegasus Hava Taşımacılığı A.Ş.",
        "sector":  "Havacılık",
        "desc":    "Türkiye merkezli düşük maliyetli havayolu şirketi. Sabiha Gökçen'i üs olarak "
                   "kullanan Pegasus, Avrupa, Orta Doğu ve Rusya'ya geniş ağla uçuş gerçekleştirir. "
                   "Esas Holding bünyesindedir.",
    },
    "ENKAI": {
        "name":    "Enka İnşaat ve Sanayi A.Ş.",
        "sector":  "Holding",
        "desc":    "Uluslararası büyük ölçekli inşaat, enerji üretimi ve gayrimenkul alanlarında "
                   "faaliyet gösteren holding. Rusya, Kazakistan ve Orta Doğu'da projeler yürütür; "
                   "doğalgaz ile kombine çevrim santralleri işletir.",
    },
    "EREGL": {
        "name":    "Ereğli Demir ve Çelik Fabrikaları T.A.Ş.",
        "sector":  "Metal",
        "desc":    "Türkiye'nin en büyük çelik üreticisi. Yassı çelik (rulo, sac, galvaniz) üretir; "
                   "otomotiv, beyaz eşya ve inşaat sektörlerine hammadde tedarik eder. "
                   "Oyak Grubu bünyesindedir.",
    },
    "PETKM": {
        "name":    "Petkim Petrokimya Holding A.Ş.",
        "sector":  "Enerji",
        "desc":    "Türkiye'nin tek entegre petrokimya şirketi. Aliağa'daki tesislerinde etilen, "
                   "polietilen, PVC ve diğer temel petrokimyasalları üretir. SOCAR (Azerbaycan) "
                   "ana hissedarıdır.",
    },
    "EKGYO": {
        "name":    "Emlak Konut Gayrimenkul Yatırım Ortaklığı A.Ş.",
        "sector":  "GYO",
        "desc":    "Türkiye'nin en büyük gayrimenkul yatırım ortaklığı. TOKİ'ye bağlı olarak "
                   "büyük ölçekli konut projeleri geliştirir; gelir paylaşımlı ve hasılat paylaşımlı "
                   "modeller kullanır.",
    },
    "MGROS": {
        "name":    "Migros Ticaret A.Ş.",
        "sector":  "Perakende",
        "desc":    "Türkiye'nin köklü süpermarket zinciri. Migros, Macrocenter ve 5M formatlarıyla "
                   "perakende gıda satışı yapar. Anadolu Grubu bünyesinde olan şirket, "
                   "e-ticaret (Sanal Market) alanında da büyümektedir.",
    },
    "HALKB": {
        "name":    "Türkiye Halk Bankası A.Ş.",
        "sector":  "Bankacılık",
        "desc":    "Türkiye Hazinesi'ne bağlı kamu bankası. KOBİ kredileri, esnaf finansmanı, "
                   "tarımsal krediler ve bireysel bankacılık hizmetleri sunar. "
                   "Yurt dışında da şube ağına sahiptir.",
    },
    "VAKBN": {
        "name":    "Türkiye Vakıflar Bankası T.A.O.",
        "sector":  "Bankacılık",
        "desc":    "Vakıflar Genel Müdürlüğü kontrolünde kamu bankası. Bireysel, ticari ve "
                   "kurumsal bankacılık hizmetleri sunar. Konut kredisi ve emekli maaşı "
                   "ödemelerinde güçlü pazar payına sahiptir.",
    },
    "KRDMD": {
        "name":    "Kardemir Karabük Demir Çelik Sanayi ve Ticaret A.Ş.",
        "sector":  "Metal",
        "desc":    "Karabük'te konuşlanan uzun çelik ürünleri (ray, profil, kiriş, filmaşin) "
                   "üreticisi. Demiryolu rayı üretiminde Türkiye'nin başlıca tedarikçisidir. "
                   "Kamuya ait ortaklık yapısına sahip özel sektör şirketidir.",
    },
    "ODAS": {
        "name":    "Odaş Elektrik Üretim Sanayi Ticaret A.Ş.",
        "sector":  "Enerji",
        "desc":    "Doğalgaz kombine çevrim santralleri ile elektrik üretimi yapan enerji şirketi. "
                   "Kapasitesini artırmak için yeni yatırımlar sürdürmektedir.",
    },
    "TAVHL": {
        "name":    "TAV Havalimanları Holding A.Ş.",
        "sector":  "Havacılık",
        "desc":    "Türkiye ve uluslararası havalimanlarını işleten şirket. İstanbul Atatürk (eski), "
                   "Ankara Esenboğa, İzmir, Gürcistan, Tunus ve diğer ülkelerdeki havalimanlarında "
                   "terminal işletmeciliği ve ground handling hizmetleri verir.",
    },
    "DOHOL": {
        "name":    "Doğan Şirketler Grubu Holding A.Ş.",
        "sector":  "Holding",
        "desc":    "Enerji (D-Enerji), otomotiv dağıtım, finans ve yatırım alanlarında faaliyet "
                   "gösteren holding. Eski medya varlıklarını Demirören'e devreden grup, "
                   "şu an yenilenebilir enerji yatırımlarına odaklanmaktadır.",
    },
    "TKFEN": {
        "name":    "Tekfen Holding A.Ş.",
        "sector":  "Holding",
        "desc":    "İnşaat & mühendislik (Tekfen İnşaat), tarım (Tarfin, gübre) ve gayrimenkul "
                   "geliştirme alanlarında faaliyet gösteren holding. BTC-CPC boru hattı ve "
                   "büyük petrol-gaz altyapı projelerinde deneyimlidir.",
    },
    "OYAKC": {
        "name":    "Oyak Çimento Fabrikaları A.Ş.",
        "sector":  "Çimento",
        "desc":    "OYAK (Ordu Yardımlaşma Kurumu) bünyesinde faaliyet gösteren büyük çimento "
                   "üreticisi. Türkiye'nin çeşitli bölgelerinde fabrikalarıyla iç piyasaya "
                   "ve ihracata çimento ve klinker tedarik eder.",
    },

    # ── BIST 100 (BIST 30 dışı) — v2 ────────────────────────────────────────

    # Bankacılık
    "ALBRK": {
        "name":    "Albaraka Türk Katılım Bankası A.Ş.",
        "sector":  "Bankacılık",
        "desc":    "Türkiye'nin önde gelen katılım bankalarından biri. Faizsiz bankacılık "
                   "prensipleriyle bireysel, ticari ve kurumsal müşterilere finansman sağlar. "
                   "Bahreyn merkezli Albaraka Banking Group'un Türkiye iştiraki.",
    },
    "SKBNK": {
        "name":    "Şekerbank T.A.Ş.",
        "sector":  "Bankacılık",
        "desc":    "Tarım, KOBİ ve bireysel bankacılık alanlarında hizmet veren köklü ticaret bankası. "
                   "Anadolu'da güçlü şube ağıyla tarımsal kredilerde önemli pazar payına sahiptir.",
    },
    "TSKB": {
        "name":    "Türkiye Sınai Kalkınma Bankası A.Ş.",
        "sector":  "Bankacılık",
        "desc":    "Türkiye'nin özel sektör kalkınma bankası. Sürdürülebilir enerji, sanayi ve "
                   "altyapı projelerine uzun vadeli kredi sağlar. Uluslararası finansman "
                   "kuruluşlarıyla ortaklıkları ile öne çıkar.",
    },

    # Holding
    "MPARK": {
        "name":    "MLP Sağlık Hizmetleri A.Ş.",
        "sector":  "Sağlık",
        "desc":    "Türkiye'nin en büyük özel hastane zinciri. Medical Park, Bahçeci Sağlık ve "
                   "VM Medical Park markaları altında Türkiye genelinde 40'tan fazla hastanede "
                   "hizmet vermektedir.",
    },
    "GLYHO": {
        "name":    "Global Yatırım Holding A.Ş.",
        "sector":  "Holding",
        "desc":    "Liman işletmeciliği (Global Ports), enerji, finans ve gayrimenkul alanlarında "
                   "faaliyet gösteren çeşitlendirilmiş holding. Türkiye ve Rusya'da liman "
                   "operasyonlarıyla uluslararası ticaret altyapısı sunar.",
    },
    "ACSEL": {
        "name":    "Acıselsan Acıpayam Selüloz Sanayi ve Ticaret A.Ş.",
        "sector":  "Holding",
        "desc":    "Selüloz ve kâğıt hammaddesi üretimi ile yatırım faaliyetleri yürüten sanayi "
                   "şirketi. Küçük ölçekli ama stratejik konumdaki Denizli merkezli işletme.",
    },
    "AGHOL": {
        "name":    "AG Anadolu Grubu Holding A.Ş.",
        "sector":  "Holding",
        "desc":    "Anadolu Grubu'nun çatı holdinglerinden biri. Otomotiv, içecek (Efes), "
                   "perakende ve sigorta sektörlerinde konsolidasyonu yönetir.",
    },

    # Havacılık
    "CLEBI": {
        "name":    "Çelebi Hava Servisi A.Ş.",
        "sector":  "Havacılık",
        "desc":    "Havalimanı yer hizmetleri (ground handling) ve kargo operasyonları alanında "
                   "uzmanlaşmış şirket. Türkiye başta olmak üzere Hindistan, Macaristan ve "
                   "diğer ülkelerdeki havalimanlarında hizmet verir.",
    },

    # Enerji
    "AYGAZ": {
        "name":    "Aygaz A.Ş.",
        "sector":  "Enerji",
        "desc":    "Türkiye'nin en büyük LPG dağıtım ve pazarlama şirketi. Koç Holding bünyesinde, "
                   "tüp gaz, otogaz ve endüstriyel gaz satışı yapar. Likit petrol gazı "
                   "depolama ve dolum tesislerine sahiptir.",
    },
    "ZOREN": {
        "name":    "Zorlu Enerji Elektrik Üretim A.Ş.",
        "sector":  "Enerji",
        "desc":    "Zorlu Holding'e bağlı elektrik üretim şirketi. Jeotermal, rüzgar ve doğalgaz "
                   "santrallerini bünyesinde barındırır. Türkiye'nin en büyük jeotermal enerji "
                   "üreticilerinden biridir.",
    },
    "AKSEN": {
        "name":    "Aksa Enerji Üretim A.Ş.",
        "sector":  "Enerji",
        "desc":    "Türkiye ve Afrika'da (Gana, Madagaskar, Senegal vb.) doğalgaz ve akaryakıt "
                   "bazlı elektrik üretim santralleri işleten enerji şirketi. "
                   "Kazancı Holding bünyesindedir.",
    },
    "AKSUE": {
        "name":    "Aksu Enerji ve Ticaret A.Ş.",
        "sector":  "Enerji",
        "desc":    "Küçük ölçekli hidroelektrik ve rüzgar santralleri üzerinden yenilenebilir "
                   "elektrik üretimi yapan şirket.",
    },
    "EUPWR": {
        "name":    "Europower Enerji ve Otomasyon Teknolojileri A.Ş.",
        "sector":  "Enerji",
        "desc":    "Yenilenebilir enerji projeleri geliştirme, otomasyon sistemleri ve "
                   "enerji verimliliği çözümleri sunan teknoloji odaklı enerji şirketi.",
    },
    "AKENR": {
        "name":    "Ak Enerji Elektrik Üretim A.Ş.",
        "sector":  "Enerji",
        "desc":    "Sabancı Holding ve Verbund ortaklığıyla kurulan elektrik üretim şirketi. "
                   "Hidroelektrik, doğalgaz ve rüzgar kaynaklarından enerji üretir.",
    },

    # Teknoloji
    "LOGO": {
        "name":    "Logo Yazılım Sanayi ve Ticaret A.Ş.",
        "sector":  "Teknoloji",
        "desc":    "Türkiye'nin en büyük kurumsal yazılım şirketlerinden biri. ERP, muhasebe, "
                   "İK ve üretim yönetimi yazılımları (Logo Tiger, Logo Go) üretir. "
                   "KOBİ ve büyük ölçekli işletmelere hizmet verir.",
    },
    "INDES": {
        "name":    "İndeks Bilgisayar Sistemleri Mühendislik Sanayi ve Ticaret A.Ş.",
        "sector":  "Teknoloji",
        "desc":    "Türkiye'nin önde gelen BT ürünleri distribütörü. Apple, Dell, HP, Lenovo "
                   "gibi markaların distribütörlüğünü üstlenir; iş ortakları kanalıyla "
                   "perakende ve kurumsal satış yapar.",
    },
    "ESCOM": {
        "name":    "Escom Elektronik Sistemleri İletişim Sanayi ve Ticaret A.Ş.",
        "sector":  "Teknoloji",
        "desc":    "Elektronik sistem entegrasyonu ve BT altyapı çözümleri alanında faaliyet "
                   "gösteren teknoloji şirketi.",
    },
    "NETAS": {
        "name":    "Netaş Telekomünikasyon A.Ş.",
        "sector":  "Teknoloji",
        "desc":    "Telekomünikasyon altyapısı, yazılım ve sistem entegrasyonu alanında hizmet "
                   "veren şirket. Türk Telekom ve diğer operatörlere ağ çözümleri sunar.",
    },
    "FONET": {
        "name":    "Fonet Bilgi Teknolojileri A.Ş.",
        "sector":  "Teknoloji",
        "desc":    "Hastane bilgi yönetim sistemi (HBYS) yazılımları geliştiren sağlık BT şirketi. "
                   "Türkiye'deki kamu ve özel hastanelere dijital sağlık çözümleri sunar.",
    },
    "DGATE": {
        "name":    "Datagate Bilgisayar Malzemeleri Ticaret A.Ş.",
        "sector":  "Teknoloji",
        "desc":    "BT donanımı distribütörü. Bilgisayar bileşenleri, çevre birimleri ve "
                   "ağ ürünlerini toptancılık kanalıyla pazarlar.",
    },

    # Otomotiv
    "OTKAR": {
        "name":    "Otokar Otomotiv ve Savunma Sanayi A.Ş.",
        "sector":  "Otomotiv",
        "desc":    "Zırhlı araç, askeri araç ve kamu ulaşım araçları (otobüs, minibüs) üreten "
                   "savunma-otomotiv firması. Koç Holding bünyesinde; COBRA ve ARMA gibi "
                   "zırhlı araçlarıyla ihracat yapar.",
    },
    "DOAS": {
        "name":    "Doğuş Otomotiv Servis ve Ticaret A.Ş.",
        "sector":  "Otomotiv",
        "desc":    "Volkswagen, Audi, Porsche, SEAT ve Bentley gibi markaların Türkiye "
                   "distribütörlüğünü yapan otomotiv grubu. Doğuş Holding bünyesinde.",
    },
    "TTRAK": {
        "name":    "Türk Traktör ve Ziraat Makineleri A.Ş.",
        "sector":  "Otomotiv",
        "desc":    "Koç Holding ve CNH Industrial ortaklığıyla faaliyet gösteren traktör üreticisi. "
                   "New Holland ve Case markalı traktörleri Ankara'da üretir; "
                   "Türkiye tarım mekanizasyonunun temel tedarikçilerindendir.",
    },
    "BRISA": {
        "name":    "Brisa Bridgestone Sabancı Lastik Sanayi ve Ticaret A.Ş.",
        "sector":  "Otomotiv",
        "desc":    "Sabancı Holding ve Bridgestone ortaklığıyla üretim yapan lastik şirketi. "
                   "Lassa ve Bridgestone markalı araç lastiklerini İzmit fabrikasında üretir.",
    },
    "KLMSN": {
        "name":    "Klimasan Klima Sanayi ve Ticaret A.Ş.",
        "sector":  "Otomotiv",
        "desc":    "Ticari araç iklimlendirme sistemleri (kamyon, otobüs, frigorifik kasa) "
                   "üreten nişe sanayi şirketi. İhracat odaklı üretim yapar.",
    },

    # GYO
    "TRGYO": {
        "name":    "Torunlar Gayrimenkul Yatırım Ortaklığı A.Ş.",
        "sector":  "GYO",
        "desc":    "Torunlar Grubu'nun GYO kolu. Mall of Istanbul, Torun Tower gibi büyük ölçekli "
                   "AVM ve karma kullanım projeleri geliştirir ve işletir.",
    },
    "ISGYO": {
        "name":    "İş Gayrimenkul Yatırım Ortaklığı A.Ş.",
        "sector":  "GYO",
        "desc":    "İş Bankası grubunun gayrimenkul yatırım ortaklığı. Ofis, AVM ve konut "
                   "projelerini portföyünde barındırır; kiralama ve değer artış gelirleri odaklıdır.",
    },
    "VKGYO": {
        "name":    "Vakıf Gayrimenkul Yatırım Ortaklığı A.Ş.",
        "sector":  "GYO",
        "desc":    "Vakıfbank grubunun GYO iştiraki. Ofis, konut ve ticari gayrimenkul "
                   "portföyünü yönetir.",
    },
    "TSGYO": {
        "name":    "Teksil Gayrimenkul Yatırım Ortaklığı A.Ş.",
        "sector":  "GYO",
        "desc":    "Ticari ve lojistik gayrimenkul alanında yatırım yapan küçük ölçekli GYO.",
    },
    "NUGYO": {
        "name":    "Nurol Gayrimenkul Yatırım Ortaklığı A.Ş.",
        "sector":  "GYO",
        "desc":    "Nurol Holding bünyesinde konut ve ticari gayrimenkul projeleri geliştiren GYO. "
                   "Ankara ve İstanbul'da büyük ölçekli projeler yürütür.",
    },
    "RGYAS": {
        "name":    "Reysaş Gayrimenkul Yatırım Ortaklığı A.Ş.",
        "sector":  "GYO",
        "desc":    "Lojistik depo ve sanayi gayrimenkulü alanında uzmanlaşmış GYO. "
                   "Kiralık depo ve lojistik üsler portföyünü yönetir.",
    },

    # Perakende & Gıda
    "ULKER": {
        "name":    "Ülker Bisküvi Sanayi A.Ş.",
        "sector":  "Gıda",
        "desc":    "Türkiye'nin en büyük bisküvi ve çikolata üreticisi. Ülker, McVitie's ve "
                   "Godiva markaları altında Orta Doğu, Afrika ve Avrupa'ya ihracat yapar. "
                   "Yıldız Holding bünyesindedir.",
    },
    "CCOLA": {
        "name":    "Coca-Cola İçecek A.Ş.",
        "sector":  "Gıda",
        "desc":    "The Coca-Cola Company'nin Türkiye ve 10 ülkede daha (Pakistan, Kazakistan, "
                   "Irak, Suriye vb.) üretim ve dağıtımını gerçekleştiren şişeleme şirketi. "
                   "Anadolu Grubu ve Coca-Cola ortaklığında faaliyet gösterir.",
    },
    "SOKM": {
        "name":    "Şok Marketler Ticaret A.Ş.",
        "sector":  "Perakende",
        "desc":    "Türkiye'nin hızla büyüyen indirimli market zinciri. Yıldız Holding'e bağlı "
                   "Şok Marketler, 10.000'i aşkın mağazasıyla gıda ve temel tüketim malları satar.",
    },
    "AEFES": {
        "name":    "Anadolu Efes Biracılık ve Malt Sanayii A.Ş.",
        "sector":  "Gıda",
        "desc":    "Türkiye'nin lider bira üreticisi ve uluslararası bira grubu. Efes markalı "
                   "biralar üretir; Rusya ve BDT ülkelerinde AB InBev ile ortaklık yürütür. "
                   "Anadolu Grubu bünyesindedir.",
    },
    "PRKME": {
        "name":    "Park Elektrik Üretim Madencilik Sanayi ve Ticaret A.Ş.",
        "sector":  "Madencilik",
        "desc":    "Bakır madeni işletmeciliği ve elektrik üretimi alanlarında faaliyet gösterir. "
                   "Siirt Madenköy'deki bakır madenini işletir.",
    },
    "TATGD": {
        "name":    "Tat Gıda Sanayi A.Ş.",
        "sector":  "Gıda",
        "desc":    "Domates salçası, ketçap, konserve sebze ve meyve suyu üreticisi. "
                   "Koç Holding bünyesinde; Tat markasıyla yurt içi ve ihracat pazarlarına hizmet eder.",
    },
    "KENT": {
        "name":    "Kent Gıda Maddeleri Sanayi ve Ticaret A.Ş.",
        "sector":  "Gıda",
        "desc":    "Şekerleme, çikolata ve bisküvi üreticisi. Pladis Global bünyesinde "
                   "faaliyet gösteren şirket, Türkiye iç pazarına ve ihracata üretim yapar.",
    },
    "PNSUT": {
        "name":    "Pınar Süt Mamulleri Sanayii A.Ş.",
        "sector":  "Gıda",
        "desc":    "Yaşar Holding bünyesinde süt ve süt ürünleri (peynir, yoğurt, tereyağı) "
                   "üreten İzmir merkezli gıda şirketi. Pınar markasıyla tanınır.",
    },

    # Metal & Madencilik
    "KRDMB": {
        "name":    "Kardemir Karabük Demir Çelik San. ve Tic. A.Ş. (B Grubu)",
        "sector":  "Metal",
        "desc":    "Kardemir'in B grubu hisseleri. Karabük'te uzun çelik ürünleri (ray, profil) "
                   "üreten entegre demir-çelik tesisi. KRDMD ile aynı şirkettir, hisse sınıfı farklıdır.",
    },
    "ISDMR": {
        "name":    "İskenderun Demir ve Çelik A.Ş.",
        "sector":  "Metal",
        "desc":    "İskenderun'daki entegre demir-çelik tesislerini işleten şirket. "
                   "Yassı çelik ürünleri üretir; Oyak Grubu bünyesindedir.",
    },

    # Çimento
    "CIMSA": {
        "name":    "Çimsa Çimento Sanayi ve Ticaret A.Ş.",
        "sector":  "Çimento",
        "desc":    "Sabancı Holding bünyesinde çimento ve hazır beton üreticisi. Mersin, Kayseri "
                   "ve İspanya'da fabrikaları bulunan şirket, beyaz çimento üretiminde "
                   "dünya liderleri arasındadır.",
    },
    "AKCNS": {
        "name":    "Akçansa Çimento Sanayi ve Ticaret A.Ş.",
        "sector":  "Çimento",
        "desc":    "Sabancı Holding ve HeidelbergCement ortaklığıyla İstanbul yakınında "
                   "faaliyet gösteren çimento ve hazır beton üreticisi.",
    },
    "NUHCM": {
        "name":    "Nuh Çimento Sanayi A.Ş.",
        "sector":  "Çimento",
        "desc":    "Körfez / Kocaeli'de kurulu köklü çimento üreticisi. İç piyasa ve "
                   "ihracat (özellikle Afrika) odaklı üretim yapar.",
    },
    "GOLTS": {
        "name":    "Göltaş Göller Bölgesi Çimento Sanayi ve Ticaret A.Ş.",
        "sector":  "Çimento",
        "desc":    "Isparta merkezli çimento üreticisi. İç Anadolu ve Akdeniz bölgelerine "
                   "çimento ve klinker tedarik eder.",
    },

    # Kimya & Cam
    "SASA": {
        "name":    "SASA Polyester Sanayi A.Ş.",
        "sector":  "Kimya",
        "desc":    "Türkiye'nin en büyük polyester iplik ve PET reçine üreticisi. Adana'daki "
                   "dev entegre tesisinde PTA, PET ve polyester elyaf üretir. Kapasite "
                   "genişleme yatırımlarıyla Avrupa'nın en büyük polyester kompleksine "
                   "dönüşme hedefiyle büyümektedir.",
    },
    "GUBRF": {
        "name":    "Gübre Fabrikaları T.A.Ş.",
        "sector":  "Kimya",
        "desc":    "Türkiye'nin en büyük gübre üreticisi. Azotlu ve kompoze gübreler üretir; "
                   "tarım sektörüne yurt içi ve ihracat kanalıyla satar.",
    },
    "VESTL": {
        "name":    "Vestel Elektronik Sanayi ve Ticaret A.Ş.",
        "sector":  "Elektronik",
        "desc":    "Türkiye'nin en büyük elektronik üreticisi. TV, beyaz eşya ve küçük "
                   "ev aletleri üretir. Avrupa'ya ihracat odaklı Manisa fabrikasıyla "
                   "Vestel markaları altında üretim yapar. Zorlu Holding bünyesindedir.",
    },

    # Sigorta & Finans
    "AKGRT": {
        "name":    "Aksigorta A.Ş.",
        "sector":  "Sigorta",
        "desc":    "Sabancı Holding ve Ageas ortaklığında faaliyet gösteren büyük sigorta şirketi. "
                   "Araç, konut, sağlık ve kurumsal sigorta ürünleri sunar.",
    },
    "RAYSG": {
        "name":    "Ray Sigorta A.Ş.",
        "sector":  "Sigorta",
        "desc":    "Türkiye'de hayat dışı sigorta alanında faaliyet gösteren sigorta şirketi. "
                   "Kasko, trafik ve sağlık sigortası ürünleri sunar.",
    },
    "ANHYT": {
        "name":    "Anadolu Hayat Emeklilik A.Ş.",
        "sector":  "Sigorta",
        "desc":    "İş Bankası Grubu bünyesinde hayat sigortası ve bireysel emeklilik (BES) "
                   "ürünleri sunan şirket. Türkiye'nin en büyük hayat/emeklilik şirketlerinden.",
    },

    # Tekstil & Moda
    "MAVI": {
        "name":    "Mavi Giyim Sanayi ve Ticaret A.Ş.",
        "sector":  "Tekstil",
        "desc":    "Türkiye'nin en değerli hazırgiyim markalarından biri. Denim odaklı "
                   "uluslararası moda markası olarak Türkiye, ABD, Kanada ve Avrupa'da "
                   "perakende satış yapar.",
    },
    "KLNMA": {
        "name":    "Türkiye Kalkınma ve Yatırım Bankası A.Ş.",
        "sector":  "Bankacılık",
        "desc":    "Türkiye Hazinesi'ne bağlı kalkınma bankası. Altyapı, enerji, sanayi ve "
                   "teknoloji projelerine uzun vadeli proje finansmanı sağlar. "
                   "Uluslararası finansman kuruluşlarından kaynak aktarır.",
    },

    # Diğer Sanayi (BIST 100 kapsamı)
    "KONYA": {
        "name":    "Konya Çimento Sanayii A.Ş.",
        "sector":  "Çimento",
        "desc":    "Konya ve çevresine çimento üreten bölgesel çimento fabrikası. "
                   "İç Anadolu inşaat sektörünün temel tedarikçilerinden.",
    },
    "PRKAB": {
        "name":    "Türk Prysmian Kablo ve Sistemleri A.Ş.",
        "sector":  "Sanayi",
        "desc":    "İtalyan Prysmian Group'un Türkiye iştiraki. Enerji ve iletişim kabloları "
                   "üretir; elektrik altyapı projeleri için tedarikçidir.",
    },
    "SELEC": {
        "name":    "Selçuk Ecza Deposu Ticaret ve Sanayi A.Ş.",
        "sector":  "Sağlık",
        "desc":    "Türkiye'nin en büyük ilaç distribütörlerinden biri. Eczanelere ve "
                   "hastanelere ilaç, tıbbi malzeme ve kozmetik ürün dağıtımı yapar.",
    },
    "TURSG": {
        "name":    "Türkiye Sigorta A.Ş.",
        "sector":  "Sigorta",
        "desc":    "Kamu destekli büyük sigorta şirketi. Zorunlu trafik, doğal afet ve "
                   "tarım sigortası başta olmak üzere geniş ürün yelpazesiyle hizmet verir.",
    },
    "GENIL": {
        "name":    "Gen İlaç ve Sağlık Ürünleri Sanayi ve Ticaret A.Ş.",
        "sector":  "Sağlık",
        "desc":    "Jenerik ilaç üretimi ve dağıtımı alanında faaliyet gösteren ilaç şirketi.",
    },
    "ADEL": {
        "name":    "Adel Kalemcilik Ticaret ve Sanayi A.Ş.",
        "sector":  "Sanayi",
        "desc":    "Türkiye'nin önde gelen kalem ve kırtasiye ürünleri üreticisi. "
                   "Pilot ve Adel markalı ürünlerle yurt içi ve ihracat pazarlarına hizmet eder.",
    },
    "IHEVA": {
        "name":    "İhlas Ev Aletleri İmalat Sanayi ve Ticaret A.Ş.",
        "sector":  "Sanayi",
        "desc":    "Ev aletleri ve küçük elektrikli ürünler üreticisi. İhlas Grubu bünyesinde; "
                   "Türkiye iç pazarı ve ihracat için üretim yapar.",
    },
    "KARSN": {
        "name":    "Karsan Otomotiv Sanayii ve Ticaret A.Ş.",
        "sector":  "Otomotiv",
        "desc":    "Elektrikli ve konvansiyonel minibüs, midibüs ve hafif ticari araç üreticisi. "
                   "Jest, Atak ve Atık modelleriyle Avrupa toplu taşıma pazarına ihracat yapar.",
    },
    "ORGE": {
        "name":    "Orge Enerji Elektrik Taahhüt A.Ş.",
        "sector":  "Enerji",
        "desc":    "Elektrik taahhüt, enerji altyapısı kurulum ve bakım hizmetleri veren şirket. "
                   "Enerji dağıtım şirketleri ve sanayi tesisleri başlıca müşterileridir.",
    },
    "PENGD": {
        "name":    "Penguen Gıda Sanayi A.Ş.",
        "sector":  "Gıda",
        "desc":    "Konserve sebze, meyve ve domates ürünleri üreticisi. "
                   "Türkiye iç pazarı ve ihracat için üretim yapan köklü gıda şirketi.",
    },
    "RYSAS": {
        "name":    "Reysaş Taşımacılık ve Lojistik Ticaret A.Ş.",
        "sector":  "Lojistik",
        "desc":    "Karayolu taşımacılığı, depolama ve lojistik hizmetleri sunan şirket. "
                   "Türkiye genelinde depo ağı ve araç filosuyla faaliyet gösterir.",
    },
    "TLMAN": {
        "name":    "Tatlıcan-Pastavilla Gıda San. ve Tic. A.Ş.",
        "sector":  "Gıda",
        "desc":    "Makarna, bulgur ve diğer tahıl ürünleri üreticisi. "
                   "Pastavilla markasıyla tanınan gıda şirketi.",
    },
    "YATAS": {
        "name":    "Yataş Yatak ve Yorgan Sanayi Ticaret A.Ş.",
        "sector":  "Sanayi",
        "desc":    "Yatak, yorgan ve uyku ürünleri üreten ve perakende satan şirket. "
                   "Türkiye genelinde mağazaları ve e-ticaret kanalıyla satış yapar.",
    },
    "GENTS": {
        "name":    "Gentaş Genel Metal Sanayi ve Ticaret A.Ş.",
        "sector":  "Metal",
        "desc":    "Dekoratif levha (melamin, MDF kaplama) ve yüzey malzemeleri üreticisi. "
                   "Mobilya sektörüne hammadde tedarik eden sanayi şirketi.",
    },

    # ── XKTUM Batch 1 (1-50): AAGYO → CIMSA — v3 ────────────────────────────

    "AAGYO": {
        "name":    "Atakule Gayrimenkul Yatırım Ortaklığı A.Ş.",
        "sector":  "GYO",
        "desc":    "İzmir'in simgesi Atakule Kulesi'ni ve çevre ticari gayrimenkulleri "
                   "portföyünde barındıran GYO. Kiralama ve değer artış gelirleri odaklıdır.",
    },
    "AHSGY": {
        "name":    "Anahtar Gayrimenkul Yatırım Ortaklığı A.Ş.",
        "sector":  "GYO",
        "desc":    "Konut ve ticari gayrimenkul portföyünü yöneten küçük ölçekli GYO.",
    },
    "AKFYE": {
        "name":    "Akfen Yenilenebilir Enerji A.Ş.",
        "sector":  "Enerji",
        "desc":    "Akfen Holding bünyesinde rüzgar ve güneş enerjisi santralleri geliştiren "
                   "ve işleten yenilenebilir enerji şirketi.",
    },
    "AKHAN": {
        "name":    "Ak-Han Tekstil Sanayi ve Ticaret A.Ş.",
        "sector":  "Tekstil",
        "desc":    "Dokuma ve tekstil ürünleri üreticisi. Türkiye iç pazarı ve ihracat için "
                   "ham ve mamul tekstil ürünleri üretir.",
    },
    "AKSA": {
        "name":    "Aksa Akrilik Kimya Sanayii A.Ş.",
        "sector":  "Kimya",
        "desc":    "Dünya'nın en büyük akrilik elyaf üreticilerinden biri. Kazancı Holding "
                   "bünyesinde; tekstil, açık hava döşemesi ve endüstriyel kullanım için "
                   "akrilik elyaf ve iplik üretir.",
    },
    "AKYHO": {
        "name":    "Akiş Gayrimenkul Yatırım Ortaklığı A.Ş.",
        "sector":  "GYO",
        "desc":    "Akköy AVM ve Akasya Acıbadem projesini bünyesinde barındıran GYO. "
                   "İstanbul'da karma kullanım (AVM + konut + ofis) projeleri geliştirir.",
    },
    "ALCTL": {
        "name":    "Alcatel Lucent Teletaş Telekomünikasyon A.Ş.",
        "sector":  "Teknoloji",
        "desc":    "Telekomünikasyon ekipmanları ve ağ çözümleri sağlayan şirket. "
                   "Nokia bünyesindeki Alcatel-Lucent'in Türkiye iştiraki.",
    },
    "ALKA": {
        "name":    "Alka Sigorta A.Ş.",
        "sector":  "Sigorta",
        "desc":    "Hayat dışı sigorta branşlarında hizmet veren sigorta şirketi.",
    },
    "ALKIM": {
        "name":    "Alkim Kağıt Sanayi ve Ticaret A.Ş.",
        "sector":  "Kimya",
        "desc":    "Sodyum sülfat ve kağıt hammaddeleri üreticisi. Çankırı'daki tesislerinde "
                   "doğal sodyum sülfat çıkarır ve işler; cam, deterjan ve kağıt sektörlerine satar.",
    },
    "ALKLC": {
        "name":    "Alkaloid İlaç Sanayi ve Ticaret A.Ş.",
        "sector":  "İlaç",
        "desc":    "Makedonya merkezli Alkaloid firmasının Türkiye iştiraki. "
                   "Jenerik ilaç üretimi ve dağıtımı alanında faaliyet gösterir.",
    },
    "ALTNY": {
        "name":    "Altınyağ Kombinaları A.Ş.",
        "sector":  "Gıda",
        "desc":    "Bitkisel yağ (ayçiçek, mısır, fındık) üretimi ve rafine etme alanında "
                   "faaliyet gösteren gıda sanayi şirketi.",
    },
    "ALVES": {
        "name":    "Alves Elektronik Ticaret A.Ş.",
        "sector":  "Teknoloji",
        "desc":    "Elektronik ürünler ticareti ve e-ticaret alanında faaliyet gösteren şirket.",
    },
    "ANGEN": {
        "name":    "Anatolia Genişbant Telekom A.Ş.",
        "sector":  "Teknoloji",
        "desc":    "Bölgesel genişbant internet ve telekomünikasyon hizmetleri sunan şirket.",
    },
    "ARASE": {
        "name":    "Arsan Tekstil Ticaret ve Sanayi A.Ş.",
        "sector":  "Tekstil",
        "desc":    "Örme kumaş ve tekstil ürünleri üreticisi. Avrupa başta olmak üzere "
                   "ihracat odaklı üretim yapan Bursa merkezli tekstil şirketi.",
    },
    "ARDYZ": {
        "name":    "Ardyz Animasyon ve Görsel Efektler A.Ş.",
        "sector":  "Teknoloji",
        "desc":    "Oyun, sinema ve reklam sektörlerine animasyon ve görsel efekt hizmetleri "
                   "üreten Türkiye'nin öncü dijital içerik şirketlerinden biri.",
    },
    "ARFYE": {
        "name":    "ARF Gayrimenkul Yatırım Ortaklığı A.Ş.",
        "sector":  "GYO",
        "desc":    "Ticari ve konut gayrimenkul projelerine yatırım yapan GYO.",
    },
    "ATAKP": {
        "name":    "Atakaş Petrokimya Sanayi ve Ticaret A.Ş.",
        "sector":  "Kimya",
        "desc":    "Petrokimyasal ürünler ticareti ve sanayi alanında faaliyet gösteren şirket.",
    },
    "ATATP": {
        "name":    "Ata Tarım Ürünleri Sanayi ve Ticaret A.Ş.",
        "sector":  "Tarım",
        "desc":    "Tarımsal ürünler işleme, depolama ve ticareti alanında faaliyet gösteren şirket.",
    },
    "AVPGY": {
        "name":    "Avrasya Petrol ve Turistik Tesisler Gayrimenkul A.Ş.",
        "sector":  "GYO",
        "desc":    "Akaryakıt istasyonu ve turizm tesisi gayrimenkullerini portföyünde "
                   "barındıran yatırım ortaklığı.",
    },
    "AYEN": {
        "name":    "Ayen Enerji A.Ş.",
        "sector":  "Enerji",
        "desc":    "Hidroelektrik santraller aracılığıyla yenilenebilir elektrik üretimi yapan "
                   "enerji şirketi. Karadeniz havzasındaki HES'lerle faaliyet gösterir.",
    },
    "BAHKM": {
        "name":    "Bahçıvan Kimya Sanayi ve Ticaret A.Ş.",
        "sector":  "Kimya",
        "desc":    "Boya, vernik ve yüzey koruma ürünleri üreten kimya sanayi şirketi.",
    },
    "BAKAB": {
        "name":    "Bak Ambalaj Sanayi ve Ticaret A.Ş.",
        "sector":  "Sanayi",
        "desc":    "Oluklu mukavva ve ambalaj malzemeleri üreticisi. Gıda ve sanayi sektörlerine "
                   "özel ambalaj çözümleri sunar.",
    },
    "BANVT": {
        "name":    "Banvit Bandırma Vitaminli Yem Sanayii A.Ş.",
        "sector":  "Gıda",
        "desc":    "Türkiye'nin önde gelen entegre tavukçuluk ve kanatlı eti şirketi. "
                   "Bandırma merkezli; yem üretiminden kesimhaneye kadar tam entegre üretim yapar. "
                   "BRF Brasil'in iştiraki.",
    },
    "BASGZ": {
        "name":    "Başkent Doğalgaz Dağıtım A.Ş.",
        "sector":  "Enerji",
        "desc":    "Ankara ve çevre illerde doğalgaz dağıtım altyapısını işleten şirket. "
                   "Milyonlarca aboneye konut ve sanayi doğalgazı dağıtır.",
    },
    "BEGYO": {
        "name":    "Bera Gayrimenkul Yatırım Ortaklığı A.Ş.",
        "sector":  "GYO",
        "desc":    "Konut ve ticari gayrimenkul projelerine yatırım yapan GYO.",
    },
    "BERA": {
        "name":    "Bera Holding A.Ş.",
        "sector":  "Holding",
        "desc":    "İnşaat, gayrimenkul ve enerji alanlarında yatırımları olan holding şirketi.",
    },
    "BESTE": {
        "name":    "Beste Tekstil Konfeksiyon Kağıt Ürünleri San. ve Tic. A.Ş.",
        "sector":  "Tekstil",
        "desc":    "Tekstil ve kağıt ürünleri üretimi alanında faaliyet gösteren sanayi şirketi.",
    },
    "BIENY": {
        "name":    "Bienayı Biyolojik Enerji A.Ş.",
        "sector":  "Enerji",
        "desc":    "Biyoenerji ve yenilenebilir enerji kaynakları alanında faaliyet gösteren şirket.",
    },
    "BINBN": {
        "name":    "Binbirondört Portföy Yönetimi A.Ş.",
        "sector":  "Finans",
        "desc":    "Portföy yönetimi ve yatırım danışmanlığı hizmetleri sunan finans şirketi.",
    },
    "BINHO": {
        "name":    "Bin Holding A.Ş.",
        "sector":  "Holding",
        "desc":    "Çeşitli sektörlerde yatırımları olan holding şirketi.",
    },
    "BMSTL": {
        "name":    "Borusan Mannesmann Boru Sanayi ve Ticaret A.Ş.",
        "sector":  "Metal",
        "desc":    "Borusan Holding ve Salzgitter (Almanya) ortaklığında çelik boru üreticisi. "
                   "Enerji boru hatları, inşaat ve makine sektörlerine büyük çaplı çelik boru tedarik eder.",
    },
    "BNTAS": {
        "name":    "Bantaş Nakliyat ve Bankacılık Teknolojileri A.Ş.",
        "sector":  "Finans",
        "desc":    "Değerli evrak, para ve kıymetli madde taşımacılığı ile nakit yönetimi "
                   "hizmetleri sunan güvenlik lojistik şirketi. Bankalara nakit taşıma ve "
                   "ATM dolum hizmetleri verir.",
    },
    "BORSK": {
        "name":    "Borsa Konya Tarım Ürünleri İhtisas Serbest Bölgesi A.Ş.",
        "sector":  "Tarım",
        "desc":    "Tarım ürünleri ticareti ve depolama hizmetleri alanında faaliyet gösteren şirket.",
    },
    "BOSSA": {
        "name":    "Bossa Ticaret ve Sanayi İşletmeleri T.A.Ş.",
        "sector":  "Tekstil",
        "desc":    "Adana merkezli entegre tekstil şirketi. Pamuklu ve sentetik dokuma kumaş, "
                   "iplik üretir; otomotiv, ev tekstili ve hazırgiyim sektörlerine satar.",
    },
    "BRKSN": {
        "name":    "Berkosan Yalıtım ve Tecrit Maddeleri Sanayi ve Ticaret A.Ş.",
        "sector":  "Sanayi",
        "desc":    "Isı ve ses yalıtım malzemeleri üreticisi. İnşaat sektörüne polystren "
                   "ve mineral yün bazlı yalıtım ürünleri tedarik eder.",
    },
    "BRLSM": {
        "name":    "Birleşim Mühendislik Elektrik İnşaat ve Bilişim Hizmetleri A.Ş.",
        "sector":  "Sanayi",
        "desc":    "Elektrik altyapısı kurulum, mühendislik ve EPC (mühendislik-tedarik-inşaat) "
                   "projeleri yürüten şirket.",
    },
    "BSOKE": {
        "name":    "Batı Söke Çimento Sanayi T.A.Ş.",
        "sector":  "Çimento",
        "desc":    "Söke / Aydın bölgesinde konuşlanmış çimento üreticisi. Ege bölgesine "
                   "ve ihracata çimento ve klinker tedarik eder.",
    },
    "BURCE": {
        "name":    "Burçelik Vana Sanayi ve Ticaret A.Ş.",
        "sector":  "Metal",
        "desc":    "Endüstriyel vana, flanş ve boru bağlantı elemanları üreten metal sanayi şirketi. "
                   "Petrol, gaz ve kimya endüstrisine tedarikçidir.",
    },
    "BURVA": {
        "name":    "Burçelik A.Ş.",
        "sector":  "Metal",
        "desc":    "Çelik çubuk, filmaşin ve inşaat demiri üreten Bursa merkezli çelik şirketi. "
                   "İnşaat ve imalat sektörlerine uzun çelik ürünleri tedarik eder.",
    },
    "CANTE": {
        "name":    "Can Tarım ve Gıda Ürünleri Sanayi ve Ticaret A.Ş.",
        "sector":  "Gıda",
        "desc":    "Tarımsal ürün işleme ve gıda sanayi alanında faaliyet gösteren şirket.",
    },
    "CATES": {
        "name":    "Çatı İnşaat ve Gayrimenkul A.Ş.",
        "sector":  "GYO",
        "desc":    "Konut ve ticari gayrimenkul geliştirme alanında faaliyet gösteren şirket.",
    },
    "CELHA": {
        "name":    "Çelik Halat ve Tel Sanayii A.Ş.",
        "sector":  "Metal",
        "desc":    "Çelik halat, tel ve kablo üreticisi. İnşaat, madencilik, asansör ve "
                   "denizcilik sektörlerine yüksek mukavemetli çelik halat tedarik eder.",
    },
    "CEMTS": {
        "name":    "Çemtaş Çelik Makine Sanayi ve Ticaret A.Ş.",
        "sector":  "Metal",
        "desc":    "Özel çelik döküm ve dövme parçalar üreten makine sanayi şirketi. "
                   "Otomotiv, savunma ve ağır sanayi sektörlerine tedarikçidir.",
    },
    "CEMZY": {
        "name":    "Çemzy Çimento Üretim ve Ticaret A.Ş.",
        "sector":  "Çimento",
        "desc":    "Bölgesel çimento üretimi alanında faaliyet gösteren sanayi şirketi.",
    },
    "CVKMD": {
        "name":    "CVK Madencilik ve İnşaat Sanayi A.Ş.",
        "sector":  "Madencilik",
        "desc":    "Maden işletmeciliği ve inşaat sektörlerinde faaliyet gösteren şirket. "
                   "Krom, bakır ve diğer madenlerin arama, çıkarma ve işlenmesiyle uğraşır.",
    },

    # ── XKTUM Batch 2 (51-100): CMBTN → GRTHO — v4 ──────────────────────────

    "CMBTN": {
        "name":    "Çimbeton Hazırbeton ve Prefabrik Yapı Elemanları San. ve Tic. A.Ş.",
        "sector":  "Çimento",
        "desc":    "Hazır beton ve prefabrik yapı elemanları üreticisi. İnşaat sektörüne "
                   "beton çözümleri sunan Çimsa grubunun iştiraki.",
    },
    "COSMO": {
        "name":    "Cosmos Yatırım Holding A.Ş.",
        "sector":  "Holding",
        "desc":    "Turizm, gayrimenkul ve ticaret alanlarında yatırımları olan holding.",
    },
    "DAPGM": {
        "name":    "DAP Gayrimenkul Geliştirme A.Ş.",
        "sector":  "GYO",
        "desc":    "İstanbul'da lüks konut ve karma kullanım projeleri geliştiren gayrimenkul şirketi. "
                   "DAP Yapı markasıyla büyük ölçekli şehir dönüşümü projeleri yürütür.",
    },
    "DARDL": {
        "name":    "Dardanel Önentaş Gıda Sanayi A.Ş.",
        "sector":  "Gıda",
        "desc":    "Balık konservesi ve deniz ürünleri işleme alanında Türkiye'nin lider "
                   "şirketlerinden biri. Ton balığı, sardalya ve diğer konserveler ihraç eder.",
    },
    "DCTTR": {
        "name":    "Doç Tarım Ürünleri Sanayi ve Ticaret A.Ş.",
        "sector":  "Tarım",
        "desc":    "Tarımsal ürünlerin işlenmesi ve ticareti alanında faaliyet gösteren şirket.",
    },
    "DENGE": {
        "name":    "Denge Yatırım Holding A.Ş.",
        "sector":  "Holding",
        "desc":    "Finans, enerji ve gayrimenkul alanlarında yatırımları olan holding şirketi.",
    },
    "DESPC": {
        "name":    "Despec Bilgisayar Pazarlama ve Ticaret A.Ş.",
        "sector":  "Teknoloji",
        "desc":    "Bilgisayar sarf malzemeleri ve çevre birimi distribütörü. Yazıcı kartuşu, "
                   "toner ve ofis teknolojisi ürünlerini toptancılık kanalıyla pazarlar.",
    },
    "DGNMO": {
        "name":    "Doğan Müzik Kitap Mağazacılık ve Pazarlama A.Ş.",
        "sector":  "Medya",
        "desc":    "Kitap, müzik ve kültürel ürünlerin perakende satışı alanında faaliyet "
                   "gösteren şirket. D&R mağaza zincirini işletir.",
    },
    "DMSAS": {
        "name":    "Demisaş Döküm Emaye Mamülleri Sanayi A.Ş.",
        "sector":  "Metal",
        "desc":    "Dökme demir ve emaye kaplı mutfak eşyası (tencere, tava) üreticisi. "
                   "Avrupa'ya ihracat yapan Bursa merkezli metal sanayi şirketi.",
    },
    "DOFER": {
        "name":    "Doğuş Otomotiv ve Finansman A.Ş.",
        "sector":  "Finans",
        "desc":    "Doğuş Otomotiv bünyesinde araç finansmanı ve leasing hizmetleri sunan finansal şirket.",
    },
    "DOFRB": {
        "name":    "Doğuş Otomotiv Finansman B Tipi",
        "sector":  "Finans",
        "desc":    "Doğuş Otomotiv grubunun finansman kolu — B grubu hisseler.",
    },
    "DOGUB": {
        "name":    "Doğuş Holding A.Ş.",
        "sector":  "Holding",
        "desc":    "Otomotiv, finans, inşaat, medya ve turizm (D-Resort) alanlarında faaliyet "
                   "gösteren büyük holding. Volkswagen Grubu Türkiye distribütörlüğünü yürütür.",
    },
    "DYOBY": {
        "name":    "DYO Boya Fabrikaları Sanayi ve Ticaret A.Ş.",
        "sector":  "Kimya",
        "desc":    "Türkiye'nin köklü boya üreticilerinden biri. Dekoratif ve endüstriyel boya, "
                   "vernik ve kaplama ürünleri üretir. Yaşar Holding bünyesindedir.",
    },
    "EBEBK": {
        "name":    "Ege Borsası Elektronik Bilgi ve Belge Yönetimi A.Ş.",
        "sector":  "Teknoloji",
        "desc":    "Elektronik belge yönetimi, arşivleme ve dijital dönüşüm çözümleri sunan "
                   "teknoloji şirketi.",
    },
    "EDATA": {
        "name":    "E-Data Teknoloji A.Ş.",
        "sector":  "Teknoloji",
        "desc":    "Yazılım geliştirme ve dijital dönüşüm hizmetleri sunan teknoloji şirketi.",
    },
    "EDIP": {
        "name":    "Edip Gayrimenkul Yatırım Sanayi ve Ticaret A.Ş.",
        "sector":  "GYO",
        "desc":    "Konut ve ticari gayrimenkul geliştirme alanında faaliyet gösteren şirket.",
    },
    "EFOR": {
        "name":    "Efor Enerji A.Ş.",
        "sector":  "Enerji",
        "desc":    "Yenilenebilir enerji ve elektrik üretimi alanında faaliyet gösteren şirket.",
    },
    "EGEPO": {
        "name":    "Ege Profil Ticaret ve Sanayi A.Ş.",
        "sector":  "Sanayi",
        "desc":    "PVC pencere ve kapı profili üreticisi. Türkiye inşaat sektörüne ve ihracata "
                   "PVC profil ve aksesuar tedarik eder.",
    },
    "EGGUB": {
        "name":    "Ege Gübre Sanayii A.Ş.",
        "sector":  "Kimya",
        "desc":    "Azotlu ve kompoze gübre üretimi yapan İzmir merkezli kimya sanayi şirketi. "
                   "Tarım sektörüne gübre tedarik eder.",
    },
    "EGPRO": {
        "name":    "Ege Profil PVC Pencere ve Kapı Sistemleri A.Ş.",
        "sector":  "Sanayi",
        "desc":    "PVC profil ve pencere sistemi üretimi yapan sanayi şirketi.",
    },
    "EKSUN": {
        "name":    "Eksun Gıda ve İhtiyaç Maddeleri Ticaret A.Ş.",
        "sector":  "Gıda",
        "desc":    "Toptan gıda ve temel ihtiyaç maddeleri ticareti alanında faaliyet gösteren şirket.",
    },
    "ELITE": {
        "name":    "Elite Naturel Organik Gıda Tarım Hayvancılık A.Ş.",
        "sector":  "Gıda",
        "desc":    "Organik gıda, zeytinyağı ve doğal tarım ürünleri üretimi yapan şirket. "
                   "İhracat odaklı üretim yapar.",
    },
    "EMPAE": {
        "name":    "Empa Ticaret A.Ş.",
        "sector":  "Sanayi",
        "desc":    "İnşaat malzemeleri ve yapı kimyasalları alanında ticaret yapan şirket.",
    },
    "ENJSA": {
        "name":    "Enerjisa Enerji A.Ş.",
        "sector":  "Enerji",
        "desc":    "Türkiye'nin en büyük özel elektrik dağıtım şirketlerinden biri. Sabancı Holding "
                   "ve E.ON ortaklığında; Başkent, Toroslar ve Ayedaş dağıtım bölgelerini işletir. "
                   "12 milyondan fazla aboneye hizmet verir.",
    },
    "EYGYO": {
        "name":    "EYG Gayrimenkul Yatırım Ortaklığı A.Ş.",
        "sector":  "GYO",
        "desc":    "Konut, ofis ve ticari gayrimenkul alanında yatırım yapan GYO.",
    },
    "FADE": {
        "name":    "Fade Gıda Yatırım ve Sanayi A.Ş.",
        "sector":  "Gıda",
        "desc":    "Baharatlar, çay ve kuru gıda ürünleri üretimi ve pazarlaması alanında "
                   "faaliyet gösteren gıda şirketi.",
    },
    "FORMT": {
        "name":    "Format İnşaat Sanayi A.Ş.",
        "sector":  "Sanayi",
        "desc":    "Yapı malzemeleri, beton kalıp sistemleri ve inşaat teknolojileri alanında "
                   "faaliyet gösteren şirket.",
    },
    "FORTE": {
        "name":    "Forte Yatırım Holding A.Ş.",
        "sector":  "Holding",
        "desc":    "Enerji, teknoloji ve gayrimenkul alanlarında yatırımları olan holding.",
    },
    "FRMPL": {
        "name":    "Formplast Plastik Sanayi A.Ş.",
        "sector":  "Sanayi",
        "desc":    "Plastik enjeksiyon kalıp parça ve ambalaj ürünleri üreticisi. "
                   "Otomotiv ve beyaz eşya sektörlerine plastik bileşen tedarik eder.",
    },
    "FZLGY": {
        "name":    "Fzl Gayrimenkul Yatırım Ortaklığı A.Ş.",
        "sector":  "GYO",
        "desc":    "Konut ve ticari gayrimenkul projelerine yatırım yapan GYO.",
    },
    "GEDZA": {
        "name":    "Gediz Ambalaj Sanayi ve Ticaret A.Ş.",
        "sector":  "Sanayi",
        "desc":    "Oluklu mukavva ve ambalaj ürünleri üreticisi. Gıda ve sanayi sektörlerine "
                   "ambalaj çözümleri sunar.",
    },
    "GENKM": {
        "name":    "Gen-Ka Tüketim Ürünleri Pazarlama ve Ticaret A.Ş.",
        "sector":  "Gıda",
        "desc":    "Tüketim ürünleri pazarlama ve dağıtımı alanında faaliyet gösteren şirket.",
    },
    "GEREL": {
        "name":    "Gereli İnşaat ve Ticaret A.Ş.",
        "sector":  "Tarım",
        "desc":    "Tarımsal sulama sistemleri ve tarım makineleri alanında faaliyet gösteren şirket.",
    },
    "GESAN": {
        "name":    "Gesan Generatör Güç Sistemleri Sanayi ve Ticaret A.Ş.",
        "sector":  "Sanayi",
        "desc":    "Dizel ve doğalgaz jeneratör üreticisi. Türkiye ve ihracat pazarlarına "
                   "yedek güç sistemleri tedarik eder.",
    },
    "GLRMK": {
        "name":    "Güler Makine İmalat Sanayi ve Ticaret A.Ş.",
        "sector":  "Sanayi",
        "desc":    "Tekstil makineleri ve sanayi ekipmanları üretimi alanında faaliyet gösteren şirket.",
    },
    "GOKNR": {
        "name":    "Göknar Enerji ve İnşaat A.Ş.",
        "sector":  "Enerji",
        "desc":    "Yenilenebilir enerji projeleri geliştirme ve inşaat alanında faaliyet "
                   "gösteren şirket.",
    },
    "GOODY": {
        "name":    "Goodyear Lastikleri T.A.Ş.",
        "sector":  "Otomotiv",
        "desc":    "ABD merkezli Goodyear Tire & Rubber Company'nin Türkiye iştiraki. "
                   "Adapazarı'ndaki fabrikasında otomobil ve kamyon lastikleri üretir; "
                   "Türkiye ve ihracat pazarlarına satar.",
    },
    "GRSEL": {
        "name":    "Güriş Sanayi ve Ticaret A.Ş.",
        "sector":  "Sanayi",
        "desc":    "Büyük ölçekli inşaat, enerji ve altyapı projeleri yürüten sanayi şirketi. "
                   "Baraj, tünel, köprü gibi ağır altyapı projelerinde deneyimlidir.",
    },
    "GRTHO": {
        "name":    "Gratis İç ve Dış Ticaret A.Ş.",
        "sector":  "Perakende",
        "desc":    "Türkiye'nin önde gelen kozmetik ve kişisel bakım ürünleri perakendecisi. "
                   "1.000'i aşkın mağazasıyla parfüm, makyaj ve cilt bakım ürünleri satar.",
    },

    # ── XKTUM Batch 3 (100-149): GUBRF → MARBL — v5 ─────────────────────────

    "GUNDG": {
        "name":    "Güneş Dağıtım Basın Yayın A.Ş.",
        "sector":  "Medya",
        "desc":    "Gazete, dergi ve basılı yayın dağıtımı alanında faaliyet gösteren şirket.",
    },
    "HATSN": {
        "name":    "Hatay Sanayi ve Ticaret A.Ş.",
        "sector":  "Sanayi",
        "desc":    "Sanayi ve ticaret alanlarında faaliyet gösteren bölgesel şirket.",
    },
    "HKTM": {
        "name":    "Hekim Yapı Ürünleri ve Dekorasyon A.Ş.",
        "sector":  "Sanayi",
        "desc":    "Plastik yapı malzemeleri ve dekorasyon ürünleri (tavan, duvar paneli) üreticisi. "
                   "İnşaat sektörüne PVC bazlı yapı elemanları tedarik eder.",
    },
    "HOROZ": {
        "name":    "Horoz Lojistik A.Ş.",
        "sector":  "Lojistik",
        "desc":    "Karayolu, demiryolu ve denizyolu kargo ile depolama ve lojistik hizmetleri sunan şirket. "
                   "Yurt içi ve uluslararası taşımacılık yapan köklü lojistik firması.",
    },
    "HRKET": {
        "name":    "Hareket Ekspres Kargo Taşıma ve Lojistik A.Ş.",
        "sector":  "Lojistik",
        "desc":    "Hızlı kargo ve ekspres dağıtım hizmetleri sunan lojistik şirketi.",
    },
    "IHYAY": {
        "name":    "İhlas Yayın Holding A.Ş.",
        "sector":  "Medya",
        "desc":    "İhlas Grubu bünyesinde gazetecilik, yayıncılık ve medya içerik üretimi "
                   "alanlarında faaliyet gösteren holding.",
    },
    "IMASM": {
        "name":    "İmaş Makine Sanayi ve Ticaret A.Ş.",
        "sector":  "Sanayi",
        "desc":    "Sanayi makineleri, pres ve döküm ekipmanları üreten makine sanayi şirketi.",
    },
    "INTEM": {
        "name":    "İntem Teknoloji A.Ş.",
        "sector":  "Teknoloji",
        "desc":    "Kurumsal yazılım, sistem entegrasyonu ve BT danışmanlık hizmetleri sunan şirket.",
    },
    "ISSEN": {
        "name":    "İş Enerji Elektrik Üretim A.Ş.",
        "sector":  "Enerji",
        "desc":    "İş Bankası grubunun enerji iştiraki. Yenilenebilir kaynaklardan elektrik "
                   "üretimi alanında faaliyet gösterir.",
    },
    "IZINV": {
        "name":    "İzmir Demir Çelik Sanayi A.Ş.",
        "sector":  "Metal",
        "desc":    "İzmir bölgesinde uzun çelik ürünleri (inşaat demiri, filmaşin) üreten "
                   "entegre demir-çelik tesisi.",
    },
    "KATMR": {
        "name":    "Katmerciler Araç Üstü Ekipman Sanayi ve Ticaret A.Ş.",
        "sector":  "Sanayi",
        "desc":    "Askeri ve sivil araç üstü ekipman (vinç, itfaiye teçhizatı, zırhlı araç "
                   "bileşenleri) üreticisi. Savunma sanayii ve belediye araçları segmentinde "
                   "ihracat yapan İzmir merkezli şirket.",
    },
    "KBORU": {
        "name":    "Kron Telekomünikasyon Hizmetleri A.Ş.",
        "sector":  "Sanayi",
        "desc":    "Çelik boru ve boru sistemleri üretimi alanında faaliyet gösteren sanayi şirketi.",
    },
    "KCAER": {
        "name":    "Kocaer Çelik Sanayi ve Ticaret A.Ş.",
        "sector":  "Metal",
        "desc":    "Soğuk haddelenmiş çelik sac ve galvanizli çelik ürünleri üreten şirket. "
                   "Beyaz eşya ve otomotiv sektörlerine hammadde tedarik eder.",
    },
    "KIMMR": {
        "name":    "Kimteks Kimya Sanayi ve Ticaret A.Ş.",
        "sector":  "Kimya",
        "desc":    "Tekstil kimyasalları, yardımcı maddeler ve özel kimyasal ürünler üreten şirket.",
    },
    "KLSYN": {
        "name":    "Kaleseramik Çanakkale Kalebodur Seramik Sanayi A.Ş.",
        "sector":  "Sanayi",
        "desc":    "Türkiye'nin lider seramik ve porselen karo üreticisi. Kale markasıyla "
                   "yer ve duvar karosu, sağlık gereci ve banyo ürünleri üretir. Kalebodur "
                   "grubuyla Avrupa ve Orta Doğu'ya ihracat yapar.",
    },
    "KNFRT": {
        "name":    "Konfrut Gıda Sanayi ve Ticaret A.Ş.",
        "sector":  "Gıda",
        "desc":    "Meyve suyu konsantresi, nektarlar ve işlenmiş meyve ürünleri üreticisi. "
                   "İhracat odaklı üretim yapan gıda sanayi şirketi.",
    },
    "KOCMT": {
        "name":    "Koç Çimento Sanayi ve Ticaret A.Ş.",
        "sector":  "Çimento",
        "desc":    "Bölgesel çimento üretimi ve dağıtımı alanında faaliyet gösteren sanayi şirketi.",
    },
    "KONKA": {
        "name":    "Konka Enerji ve Maden İşletmeleri A.Ş.",
        "sector":  "Madencilik",
        "desc":    "Kömür ve maden işletmeciliği ile enerji üretimi alanlarında faaliyet gösteren şirket.",
    },
    "KONTR": {
        "name":    "Kontrolmatik Teknoloji Enerji ve Mühendislik A.Ş.",
        "sector":  "Teknoloji",
        "desc":    "Enerji otomasyonu, SCADA sistemleri ve akıllı şebeke çözümleri geliştiren "
                   "mühendislik ve teknoloji şirketi.",
    },
    "KOPOL": {
        "name":    "Konya Polatlı Çimento Sanayi A.Ş.",
        "sector":  "Çimento",
        "desc":    "Orta Anadolu bölgesine çimento üreten fabrika. İnşaat sektörüne klinker "
                   "ve çimento tedarik eder.",
    },
    "KRDMA": {
        "name":    "Kardemir Karabük Demir Çelik San. ve Tic. A.Ş. (A Grubu)",
        "sector":  "Metal",
        "desc":    "Kardemir'in A grubu hisseleri. Karabük'te ray, profil ve uzun çelik ürünleri "
                   "üreten Türkiye'nin önemli demir-çelik tesisi. KRDMD ile aynı şirkettir.",
    },
    "KRGYO": {
        "name":    "Körfez Gayrimenkul Yatırım Ortaklığı A.Ş.",
        "sector":  "GYO",
        "desc":    "Konut ve ticari gayrimenkul alanında yatırım yapan GYO.",
    },
    "KRONT": {
        "name":    "Kron Telekomünikasyon Hizmetleri A.Ş.",
        "sector":  "Teknoloji",
        "desc":    "Kurumsal ağ güvenliği ve siber güvenlik çözümleri geliştiren Türk teknoloji şirketi. "
                   "Güvenlik duvarı ve ağ yönetimi ürünleriyle kamu ve özel sektöre hizmet verir.",
    },
    "KRPLS": {
        "name":    "Körplas Plastik Ambalaj San. ve Tic. A.Ş.",
        "sector":  "Sanayi",
        "desc":    "Plastik ambalaj, şişe ve kapak üreticisi. Gıda, ilaç ve kozmetik sektörlerine "
                   "özel ambalaj çözümleri sunar.",
    },
    "KRSTL": {
        "name":    "Kristal Kola ve Meşrubat Sanayi ve Ticaret A.Ş.",
        "sector":  "Gıda",
        "desc":    "Meşrubat, gazlı içecek ve meyve suyu üreticisi. Türkiye iç pazarına "
                   "Kristal markasıyla içecek ürünleri sunar.",
    },
    "KRVGD": {
        "name":    "Kervan Gıda Sanayi ve Ticaret A.Ş.",
        "sector":  "Gıda",
        "desc":    "Şekerleme, çikolata ve lokum üreticisi. Yurt içi ve ihracat pazarlarına "
                   "geleneksel ve modern şekerleme ürünleri sunar.",
    },
    "KTLEV": {
        "name":    "Katılım Emeklilik ve Hayat A.Ş.",
        "sector":  "Sigorta",
        "desc":    "Faizsiz ilkelerle bireysel emeklilik (BES) ve hayat sigortası ürünleri "
                   "sunan katılım finansı şirketi.",
    },
    "KUTPO": {
        "name":    "Kütahya Porselen Sanayi A.Ş.",
        "sector":  "Sanayi",
        "desc":    "Türkiye'nin en büyük porselen mutfak ve sofra eşyası üreticisi. "
                   "Yemek takımı, fincan ve dekoratif porselen ürünleri ihraç eder.",
    },
    "KUYAS": {
        "name":    "Kuyas Kuyu Açma Sanayi ve Ticaret A.Ş.",
        "sector":  "Sanayi",
        "desc":    "Sondaj, kuyu açma ve zemin mühendisliği hizmetleri veren sanayi şirketi.",
    },
    "KZBGY": {
        "name":    "Kazibey Gayrimenkul Yatırım Ortaklığı A.Ş.",
        "sector":  "GYO",
        "desc":    "Konut ve ticari gayrimenkul projelerine yatırım yapan GYO.",
    },
    "LKMNH": {
        "name":    "Lokman Hekim Engürüsağ Sağlık Turizm San. ve Tic. A.Ş.",
        "sector":  "Sağlık",
        "desc":    "Özel hastane, tıp merkezi ve sağlık turizmi hizmetleri sunan sağlık grubu.",
    },
    "LMKDC": {
        "name":    "Lüks Kadife Dokuma ve Ticaret İşletmeleri A.Ş.",
        "sector":  "Tekstil",
        "desc":    "Kadife, kadife kumaş ve döşemelik tekstil ürünleri üreticisi. Mobilya ve "
                   "otomotiv sektörlerine döşemelik kumaş tedarik eder.",
    },
    "LXGYO": {
        "name":    "Lux Gayrimenkul Yatırım Ortaklığı A.Ş.",
        "sector":  "GYO",
        "desc":    "Lüks konut ve ticari gayrimenkul projelerine yatırım yapan GYO.",
    },
    "MAGEN": {
        "name":    "Mag Endüstri ve Ticaret A.Ş.",
        "sector":  "Sanayi",
        "desc":    "Endüstriyel ürünler ticareti ve mühendislik hizmetleri alanında faaliyet "
                   "gösteren şirket.",
    },
    "MAKIM": {
        "name":    "Makina ve Kimya Endüstrisi A.Ş.",
        "sector":  "Sanayi",
        "desc":    "MKEK bünyesinde savunma ve silah sistemleri, patlayıcı madde ve kimyasal "
                   "ürünler üreten kamu sanayi kuruluşu.",
    },
    "MARBL": {
        "name":    "Marbay Boyar Madde ve Kimya San. ve Tic. A.Ş.",
        "sector":  "Kimya",
        "desc":    "Tekstil boyar maddeleri ve kimyasal yardımcı maddeler üreten kimya şirketi.",
    },

    # ── XKTUM Batch 4 (150-228): MAVI → ZERGY — v6 (son batch) ──────────────

    "MCARD": {
        "name":    "Mastercard Türkiye Bilişim ve Teknoloji Hizmetleri A.Ş.",
        "sector":  "Teknoloji",
        "desc":    "Ödeme teknolojileri ve finansal hizmetler alanında faaliyet gösteren şirket.",
    },
    "MEDTR": {
        "name":    "Meditera Tıbbi Malzeme Sanayi ve Ticaret A.Ş.",
        "sector":  "Sağlık",
        "desc":    "Tıbbi sarf malzeme ve cerrahi ürünler üreticisi. Hastanelere tek kullanımlık "
                   "tıbbi malzeme tedarik eden sağlık sanayi şirketi.",
    },
    "MEKAG": {
        "name":    "Mekanik Güç Aktarma Sistemleri A.Ş.",
        "sector":  "Sanayi",
        "desc":    "Otomotiv ve makine sektörlerine güç aktarma ve mekanik bileşen tedarik eden şirket.",
    },
    "MERCN": {
        "name":    "Mercan Kimya Sanayi ve Ticaret A.Ş.",
        "sector":  "Kimya",
        "desc":    "Endüstriyel kimyasallar, boya yardımcı maddeleri ve spesiyalite kimyasal "
                   "ürünler üreticisi.",
    },
    "MEYSU": {
        "name":    "Meybio Biyoteknoloji Sanayi ve Ticaret A.Ş.",
        "sector":  "Gıda",
        "desc":    "Meyve suyu, nektarlar ve içecek konsantreleri üreticisi. İhracat odaklı "
                   "üretim yapan gıda sanayi şirketi.",
    },
    "MNDRS": {
        "name":    "Menderes Tekstil Sanayi ve Ticaret A.Ş.",
        "sector":  "Tekstil",
        "desc":    "Pamuklu dokuma ve baskılı kumaş üreticisi. Ev tekstili (nevresim, çarşaf) "
                   "alanında Avrupa'ya ihracat yapan Denizli merkezli tekstil şirketi.",
    },
    "MNDTR": {
        "name":    "Menderes Tekstil (B Serisi)",
        "sector":  "Tekstil",
        "desc":    "Menderes Tekstil'in B grubu hisseleri. Pamuklu dokuma ve ev tekstili üretimi.",
    },
    "MOBTL": {
        "name":    "Mobil Ödeme ve Elektronik Para Hizmetleri A.Ş.",
        "sector":  "Teknoloji",
        "desc":    "Mobil ödeme altyapısı ve elektronik para hizmetleri sunan fintech şirketi.",
    },
    "NTGAZ": {
        "name":    "Naturelgaz Sıkıştırılmış Doğal Gaz Sanayi ve Ticaret A.Ş.",
        "sector":  "Enerji",
        "desc":    "Sıkıştırılmış doğal gaz (CNG) üretimi, dağıtımı ve araç yakıt istasyonları "
                   "işletmeciliği yapan enerji şirketi.",
    },
    "OBAMS": {
        "name":    "OBA Mağazacılık Sanayi ve Ticaret A.Ş.",
        "sector":  "Perakende",
        "desc":    "Ev dekorasyon, mutfak eşyası ve ev tekstili ürünleri satan perakende zinciri.",
    },
    "OFSYM": {
        "name":    "Ofis Yönetim Sistemleri Sanayi ve Ticaret A.Ş.",
        "sector":  "Teknoloji",
        "desc":    "Ofis mobilyası, ofis ekipmanı ve kurumsal iç mekan çözümleri sunan şirket.",
    },
    "ONCSM": {
        "name":    "Öncü Serbest Bölge İşleticisi A.Ş.",
        "sector":  "Lojistik",
        "desc":    "Serbest ticaret bölgesi işletmeciliği ve lojistik hizmetleri sunan şirket.",
    },
    "OSTIM": {
        "name":    "Ostim Endüstriyel Yatırımlar ve İşletme A.Ş.",
        "sector":  "Sanayi",
        "desc":    "Ankara Ostim Organize Sanayi Bölgesi'nde altyapı ve gayrimenkul yönetimi "
                   "yapan şirket. KOBİ'lere sanayi alanı ve hizmet sunar.",
    },
    "OZRDN": {
        "name":    "Özrıdvan Tarım Ürünleri Sanayi ve Ticaret A.Ş.",
        "sector":  "Tarım",
        "desc":    "Tarımsal ürünlerin işlenmesi ve pazarlanması alanında faaliyet gösteren şirket.",
    },
    "OZYSR": {
        "name":    "Özyaşar Elektrik Enerjisi Üretim ve Ticaret A.Ş.",
        "sector":  "Enerji",
        "desc":    "Küçük ölçekli yenilenebilir enerji üretimi ve ticaret alanında faaliyet "
                   "gösteren şirket.",
    },
    "PAGYO": {
        "name":    "Panora Gayrimenkul Yatırım Ortaklığı A.Ş.",
        "sector":  "GYO",
        "desc":    "Ankara Panora AVM'yi portföyünde barındıran GYO. Ticari gayrimenkul "
                   "işletmeciliği ve kira gelirleri odaklı yapı.",
    },
    "PARSN": {
        "name":    "Parsan Makine Parçaları Sanayi A.Ş.",
        "sector":  "Otomotiv",
        "desc":    "Otomotiv ve savunma sanayii için hassas işlenmiş makine parçaları üreten şirket. "
                   "Dişli, mil ve transmisyon bileşenleri üretir.",
    },
    "PASEU": {
        "name":    "Paşabahçe Cam Sanayi ve Ticaret A.Ş.",
        "sector":  "Cam",
        "desc":    "Türkiye'nin ve dünyanın önde gelen cam ev eşyası üreticisi. Bardak, "
                   "tabak ve dekoratif cam ürünlerini 100'den fazla ülkeye ihraç eder. "
                   "Şişecam Grubu bünyesindedir.",
    },
    "PENTA": {
        "name":    "Penta Teknoloji Ürünleri Dağıtım Ticaret A.Ş.",
        "sector":  "Teknoloji",
        "desc":    "BT ürünleri ve tüketici elektroniği distribütörü. Apple, Samsung ve diğer "
                   "markaların ürünlerini perakende ve kurumsal kanallara dağıtır.",
    },
    "PETUN": {
        "name":    "Petek Un Gıda Sanayi ve Ticaret A.Ş.",
        "sector":  "Gıda",
        "desc":    "Un, irmik ve tahıl bazlı ürünler üreten gıda sanayi şirketi.",
    },
    "PKART": {
        "name":    "Plastikkart Akıllı Kart İletişim Sistemleri A.Ş.",
        "sector":  "Teknoloji",
        "desc":    "Akıllı kart (SIM, banka kartı, kimlik kartı) üreticisi. Telekom operatörleri "
                   "ve bankacılık sektörüne kart tedarik eden teknoloji şirketi.",
    },
    "PLTUR": {
        "name":    "Poltur Plastik Turizm İnşaat Sanayi ve Ticaret A.Ş.",
        "sector":  "Sanayi",
        "desc":    "Plastik ürünler üretimi ve turizm altyapısı yatırımları alanında faaliyet "
                   "gösteren şirket.",
    },
    "PNLSN": {
        "name":    "Panelsan Çelik Yapı Elemanları Sanayi ve Ticaret A.Ş.",
        "sector":  "Sanayi",
        "desc":    "Çelik panel, sandviç panel ve prefabrik yapı elemanları üreticisi. "
                   "Soğuk hava deposu, sanayi tesisi ve çatı sistemlerine tedarikçidir.",
    },
    "POLHO": {
        "name":    "Polisan Holding A.Ş.",
        "sector":  "Holding",
        "desc":    "Boya (Polisan Boya), kimya ve liman işletmeciliği alanlarında faaliyet "
                   "gösteren holding. Polisan Liman ile Ambarlı'da konteyner elleçleme yapar.",
    },
    "QUAGR": {
        "name":    "Qua Granite ve Doğaltaş Endüstrisi Ticaret A.Ş.",
        "sector":  "Sanayi",
        "desc":    "Granit, mermer ve doğal taş yüzey kaplama malzemeleri üreticisi ve ihracatçısı. "
                   "İnşaat ve iç mimari sektörlerine tedarikçidir.",
    },
    "RNPOL": {
        "name":    "Ren Plastik Sanayi ve Ticaret A.Ş.",
        "sector":  "Sanayi",
        "desc":    "Plastik boru, profil ve yapı malzemeleri üreticisi.",
    },
    "RODRG": {
        "name":    "Rodrigo Tekstil Sanayi ve Ticaret A.Ş.",
        "sector":  "Tekstil",
        "desc":    "İplik ve dokuma ürünleri üretimi alanında faaliyet gösteren tekstil şirketi.",
    },
    "RUBNS": {
        "name":    "Rubenis Tekstil Sanayi ve Ticaret A.Ş.",
        "sector":  "Tekstil",
        "desc":    "Örgü ve dokuma kumaş üreticisi. İhracat odaklı hazırgiyim sektörüne hizmet eder.",
    },
    "SAMAT": {
        "name":    "Samat Lojistik Taşımacılık Sanayi ve Ticaret A.Ş.",
        "sector":  "Lojistik",
        "desc":    "Karayolu taşımacılığı ve uluslararası lojistik hizmetleri sunan şirket.",
    },
    "SANEL": {
        "name":    "Sanel Elektrik Sanayi ve Ticaret A.Ş.",
        "sector":  "Sanayi",
        "desc":    "Elektrik pano, şalt malzemeleri ve enerji dağıtım ekipmanları üreten şirket.",
    },
    "SANKO": {
        "name":    "Sanko Holding A.Ş.",
        "sector":  "Holding",
        "desc":    "Enerji (doğalgaz, elektrik), tekstil, makine ve gayrimenkul alanlarında "
                   "faaliyet gösteren büyük sanayi holdinglerinden biri. Gaziantep merkezlidir.",
    },
    "SARKY": {
        "name":    "Sarkuysan Elektrolitik Bakır Sanayi ve Ticaret A.Ş.",
        "sector":  "Metal",
        "desc":    "Elektrolitik bakır ürünleri (tel, çubuk, bant, profil) üreticisi. "
                   "Elektrik, elektronik ve inşaat sektörlerine bakır yarı mamul tedarik eder.",
    },
    "SAYAS": {
        "name":    "Saya Yatırım Anonim Şirketi",
        "sector":  "Holding",
        "desc":    "Çeşitli sektörlerde yatırım ve iştirak yönetimi yapan yatırım holding şirketi.",
    },
    "SEKUR": {
        "name":    "Sekuro Plastik Ambalaj Sanayi A.Ş.",
        "sector":  "Sanayi",
        "desc":    "PET şişe, kapak ve plastik ambalaj çözümleri üreticisi. Gıda, meşrubat "
                   "ve kişisel bakım sektörlerine ambalaj tedarik eder.",
    },
    "SELVA": {
        "name":    "Selva Gıda Sanayi A.Ş.",
        "sector":  "Gıda",
        "desc":    "Bitkisel yağ, margarın ve katı yağ üreticisi. Selva markasıyla mutfak "
                   "yağlarını tüketici ve endüstriyel segmentlere satar.",
    },
    "SILVR": {
        "name":    "Silver Gayrimenkul Yatırım Ortaklığı A.Ş.",
        "sector":  "GYO",
        "desc":    "Ticari ve konut gayrimenkul projelerine yatırım yapan GYO.",
    },
    "SMRTG": {
        "name":    "Smart Güneş Enerjisi Teknolojileri Sanayi ve Ticaret A.Ş.",
        "sector":  "Enerji",
        "desc":    "Güneş enerjisi paneli ve fotovoltaik sistem kurulum hizmetleri sunan şirket.",
    },
    "SNGYO": {
        "name":    "Sinpaş Gayrimenkul Yatırım Ortaklığı A.Ş.",
        "sector":  "GYO",
        "desc":    "Sinpaş Yapı bünyesinde büyük ölçekli konut ve karma kullanım projeleri "
                   "geliştiren GYO. İstanbul başta olmak üzere Türkiye genelinde projeleri bulunur.",
    },
    "SNICA": {
        "name":    "Sönmez Pamuklu Sanayii A.Ş.",
        "sector":  "Tekstil",
        "desc":    "Pamuklu iplik, dokuma kumaş ve hazırgiyim ürünleri üreten entegre tekstil şirketi.",
    },
    "SOKE": {
        "name":    "Söke Değirmencilik Sanayi ve Ticaret A.Ş.",
        "sector":  "Gıda",
        "desc":    "Un, irmik ve tahıl ürünleri üreten köklü değirmencilik şirketi. "
                   "Türkiye'nin önde gelen un üreticilerinden biri.",
    },
    "SRVGY": {
        "name":    "Servet Gayrimenkul Yatırım Ortaklığı A.Ş.",
        "sector":  "GYO",
        "desc":    "Konut ve ticari gayrimenkul portföyünü yöneten GYO.",
    },
    "SUNTK": {
        "name":    "Sün Tekstil Sanayi ve Ticaret A.Ş.",
        "sector":  "Tekstil",
        "desc":    "İplik ve dokuma ürünleri üreticisi. İhracat odaklı tekstil şirketi.",
    },
    "SURGY": {
        "name":    "Suryapı Gayrimenkul Yatırım Ortaklığı A.Ş.",
        "sector":  "GYO",
        "desc":    "Konut geliştirme ve gayrimenkul yatırımları alanında faaliyet gösteren GYO.",
    },
    "TARKM": {
        "name":    "Tar Kimya Sanayi ve Ticaret A.Ş.",
        "sector":  "Kimya",
        "desc":    "Tarım ilaçları, gübreler ve bitki koruma ürünleri üreten kimya sanayi şirketi.",
    },
    "TDGYO": {
        "name":    "Trend Gayrimenkul Yatırım Ortaklığı A.Ş.",
        "sector":  "GYO",
        "desc":    "Konut ve ticari gayrimenkul projelerine yatırım yapan GYO.",
    },
    "TEZOL": {
        "name":    "Tezol Kağıt ve Ambalaj Sanayi Ticaret A.Ş.",
        "sector":  "Sanayi",
        "desc":    "Kağıt, karton ve ambalaj ürünleri üreticisi. Gıda ve endüstriyel ambalaj "
                   "sektörlerine hizmet eden İzmir merkezli şirket.",
    },
    "TKNSA": {
        "name":    "Teknosa İç ve Dış Ticaret A.Ş.",
        "sector":  "Perakende",
        "desc":    "Türkiye'nin önde gelen tüketici elektroniği perakendecisi. Sabancı Holding "
                   "bünyesinde; TV, bilgisayar, telefon ve ev elektroniği ürünlerini mağaza "
                   "ve e-ticaret kanallarıyla satar.",
    },
    "TMSN": {
        "name":    "Tümosan Motor ve Traktör Sanayi A.Ş.",
        "sector":  "Otomotiv",
        "desc":    "Türk yapımı traktör ve dizel motor üreticisi. Konya'daki fabrikasında "
                   "yerli traktör üretir; tarım mekanizasyonuna katkı sağlar.",
    },
    "TNZTP": {
        "name":    "Tanztaş Tekstil Sanayi ve Ticaret A.Ş.",
        "sector":  "Tekstil",
        "desc":    "Dokuma ve örgü tekstil ürünleri üreticisi.",
    },
    "TUCLK": {
        "name":    "Tucluk Endüstriyel Tekstil Sanayi ve Ticaret A.Ş.",
        "sector":  "Tekstil",
        "desc":    "Endüstriyel tekstil ürünleri (filtre bezi, teknik tekstil) üreticisi.",
    },
    "TUREX": {
        "name":    "Türkiye Enerji Sanayi ve Ticaret A.Ş.",
        "sector":  "Enerji",
        "desc":    "Enerji ticareti ve dağıtımı alanında faaliyet gösteren şirket.",
    },
    "UCAYM": {
        "name":    "Uçak Servisi A.Ş.",
        "sector":  "Havacılık",
        "desc":    "Havalimanı yer hizmetleri ve uçak ikmal hizmetleri sunan şirket.",
    },
    "ULAS": {
        "name":    "Ulaşlar Turizm Yatırımları ve Dayanıklı Tüketim Malları Tic. A.Ş.",
        "sector":  "Turizm",
        "desc":    "Turizm yatırımları, otelcilik ve dayanıklı tüketim malları ticareti alanında "
                   "faaliyet gösteren şirket.",
    },
    "ULUSE": {
        "name":    "Ulusoy Elektrik İmalat Taahhüt ve Ticaret A.Ş.",
        "sector":  "Sanayi",
        "desc":    "Güç transformatörü, elektrik panosu ve enerji dağıtım ekipmanları üreticisi. "
                   "Enerji altyapı projelerine trafo ve şalt ekipmanı tedarik eder.",
    },
    "USAK": {
        "name":    "Uşak Seramik Sanayi A.Ş.",
        "sector":  "Sanayi",
        "desc":    "Yer ve duvar karosu ile seramik yapı malzemeleri üreticisi. "
                   "Uşak merkezli seramik sanayi şirketi.",
    },
    "VAKKO": {
        "name":    "Vakko Tekstil ve Hazır Giyim Sanayi İşletmeleri A.Ş.",
        "sector":  "Tekstil",
        "desc":    "Türkiye'nin prestijli moda ve lüks hazırgiyim markası. Vakko ve "
                   "V2K markaları altında giyim, aksesuar ve ev tekstili satar.",
    },
    "VANGD": {
        "name":    "Van Güneş Enerji Sanayi ve Ticaret A.Ş.",
        "sector":  "Enerji",
        "desc":    "Güneş enerjisi santralleri ve yenilenebilir enerji projeleri geliştiren şirket.",
    },
    "VESBE": {
        "name":    "Vestel Beyaz Eşya Sanayi ve Ticaret A.Ş.",
        "sector":  "Elektronik",
        "desc":    "Vestel Grubu'nun beyaz eşya kolu. Manisa fabrikasında çamaşır makinesi, "
                   "buzdolabı ve bulaşık makinesi üretir; Avrupa'ya önemli miktarda ihracat yapar.",
    },
    "VRGYO": {
        "name":    "Varlık Gayrimenkul Yatırım Ortaklığı A.Ş.",
        "sector":  "GYO",
        "desc":    "Konut, ofis ve ticari gayrimenkul portföyünü yöneten GYO.",
    },
    "YEOTK": {
        "name":    "Yeo Teknoloji Çözümleri A.Ş.",
        "sector":  "Teknoloji",
        "desc":    "Yazılım geliştirme, dijital dönüşüm ve BT danışmanlık hizmetleri sunan şirket.",
    },
    "YUNSA": {
        "name":    "Yünsa Yünlü Sanayi ve Ticaret A.Ş.",
        "sector":  "Tekstil",
        "desc":    "Yünlü kumaş ve tekstil ürünleri üreticisi. Sabancı Holding bünyesinde; "
                   "erkek takım elbisesi kumaşı alanında Avrupa'nın önde gelen tedarikçilerinden.",
    },
    "ZERGY": {
        "name":    "Zergün Ticaret ve Sanayi A.Ş.",
        "sector":  "Sanayi",
        "desc":    "Endüstriyel ürünler ticareti ve sanayi hizmetleri alanında faaliyet gösteren şirket.",
    },

    # ── XKTUM kapsamı tamamlama (eksik 13 sembol) ────────────────────────────

    "CWENE": {
        "name":    "CW Enerji Mühendislik Ticaret ve Sanayi A.Ş.",
        "sector":  "Enerji",
        "desc":    "Yenilenebilir enerji (rüzgar, güneş) proje geliştirme ve enerji mühendisliği "
                   "hizmetleri sunan şirket.",
    },
    "IDGYO": {
        "name":    "İdeal Gayrimenkul Yatırım Ortaklığı A.Ş.",
        "sector":  "GYO",
        "desc":    "Konut ve ticari gayrimenkul projelerine yatırım yapan GYO.",
    },
    "IHLAS": {
        "name":    "İhlas Holding A.Ş.",
        "sector":  "Holding",
        "desc":    "Medya, ev aletleri, yapı ve turizm alanlarında faaliyet gösteren holding. "
                   "TGRT, İhlas Haber Ajansı ve ev aletleri üretimi bünyesinde yer alır.",
    },
    "IHLGM": {
        "name":    "İhlas Gazetecilik A.Ş.",
        "sector":  "Medya",
        "desc":    "Türkiye Gazetesi ve dijital haber platformlarını bünyesinde barındıran "
                   "İhlas Grubu'nun medya iştiraki.",
    },
    "IZFAS": {
        "name":    "İzmir Fuar A.Ş.",
        "sector":  "Sanayi",
        "desc":    "İzmir Enternasyonal Fuarı'nı organize eden ve fuar altyapısını işleten şirket. "
                   "Tarımdan teknolojiye geniş yelpazede fuarlar düzenler.",
    },
    "JANTS": {
        "name":    "JANTSA Jant Sanayi ve Ticaret A.Ş.",
        "sector":  "Otomotiv",
        "desc":    "Çelik jant ve tekerlek üreticisi. Otomotiv, tarım makineleri ve iş "
                   "makineleri sektörlerine jant tedarik eden Bursa merkezli şirket.",
    },
    "KOTON": {
        "name":    "Koton Mağazacılık Tekstil Sanayi ve Ticaret A.Ş.",
        "sector":  "Tekstil",
        "desc":    "Türkiye'nin lider hazırgiyim perakendecilerinden biri. Kadın, erkek ve "
                   "çocuk giyim ürünlerini 400'den fazla mağaza ve e-ticaret kanalıyla satar.",
    },
    "OBASE": {
        "name":    "Obase Bilgisayar ve Organizasyon A.Ş.",
        "sector":  "Teknoloji",
        "desc":    "Kurumsal yazılım, ERP entegrasyonu ve dijital dönüşüm çözümleri sunan şirket. "
                   "SAP uygulamaları ve iş zekası çözümleriyle öne çıkar.",
    },
    "SAFKR": {
        "name":    "Safkar Ege Soğutma Klima Isıtma Sanayi ve Ticaret A.Ş.",
        "sector":  "Sanayi",
        "desc":    "Soğutma, klima ve ısıtma sistemleri üreten sanayi şirketi. "
                   "Endüstriyel soğutma çözümleri ve kompresör sistemleri üretir.",
    },
    "SMART": {
        "name":    "Smart Güneş Enerjisi Teknolojileri San. ve Tic. A.Ş.",
        "sector":  "Teknoloji",
        "desc":    "Akıllı enerji yönetim sistemleri, güneş paneli ve IoT tabanlı enerji "
                   "çözümleri geliştiren teknoloji şirketi.",
    },
    "SUWEN": {
        "name":    "Süwen İplik Sanayi ve Ticaret A.Ş.",
        "sector":  "Tekstil",
        "desc":    "İç çamaşırı, pijama ve ev giyim ürünleri üreticisi ve perakendecisi. "
                   "Suwen markasıyla Türkiye genelinde mağazalar işletir.",
    },
    "TUKAS": {
        "name":    "Tukaş Gıda Sanayi ve Ticaret A.Ş.",
        "sector":  "Gıda",
        "desc":    "Domates salçası, konserve sebze ve meyve ürünleri üreticisi. "
                   "Türkiye'nin köklü konserve gıda markalarından biri.",
    },
    "ZEDUR": {
        "name":    "Zedur Enerji İnşaat Sanayi ve Ticaret A.Ş.",
        "sector":  "Enerji",
        "desc":    "Yenilenebilir enerji santralleri kurulum ve işletmeciliği ile enerji "
                   "altyapısı inşaatı alanında faaliyet gösteren şirket.",
    },
}

# ─────────────────────────────────────────────────────────────────────────────
# Yardımcı fonksiyonlar
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=86400, show_spinner=False)
def _yf_info(ticker: str) -> dict:
    """yfinance'ten şirket adı ve açıklamasını çeker (fallback)."""
    try:
        import yfinance as yf
        info = yf.Ticker(f"{ticker}.IS").info
        return {
            "name":   info.get("longName") or info.get("shortName") or ticker,
            "sector": info.get("sector") or "Diğer",
            "desc":   info.get("longBusinessSummary") or "Açıklama bulunamadı.",
        }
    except Exception:
        return {"name": ticker, "sector": "Diğer", "desc": "Veri alınamadı."}


def get_company(ticker: str) -> dict:
    """
    Verilen ticker için şirket bilgisini döner.
    Önce statik DB'ye bakar, yoksa yfinance'e düşer.

    Dönen dict: {"name": str, "sector": str, "desc": str}
    """
    clean = ticker.replace(".IS", "").upper()
    if clean in COMPANY_DB:
        return COMPANY_DB[clean]
    return _yf_info(clean)


def get_name(ticker: str) -> str:
    """Sadece tam şirket adını döner."""
    return get_company(ticker)["name"]


def get_sector(ticker: str) -> str:
    """Sadece sektörü döner."""
    return get_company(ticker)["sector"]


def get_desc(ticker: str) -> str:
    """Sadece kısa açıklamayı döner."""
    return get_company(ticker)["desc"]


def company_label(ticker: str) -> str:
    """
    UI için birleşik etiket: 'THYAO — Türk Hava Yolları A.O.'
    Selectbox ve başlıklarda kullanılır.
    """
    clean = ticker.replace(".IS", "").upper()
    name  = get_name(clean)
    if name == clean:
        return clean
    return f"{clean} — {name}"
