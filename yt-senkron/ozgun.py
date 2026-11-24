"""Her YouTube kanalı için özgün başlık, açıklama, etiket ve kapak üretir (yapay zekâ gerektirmez).

Kaynak videonun başlık/açıklamasını kanalın kendi diline, yapısına ve görsel kimliğine çevirir:
- başlık: kaynak başlığı temizlenir, büyük harfler düzeltilir, kanala özgü son ek eklenir
- açıklama: kanala özgü giriş cümlesi + kaynaktaki ana fikirler madde madde + kanala özgü kapanış + etiketler
- kapak: videodan bir kare + kanalın renkleri, logosu ve başlık yazısı
"""
import hashlib
import os
import re
import subprocess

from PIL import Image, ImageDraw, ImageFilter, ImageFont

KOK = os.path.dirname(os.path.abspath(__file__))
FONT = os.path.join(KOK, "..", "motor", "fonts")

KANALLAR = {
    "gidersiz": {
        "ad": "Gidersiz E-Ticaret",
        "renk1": (12, 28, 64), "renk2": (0, 168, 150), "vurgu": (255, 196, 0),
        "girisler": [
            "Gidersiz e-ticaretin mantığını merak ediyorsan bu video tam sana göre.",
            "Stok, depo ve kira gideri olmadan e-ticaret mümkün mü? Bu videoda bir örneğini izliyorsun.",
            "Ek gelir arayanlar için gerçek bir deneyimden notlar.",
            "Masrafsız bir iş modeline adım atmadan önce bu anlatımı mutlaka dinle.",
            "Kendi işini düşük maliyetle kurmak isteyenler için kısa ama net bir anlatım.",
            "E-ticarete başlamadan önce sorulması gereken soruların cevabı bu videoda.",
            "Evden, kendi zamanını yöneterek çalışmak isteyenler için ilham veren bir paylaşım.",
            "Gidersiz bir başlangıç nasıl olur? Bu videoda adım adım dinliyorsun.",
        ],
        "kapanis": ("Gidersiz E-Ticaret kanalında; stok tutmadan, depo ve personel gideri olmadan "
                    "e-ticarete başlamak isteyenler için gerçek hikâyeler ve uygulanabilir bilgiler paylaşıyoruz.\n"
                    "Yeni videoları kaçırmamak için abone ol, bildirimleri aç.\n"
                    "Detaylı bilgi: https://www.anahtarteslimeticaret.com.tr"),
        "etiketler": ["#gidersizeticaret", "#eticaret", "#stoksuzeticaret", "#ekgelir", "#evdenkazanç",
                      "#kendiişinikur", "#onlinekazanç", "#girişimcilik", "#dijitalgelir", "#eticaretbaşlangıç"],
        "anahtar_kelime": ["gidersiz e-ticaret", "masrafsız e-ticaret", "stoksuz e-ticaret", "ek gelir",
                           "evden e-ticaret", "e-ticarete başlamak", "online iş", "kendi işini kurmak"],
    },
    "anahtar": {
        "ad": "Anahtar Teslim E-ticaret",
        "renk1": (48, 12, 70), "renk2": (190, 0, 110), "vurgu": (255, 255, 255),
        "girisler": [
            "Anahtar teslim bir e-ticaret mağazasıyla neler mümkün? Bu videoda anlatıyoruz.",
            "Hazır altyapıyla e-ticarete başlamak isteyenler için bu videoyu hazırladık.",
            "Kendi mağazanı kurmayı düşünüyorsan önce bu videoyu izle.",
            "E-ticarette doğru başlangıcın ipuçları bu videoda.",
            "Mağaza sahiplerimizin deneyimlerinden öne çıkanlar.",
            "Stoksuz e-ticaret modelini merak edenler için net bir anlatım.",
        ],
        "kapanis": ("Anahtar Teslim E-ticaret kanalında, hazır altyapıyla kendi e-ticaret mağazasını kurmak "
                    "isteyenler için eğitimler, deneyimler ve duyurular paylaşıyoruz.\n"
                    "Abone olmayı ve bildirimleri açmayı unutma.\n"
                    "Detaylı bilgi: https://www.anahtarteslimeticaret.com.tr"),
        "etiketler": ["#anahtarteslimeticaret", "#eticaret", "#stoksuzeticaret", "#magazanolsun",
                      "#eticaretsitesi", "#kendiişinikur", "#ekgelir", "#dropshipping"],
        "anahtar_kelime": ["anahtar teslim e-ticaret", "hazır e-ticaret sitesi", "stoksuz e-ticaret",
                           "e-ticaret mağazası", "mağazanolsun", "e-ticaret nasıl yapılır"],
    },
}

