"""Üretilen medyayı ve durum dosyalarını GitHub'a gönderir, herkese açık linkleri verir.

Kullanım:  python motor/yayinla.py medya/<klasör>
Son satır JSON: {"klasor": ..., "karusel": [url...], "reel": url, "kapak": url}

Hem yerel bilgisayarda (Windows) hem bulutta (Linux) çalışır.
Token: GH_TOKEN ortam değişkeni, yoksa ../github-token.txt (yerel).
- 7 günden eski medya klasörlerindeki büyük dosyalar silinir (icerik.json ve açıklamalar kalır).
- .git 700 MB'ı geçerse geçmiş tek commit'e indirilir.
"""
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

DEPO = Path(__file__).resolve().parent.parent
SITE = "https://gecirgenbagirsak.github.io/icerik"
UZAK = "github.com/gecirgenbagirsak/icerik.git"
BUYUK = (".mp4", ".jpg", ".png")


def token():
    if os.environ.get("GH_TOKEN"):
        return os.environ["GH_TOKEN"].strip()
    return (DEPO.parent / "github-token.txt").read_text(encoding="utf-8-sig").strip()


def git(*args, ozel=False):
    exe = shutil.which("git") or r"C:\Program Files\Git\cmd\git.exe"
    r = subprocess.run([exe, "-C", str(DEPO), *args], capture_output=True, text=True)
    if r.returncode != 0:
        hata = r.stderr.replace(token(), "***") if ozel else r.stderr
        raise RuntimeError(f"git {args[0]} başarısız: {hata.strip()}")
    return r.stdout


def _var(anahtar):
    try:
        return bool(git("config", anahtar).strip())
    except RuntimeError:
        return False


def gonder(force=False):
    url = f"https://x-access-token:{token()}@{UZAK}"
    args = ["push", "-q", url, "HEAD:main"]
    if force:
        args.insert(2, "--force")
    git(*args, ozel=True)


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


def git_boyutu():
    return sum(f.stat().st_size for f in (DEPO / ".git").rglob("*") if f.is_file())


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
    klasor = (DEPO / sys.argv[1]).resolve() if not Path(sys.argv[1]).is_absolute() else Path(sys.argv[1])
    ad = klasor.name
    if klasor.parent != DEPO / "medya":
        sys.exit("Klasör medya/ altında olmalı")
    if not _var("user.email"):
        git("config", "user.name", "gecirgenbagirsak")
        git("config", "user.email", "gecirgenbagirsak@users.noreply.github.com")
    eski_temizle()
    git("add", "-A", "medya", "durum")
    if git("status", "--porcelain").strip():
        git("commit", "-q", "-m", f"icerik: {ad}")
        if git_boyutu() > 700 * 1024 * 1024:
            git("checkout", "-q", "--orphan", "_yeni")
            git("add", "-A")
            git("commit", "-q", "-m", f"icerik (gecmis sifirlandi): {ad}")
            gonder(force=True)
        else:
            gonder()

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
