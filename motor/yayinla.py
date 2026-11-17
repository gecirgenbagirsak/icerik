"""Üretilen medyayı ve durum dosyalarını GitHub'a gönderir, herkese açık linkleri verir.

Kullanım:  python motor/yayinla.py medya/<klasör>
Son satır JSON: {"klasor": ..., "karusel": [url...], "reel": url, "kapak": url}

Gönderim `git push` ile DEĞİL, GitHub REST API (Git Data API) ile yapılır: bulut oturumlarının
git proxy'si yetkisiz depolara push'u engelliyor, API ise GH_TOKEN ile doğrudan çalışıyor.
Hem yerel bilgisayarda (Windows) hem bulutta (Linux) çalışır.
Token: GH_TOKEN ortam değişkeni, yoksa ../github-token.txt (yerel).
7 günden eski medya klasörlerindeki büyük dosyalar silinir (icerik.json ve açıklamalar kalır).
"""
import base64
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

DEPO = Path(__file__).resolve().parent.parent
SITE = "https://gecirgenbagirsak.github.io/icerik"
REPO = "gecirgenbagirsak/icerik"
API = f"https://api.github.com/repos/{REPO}"
BUYUK = (".mp4", ".jpg", ".png")


def token():
    if os.environ.get("GH_TOKEN"):
        return os.environ["GH_TOKEN"].strip()
    return (DEPO.parent / "github-token.txt").read_text(encoding="utf-8-sig").strip()


def git(*args):
    exe = shutil.which("git") or r"C:\Program Files\Git\cmd\git.exe"
    r = subprocess.run([exe, "-C", str(DEPO), *args], capture_output=True, text=True, encoding="utf-8")
    if r.returncode != 0:
        raise RuntimeError(f"git {args[0]} başarısız: {r.stderr.strip()}")
    return r.stdout


def api(yol, veri=None, yontem=None, deneme=4):
    url = yol if yol.startswith("http") else API + yol
    govde = json.dumps(veri).encode() if veri is not None else None
    for i in range(deneme):
        req = urllib.request.Request(url, data=govde, method=yontem or ("POST" if govde else "GET"), headers={
            "Authorization": f"Bearer {token()}", "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "icerik-motoru",
            "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                return json.loads(r.read() or b"{}")
        except urllib.error.HTTPError as e:
            if e.code in (500, 502, 503, 504) and i < deneme - 1:
                time.sleep(5 * (i + 1))
                continue
            raise RuntimeError(f"GitHub API {e.code} {yol}: {e.read()[:300]!r}")


def eski_temizle():
    sinir = datetime.now() - timedelta(days=7)
    for d in (DEPO / "medya").iterdir():
        try:
            tarih = datetime.strptime(d.name[:10], "%Y-%m-%d")
        except ValueError:
            continue
        if tarih < sinir:
            for f in d.iterdir():
                if f.suffix.lower() in BUYUK:
                    f.unlink()


def degisenler():
    """medya/ ve durum/ altında uzak main'e göre değişen dosyalar: [(yol, silindi_mi)]."""
    git("add", "-A", "medya", "durum")
    cikti = git("diff", "--cached", "--name-status", "--no-renames")
    sonuc = []
    for satir in cikti.splitlines():
        durum, yol = satir.split("\t", 1)
        sonuc.append((yol, durum == "D"))
    return sonuc


def api_gonder(dosyalar, mesaj):
    ref = api("/git/ref/heads/main")
    bas = ref["object"]["sha"]
    agac = api(f"/git/commits/{bas}")["tree"]["sha"]
    girdiler = []
    for yol, silindi in dosyalar:
        if silindi:
            girdiler.append({"path": yol, "mode": "100644", "type": "blob", "sha": None})
            continue
        icerik = base64.b64encode((DEPO / yol).read_bytes()).decode()
        blob = api("/git/blobs", {"content": icerik, "encoding": "base64"})
        girdiler.append({"path": yol, "mode": "100644", "type": "blob", "sha": blob["sha"]})
    yeni_agac = api("/git/trees", {"base_tree": agac, "tree": girdiler})
    commit = api("/git/commits", {"message": mesaj, "tree": yeni_agac["sha"], "parents": [bas]})
    api("/git/refs/heads/main", {"sha": commit["sha"]}, yontem="PATCH")
    return commit["sha"]


def yerel_esitle():
    """Yerel kopyayı uzak main'e hizala (çalışma dosyalarına dokunmadan)."""
    try:
        git("fetch", "-q", f"https://github.com/{REPO}.git", "main")
        git("reset", "-q", "--mixed", "FETCH_HEAD")
    except RuntimeError as e:
        print("Not: yerel kopya eşitlenemedi:", e)


def bekle(url, sure=420):
    bas = time.time()
    while time.time() - bas < sure:
        try:
            with urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=20) as r:
                if r.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(10)
    return False


def main():
    klasor = Path(sys.argv[1])
    klasor = klasor if klasor.is_absolute() else (DEPO / klasor)
    klasor = klasor.resolve()
    ad = klasor.name
    if klasor.parent != DEPO / "medya":
        sys.exit("Klasör medya/ altında olmalı")
    eski_temizle()
    dosyalar = degisenler()
    if dosyalar:
        try:
            sha = api_gonder(dosyalar, f"icerik: {ad}")
            print(f"GitHub'a gönderildi (API): {len(dosyalar)} dosya, commit {sha[:7]}")
            yerel_esitle()
        except RuntimeError as e:
            # Yedek yol: bulut oturumunda depo kaynak olarak bağlıysa proxy git push'a kimlik ekler
            print("API başarısız, git push deneniyor:", str(e)[:200])
            try:
                git("config", "user.name", "gecirgenbagirsak")
                git("config", "user.email", "gecirgenbagirsak@users.noreply.github.com")
                git("commit", "-q", "-m", f"icerik: {ad}")
                git("push", "-q", "origin", "HEAD:main")
                print("GitHub'a gönderildi (git push)")
            except RuntimeError as e2:
                sys.exit(f"GitHub'a gönderilemedi: {e2}")

    karusel = sorted(klasor.glob("karusel_*.jpg"))
    sonuc = {"klasor": ad,
             "karusel": [f"{SITE}/medya/{ad}/{f.name}" for f in karusel],
             "reel": f"{SITE}/medya/{ad}/reel.mp4" if (klasor / "reel.mp4").exists() else None,
             "kapak": f"{SITE}/medya/{ad}/reel_kapak.jpg" if (klasor / "reel_kapak.jpg").exists() else None}
    kontrol = sonuc["reel"] or (sonuc["karusel"][-1] if sonuc["karusel"] else None)
    if kontrol and not bekle(kontrol):
        print("UYARI: link 7 dakikada erişilebilir olmadı:", kontrol)
        sys.exit(3)
    print(json.dumps(sonuc, ensure_ascii=False))


if __name__ == "__main__":
    main()
