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

KOK = os.path.dirname(os.path.abspath(__file__))
KUYRUK = os.path.join(KOK, "kuyruk.json")
DURUM = os.path.join(KOK, "durum.json")
ADET = int(os.environ.get("ADET", "1"))
REPO = os.environ.get("GITHUB_REPOSITORY", "gecirgenbagirsak/icerik")
RELEASE = "yt-senkron"
KANAL_LISTESI = ("gidersiz", "anahtar")
GUNLUK_KANAL = int(os.environ.get("GUNLUK_KANAL", "2"))   # her kanala günde en fazla
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
        "snippet": {"title": ogr["baslik"][kanal], "description": ogr["aciklama"][kanal],
                    "tags": ogr["etiketler"][kanal], "categoryId": "27", "defaultLanguage": "tr"},
        "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False},
    }
    istek = yt.videos().insert(part="snippet,status", body=govde,
                               media_body=MediaFileUpload(video, chunksize=8 << 20, resumable=True))
    cevap = None
    while cevap is None:
        _, cevap = istek.next_chunk()
    return cevap["id"]


def main():
    kuyruk = oku(KUYRUK, [])
    durum = oku(DURUM, {"yuklenen": {}, "hata": {}})
    # öncelik: Mağazanolsun (yeni/ileri tarihli) > diğerleri; kuyruk sırası korunur
    isler = [(o, k) for o in kuyruk for k in o["hedefler"]
             if f"{o['id']}:{k}" not in durum["yuklenen"] and durum["hata"].get(f"{o['id']}:{k}", 0) < 3]
    isler.sort(key=lambda x: 0 if x[0].get("kaynak") == "magazanolsun" else 1)
    print(f"Bekleyen {len(isler)} yükleme")
    # Zamanlama kararı (görev her saat uyanır): TR 09-22 arası, yüklemeler arası en az ARALIK_SAAT
    import datetime
    tr = datetime.timezone(datetime.timedelta(hours=3))
    simdi = datetime.datetime.now(tr)
    if not ZORLA:
        if not (PENCERE[0] <= simdi.hour < PENCERE[1]):
            print(f"Saat {simdi:%H:%M} yükleme penceresi dışında; atlandı.")
            return
        son = durum.get("son_yukleme")
        if son:
            gecen = (simdi - datetime.datetime.fromisoformat(son)).total_seconds() / 3600
            if gecen < ARALIK_SAAT:
                print(f"Son yüklemeden {gecen:.1f} saat geçti (< {ARALIK_SAAT}); atlandı.")
                return
    # Kanal başına günlük kota: her kanala günde 2; bir kanalın kuyruğu boşsa hakkı diğerine geçer
    bugun = simdi.strftime("%Y-%m-%d")
    gunluk = durum.setdefault("gunluk", {}).setdefault(bugun, {})
    bekleyen_kanallar = {k for _, k in isler}
    toplam_hak = GUNLUK_KANAL * len(KANAL_LISTESI)

    def uygun_mu(kanal):
        if sum(gunluk.values()) >= toplam_hak:
            return False
        if gunluk.get(kanal, 0) < GUNLUK_KANAL:
            return True
        # bu kanal kotasını doldurdu; diğer kanalın bekleyeni yoksa onun hakkını kullan
        return not any(k in bekleyen_kanallar for k in KANAL_LISTESI if k != kanal and gunluk.get(k, 0) < GUNLUK_KANAL)

    # sıra: bugün en az yükleme alan kanal önce
    isler.sort(key=lambda x: (gunluk.get(x[1], 0), 0 if x[0].get("kaynak") == "magazanolsun" else 1))
    yapilan = 0
    for ogr, kanal in isler:
        if yapilan >= ADET:
            break
        if not uygun_mu(kanal):
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
            kapak = f"/tmp/{ogr['id']}_{kanal}.jpg"
            if asset_indir(f"{ogr['id']}_{kanal}.jpg", kapak):
                try:
                    yt.thumbnails().set(videoId=vid, media_body=MediaFileUpload(kapak)).execute()
                except HttpError as e:
                    print(f"  kapak eklenemedi: {e}")
            durum["yuklenen"][anahtar] = vid
            gunluk[kanal] = gunluk.get(kanal, 0) + 1
            durum["son_yukleme"] = datetime.datetime.now(tr).isoformat()
            yapilan += 1
        except HttpError as e:
            metin = str(e)
            print(f"[hata] {anahtar}: {metin[:300]}")
            if "quotaExceeded" in metin or "uploadLimitExceeded" in metin:
                break   # günlük sınır: yarın devam
            durum["hata"][anahtar] = durum["hata"].get(anahtar, 0) + 1
        yaz(DURUM, durum)
    yaz(DURUM, durum)
    print(f"Bu çalışmada {yapilan} yükleme. Toplam yüklenen: {len(durum['yuklenen'])}")


if __name__ == "__main__":
    main()
