"""@anahtarteslimeticaret -> @gidersizeticaret Instagram senkronu.

Her calismada:
  1. Kaynakta o an yayinda olan hikayeleri hedefe hikaye olarak kopyalar (daha once kopyalanmadiysa).
  2. Kaynaktaki en eski, hedefte olmayan 1 gonderiyi (reels / gorsel / carousel) hedefe paylasir
     ve ayni icerigi hedefin hikayesine de koyar.
Workflow gunde 3 kez calisir -> gunde 3 gonderi.

Yon tek: kaynak -> hedef. Hedeften kaynaga hicbir sey atilmaz.

Ortam degiskenleri:
  IG_TOKENS  JSON: {"kaynak": "<anahtarteslim sayfa tokeni>", "hedef": "<gidersiz sayfa tokeni>"}
  KURU       "true" ise paylasim yapmaz, sadece ne yapacagini yazar.
"""
import json
import os
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request

API = "https://graph.facebook.com/v24.0"
KAYNAK_IG = "17841459038061731"   # anahtarteslimeticaret
HEDEF_IG = "17841464104791427"    # gidersizeticaret
KLASOR = os.path.dirname(os.path.abspath(__file__))
DURUM = os.path.join(KLASOR, "durum.json")
GONDERI_PER_CALISMA = int(os.environ.get("GONDERI_SAYISI", "1"))
KURU = os.environ.get("KURU", "").lower() == "true"
ARALIK_SAAT = float(os.environ.get("ARALIK_SAAT", "4"))   # gönderiler arası en az (saat)
GUNLUK = int(os.environ.get("GUNLUK", "3"))                # günde en fazla gönderi
PENCERE = (9, 22)                                          # TR saati: 09:00-22:00 arası paylaş

TOK = json.loads(os.environ["IG_TOKENS"])


def istek(yol, tok, params=None, post=False):
    params = dict(params or {})
    params["access_token"] = tok
    url = yol if yol.startswith("http") else f"{API}/{yol}"
    veri = None
    if post:
        veri = urllib.parse.urlencode(params).encode()
    else:
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    for deneme in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, data=veri), timeout=120) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            govde = e.read().decode(errors="replace")
            if e.code >= 500 and deneme < 3:
                time.sleep(10 * (deneme + 1))
                continue
            raise RuntimeError(f"Graph API {e.code}: {govde}") from None


def hepsini_cek(yol, tok, params):
    sonuc, url, p = [], yol, params
    while url:
        d = istek(url, tok, p)
        sonuc += d.get("data", [])
        url = d.get("paging", {}).get("next")
        p = {}
    return sonuc


IG_ILETISIM = ("📲 Siz de kendi e-ticaret işinizi başlatmak ve daha fazla bilgi almak için "
               "benimle WhatsApp'tan iletişime geçebilirsiniz:\n👉 wa.me/905078784881")


def iletisimsiz(caption):
    """WhatsApp bloğunu çıkarır (kaynak-hedef eşleştirmesi bloktan etkilenmesin)."""
    c = (caption or "").replace(IG_ILETISIM, "")
    return "\n".join(l for l in c.split("\n") if "wa.me/905078784881" not in l and "WhatsApp'tan iletişime" not in l)


def anahtar(caption):
    c = iletisimsiz(caption).split("#")[0]
    c = unicodedata.normalize("NFC", c.lower())
    return re.sub(r"[^a-z0-9çğıöşü]", "", c)[:60]


def aciklama_uyarla(c):
    c = c or ""
    c = re.sub(r"#anahtarteslimeticaret\b", "#gidersizeticaret", c, flags=re.I)
    c = re.sub(r"@anahtarteslimeticaret\b", "@gidersizeticaret", c, flags=re.I)
    # ayni etiket iki kez kaldiysa birini sil
    gorulen, parcalar = set(), []
    for p in re.split(r"(\s+)", c):
        k = p.lower()
        if k.startswith("#") and k in gorulen:
            continue
        if k.startswith("#"):
            gorulen.add(k)
        parcalar.append(p)
    return iletisim_ekle_ig("".join(parcalar).strip())