KUCUK = str.maketrans("IİÇĞÖŞÜ", "ıiçğöşü")


def tr_upper(s):
    return s.replace("i", "İ").replace("ı", "I").upper()


def tr_lower(s):
    return s.translate(KUCUK).lower()


def tohum(*parca):
    return int(hashlib.md5("|".join(parca).encode()).hexdigest(), 16)


def baslik_temizle(t):
    t = re.sub(r"#\S+", "", t or "")
    t = re.sub(r"\s*[|｜]\s*(Anahtar Teslim|Mağazanolsun|Gidersiz|Ege I[ŞS]IK).*$", "", t, flags=re.I)
    t = re.sub(r"\s+", " ", t).strip(" -|,")
    harfler = [c for c in t if c.isalpha()]
    if harfler and sum(c.isupper() for c in harfler) / len(harfler) > 0.7:   # TAMAMI BÜYÜK -> cümle düzeni
        k = tr_lower(t)
        t = k[:1].replace("i", "İ").upper() + k[1:]
        t = re.sub(r"([.!?]\s+)(\w)", lambda m: m.group(1) + m.group(2).upper(), t)
        for ozel in ["Mağazanolsun", "E-ticaret", "Instagram", "WhatsApp", "Trendyol", "Türkiye"]:
            t = re.sub(re.escape(tr_lower(ozel)), ozel, t, flags=re.I)
    return t


def youtube_baslik(kaynak_baslik, kanal, short=False):
    k = KANALLAR[kanal]
    t = baslik_temizle(kaynak_baslik)
    ek = f" | {k['ad']}"
    if short:
        ek = " #shorts"
    return kisalt(t, 100 - len(ek)) + ek


def kisalt(t, sinir):
    """Başlığı sınıra sığdırır: önce ' | ' sonrası ek bölümleri atar, sonra kelime sınırından keser."""
    if len(t) <= sinir:
        return t
    parca = [p.strip() for p in t.split("|") if p.strip()]
    while len(parca) > 1 and len(" | ".join(parca)) > sinir:
        parca.pop()
    t = " | ".join(parca)
    if len(t) > sinir:
        t = t[:sinir].rsplit(" ", 1)[0]
    return t.rstrip(" ,.-|:")


def cumleler(aciklama):
    """Kaynak açıklamadan link/etiket/iletişim dışındaki anlamlı cümleleri çıkarır."""
    satirlar = []
    for s in (aciklama or "").splitlines():
        s = s.strip(" \t•-–►🔼📌✅")
        if not s or s.startswith("#") or "http" in s or re.search(r"\d{3}[\s-]?\d{3}[\s-]?\d{2}", s):
            continue
        if re.fullmatch(r"[-_=─]+", s):
            continue
        s = re.sub(r"#\S+", "", s).strip()
        if len(s) >= 25:
            satirlar.append(s)
    return satirlar


def linkler(aciklama):
    return [l for l in re.findall(r"https?://\S+", aciklama or "") if "magazanolsun.com" in l or "anahtarteslim" in l][:3]


def youtube_aciklama(kaynak_baslik, kaynak_aciklama, kanal, vid=""):
    k = KANALLAR[kanal]
    r = tohum(vid, kanal)
    giris = k["girisler"][r % len(k["girisler"])]
    cs = cumleler(kaynak_aciklama)
    # ilk cümle başlığın tekrarıysa at
    if cs and tr_lower(cs[0])[:30] == tr_lower(baslik_temizle(kaynak_baslik))[:30]:
        cs = cs[1:]
    ozet = cs[:6]
    parcalar = [giris, ""]
    if ozet:
        parcalar.append("Videoda öne çıkanlar:")
        parcalar += [f"▸ {c}" for c in ozet]
        parcalar.append("")
    for l in linkler(kaynak_aciklama):
        parcalar.append(f"🔗 {l}")
    if linkler(kaynak_aciklama):
        parcalar.append("")
    parcalar.append(k["kapanis"])
    parcalar.append("")
    et = k["etiketler"][:]
    bas = r % len(et)
    secili = (et[bas:] + et[:bas])[:6]
    parcalar.append(" ".join(secili))
    metin = "\n".join(parcalar)
    return metin.replace("<", "").replace(">", "")[:4900]


