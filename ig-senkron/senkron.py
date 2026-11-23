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


def anahtar(caption):
    c = (caption or "").split("#")[0]
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
    return "".join(parcalar).strip()[:2200]


def hazir_bekle(cid, tok):
    for _ in range(60):
        d = istek(cid, tok, {"fields": "status_code,status"})
        if d.get("status_code") == "FINISHED":
            return
        if d.get("status_code") in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"Konteyner hatasi {cid}: {d}")
        time.sleep(10)
    raise RuntimeError(f"Konteyner zaman asimi {cid}")


def yayinla(params):
    tok = TOK["hedef"]
    c = istek(f"{HEDEF_IG}/media", tok, params, post=True)["id"]
    hazir_bekle(c, tok)
    return istek(f"{HEDEF_IG}/media_publish", tok, {"creation_id": c}, post=True)["id"]


def gonderi_paylas(m):
    cap = aciklama_uyarla(m.get("caption"))
    tur = m["media_type"]
    if tur == "VIDEO":
        p = {"media_type": "REELS", "video_url": m["media_url"], "caption": cap, "share_to_feed": "true"}
        if m.get("thumbnail_url"):
            p["cover_url"] = m["thumbnail_url"]
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
            cid = istek(f"{HEDEF_IG}/media", TOK["hedef"], p, post=True)["id"]
            hazir_bekle(cid, TOK["hedef"])
            cocuklar.append(cid)
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
    hedef = hepsini_cek(f"{HEDEF_IG}/media", TOK["hedef"], {"fields": "id,caption", "limit": 100})
    hedef_anahtarlar = {anahtar(h.get("caption")) for h in hedef if h.get("caption")}

    # 1) Canli hikayeler
    hikayeler = hepsini_cek(f"{KAYNAK_IG}/stories", TOK["kaynak"], {"fields": "id,media_type,media_url,timestamp"})
    for h in sorted(hikayeler, key=lambda x: x["timestamp"]):
        if h["id"] in durum["hikayeler"] or not h.get("media_url"):
            continue
        print(f"[hikaye] {h['timestamp']} {h['media_type']}")
        if KURU:
            continue
        try:
            durum["hikayeler"][h["id"]] = hikaye_paylas(h["media_type"], h["media_url"])
        except Exception as e:
            print(f"  hikaye kopyalanamadi: {e}")
        kaydet(durum)

    # 2) Eksik gonderiler, en eskiden baslayarak
    bekleyen = [
        m for m in sorted(kaynak, key=lambda x: x["timestamp"])
        if m["id"] not in durum["gonderiler"]
        and m["id"] not in durum["atlananlar"]
        and anahtar(m.get("caption")) not in hedef_anahtarlar
        and (m.get("media_url") or m.get("media_type") == "CAROUSEL_ALBUM")
    ]
    print(f"Kaynak {len(kaynak)} gonderi, hedefte eksik {len(bekleyen)}")

    paylasilan = 0
    for m in bekleyen:
        if paylasilan >= GONDERI_PER_CALISMA:
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
                hikaye_paylas(m["media_type"], m["media_url"])
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
