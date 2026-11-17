"""Ücretsiz içerik motoru v2: gerçek fotoğraf/video (Pixabay) + yazı + Türkçe seslendirme.

Kullanım:  py uret.py <icerik-klasoru>      (klasörde icerik.json olmalı)
Hiçbir ChatPlace / Virale kredisi kullanmaz: Pixabay + Pillow + ffmpeg + edge-tts.

icerik.json:
  karusel.slides[]: tip (kapak|madde|cta), baslik, metin/alt, no, foto (Pixabay foto ID),
                    odak (0-1, kırpmada dikey odak; varsayılan 0.35), buton, not
  reel.sahneler[]:  ses (seslendirme + altyazı), video (Pixabay video ID ya da ID listesi),
                    baslik (opsiyonel üst başlık)
"""
import asyncio
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
import medya  # noqa: E402

_F = Path(__file__).resolve().parent / "fonts"  # Poppins (OFL lisans) — Windows ve Linux'ta aynı görünüm
FONT_B = str(_F / "Poppins-SemiBold.ttf")
FONT_BL = str(_F / "Poppins-Black.ttf")
FONT_R = str(_F / "Poppins-Regular.ttf")

KOYU_YESIL = (14, 34, 28)
TURUNCU = (240, 158, 50)
BEYAZ = (255, 255, 255)
ACIK = (225, 236, 228)
SES = "tr-TR-EmelNeural"  # alternatif: tr-TR-AhmetNeural


def font(path, size):
    return ImageFont.truetype(path, size)


def sar(draw, text, fnt, max_w):
    lines = []
    for para in text.split("\n"):
        words, cur = para.split(), ""
        for w in words:
            test = (cur + " " + w).strip()
            if draw.textlength(test, font=fnt) <= max_w:
                cur = test
            else:
                if cur:
                    lines.append(cur)
                cur = w
        lines.append(cur)
    return lines


def yaz(draw, xy, lines, fnt, fill, lh, align="left", max_w=0, stroke=0):
    x, y = xy
    for line in lines:
        lx = x + (max_w - draw.textlength(line, font=fnt)) / 2 if align == "center" else x
        draw.text((lx, y), line, font=fnt, fill=fill,
                  stroke_width=stroke, stroke_fill=(0, 0, 0) if stroke else None)
        y += lh
    return y


def kapla(img, W, H, odak=0.35):
    """Görseli W×H alanı dolduracak şekilde ölçekle ve kırp (odak: dikey kırpma noktası)."""
    s = max(W / img.width, H / img.height)
    img = img.resize((round(img.width * s), round(img.height * s)), Image.LANCZOS)
    x = (img.width - W) // 2
    y = int((img.height - H) * odak)
    return img.crop((x, y, x + W, y + H))


def gradyan(W, H, bas=0.38, renk=KOYU_YESIL, max_alpha=238):
    """Alt kısımda koyulaşan geçiş katmanı (yazı okunurluğu için)."""
    g = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(g)
    y0 = int(H * bas)
    for y in range(y0, H):
        t = (y - y0) / (H - y0)
        a = int(max_alpha * min(1, t * 1.35) ** 1.3)
        d.line([(0, y), (W, y)], fill=(*renk, a))
    return g