def youtube_etiketler(kaynak_etiketler, kanal):
    k = KANALLAR[kanal]
    out, toplam = [], 0
    for t in k["anahtar_kelime"] + list(kaynak_etiketler or []):
        t = t.strip()
        if t and t.lower() not in [o.lower() for o in out] and toplam + len(t) < 450:
            out.append(t)
            toplam += len(t) + 1
    return out


# ---------------------------------------------------------------- kapak
def _font(ad, boyut):
    return ImageFont.truetype(os.path.join(FONT, ad), boyut)


def kare_al(video, hedef, oran=0.35):
    sure = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", video],
                                capture_output=True, text=True).stdout.strip() or 10)
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-ss", str(max(1, sure * oran)), "-i", video,
                    "-frames:v", "1", hedef], check=True)


def satirla(d, metin, font, genislik):
    kelimeler, satirlar, sat = metin.split(), [], ""
    for w in kelimeler:
        dene = (sat + " " + w).strip()
        if d.textlength(dene, font=font) <= genislik:
            sat = dene
        else:
            if sat:
                satirlar.append(sat)
            sat = w
    if sat:
        satirlar.append(sat)
    return satirlar


# Premium kapak (Full HD 1920x1080) --------------------------------------------
KAPAK_W, KAPAK_H = 1920, 1080
KAPAK_TEMA = {
    "gidersiz": {"zemin": (7, 16, 36), "zemin2": (12, 34, 74), "parilti": (0, 168, 150),
                 "vurgu": (255, 196, 0), "vurgu_yazi": (10, 18, 40),
                 "slogan": ("STOK YOK", "DEPO YOK", "KİRA YOK"), "cta": "ŞİMDİ İZLE"},
    "anahtar": {"zemin": (24, 6, 38), "zemin2": (60, 12, 82), "parilti": (190, 0, 110),
                "vurgu": (255, 255, 255), "vurgu_yazi": (60, 12, 82),
                "slogan": ("HAZIR MAĞAZA", "TEDARİKÇİ", "DESTEK"), "cta": "ŞİMDİ İZLE"},
}
VURGU_KELIME = re.compile(
    r"^(\d[\d.,/%]*\S*|e-?ticaret\w*|kazan\w*|gelir\w*|para\w*|ücretsiz\w*|stoksuz\w*|gidersiz\w*|masrafsız\w*|"
    r"sermaye\w*|maaş\w*|emeklilik\w*|evden|evde|kendi|işini|işinizi|patron\w*|özgürlü\w*|ai|yapay|whatsapp|"
    r"satış\w*|mağaza\w*|nasıl|neden|gerçek\w*|sır\w*|hata\w*|yeni)$", re.I)


def kapak_metni(baslik):
    """Uzun başlıktan kapak için kısa, vurucu bir cümle çıkarır (en çok ~55 karakter)."""
    t = baslik_temizle(baslik)
    t = re.sub(r"[“”\"«»]", "", t).strip()
    t = t.split("|")[0].strip()
    if "?" in t[:70]:
        t = t[:t.index("?") + 1]
    if len(t) > 55:
        for ayrac in (":", " – ", " - ", ". ", "! ", ", "):
            if ayrac in t and 12 <= t.index(ayrac) <= 55:
                t = t[:t.index(ayrac) + (1 if ayrac.strip() in "!" else 0)]
                break
    if len(t) > 55:
        t = t[:55].rsplit(" ", 1)[0]
    t = t.rstrip(" ,.-:…")
    return t[:1].upper() + t[1:] if t else "Gidersiz E-Ticaret"


