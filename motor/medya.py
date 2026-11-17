"""Pixabay medya yardımcıları (ücretsiz, ticari kullanım serbest).

Arama + önizleme kontak sayfası:
    py medya.py ara foto "woman stomach pain"
    py medya.py ara video "tired woman sofa"
Çıktı: önizleme görseli (numaralı) + aday ID listesi. Seçilen ID'ler icerik.json'a
"foto": 123456 / "video": 123456 olarak yazılır; uret.py dosyaları cache'e indirir.
"""
import json
import sys
import urllib.parse
import urllib.request
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

import os

KOK = Path(__file__).resolve().parent.parent          # depo kökü
CACHE = KOK / "cache"
ANAHTAR_DOSYASI = KOK.parent / "pixabay-anahtar.txt"  # yerel bilgisayar; bulutta PIXABAY_KEY ortam değişkeni
UA = {"User-Agent": "icerik-motoru/1.0"}


def anahtar():
    if os.environ.get("PIXABAY_KEY"):
        return os.environ["PIXABAY_KEY"].strip()
    return ANAHTAR_DOSYASI.read_text(encoding="utf-8-sig").strip()


def _get(url, deneme=6):
    import time
    import urllib.error
    for i in range(deneme):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=120) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code != 429 or i == deneme - 1:
                raise
            bekle = int(e.headers.get("Retry-After") or 0) or 5 * (i + 1)
            time.sleep(min(bekle, 60))


def api(tur, **params):
    base = "https://pixabay.com/api/videos/" if tur == "video" else "https://pixabay.com/api/"
    params = {"key": anahtar(), "safesearch": "true", **params}
    return json.loads(_get(base + "?" + urllib.parse.urlencode(params)))


def ara(tur, sorgu, adet=12, **ekstra):
    p = {"q": sorgu, "per_page": max(adet, 3)}
    if tur == "foto":
        p.update(image_type="photo")
    p.update(ekstra)
    return api(tur, **p).get("hits", [])[:adet]


def onizleme_url(hit, tur):
    if tur == "video":
        v = hit["videos"]
        for k in ("medium", "small", "tiny"):
            if v.get(k, {}).get("thumbnail"):
                return v[k]["thumbnail"]
        return hit.get("userImageURL")
    return hit["webformatURL"]


def kontak_sayfasi(hits, tur, cikis):
    tw, th, cols = 360, 240, 4
    rows = (len(hits) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * tw, rows * (th + 40)), (20, 20, 20))
    d = ImageDraw.Draw(sheet)
    f = ImageFont.truetype(str(Path(__file__).resolve().parent / "fonts" / "Poppins-SemiBold.ttf"), 22)
    for i, h in enumerate(hits):
        try:
            im = Image.open(BytesIO(_get(onizleme_url(h, tur)))).convert("RGB")
            im.thumbnail((tw, th))
        except Exception:
            im = Image.new("RGB", (tw, th), (60, 0, 0))
        x, y = (i % cols) * tw, (i // cols) * (th + 40)
        sheet.paste(im, (x + (tw - im.width) // 2, y))
        etiket = f"#{i} id={h['id']}"
        if tur == "video":
            etiket += f" {h['duration']}s {h['videos']['large']['width'] or h['videos']['medium']['width']}px"
        d.text((x + 6, y + th + 6), etiket, font=f, fill=(255, 210, 90))
    sheet.save(cikis, quality=85)


def indir_foto(pid):
    CACHE.mkdir(exist_ok=True)
    yol = CACHE / f"foto_{pid}.jpg"
    if not yol.exists():
        hit = api("foto", id=pid)["hits"][0]
        url = hit.get("largeImageURL") or hit["webformatURL"]
        yol.write_bytes(_get(url))
    return yol


def indir_video(vid):
    CACHE.mkdir(exist_ok=True)
    yol = CACHE / f"video_{vid}.mp4"
    if not yol.exists():
        v = api("video", id=vid)["hits"][0]["videos"]
        # Dikey kırpma için en yüksek çözünürlük (4K yataydan 9:16 kırpınca net kalır)
        secim = None
        for k in ("large", "medium", "small"):
            if v.get(k, {}).get("url") and v[k]["width"] >= 1280:
                secim = v[k]
                break
        if secim is None:
            secim = v["large"] if v["large"].get("url") else v["medium"]
        yol.write_bytes(_get(secim["url"]))
    return yol


if __name__ == "__main__":
    if sys.argv[1] == "ara":
        tur, sorgu = sys.argv[2], sys.argv[3]
        cikis = Path(sys.argv[4]) if len(sys.argv) > 4 else KOK / f"_onizleme_{tur}.jpg"
        hits = ara(tur, sorgu)
        kontak_sayfasi(hits, tur, cikis)
        print(f"{len(hits)} sonuç -> {cikis}")
        for i, h in enumerate(hits):
            print(i, h["id"], h.get("tags", ""))
