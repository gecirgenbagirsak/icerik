"""Bulutta (GitHub Actions) uzun video planlayıcı — bilgisayar kapalıyken çalışır.

Videolar bu deponun 'uzun-videolar' Release'inde durur (kaynak kanaldan indirme yok).
Her çalışmada sıradaki videoları (en fazla parti_boyu() adet) indirir ve kanala
GİZLİ + publishAt ile yükler; yayınlar ARALIK_GUN günde bir, saatler döner.
kapaklar/<id>.jpg küçük resim yapılır, yuklenenler.json güncellenir (workflow commit eder).
YouTube kotası dolarsa durur, bir sonraki çalışmada kaldığı yerden devam eder.
Ortam: YOUTUBE_TOKEN_JSON (tek satır JSON).
"""
import datetime as dt
import json
import os
import shutil
import sys
import urllib.request
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

BASE = Path(__file__).resolve().parent
DURUM = BASE / "yuklenenler.json"
TR = dt.timezone(dt.timedelta(hours=3))
SAATLER = ["10:30", "15:00", "19:30", "11:15", "16:45", "20:15", "09:45", "14:15", "21:00", "17:30"]
ARALIK_GUN = 3
RELEASE = "https://github.com/gecirgenbagirsak/icerik/releases/download/uzun-videolar/{}.mp4"
TMP = Path(os.environ.get("RUNNER_TEMP", "/tmp"))


def parti_boyu():
    # Kota günü 08:00 UTC'de başlar; Shorts 09:05 ve 17:05 UTC'de yükler.
    # Sabah (05 UTC) çalışması kota gününün sonu: 3 video. Öğlen (11 UTC): 1 video, akşam Shorts'a yer kalsın.
    return 3 if dt.datetime.now(dt.timezone.utc).hour < 8 else 1


def indir(kaynak_id, hedef):
    try:
        with urllib.request.urlopen(RELEASE.format(kaynak_id), timeout=600) as r, open(hedef, "wb") as f:
            shutil.copyfileobj(r, f, 8 * 1024 * 1024)
    except Exception as e:
        print(f"İndirilemedi ({kaynak_id}): {e}")
        return False
    return hedef.exists() and hedef.stat().st_size > 0


def kota_hatasi(e):
    s = str(e)
    return "quota" in s.lower() or "uploadLimitExceeded" in s


def main():
    meta = json.load(open(BASE / "yukleme.json", encoding="utf-8"))
    durum = json.load(open(DURUM, encoding="utf-8"))
    yapilan = {x["id"] for x in durum["yuklenen"]}
    kalan = [m for m in meta if m["id"] not in yapilan]
    if not kalan:
        print("Tüm videolar planlandı. Yapılacak iş yok.")
        return

    if os.environ.get("INDIRME_TESTI") == "true":
        ok = indir(kalan[0]["id"], TMP / "test.mp4")
        print(f"İndirme testi: {'BAŞARILI' if ok else 'BAŞARISIZ'} ({kalan[0]['id']})")
        sys.exit(0 if ok else 1)

    creds = Credentials.from_authorized_user_info(json.loads(os.environ["YOUTUBE_TOKEN_JSON"]))
    if not creds.valid:
        creds.refresh(Request())
    yt = build("youtube", "v3", credentials=creds)

    for m in kalan[:parti_boyu()]:
        simdi = dt.datetime.now(TR)
        son = max((dt.datetime.fromisoformat(x["yayin"]) for x in durum["yuklenen"]), default=None)
        gun = (son.date() + dt.timedelta(days=ARALIK_GUN)) if son and son > simdi else (simdi + dt.timedelta(days=1)).date()
        saat = SAATLER[len(durum["yuklenen"]) % len(SAATLER)]
        hh, mm = map(int, saat.split(":"))
        yayin = dt.datetime(gun.year, gun.month, gun.day, hh, mm, tzinfo=TR)

        video = TMP / f"{m['id']}.mp4"
        print(f"İndiriliyor: {m['id']}", flush=True)
        if not indir(m["id"], video):
            return
        govde = {
            "snippet": {"title": m["title"][:100], "description": m["full_desc"][:5000],
                        "tags": m["tag_list"][:30], "categoryId": "27",
                        "defaultLanguage": "tr", "defaultAudioLanguage": "tr"},
            "status": {"privacyStatus": "private",
                       "publishAt": yayin.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                       "selfDeclaredMadeForKids": False},
        }
        print(f"Yükleniyor → yayın {yayin:%Y-%m-%d %H:%M} TR", flush=True)
        istek = yt.videos().insert(part="snippet,status", body=govde,
                                   media_body=MediaFileUpload(str(video), mimetype="video/mp4", resumable=True,
                                                              chunksize=32 * 1024 * 1024))
        yanit = None
        try:
            while yanit is None:
                _, yanit = istek.next_chunk()
        except Exception as e:
            if kota_hatasi(e):
                print("YouTube günlük kotası doldu; sonraki çalışmada devam edilecek.")
                return
            raise
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
        print(f"Tamam: https://youtu.be/{vid}  kapak={kayit['kapak']}", flush=True)
        video.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
