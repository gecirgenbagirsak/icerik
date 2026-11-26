"""YouTube senkron yükleyici (bulut, GitHub Actions).

Kuyruk: yt-senkron/kuyruk.json  -> her öğe: {id, kaynak, hedefler, baslik{kanal}, aciklama{kanal}, etiketler{kanal}, short}
Videolar ve kapaklar: bu deponun "yt-senkron" Release'i  (<id>.mp4, <id>_<kanal>.jpg)
Durum: yt-senkron/durum.json  -> {"yuklenen": {"<id>:<kanal>": "<youtube id>"}, "hata": {...}}

Ortam: YT_TOKENS = {"gidersiz": {...token json...}, "anahtar": {...}}, GITHUB_TOKEN, GITHUB_REPOSITORY
       ADET (varsayılan 1)  -> bu çalışmada en fazla kaç yükleme
"""
import json
import os
import sys
import time
import urllib.request

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ozgun import iletisim_ekle   # WhatsApp iletişim bloğu (eski kuyruk kayıtlarına da uygulanır)

KOK = os.path.dirname(os.path.abspath(__file__))
KUYRUK = os.path.join(KOK, "kuyruk.json")
DURUM = os.path.join(KOK, "durum.json")
ADET = int(os.environ.get("ADET", "1"))
REPO = os.environ.get("GITHUB_REPOSITORY", "gecirgenbagirsak/icerik")
RELEASE = "yt-senkron"
KANAL_LISTESI = ("gidersiz", "anahtar")
GUNLUK_KANAL = int(os.environ.get("GUNLUK_KANAL", "4"))   # her kanala günde en fazla
ARALIK_SAAT = float(os.environ.get("ARALIK_SAAT", "2.5"))  # iki yükleme arası en az (saat)
PENCERE = (9, 22)                                          # TR saati
ZORLA = os.environ.get("ZORLA", "").lower() == "true"     # sadece test için
SCOPES = ["https://www.googleapis.com/auth/youtube.upload", "https://www.googleapis.com/auth/youtube.readonly"]


def oku(p, v):
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else v