def iletisim_ekle_ig(c):
    """WhatsApp bloğunu hashtag'lerden önce ekler; 2200 karakter sınırı için gövdeyi kısaltır."""
    if "wa.me/905078784881" in c:
        return c[:2200]
    m = re.search(r"(\s*(?:#\S+\s*)+)$", c)
    govde, etiket = (c[:m.start()], m.group(1).strip()) if m else (c, "")
    yer = 2200 - len(IG_ILETISIM) - len(etiket) - 6
    govde = govde.rstrip()[:max(0, yer)].rstrip()
    return "\n\n".join(x for x in (govde, IG_ILETISIM, etiket) if x)


SEHIRLER = """adana adıyaman afyon ağrı amasya ankara antalya artvin aydın balıkesir bilecik bingöl bitlis bolu
burdur bursa çanakkale çankırı çorum denizli diyarbakır edirne elazığ erzincan erzurum eskişehir gaziantep giresun
gümüşhane hakkari hatay ısparta isparta mersin istanbul izmir kars kastamonu kayseri kırklareli kırşehir kocaeli
konya kütahya malatya manisa kahramanmaraş mardin muğla muş nevşehir niğde ordu rize sakarya samsun siirt sinop
sivas tekirdağ tokat trabzon tunceli şanlıurfa uşak van yozgat zonguldak aksaray bayburt karaman kırıkkale batman
şırnak bartın ardahan iğdır yalova karabük kilis osmaniye düzce alanya kuşadası iskenderun pamukkale kapadokya
bodrum fethiye marmaris didim çeşme gebze afyonkarahisar karadeniz ege""".split()
ETKINLIK = re.compile(
    r"seminer|toplant[ıi]|etkinli|masterclass|\bkamp(ı|i|ımız|imiz|lar|ları|\b)|\bturu\b|buluşma|"
    r"netlik akşamı|geride (bıraktık|kaldı)|geri sayım|röportaj|kontenjan|yer ayırt", re.I)


def kucuk(s):
    return (s or "").replace("I", "ı").replace("İ", "i").lower()


AYLAR = r"(ocak|şubat|mart|nisan|mayıs|haziran|temmuz|ağustos|eylül|ekim|kasım|aralık)"
TARIHLI = re.compile(
    r"\b\d{1,2}\s*(-|–|ve)?\s*(\d{1,2}\s*)?" + AYLAR + r"\b"          # 15 mart, 12-18 haziran
    r"|\b" + AYLAR + r"\s+(ayı|20\d\d)\b"                               # kasım ayı, mart 2025
    r"|\b\d{1,2}[./]\d{1,2}[./](20)?\d\d\b"                             # 15.03.2025
    r"|\b(pazartesi|salı|çarşamba|perşembe|cumartesi|cuma)\b|\bpazar (günü|akşamı|saat)"
    r"|\bsaat\s*\d{1,2}[:.]\d{2}|\b\d{1,2}[:.]\d{2}['’]?(da|de|ta|te)\b"  # saat 20:00, 20.00'de
    r"|zoom|canlı yayın|webinar|davetlisiniz|duyuru", re.I)


def tarihli_icerik(caption):
    """Belli bir tarihe/saate bagli duyuru (canli yayin, zoom, egitim tarihi) mi?"""
    return bool(TARIHLI.search(kucuk(caption)))


