"""Daha önce yüklenmiş videoların kapaklarını premium tasarımla yeniler (bulut, GitHub Actions).

durum.json'daki her "<id>:<kanal>" -> YouTube video için: videoyu Release'ten indir, ozgun.kapak ile
Full HD kapak üret, YouTube'a kapak olarak yükle; aynı kapağı Release'teki <id>_<kanal>.jpg yerine koy.
Yenilenenler durum.json -> "kapak_v2" listesine yazılır, tekrar çalıştırınca atlanır.

Ortam: YT_TOKENS, GITHUB_TOKEN, KANALLAR (varsayılan "gidersiz,anahtar"), YENIDEN=true (hepsini yeniden yap)
"""
import json
import os
import sys
import urllib.request

KOK = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, KOK)
import ozgun  # noqa: E402
import yukle as y  # noqa: E402
from googleapiclient.errors import HttpError  # noqa: E402

KANALLAR = [k.strip() for k in os.environ.get("KANALLAR", "gidersiz,anahtar").split(",") if k.strip()]
YENIDEN = os.environ.get("YENIDEN", "").lower() == "true"


def release_degistir(yol, ad):
    """Release'teki aynı adlı kapağı siler ve yenisini yükler."""
    h = {"Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}", "Accept": "application/vnd.github+json"}
    rel = json.loads(urllib.request.urlopen(urllib.request.Request(
        f"https://api.github.com/repos/{y.REPO}/releases/tags/{y.RELEASE}", headers=h)).read())
    for a in rel["assets"]:
        if a["name"] == ad:
            urllib.request.urlopen(urllib.request.Request(a["url"], headers=h, method="DELETE"))
    with open(yol, "rb") as f:
        urllib.request.urlopen(urllib.request.Request(
            f"https://uploads.github.com/repos/{y.REPO}/releases/{rel['id']}/assets?name={ad}",
            data=f.read(), method="POST", headers={**h, "Content-Type": "image/jpeg"}), timeout=300)


def main():
    kuyruk = {o["id"]: o for o in y.oku(y.KUYRUK, [])}
    durum = y.oku(y.DURUM, {"yuklenen": {}, "hata": {}})
    yapilan = set() if YENIDEN else set(durum.get("kapak_v2", []))
    servis = {}
    tamam = 0
    for anahtar, vid in durum["yuklenen"].items():
        oid, kanal = anahtar.rsplit(":", 1)
        if kanal not in KANALLAR or anahtar in yapilan or oid not in kuyruk:
            continue
        ogr = kuyruk[oid]
        video = f"/tmp/{oid}.mp4"
        if not os.path.exists(video) and not y.asset_indir(f"{oid}.mp4", video):
            print(f"[atla] {anahtar}: video arşivde yok")
            continue
        kapak = f"/tmp/{oid}_{kanal}.jpg"
        ozgun.kapak(video, ogr["baslik"][kanal], kanal, kapak)
        try:
            if kanal not in servis:
                servis[kanal] = y.youtube(kanal)
            y.kapak_ayarla(servis[kanal], vid, kapak)
        except HttpError as e:
            print(f"[hata] {anahtar} -> {vid}: {str(e)[:300]}")
            if "quotaExceeded" in str(e):
                break
            continue
        try:
            release_degistir(kapak, f"{oid}_{kanal}.jpg")
        except Exception as e:
            print(f"  release kapağı güncellenemedi: {e}")
        yapilan.add(anahtar)
        tamam += 1
        print(f"[kapak yenilendi] https://youtu.be/{vid}  {ozgun.kapak_metni(ogr['baslik'][kanal])}")
    durum = y.oku(y.DURUM, {"yuklenen": {}, "hata": {}})          # arada değişmiş olabilir
    durum["kapak_v2"] = sorted(yapilan | set(durum.get("kapak_v2", [])))
    y.yaz(y.DURUM, durum)
    print(f"Yenilenen kapak: {tamam}")


if __name__ == "__main__":
    main()