def yaz(p, d):
    json.dump(d, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def youtube(kanal):
    info = json.loads(os.environ["YT_TOKENS"])[kanal]
    c = Credentials.from_authorized_user_info(info, SCOPES)
    if not c.valid:
        c.refresh(Request())
    return build("youtube", "v3", credentials=c, cache_discovery=False)


def asset_indir(ad, hedef):
    tok = os.environ.get("GITHUB_TOKEN", "")
    h = {"Authorization": f"Bearer {tok}", "Accept": "application/vnd.github+json"}
    rel = json.loads(urllib.request.urlopen(urllib.request.Request(
        f"https://api.github.com/repos/{REPO}/releases/tags/{RELEASE}", headers=h)).read())
    a = next((x for x in rel["assets"] if x["name"] == ad), None)
    if not a:
        return False
    req = urllib.request.Request(a["url"], headers={**h, "Accept": "application/octet-stream"})
    with urllib.request.urlopen(req, timeout=600) as r, open(hedef, "wb") as f:
        while True:
            b = r.read(1 << 20)
            if not b:
                break
            f.write(b)
    return True


def yukle(yt, video, ogr, kanal):
    govde = {
        "snippet": {"title": ogr["baslik"][kanal], "description": iletisim_ekle(ogr["aciklama"][kanal]),
                    "tags": ogr["etiketler"][kanal], "categoryId": "27", "defaultLanguage": "tr"},
        "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False},
    }
    istek = yt.videos().insert(part="snippet,status", body=govde,
                               media_body=MediaFileUpload(video, chunksize=8 << 20, resumable=True))
    cevap = None
    while cevap is None:
        _, cevap = istek.next_chunk()
    return cevap["id"]


def kapak_tak(yt, vid, ogr, kanal, video=None):
    """Videoya premium kapağı takar. Release'te kapak yoksa videodan yerinde üretir; 3 kez dener.
    Hiçbir video kapaksız kalmasın diye başarısızsa False döner (sonraki çalışmada tekrar denenir)."""
    kapak = f"/tmp/{ogr['id']}_{kanal}.jpg"
    if not os.path.exists(kapak) and not asset_indir(f"{ogr['id']}_{kanal}.jpg", kapak):
        try:
            if not video:
                video = f"/tmp/{ogr['id']}.mp4"
                if not os.path.exists(video) and not asset_indir(f"{ogr['id']}.mp4", video):
                    return False
            from ozgun import kapak as kapak_uret
            kapak_uret(video, ogr["baslik"][kanal].replace(" #shorts", ""), kanal, kapak)
            print("  kapak Release'te yoktu, videodan üretildi")
        except Exception as e:
            print(f"  kapak üretilemedi: {e}")
            return False
    for deneme in range(3):
        try:
            yt.thumbnails().set(videoId=vid, media_body=MediaFileUpload(kapak)).execute()
            print(f"  premium kapak takıldı ({kanal})")
            return True
        except HttpError as e:
            print(f"  kapak denemesi {deneme + 1} başarısız: {str(e)[:200]}")
            time.sleep(20)
    return False


def kapak_tamamla(durum):
    bekleyen = durum.get("kapaksiz", {})
    if not bekleyen:
        return
    kuyruk = {o["id"]: o for o in oku(KUYRUK, [])}
    for anahtar, vid in list(bekleyen.items()):
        oid, kanal = anahtar.rsplit(":", 1)
        if oid in kuyruk:
            try:
                if kapak_tak(youtube(kanal), vid, kuyruk[oid], kanal):
                    bekleyen.pop(anahtar)
            except Exception as e:
                print(f"  kapak tamamlanamadı {anahtar}: {e}")


def main():
    kuyruk = oku(KUYRUK, [])
    durum = oku(DURUM, {"yuklenen": {}, "hata": {}})
    # öncelik: Mağazanolsun (yeni/ileri tarihli) > diğerleri; kuyruk sırası korunur
    isler = [(o, k) for o in kuyruk for k in o["hedefler"]
             if f"{o['id']}:{k}" not in durum["yuklenen"] and durum["hata"].get(f"{o['id']}:{k}", 0) < 3]
    isler.sort(key=lambda x: 0 if x[0].get("kaynak") == "magazanolsun" else 1)
    print(f"Bekleyen {len(isler)} yükleme")
    # Zamanlama (görev her saat uyanır): TR 09-22 arası; her kanala günde GUNLUK_KANAL (4),
    # aynı kanalda iki yükleme arası en az ARALIK_SAAT; bir çalışmada kanal başına en fazla 1 yükleme.
    import datetime
    tr = datetime.timezone(datetime.timedelta(hours=3))
    simdi = datetime.datetime.now(tr)
    kapak_tamamla(durum)      # önceki çalışmalarda kapağı takılamayan videolar
    if not ZORLA and not (PENCERE[0] <= simdi.hour < PENCERE[1]):
        print(f"Saat {simdi:%H:%M} yükleme penceresi dışında; atlandı.")
        yaz(DURUM, durum)
        return
    bugun = simdi.strftime("%Y-%m-%d")
    gunluk = durum.setdefault("gunluk", {}).setdefault(bugun, {})
    son_kanal = durum.setdefault("son_kanal", {})

    def uygun_mu(kanal):
        if gunluk.get(kanal, 0) >= GUNLUK_KANAL:
            return False
        if ZORLA or not son_kanal.get(kanal):
            return True
        gecen = (simdi - datetime.datetime.fromisoformat(son_kanal[kanal])).total_seconds() / 3600
        return gecen >= ARALIK_SAAT

    # sıra: bugün en az yükleme alan kanal önce, Mağazanolsun öncelikli
    isler.sort(key=lambda x: (gunluk.get(x[1], 0), 0 if x[0].get("kaynak") == "magazanolsun" else 1))
    yapilan, bu_tur = 0, set()
    for ogr, kanal in isler:
        if yapilan >= max(ADET, len(KANAL_LISTESI)):
            break
        if kanal in bu_tur or not uygun_mu(kanal):
            continue
        anahtar = f"{ogr['id']}:{kanal}"
        video = f"/tmp/{ogr['id']}.mp4"
        if not os.path.exists(video) and not asset_indir(f"{ogr['id']}.mp4", video):
            print(f"[atla] {anahtar}: video arşivde yok (henüz indirilmedi)")
            continue
        try:
            yt = youtube(kanal)
            vid = yukle(yt, video, ogr, kanal)
            print(f"[yüklendi] {anahtar} -> https://youtu.be/{vid}  {ogr['baslik'][kanal]}")
            durum["yuklenen"][anahtar] = vid
            gunluk[kanal] = gunluk.get(kanal, 0) + 1
            son_kanal[kanal] = durum["son_yukleme"] = datetime.datetime.now(tr).isoformat()
            bu_tur.add(kanal)
            yapilan += 1
            yaz(DURUM, durum)
            if not kapak_tak(yt, vid, ogr, kanal, video):
                durum.setdefault("kapaksiz", {})[anahtar] = vid
        except HttpError as e:
            metin = str(e)
            print(f"[hata] {anahtar}: {metin[:300]}")
            if "quotaExceeded" in metin or "uploadLimitExceeded" in metin:
                bu_tur.add(kanal)   # bu kanal bugünlük sınırda; diğer kanal denenebilir
                continue
            durum["hata"][anahtar] = durum["hata"].get(anahtar, 0) + 1
        yaz(DURUM, durum)
    yaz(DURUM, durum)
    print(f"Bu çalışmada {yapilan} yükleme. Toplam yüklenen: {len(durum['yuklenen'])}")


if __name__ == "__main__":
    main()