def ust_golge(W, h=220):
    g = Image.new("RGBA", (W, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(g)
    for y in range(h):
        d.line([(0, y), (W, y)], fill=(0, 0, 0, int(120 * (1 - y / h))))
    return g


# ---------------------------------------------------------------- KARUSEL
def karusel(spec, out: Path, handle):
    W, H, M = 1080, 1350, 80
    slides = spec["slides"]
    n = len(slides)
    for i, s in enumerate(slides, 1):
        kind = s.get("tip", "madde")
        foto = Image.open(medya.indir_foto(s["foto"])).convert("RGB")
        img = kapla(foto, W, H, s.get("odak", 0.35)).convert("RGBA")
        bas = 0.30 if kind in ("kapak", "cta") else 0.40
        img.alpha_composite(gradyan(W, H, bas))
        img.alpha_composite(ust_golge(W), (0, 0))
        d = ImageDraw.Draw(img)
        tw = W - 2 * M

        # Metin bloğunu alttan yukarı yerleştir
        parcalar = []  # (lines, font, renk, satır_yük, önce_boşluk)
        if kind == "kapak":
            fb = font(FONT_BL, 104)
            parcalar.append((sar(d, s["baslik"], fb, tw), fb, BEYAZ, 112, 0))
            if s.get("alt"):
                fa = font(FONT_R, 44)
                parcalar.append((sar(d, s["alt"], fa, tw), fa, ACIK, 58, 34))
        else:
            fb = font(FONT_BL, 84 if kind != "cta" else 92)
            parcalar.append((sar(d, s["baslik"], fb, tw), fb, BEYAZ, 94, 0))
            if s.get("metin"):
                fm = font(FONT_R, 42)
                parcalar.append((sar(d, s["metin"], fm, tw), fm, ACIK, 58, 30))
        alt_bosluk = 150 if (kind == "cta" and s.get("buton")) or kind == "kapak" else 120
        toplam = sum(len(l) * lh + b for l, _, _, lh, b in parcalar)
        y = H - alt_bosluk - toplam - 20

        if s.get("no"):
            r = 58
            d.ellipse([M, y - 2 * r - 30, M + 2 * r, y - 30], fill=TURUNCU)
            nf = font(FONT_BL, 66)
            nt = str(s["no"])
            d.text((M + r - d.textlength(nt, font=nf) / 2, y - 2 * r - 30 + 14), nt, font=nf, fill=KOYU_YESIL)
        elif kind != "kapak":
            d.rectangle([M, y - 40, M + 110, y - 30], fill=TURUNCU)

        for lines, f, renk, lh, bosluk in parcalar:
            y += bosluk
            y = yaz(d, (M, y), lines, f, renk, lh)

        ff = font(FONT_B, 30)
        if kind == "kapak":
            pill = "Kaydırarak oku"
            tw_ = d.textlength(pill, font=ff)
            pw = tw_ + 100
            d.rounded_rectangle([M, H - 120, M + pw, H - 60], 30, fill=TURUNCU)
            d.text((M + 28, H - 113), pill, font=ff, fill=KOYU_YESIL)
            ax, ay = M + 28 + tw_ + 18, H - 90  # ok işareti çizimle (fontta → yok)
            d.line([(ax, ay), (ax + 26, ay)], fill=KOYU_YESIL, width=4)
            d.polygon([(ax + 32, ay), (ax + 20, ay - 9), (ax + 20, ay + 9)], fill=KOYU_YESIL)
        if kind == "cta" and s.get("buton"):
            # sade, çerçeveli kapanış satırı (dolu "buton" yerine)
            bf = font(FONT_B, 36)
            bw = d.textlength(s["buton"], font=bf) + 70
            d.rounded_rectangle([M, H - 140, M + bw, H - 66], 37, outline=TURUNCU, width=3)
            d.text((M + 35, H - 125), s["buton"], font=bf, fill=BEYAZ)

        # üst bilgi: sadece hesap adı (sayfa numarası yok; madde numaralarıyla karışıyordu)
        d.text((M, 46), "@" + handle, font=ff, fill=BEYAZ)
        if s.get("not"):
            nf2 = font(FONT_R, 24)
            d.text((W - M - d.textlength(s["not"], font=nf2), H - 44), s["not"], font=nf2, fill=ACIK)

        img.convert("RGB").save(out / f"karusel_{i:02d}.jpg", quality=92)
    return n


# ---------------------------------------------------------------- REELS
def _bulut_ssl():
    """Bulut oturumunda giden HTTPS bir proxy'den geçer; proxy'nin CA sertifikasına güven."""
    import ssl
    import edge_tts.communicate as ec
    ca = "/root/.ccr/ca-bundle.crt"
    if os.path.exists(ca):
        ec._SSL_CTX = ssl.create_default_context(cafile=ca)
    return os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")


async def tts(text, mp3):
    """Seslendirme + kelime zamanlamaları (altyazı için)."""
    import edge_tts
    proxy = _bulut_ssl()
    for deneme in range(4):
        try:
            words = []
            c = edge_tts.Communicate(text, SES, rate="+6%", boundary="WordBoundary", proxy=proxy)
            with open(mp3, "wb") as f:
                async for m in c.stream():
                    if m["type"] == "audio":
                        f.write(m["data"])
                    elif m["type"] == "WordBoundary":
                        words.append((m["offset"] / 1e7, (m["offset"] + m["duration"]) / 1e7, m["text"]))
            if words:
                return words
        except edge_tts.exceptions.NoAudioReceived:
            pass
        await asyncio.sleep(2 + deneme * 3)
    raise RuntimeError(f"Seslendirme alınamadı: {text[:40]}")


def sure(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                        str(path)], capture_output=True, text=True, check=True)
    return float(r.stdout.strip())


def altyazi_gruplari(words, toplam, max_kelime=3, max_harf=20):
    """Kelimeleri 2-3'lük gruplara böl; her grup bir sonrakinin başına kadar ekranda kalır."""
    gruplar, cur = [], []
    for w in words:
        if cur and (len(cur) >= max_kelime or len(" ".join(x[2] for x in cur + [w])) > max_harf):
            gruplar.append(cur)
            cur = []
        cur.append(w)
        if w[2].endswith((".", ",", "?", "!", ":")):
            gruplar.append(cur)
            cur = []
    if cur:
        gruplar.append(cur)
    sonuc = []
    for i, g in enumerate(gruplar):
        bas = g[0][0]
        bit = gruplar[i + 1][0][0] if i + 1 < len(gruplar) else toplam
        sonuc.append((bas, bit, " ".join(x[2] for x in g)))
    return sonuc


def altyazi_png(text, path, W=1080, H=1920):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    f = font(FONT_BL, 86)
    tr_buyuk = text.replace("i", "İ").replace("ı", "I").upper()  # Türkçe büyük harf
    lines = sar(d, tr_buyuk, f, W - 160)
    y = 1180 - len(lines) * 100 / 2
    yaz(d, (80, y), lines, f, BEYAZ, 100, align="center", max_w=W - 160, stroke=7)
    img.save(path)


def sahne_katmani(path, handle, baslik=None, kapanis=None, W=1080, H=1920):
    """Her sahnede sabit duran katman: alt gölge, hesap adı, opsiyonel üst başlık / kapanış kartı."""
    img = gradyan(W, H, 0.40 if kapanis else 0.45, (0, 0, 0), 200 if kapanis else 170)
    img.alpha_composite(ust_golge(W, 420), (0, 0))
    d = ImageDraw.Draw(img)
    hf = font(FONT_B, 38)
    d.text(((W - d.textlength("@" + handle, font=hf)) / 2, H - 330), "@" + handle, font=hf, fill=BEYAZ)
    if kapanis:
        # Sade kapanış: küçük üst satır + ana mesaj, ince turuncu çizgi
        uf, af = font(FONT_R, 46), font(FONT_BL, 68)
        ana = sar(d, kapanis["ana"], af, W - 200)
        y = 1250 - len(ana) * 80
        d.rectangle([(W - 90) / 2, y - 60, (W + 90) / 2, y - 52], fill=TURUNCU)
        ust = kapanis.get("ust", "")
        if ust:
            d.text(((W - d.textlength(ust, font=uf)) / 2, y), ust, font=uf, fill=ACIK)
            y += 72
        yaz(d, (100, y), ana, af, BEYAZ, 80, align="center", max_w=W - 200)
    if baslik:
        bf = font(FONT_BL, 70)
        lines = sar(d, baslik, bf, W - 200)
        bh = len(lines) * 84 + 50
        d.rounded_rectangle([70, 250, W - 70, 250 + bh], 36, fill=(*TURUNCU, 255))
        yaz(d, (100, 270), lines, bf, KOYU_YESIL, 84, align="center", max_w=W - 200)
    img.save(path)


def reel(spec, out: Path, handle):
    tmp = out / "_tmp"
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir()
    parcalar = []
    for i, s in enumerate(spec["sahneler"], 1):
        mp3 = tmp / f"s{i}.mp3"
        words = asyncio.run(tts(s["ses"], mp3))
        dur = sure(mp3) + 0.25
        klipler = s["video"] if isinstance(s["video"], list) else [s["video"]]
        dosyalar = [medya.indir_video(v) for v in klipler]
        katman = tmp / f"s{i}_katman.png"
        sahne_katmani(katman, handle, s.get("baslik"), s.get("kapanis"))
        # kapanış sahnesinde altyazı yok (kart zaten mesajı veriyor)
        grup = [] if s.get("kapanis") else altyazi_gruplari(words, dur)
        ay_png = []
        for j, (a, b, t) in enumerate(grup):
            p = tmp / f"s{i}_ay{j}.png"
            altyazi_png(t, p)
            ay_png.append((p, a, b))

        args = ["ffmpeg", "-y", "-loglevel", "error"]
        for f in dosyalar:
            args += ["-stream_loop", "-1", "-ss", "0.5", "-i", str(f)]
        args += ["-i", str(mp3), "-i", str(katman)]
        for p, _, _ in ay_png:
            args += ["-i", str(p)]
        nk = len(dosyalar)
        parca = dur / nk
        odak = s.get("x", 0.5)  # yatay kırpma noktası (0 = sol, 1 = sağ)
        odaklar = odak if isinstance(odak, list) else [odak] * nk
        fc = []
        for k in range(nk):
            fc.append(f"[{k}:v]trim=0:{parca:.3f},setpts=PTS-STARTPTS,"
                      f"scale=1080:1920:force_original_aspect_ratio=increase,"
                      f"crop=1080:1920:(iw-1080)*{odaklar[k]}:0,setsar=1,fps=30,"
                      f"eq=saturation=1.08:contrast=1.04[k{k}]")
        fc.append("".join(f"[k{k}]" for k in range(nk)) + f"concat=n={nk}:v=1:a=0[v0]")
        fc.append(f"[v0][{nk + 1}:v]overlay=0:0[v1]")
        son = "v1"
        for j, (_, a, b) in enumerate(ay_png):
            yeni = f"v{j + 2}"
            fc.append(f"[{son}][{nk + 2 + j}:v]overlay=0:0:enable='between(t,{a:.3f},{b:.3f})'[{yeni}]")
            son = yeni
        mp4 = tmp / f"s{i}.mp4"
        args += ["-filter_complex", ";".join(fc), "-map", f"[{son}]", "-map", f"{nk}:a",
                 "-af", "apad", "-t", f"{dur:.3f}",
                 # ChatPlace video sınırı 20 MB -> bit hızını sınırla (~60 sn'ye kadar sığar)
                 "-c:v", "libx264", "-preset", "medium", "-crf", "21", "-maxrate", "2500k",
                 "-bufsize", "5000k", "-pix_fmt", "yuv420p", "-r", "30",
                 "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2", str(mp4)]
        subprocess.run(args, check=True)
        parcalar.append(mp4)
        print(f"  sahne {i}: {dur:.1f} sn")

    liste = tmp / "liste.txt"
    liste.write_text("".join(f"file '{p.name}'\n" for p in parcalar), encoding="utf-8")
    final = out / "reel.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(liste),
                    "-c", "copy", "-movflags", "+faststart", str(final)], check=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", "1.2", "-i", str(final), "-frames:v", "1",
                    "-q:v", "2", str(out / "reel_kapak.jpg")], check=True)
    shutil.rmtree(tmp, ignore_errors=True)
    return final


def main():
    klasor = Path(sys.argv[1]).resolve()
    spec = json.loads((klasor / "icerik.json").read_text(encoding="utf-8"))
    handle = spec.get("hesap", "gecirgenbagirsak")
    for eski in list(klasor.glob("karusel_*.png")):
        eski.unlink()
    if "karusel" in spec:
        n = karusel(spec["karusel"], klasor, handle)
        (klasor / "karusel_aciklama.txt").write_text(spec["karusel"]["aciklama"], encoding="utf-8")
        print(f"karusel: {n} slayt")
    if "reel" in spec:
        f = reel(spec["reel"], klasor, handle)
        (klasor / "reel_aciklama.txt").write_text(spec["reel"]["aciklama"], encoding="utf-8")
        print(f"reel: {f.name} {sure(f):.1f} sn, {f.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
