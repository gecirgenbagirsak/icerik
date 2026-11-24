"""Mağazanolsun Instagram'ındaki YENİ videoları YouTube kuyruğuna ekler (bulut, bilgisayar gerekmez).

Resmi Instagram Graph API (business_discovery) ile Mağazanolsun'un son paylaşımlarını okur.
Yeni video -> filtre (şehir toplantısı / geçmiş tarih / duyuru; yakın ileri tarihli seminer OLUR)
-> kuyrukta benzeri yoksa indir -> iki kanal için özgün kapak -> Release'e yükle -> kuyruk.json'un en önüne ekle.
Yüklemeyi yukle.py yapar.
"""
import datetime
import difflib
import json
import os
import re
import sys
import urllib.parse
import urllib.request

KOK = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, KOK)
sys.path.insert(0, os.path.join(KOK, "..", "ig-senkron"))
import ozgun as o
import senkron as s   # sehir_etkinligi, tarihli_icerik, kucuk (IG_TOKENS ortamdan)

KUYRUK = os.path.join(KOK, "kuyruk.json")
ISLENEN = os.path.join(KOK, "ig_islenen.json")
BASLANGIC = "2026-11-24"
HEDEFLER = ("gidersiz", "anahtar")
REPO = os.environ.get("GITHUB_REPOSITORY", "gecirgenbagirsak/icerik")
AY = {a: i + 1 for i, a in enumerate("ocak şubat mart nisan mayıs haziran temmuz ağustos eylül ekim kasım aralık".split())}


def tarihler(metin, yuk):
    c = s.kucuk(metin)
    out = []
    for m in re.finditer(r"\b(\d{1,2})\s*(?:[-–]\s*\d{1,2}\s*)?(ocak|şubat|mart|nisan|mayıs|haziran|temmuz|ağustos|eylül|ekim|kasım|aralık)\b(?:\s+(20\d\d))?", c):
        g, a, y = int(m.group(1)), AY[m.group(2)], m.group(3)
        yil = int(y) if y else yuk.year + (1 if a < yuk.month - 1 else 0)
        try:
            out.append(datetime.date(yil, a, g))
        except ValueError:
            pass
    return out


def karar(metin, yuk):
    tl = tarihler(metin, yuk)
    if tl and min(tl) < datetime.date.today():
        return "gecmis-tarih"
    if tl and any((t - yuk).days > 100 for t in tl):
        return "belirsiz-tarih"
    if tl:
        return "ok"                      # yakın ileri tarihli resmi duyuru
    if s.sehir_etkinligi(metin):
        return "sehir-etkinligi"
    if s.tarihli_icerik(metin):
        return "tarihli/duyuru"
    return "ok"


def gh(url, data=None, method=None, tip=None):
    h = {"Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}", "Accept": "application/vnd.github+json"}
    if tip:
        h["Content-Type"] = tip
    return json.loads(urllib.request.urlopen(urllib.request.Request(url, data=data, method=method, headers=h),
                                             timeout=900).read() or b"{}")


def release_yukle(yol, ad, tip):
    rel = gh(f"https://api.github.com/repos/{REPO}/releases/tags/yt-senkron")
    with open(yol, "rb") as f:
        gh(f"https://uploads.github.com/repos/{REPO}/releases/{rel['id']}/assets?name={ad}", f.read(), "POST", tip)


def baslik_cikar(caption):
    satir = next((l.strip() for l in (caption or "").splitlines() if len(l.strip()) > 10), "Mağazanolsun")
    satir = re.sub(r"#\S+", "", satir).strip(" “”\"")
    return satir[:90]


def main():
    kuyruk = json.load(open(KUYRUK, encoding="utf-8"))
    islenen = json.load(open(ISLENEN, encoding="utf-8")) if os.path.exists(ISLENEN) else {}
    tok = s.TOK["kaynak"]
    alan = "business_discovery.username(magazanolsun){media.limit(25){id,timestamp,media_type,media_product_type,media_url,caption}}"
    d = json.loads(urllib.request.urlopen("https://graph.facebook.com/v24.0/17841459038061731?" +
                                          urllib.parse.urlencode({"fields": alan, "access_token": tok}), timeout=60).read())
    medya = d["business_discovery"]["media"]["data"]
    mevcut = [o.tr_lower(o.baslik_temizle(b)) for k in kuyruk for b in k["baslik"].values()]
    eklenen = 0
    for m in sorted(medya, key=lambda x: x["timestamp"]):
        mid = m["id"]
        if m["timestamp"][:10] < BASLANGIC or mid in islenen or m.get("media_type") != "VIDEO" or not m.get("media_url"):
            continue
        cap = m.get("caption") or ""
        yuk = datetime.date.fromisoformat(m["timestamp"][:10])
        k = karar(cap, yuk)
        if k != "ok":
            islenen[mid] = k
            print("[elendi]", k, cap[:60])
            continue
        baslik = baslik_cikar(cap)
        bnorm = o.tr_lower(baslik)
        if any(difflib.SequenceMatcher(None, bnorm, x).ratio() > 0.6 for x in mevcut):
            islenen[mid] = "kuyrukta-benzeri-var"
            print("[zaten var]", baslik)
            continue
        vid = "ig" + mid
        mp4 = f"/tmp/{vid}.mp4"
        urllib.request.urlretrieve(m["media_url"], mp4)
        release_yukle(mp4, vid + ".mp4", "video/mp4")
        for h in HEDEFLER:
            kp = f"/tmp/{vid}_{h}.jpg"
            o.kapak(mp4, baslik, h, kp)
            release_yukle(kp, f"{vid}_{h}.jpg", "image/jpeg")
        kuyruk.insert(0, {
            "id": vid, "kaynak": "magazanolsun", "hedefler": list(HEDEFLER), "short": True, "sure": None,
            "kaynak_tarih": m["timestamp"][:10].replace("-", ""),
            "baslik": {h: o.youtube_baslik(baslik, h, True) for h in HEDEFLER},
            "aciklama": {h: o.youtube_aciklama(baslik, cap, h, vid) for h in HEDEFLER},
            "etiketler": {h: o.youtube_etiketler([], h) for h in HEDEFLER},
        })
        islenen[mid] = "kuyruga-eklendi"
        mevcut.append(bnorm)
        eklenen += 1
        print("[eklendi]", baslik)
    json.dump(kuyruk, open(KUYRUK, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(islenen, open(ISLENEN, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("Instagram'dan eklenen:", eklenen)


if __name__ == "__main__":
    main()