def sehir_etkinligi(caption):
    """Sehir toplantisi / seminer / kamp duyurusu veya haberi mi?"""
    c = kucuk(caption)
    if ETKINLIK.search(c):
        return True
    ust = " ".join(c.split("\n")[:3])
    kelimeler = set(re.findall(r"[a-zçğıöşü]+", ust))
    # "ankara'da", "izmir’de" gibi ekli halleri de yakala
    for s in SEHIRLER:
        if s in kelimeler or re.search(rf"\b{s}\s*['’`]", ust) or re.search(rf"\b{s}(da|de|ta|te|dan|den|lı|li)\b", ust):
            return True
    return False


def hazir_bekle(cid, tok):
    for _ in range(60):
        d = istek(cid, tok, {"fields": "status_code,status"})
        if d.get("status_code") == "FINISHED":
            return
        if d.get("status_code") in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"Konteyner hatasi {cid}: {d}")
        time.sleep(10)
    raise RuntimeError(f"Konteyner zaman asimi {cid}")


def indir(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return r.read()


def konteyner(params):
    """Video ise dosyayi indirip Instagram'a dogrudan yukler (resumable); gorsel ise URL ile."""
    tok = TOK["hedef"]
    params = dict(params)
    video = params.pop("video_url", None)
    if video:
        params["upload_type"] = "resumable"
    d = istek(f"{HEDEF_IG}/media", tok, params, post=True)
    cid = d["id"]
    if video:
        veri = indir(video)
        hedef_url = d.get("uri") or f"https://rupload.facebook.com/ig-api-upload/v24.0/{cid}"
        req = urllib.request.Request(hedef_url, data=veri, method="POST", headers={
            "Authorization": f"OAuth {tok}", "offset": "0", "file_size": str(len(veri))})
        with urllib.request.urlopen(req, timeout=600) as r:
            r.read()
    hazir_bekle(cid, tok)
    return cid


def yayinla(params):
    c = konteyner(params)
    return istek(f"{HEDEF_IG}/media_publish", TOK["hedef"], {"creation_id": c}, post=True)["id"]


def gonderi_paylas(m):
    cap = aciklama_uyarla(m.get("caption"))
    tur = m["media_type"]
    if tur == "VIDEO":
        p = {"media_type": "REELS", "video_url": m["media_url"], "caption": cap, "share_to_feed": "true"}
        return yayinla(p)
    if tur == "IMAGE":
        return yayinla({"image_url": m["media_url"], "caption": cap})
    if tur == "CAROUSEL_ALBUM":
        cocuklar = []
        for ch in m.get("children", {}).get("data", [])[:10]:
            p = {"is_carousel_item": "true"}
            if ch["media_type"] == "VIDEO":
                p.update(media_type="VIDEO", video_url=ch["media_url"])
            else:
                p["image_url"] = ch["media_url"]
            cocuklar.append(konteyner(p))
        return yayinla({"media_type": "CAROUSEL", "children": ",".join(cocuklar), "caption": cap})
    raise RuntimeError(f"Bilinmeyen tur {tur}")


def hikaye_paylas(media_type, url):
    p = {"media_type": "STORIES"}
    p["video_url" if media_type == "VIDEO" else "image_url"] = url
    return yayinla(p)


def main():
    durum = {"gonderiler": {}, "hikayeler": {}, "atlananlar": {}}
    if os.path.exists(DURUM):
        durum.update(json.load(open(DURUM, encoding="utf-8")))

    alanlar = "id,caption,media_type,media_product_type,media_url,thumbnail_url,timestamp,permalink,children{media_type,media_url}"
    kaynak = hepsini_cek(f"{KAYNAK_IG}/media", TOK["kaynak"], {"fields": alanlar, "limit": 50})
    hedef = hepsini_cek(f"{HEDEF_IG}/media", TOK["hedef"], {"fields": "id,caption,timestamp", "limit": 100})
    hedef_anahtarlar = {anahtar(h.get("caption")) for h in hedef if h.get("caption")}

    # Zamanlama kararı (görev her saat uyanır; paylaşıp paylaşmamaya burada karar verilir):
    #  - TR saatiyle PENCERE içinde olmalı, - bugün GUNLUK'ten az gönderi olmalı,
    #  - son gönderiden en az ARALIK_SAAT geçmiş olmalı.
    if not KURU:
        import datetime
        tr = datetime.timezone(datetime.timedelta(hours=3))
        simdi = datetime.datetime.now(tr)
        if not (PENCERE[0] <= simdi.hour < PENCERE[1]):
            print(f"Saat {simdi:%H:%M} paylaşım penceresi dışında; atlandı.")
            return
        zamanlar = [datetime.datetime.strptime(h["timestamp"][:19], "%Y-%m-%dT%H:%M:%S")
                    .replace(tzinfo=datetime.timezone.utc).astimezone(tr) for h in hedef]
        bugun = sum(1 for z in zamanlar if z.date() == simdi.date())
        if bugun >= GUNLUK:
            print(f"Bugün {bugun} gönderi yapıldı (sınır {GUNLUK}); atlandı.")
            return
        if zamanlar:
            gecen = (simdi - max(zamanlar)).total_seconds() / 3600
            if gecen < ARALIK_SAAT:
                print(f"Son gönderiden {gecen:.1f} saat geçti (< {ARALIK_SAAT}); atlandı.")
                return

    # 1) Canli hikayeler kopyalanmiyor: kaynaktaki hikayeler cogunlukla sehir etkinligi
    #    ve aciklamasi olmadigi icin filtrelenemiyor (kullanici istegi, 24.11.2026).

    # 2) Eksik gonderiler, en yeniden baslayarak; sehir etkinlikleri atlanir
    bekleyen = [
        m for m in sorted(kaynak, key=lambda x: x["timestamp"], reverse=True)
        if m.get("media_product_type") != "STORY"
        and not sehir_etkinligi(m.get("caption"))
        and not tarihli_icerik(m.get("caption"))
        and m["id"] not in durum["gonderiler"]
        and m["id"] not in durum["atlananlar"]
        and anahtar(m.get("caption")) not in hedef_anahtarlar
        and (m.get("media_url") or m.get("media_type") == "CAROUSEL_ALBUM")
    ]
    print(f"Kaynak {len(kaynak)} gonderi, hedefte eksik {len(bekleyen)}")

    paylasilan = hata = 0
    for m in bekleyen:
        if paylasilan >= GONDERI_PER_CALISMA or hata >= 3:
            break
        print(f"[gonderi] {m['timestamp']} {m['media_type']} {m.get('permalink')}")
        if KURU:
            paylasilan += 1
            continue
        try:
            yeni = gonderi_paylas(m)
        except Exception as e:
            print(f"  paylasilamadi, atlandi: {e}")
            durum["atlananlar"][m["id"]] = str(e)[:300]
            kaydet(durum)
            hata += 1
            continue
        durum["gonderiler"][m["id"]] = yeni
        paylasilan += 1
        kaydet(durum)
        print(f"  paylasildi -> {yeni}")
        # ayni icerigi hikayeye de koy
        try:
            if m["media_type"] == "CAROUSEL_ALBUM":
                ilk = m["children"]["data"][0]
                hikaye_paylas(ilk["media_type"], ilk["media_url"])
            else:
                try:
                    hikaye_paylas(m["media_type"], m["media_url"])
                except Exception:
                    if m["media_type"] != "VIDEO" or not m.get("thumbnail_url"):
                        raise
                    # uzun video hikayeye sigmiyor: kapak gorselini hikaye yap
                    hikaye_paylas("IMAGE", m["thumbnail_url"])
            print("  hikayeye de eklendi")
        except Exception as e:
            print(f"  hikayeye eklenemedi: {e}")

    if not KURU and paylasilan == 0 and bekleyen:
        sys.exit("Bu calismada hicbir gonderi paylasilamadi")


def kaydet(durum):
    with open(DURUM, "w", encoding="utf-8") as f:
        json.dump(durum, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
