"""Bulutta (GitHub Actions) günlük uzun video yükleyici.

Her çalışmada en fazla 1 video:
  - Sıradaki videoyu kaynak YouTube kanalından yt-dlp ile indirir.
  - Kendi kanalına GİZLİ + publishAt ile yükler (yayın saati her gün farklı).
  - kapaklar/<id>.jpg dosyasını küçük resim yapar.
  - yuklenenler.json'u günceller (workflow commit eder).
Önde 1 gün tampon tutar: yarının videosu planlıysa hiçbir şey yapmaz.
Ortam: YOUTUBE_TOKEN_JSON (tek satır JSON).
"""
import datetime as dt
import json
import os
import subprocess
import sys
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

BASE = Path(__file__).resolve().parent
DURUM = BASE / "yuklenenler.json"
TR = dt.timezone(dt.timedelta(hours=3))
SAATLER = ["10:30", "15:00", "19:30", "11:15", "16:45", "20:15", "09:45", "14:15", "21:00", "17:30"]
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def indir(kaynak_id, hedef):
    komut = ["yt-dlp", "-f", "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/b[height<=1080]/b",
             "--merge-output-format", "mp4", "-o", str(hedef), "--no-progress",
             f"https://www.youtube.com/watch?v={kaynak_id}"]
    subprocess.run(komut, check=True)
    return hedef.exists()


def main():
    meta = json.load(open(BASE / "yukleme.json", encoding="utf-8"))
    durum = json.load(open(DURUM, encoding="utf-8"))
    yapilan = {x["id"] for x in durum["yuklenen"]}
    kalan = [m for m in meta if m["id"] not in yapilan]
    if not kalan:
        print("Tüm videolar planlandı.")
        return

    if os.environ.get("INDIRME_TESTI") == "true":
        ok = indir(kalan[0]["id"], Path("/tmp") / "test.mp4")
        print(f"İndirme testi: {'BAŞARILI' if ok else 'BAŞARISIZ'} ({kalan[0]['id']})")
        sys.exit(0 if ok else 1)

    simdi = dt.datetime.now(TR)
    bugun = simdi.date()
    son = max((dt.datetime.fromisoformat(x["yayin"]) for x in durum["yuklenen"]), default=None)
    gun = (son.date() + dt.timedelta(days=1)) if son else bugun
    if gun < bugun:
        gun = bugun
    if gun > bugun + dt.timedelta(days=1):
        print(f"Tampon yeterli (son planlı: {son:%Y-%m-%d}). Bugün iş yok.")
        return

    saat = SAATLER[len(durum["yuklenen"]) % len(SAATLER)]
    hh, mm = map(int, saat.split(":"))
    yayin = dt.datetime(gun.year, gun.month, gun.day, hh, mm, tzinfo=TR)
    if yayin < simdi + dt.timedelta(minutes=90):
        yayin = (simdi + dt.timedelta(minutes=90)).replace(second=0, microsecond=0)

    m = kalan[0]
    video = Path("/tmp") / f"{m['id']}.mp4"
    print(f"İndiriliyor: {m['id']}")
    if not indir(m["id"], video):
        sys.exit("İndirme başarısız")

    creds = Credentials.from_authorized_user_info(json.loads(os.environ["YOUTUBE_TOKEN_JSON"]), SCOPES)
    if not creds.valid:
        creds.refresh(Request())
    yt = build("youtube", "v3", credentials=creds)
    govde = {
        "snippet": {"title": m["title"][:100], "description": m["full_desc"][:5000],
                    "tags": m["tag_list"][:30], "categoryId": "27",
                    "defaultLanguage": "tr", "defaultAudioLanguage": "tr"},
        "status": {"privacyStatus": "private",
                   "publishAt": yayin.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                   "selfDeclaredMadeForKids": False},
    }
    print(f"Yükleniyor → yayın {yayin:%Y-%m-%d %H:%M} TR")
    istek = yt.videos().insert(part="snippet,status", body=govde,
                               media_body=MediaFileUpload(str(video), mimetype="video/mp4", resumable=True,
                                                          chunksize=32 * 1024 * 1024))
    yanit = None
    while yanit is None:
        _, yanit = istek.next_chunk()
    vid = yanit["id"]
    kayit = {"id": m["id"], "youtube": vid, "yayin": yayin.isoformat(), "kapak": False}
    kapak = BASE / "kapaklar" / f"{m['id']}.jpg"
    try:
        if kapak.exists():
            yt.thumbnails().set(videoId=vid, media_body=MediaFileUpload(str(kapak), mimetype="image/jpeg")).execute()
            kayit["kapak"] = True
    except Exception as e:
        print(f"Kapak ayarlanamadı: {e}")
    durum["yuklenen"].append(kayit)
    json.dump(durum, open(DURUM, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"Tamam: https://youtu.be/{vid}  kapak={kayit['kapak']}")


if __name__ == "__main__":
    main()
