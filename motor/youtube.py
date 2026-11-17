"""YouTube Shorts yükleyici (YouTube Data API v3, ücretsiz).

İlk kurulum (bir kez, tarayıcıda izin verilir):
    py youtube.py giris
Yükleme:
    py youtube.py yukle <video.mp4> --baslik "..." --aciklama-dosyasi aciklama.txt [--gizlilik public|unlisted|private]

Gizli dosyalar Chatplace klasöründe durur, GitHub'a gitmez:
    youtube-client.json  (Google Cloud > Clients > Desktop app)
    youtube-token.json   (giriş sonrası otomatik oluşur)
"""
import argparse
import sys
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

import json
import os

KLASOR = Path(__file__).resolve().parent.parent.parent   # Chatplace (yerel bilgisayar)
CLIENT = KLASOR / "youtube-client.json"
TOKEN = KLASOR / "youtube-token.json"
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def kimlik(yeni_giris=False):
    # Bulut: YOUTUBE_TOKEN_JSON ortam değişkeni (tek satır JSON). Token bellekte yenilenir.
    if os.environ.get("YOUTUBE_TOKEN_JSON") and not yeni_giris:
        creds = Credentials.from_authorized_user_info(json.loads(os.environ["YOUTUBE_TOKEN_JSON"]), SCOPES)
        if not creds.valid:
            try:
                creds.refresh(Request())
            except Exception as e:
                print(f"YouTube oturumu yenilenemedi ({e}). Bilgisayarda 'py yayin\\motor\\youtube.py giris' "
                      "çalıştırılıp yeni token bulut ortamına girilmeli.")
                sys.exit(2)
        return creds
    creds = None
    if TOKEN.exists() and not yeni_giris:
        creds = Credentials.from_authorized_user_file(str(TOKEN), SCOPES)
    if creds and creds.valid:
        return creds
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            TOKEN.write_text(creds.to_json(), encoding="utf-8")
            return creds
        except Exception as e:  # Testing modunda 7 günde bir düşer
            print(f"Oturum yenilenemedi ({e}). Yeniden giriş gerekiyor: py youtube.py giris")
            if not yeni_giris:
                sys.exit(2)
    flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT), SCOPES)
    creds = flow.run_local_server(port=0, prompt="consent", access_type="offline",
                                  success_message="YouTube bağlantısı tamam. Bu sekmeyi kapatabilirsiniz.")
    TOKEN.write_text(creds.to_json(), encoding="utf-8")
    return creds


def yukle(video, baslik, aciklama, etiketler, gizlilik="public", kategori="27"):
    yt = build("youtube", "v3", credentials=kimlik())
    govde = {
        "snippet": {
            "title": baslik[:100],
            "description": aciklama[:5000],
            "tags": etiketler[:30],
            "categoryId": kategori,  # 27 = Eğitim
            "defaultLanguage": "tr",
            "defaultAudioLanguage": "tr",
        },
        "status": {"privacyStatus": gizlilik, "selfDeclaredMadeForKids": False},
    }
    istek = yt.videos().insert(part="snippet,status", body=govde,
                               media_body=MediaFileUpload(str(video), mimetype="video/mp4", resumable=True))
    yanit = None
    while yanit is None:
        durum, yanit = istek.next_chunk()
        if durum:
            print(f"  yükleniyor %{int(durum.progress() * 100)}")
    vid = yanit["id"]
    print(f"Yüklendi: https://youtube.com/shorts/{vid}  (durum: {yanit['status']['privacyStatus']})")
    return yanit


def main():
    p = argparse.ArgumentParser()
    alt = p.add_subparsers(dest="komut", required=True)
    alt.add_parser("giris")
    y = alt.add_parser("yukle")
    y.add_argument("video")
    y.add_argument("--baslik", required=True)
    y.add_argument("--aciklama-dosyasi")
    y.add_argument("--etiketler", default="")
    y.add_argument("--gizlilik", default="public", choices=["public", "unlisted", "private"])
    a = p.parse_args()
    if a.komut == "giris":
        kimlik(yeni_giris=True)
        print("YouTube girişi tamamlandı, token kaydedildi.")
    else:
        aciklama = Path(a.aciklama_dosyasi).read_text(encoding="utf-8") if a.aciklama_dosyasi else ""
        etiketler = [t.strip().lstrip("#") for t in a.etiketler.split(",") if t.strip()]
        yukle(a.video, a.baslik, aciklama, etiketler, a.gizlilik)


if __name__ == "__main__":
    main()