def _yuzler(im):
    """OpenCV varsa yüzleri bulur: [(x, y, w, h), ...]; yoksa boş liste."""
    try:
        import cv2
        import numpy as np
        cv2.CascadeClassifier
    except (ImportError, AttributeError):
        return []
    g = cv2.cvtColor(np.asarray(im), cv2.COLOR_RGB2GRAY)
    sinif = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    en_kucuk = max(40, int(min(g.shape) * 0.08))
    goz = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_eye.xml")
    out = []
    for x, y, w, h in sinif.detectMultiScale(g, 1.1, 6, minSize=(en_kucuk, en_kucuk)):
        ust_yuz = g[y:y + h // 2 + h // 8, x:x + w]
        acik = len(goz.detectMultiScale(ust_yuz, 1.1, 5, minSize=(max(8, w // 10), max(8, w // 10))))
        out.append((int(x), int(y), int(w), int(h), min(acik, 2)))
    return out


def _kenar_kirp(im, esik=32):
    """Kayıtlardaki siyah çerçeveleri (letterbox/pillarbox) atar."""
    import numpy as np
    g = np.asarray(im.convert("L"), np.float32)
    satir = np.where(g.mean(axis=1) > esik)[0]
    sutun = np.where(g.mean(axis=0) > esik)[0]
    if len(satir) < g.shape[0] * 0.3 or len(sutun) < g.shape[1] * 0.3:
        return im
    return im.crop((int(sutun[0]), int(satir[0]), int(sutun[-1]) + 1, int(satir[-1]) + 1))


def _kare_sec(video, adet=12):
    """Videodan birkaç kare alır; yüzü net görünen, iyi pozlanmış kareyi seçer -> (kare, odak_x, odak_y)."""
    import numpy as np
    sure = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", video],
                                capture_output=True, text=True).stdout.strip() or 10)
    en_iyi, puan_max = None, -1
    for i in range(adet):
        zaman = max(0.5, sure * (0.12 + 0.7 * i / max(1, adet - 1)))
        cik = subprocess.run(["ffmpeg", "-loglevel", "error", "-ss", f"{zaman:.2f}", "-i", video, "-frames:v", "1",
                              "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True)
        if not cik.stdout:
            continue
        import io
        im = _kenar_kirp(Image.open(io.BytesIO(cik.stdout)).convert("RGB"))
        g = np.asarray(im.convert("L").resize((320, int(320 * im.height / im.width))), dtype=np.float32)
        ust = g[: int(g.shape[0] * 0.75)]                         # alt yazıların olduğu kısım hariç
        net = (np.abs(np.diff(ust, axis=0)).mean() + np.abs(np.diff(ust, axis=1)).mean())
        parlak = ust.mean()
        puan = net * (1 - abs(parlak - 120) / 160) * (0.6 + 0.4 * ust.std() / 64)
        odak = (im.width / 2, im.height * 0.38, 0)
        yz = [y_ for y_ in _yuzler(im) if y_[1] + y_[3] < im.height * 0.75]
        if yz:
            fx, fy, fw, fh, acik = max(yz, key=lambda r: r[2] * r[3])
            odak = (fx + fw / 2, fy + fh / 2, fw)
            puan *= (2.5 + min(1.5, fw / im.width * 6)) * (1 + 0.6 * acik)   # büyük yüz, açık gözler
        if puan > puan_max:
            en_iyi, puan_max = (im, odak), puan
    if en_iyi is None:
        raise RuntimeError("videodan kare alınamadı")
    return en_iyi


def _renklendir(im):
    from PIL import ImageEnhance
    im = ImageEnhance.Contrast(im).enhance(1.12)
    im = ImageEnhance.Color(im).enhance(1.15)
    im = ImageEnhance.Brightness(im).enhance(1.04)
    return im.filter(ImageFilter.UnsharpMask(radius=2.2, percent=140, threshold=2))


def _radyal(boyut, merkez, yaricap, renk, guc):
    import numpy as np
    w, h = boyut
    yy, xx = np.mgrid[0:h, 0:w]
    m = np.clip(1 - np.hypot(xx - merkez[0], yy - merkez[1]) / yaricap, 0, 1) ** 2 * guc
    katman = Image.new("RGB", boyut, renk)
    return katman, Image.fromarray((m * 255).astype("uint8"), "L")


def _tik(d, x, y, boy, renk, kalin):
    d.line([(x, y + boy * 0.55), (x + boy * 0.38, y + boy * 0.9), (x + boy, y + boy * 0.1)],
           fill=renk, width=kalin, joint="curve")


def kapak(video, baslik, kanal, hedef):
    """Premium Full HD (1920x1080) YouTube kapağı.

    Solda kısa ve vurgulu başlık + marka + CTA butonu, sağda videodan seçilmiş en net kare
    (alt yazılar kırpılır), çapraz altın kesim, sinematik ışık ve derinlik.
    """
    import numpy as np
    k, tm = KANALLAR[kanal], KAPAK_TEMA[kanal]
    W, H = KAPAK_W, KAPAK_H

    # 1) zemin: koyu degrade + ışık hüzmeleri + ince ızgara + gren
    yy = np.linspace(0, 1, H)[:, None]
    xx = np.linspace(0, 1, W)[None, :]
    t = np.clip(0.65 * xx + 0.35 * yy, 0, 1)[..., None]
    z = np.array(tm["zemin"], np.float32) * (1 - t) + np.array(tm["zemin2"], np.float32) * t
    img = Image.fromarray(z.astype("uint8"), "RGB")
    for merkez, yaricap, renk, guc in (((1350, 380), 900, tm["parilti"], 0.55), ((150, 1050), 700, tm["vurgu"], 0.10)):
        kat, m = _radyal((W, H), merkez, yaricap, renk, guc)
        img = Image.composite(kat, img, m)
    d = ImageDraw.Draw(img, "RGBA")
    for x in range(-H, W, 64):
        d.line([(x, H), (x + H, 0)], fill=(255, 255, 255, 7), width=1)

    # 2) sağ fotoğraf paneli: çapraz kesim, sinematik renk, kenar kararması
    kare, (fx, fy, fw) = _kare_sec(video)
    if fw and fw < kare.width * 0.2:                              # küçük yüz (ör. ekran paylaşımlı kayıt): kameraya yaklaş
        g = np.asarray(kare.convert("L"), np.float32)
        bant_x = g[:, max(0, int(fx - fw)):int(fx + fw)]          # yüzün dikey şeridi
        bant_y = g[max(0, int(fy - fw)):int(fy + fw), :]          # yüzün yatay şeridi
        acik_s = bant_x.mean(axis=1) > 32
        acik_k = bant_y.mean(axis=0) > 32
        y0 = int(fy) - int(np.argmin(acik_s[int(fy)::-1])) if not acik_s[:int(fy)].all() else 0
        y1 = int(fy) + int(np.argmin(acik_s[int(fy):])) if not acik_s[int(fy):].all() else kare.height
        x0 = int(fx) - int(np.argmin(acik_k[int(fx)::-1])) if not acik_k[:int(fx)].all() else 0
        x1 = int(fx) + int(np.argmin(acik_k[int(fx):])) if not acik_k[int(fx):].all() else kare.width
        pay = max(4, int(fw * 0.08))                              # çerçeve kenarındaki geçişi de at
        x0, x1 = max(x0 + pay, int(fx - fw * 4)), min(x1 - pay, int(fx + fw * 4))
        y0, y1 = max(y0 + pay, int(fy - fw * 2.2)), min(y1 - pay, int(fy + fw * 3.5))
        if x1 - x0 > fw * 1.5 and y1 - y0 > fw * 1.5:
            kare, fx, fy = kare.crop((x0, y0, x1, y1)), fx - x0, fy - y0
    kare = _renklendir(kare)
    alt_kes = int(kare.height * (0.74 if kare.height > kare.width else 0.86))   # alt yazı bölgesini at
    kare = kare.crop((0, 0, kare.width, max(alt_kes, int(fy + kare.height * 0.2))))
    px0 = 1000                                                    # panelin sol üst köşesi
    pw = W - px0 + 200
    oran = max(pw / kare.width, H / kare.height) * 1.08           # hafif yakınlaştırma
    kare = kare.resize((int(kare.width * oran) + 1, int(kare.height * oran) + 1), Image.LANCZOS)
    fx, fy = fx * oran, fy * oran
    # yüz panelin görünen kısmının ortasına (çapraz kesimin sağına) gelsin
    hedef_x, hedef_y = (W - px0 + 200) * 0.58, H * 0.36
    cx = int(min(max(fx - hedef_x, 0), kare.width - pw))
    cy = int(min(max(fy - hedef_y, 0), kare.height - H))
    kare = kare.crop((cx, cy, cx + pw, cy + H))
    foto = Image.new("RGB", (W, H))
    foto.paste(kare, (px0 - 200, 0))
    # sol kenara doğru ve altta kararma (yazı okunurluğu + derinlik)
    kar = np.zeros((H, W), np.float32)
    gx = np.clip((np.arange(W) - (px0 - 120)) / 420, 0, 1)[None, :]
    kar += (1 - gx) * 0.85
    kar += np.clip((np.arange(H) - H * 0.62) / (H * 0.38), 0, 1)[:, None] * 0.45
    kar = np.clip(kar, 0, 0.92)
    foto_np = np.asarray(foto, np.float32) * (1 - kar[..., None]) + np.array(tm["zemin"], np.float32) * kar[..., None]
    foto = Image.fromarray(foto_np.astype("uint8"))
    maske = Image.new("L", (W, H), 0)
    ImageDraw.Draw(maske).polygon([(px0 + 160, 0), (W, 0), (W, H), (px0 - 160, H)], fill=255)
    maske = maske.filter(ImageFilter.GaussianBlur(1.2))
    img.paste(foto, (0, 0), maske)
    d = ImageDraw.Draw(img, "RGBA")
    # çapraz altın şerit + ince ikinci çizgi
    d.polygon([(px0 + 160, 0), (px0 + 182, 0), (px0 - 138, H), (px0 - 160, H)], fill=tm["vurgu"] + (255,))
    d.line([(px0 + 214, 0), (px0 - 106, H)], fill=tm["vurgu"] + (90,), width=3)

    # 3) marka satırı (sol üst)
    X = 96
    d.rounded_rectangle((X, 78, X + 74, 152), radius=18, fill=tm["vurgu"])
    d.polygon([(X + 27, 98), (X + 27, 132), (X + 56, 115)], fill=tm["vurgu_yazi"])   # oynat simgesi
    mf = _font("Poppins-Black.ttf", 40)
    d.text((X + 98, 82), tr_upper(k["ad"]), font=mf, fill=(255, 255, 255))
    sf = _font("Poppins-SemiBold.ttf", 23)
    d.text((X + 100, 128), "  •  ".join(tm["slogan"]), font=sf, fill=(255, 255, 255, 170))

    # 4) başlık: en fazla 4 satır, vurgu kelimeleri renkli kutuda
    metin = kapak_metni(baslik)
    kelimeler = metin.split()
    def _oncelik(w):
        w = tr_lower(w.strip("?!.,:;…'’"))
        if re.match(r"^\d", w):
            return 0
        if re.match(r"^(kazan|gelir|para|maaş|sermaye|ücretsiz|stoksuz|gidersiz|masrafsız|emeklilik|patron|özgür)", w):
            return 1
        if re.match(r"^(e-?ticaret|satış|mağaza|whatsapp|ai$|yapay|evden|evde|hata|sır|gerçek)", w):
            return 2
        return 9 if not VURGU_KELIME.match(w) else 5
    adaylar = sorted(range(len(kelimeler)), key=lambda i: (_oncelik(kelimeler[i]), i))
    vurgular = [adaylar[0]] if adaylar and _oncelik(kelimeler[adaylar[0]]) < 9 else [len(kelimeler) - 1]
    ust = 225

    def _gen(y_alt):                                              # satırın altındaki çapraz kesimden 60 px önce dur
        return (px0 + 160 - 320 * y_alt / H) - 60 - X

    def _diz(f, boy):
        satir_h = int(boy * 1.12)
        sat, cur = [], []
        for i in range(len(kelimeler)):
            dene = " ".join(kelimeler[j] for j in cur + [i]) + "  " * sum(j in vurgular for j in cur + [i])
            if cur and d.textlength(dene, font=f) > _gen(ust + (len(sat) + 1) * satir_h):
                sat.append(cur)
                cur = [i]
            else:
                cur.append(i)
        if cur:
            sat.append(cur)
        sigdi = all(d.textlength(" ".join(kelimeler[j] for j in s_) + "  " * sum(j in vurgular for j in s_), font=f)
                    <= _gen(ust + (n + 1) * satir_h) for n, s_ in enumerate(sat))
        return sat, sigdi and ust + len(sat) * satir_h <= 800

    for boy in (138, 128, 118, 108, 98, 90, 82, 74, 66):
        f = _font("Poppins-Black.ttf", boy)
        sat, tamam = _diz(f, boy)
        if tamam and len(sat) <= 4:
            break
    satir_h = int(boy * 1.12)
    y = ust
    bosluk = d.textlength(" ", font=f)
    for s_ in sat:
        x = X
        for j in s_:
            w = kelimeler[j]
            wl = d.textlength(w, font=f)
            if j in vurgular and x > X:
                x += 16
            if j in vurgular:
                d.rounded_rectangle((x - 14, y + boy * 0.12, x + wl + 14, y + boy * 1.10), radius=14,
                                    fill=tm["vurgu"])
                d.text((x, y - boy * 0.04), w, font=f, fill=tm["vurgu_yazi"])
            else:
                d.text((x + 5, y + 6), w, font=f, fill=(0, 0, 0, 150))
                d.text((x, y - boy * 0.04), w, font=f, fill=(255, 255, 255))
            x += wl + bosluk + (30 if j in vurgular else 0)
        y += satir_h
    d.rectangle((X, y + 18, X + 170, y + 30), fill=tm["vurgu"])

    # 5) CTA: ana buton + güven satırı (sağ alt köşe YouTube süre etiketine bırakılır)
    by, bh = 880, 112
    cf = _font("Poppins-Black.ttf", 46)
    cta = tm["cta"]
    bw = int(d.textlength(cta, font=cf)) + 170
    golge = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(golge).rounded_rectangle((X + 6, by + 14, X + bw + 6, by + bh + 14), radius=bh // 2,
                                            fill=(0, 0, 0, 140))
    img.paste(golge.filter(ImageFilter.GaussianBlur(14)), (0, 0), golge.filter(ImageFilter.GaussianBlur(14)))
    d = ImageDraw.Draw(img, "RGBA")
    d.rounded_rectangle((X, by, X + bw, by + bh), radius=bh // 2, fill=tm["vurgu"])
    d.ellipse((X + 16, by + 16, X + 16 + bh - 32, by + bh - 16), fill=tm["vurgu_yazi"])
    ox, oy = X + 16 + (bh - 32) // 2, by + bh // 2
    d.polygon([(ox - 11, oy - 18), (ox - 11, oy + 18), (ox + 19, oy)], fill=tm["vurgu"])
    d.text((X + bh + 8, by + bh // 2), cta, font=cf, fill=tm["vurgu_yazi"], anchor="lm")
    gx0 = X + bw + 44
    gf = _font("Poppins-SemiBold.ttf", 30)
    for i, sl in enumerate(tm["slogan"][:2]):
        yy_ = by + 14 + i * 46
        _tik(d, gx0, yy_ + 6, 26, tm["vurgu"], 6)
        d.text((gx0 + 42, yy_), sl.capitalize() if False else sl, font=gf, fill=(255, 255, 255))

    # 6) son dokunuş: hafif gren + vinyet
    gren = np.random.default_rng(tohum(baslik, kanal) % (2 ** 32)).normal(0, 4.5, (H, W, 1))
    son = np.asarray(img, np.float32) + gren
    vy = ((np.linspace(-1, 1, H)[:, None] ** 2) * 0.5 + (np.linspace(-1, 1, W)[None, :] ** 2) * 0.35)
    son *= (1 - np.clip(vy - 0.25, 0, 1) * 0.35)[..., None]
    img = Image.fromarray(np.clip(son, 0, 255).astype("uint8"))
    img.save(hedef, "JPEG", quality=92, optimize=True, progressive=True, subsampling=0)
    if os.path.getsize(hedef) > 1_900_000:                        # YouTube sınırı 2 MB
        img.save(hedef, "JPEG", quality=84, optimize=True, progressive=True)
    return hedef
