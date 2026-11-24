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
    return iletisim_ekle(metin.replace("<", "").replace(">", "")[:4600])


WHATSAPP = "https://wa.me/905078784881"
ILETISIM_UST = ("📲 Siz de kendi e-ticaret işinizi başlatmak ve daha fazla bilgi almak için "
                "benimle WhatsApp'tan iletişime geçebilirsiniz:\n👉 " + WHATSAPP)
ILETISIM_ALT = "💬 WhatsApp ile iletişim: " + WHATSAPP


def iletisim_ekle(metin):
    """Açıklamaya WhatsApp iletişim bloğunu ekler: ilk paragraftan sonra (önizlemede görünür) ve
    etiket satırından önce. Zaten ekliyse dokunmaz; eski kuyruk kayıtlarına yükleme anında uygulanır."""
    metin = (metin or "").strip()
    if "wa.me/905078784881" in metin:
        return metin
    ilk, _, kalan = metin.partition("\n\n")
    if len(metin) > 4600:                       # YouTube 5000 karakter sınırı: blok için yer aç
        kalan = kalan[: max(0, 4600 - len(ilk))]
    satirlar = kalan.rstrip().split("\n") if kalan else []
    etiket = satirlar.pop() if satirlar and satirlar[-1].lstrip().startswith("#") else ""
    govde = "\n".join(satirlar).rstrip()
    parca = [ilk, ILETISIM_UST]
    if govde:
        parca.append(govde + "\n" + ILETISIM_ALT)
    if etiket:
        parca.append(etiket)
    return "\n\n".join(parca)


def youtube_etiketler(kaynak_etiketler, kanal):
    k = KANALLAR[kanal]
    out, toplam = [], 0
    for t in k["anahtar_kelime"] + list(kaynak_etiketler or []):
        t = t.strip()
        if t and t.lower() not in [o.lower() for o in out] and toplam + len(t) < 450:
            out.append(t)
            toplam += len(t) + 1
    return out


# ---------------------------------------------------------------- kapak (premium konsept, v2)
# Uzun video: 1920x1080 (16:9).  Shorts / dikey video: 1080x1920 (9:16).
# Gidersiz  -> "Gece & Altın": lacivert panel, altın vurgu kelime, altın çizgi; görsel SAĞDA.
# Anahtar   -> "Mürdüm & Magenta": mürdüm panel, magenta vurgu bandı, beyaz yazı; görsel SOLDA.
# Kare seçimi: videonun farklı anlarından 9 kare alınır, en net + en iyi pozlanmış olan seçilir.
from PIL import ImageEnhance, ImageStat


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



KAPAK_STIL = {
    "gidersiz": {"koyu": (6, 14, 36), "orta": (14, 38, 84), "vurgu": (255, 200, 40), "vurgu_yazi": (6, 14, 36),
                 "bant": False, "gorsel": "sag", "slogan": "STOKSUZ  •  DEPOSUZ  •  GİDERSİZ"},
    "anahtar": {"koyu": (28, 6, 40), "orta": (86, 10, 86), "vurgu": (226, 0, 122), "vurgu_yazi": (255, 255, 255),
                "bant": True, "gorsel": "sol", "slogan": "HAZIR ALTYAPI  •  KENDİ MAĞAZAN"},
}
VURGU_KELIME = re.compile(
    r"e-?ticaret|emekli|gelir|kazan|kendi|işini|patron|maaş|stoksuz|gidersiz|masrafsız|mağaza|başla|"
    r"yaşında|hayal|özgür|sermaye|evden|ek\b|para|\d+", re.I)


def _video_sure(video):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", video],
                         capture_output=True, text=True).stdout.strip()
    try:
        return float(out)
    except ValueError:
        return 10.0


def _kare_puani(im):
    k = im.convert("L").resize((320, int(320 * im.height / im.width)))
    netlik = ImageStat.Stat(k.filter(ImageFilter.FIND_EDGES)).var[0]
    parlak = ImageStat.Stat(k).mean[0]
    poz = 1.0 - min(abs(parlak - 120) / 120, 0.9)        # çok karanlık / patlamış kareyi cezalandır
    kontrast = min(ImageStat.Stat(k).stddev[0] / 55, 1.2)
    return netlik * poz * kontrast


def en_iyi_kare(video, gecici):
    """Videonun %12-%82 arasından 9 kare alır, en net ve iyi pozlanmış kareyi döndürür."""
    sure = _video_sure(video)
    adaylar = []
    for i, oran in enumerate([0.12, 0.2, 0.28, 0.36, 0.44, 0.52, 0.6, 0.7, 0.82]):
        yol = f"{gecici}.{i}.png"
        r = subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-ss", f"{max(0.5, sure * oran):.2f}", "-i", video,
                            "-frames:v", "1", yol])
        if r.returncode == 0 and os.path.exists(yol):
            im = Image.open(yol).convert("RGB")
            adaylar.append((_kare_puani(im), im))
            os.remove(yol)
    if not adaylar:
        raise RuntimeError("videodan kare alınamadı")
    return max(adaylar, key=lambda x: x[0])[1]


def _rotus(im):
    im = ImageEnhance.Contrast(im).enhance(1.10)
    im = ImageEnhance.Color(im).enhance(1.12)
    return im.filter(ImageFilter.UnsharpMask(radius=2.2, percent=90, threshold=2))


def _kapla(im, w, h, dikey_kay=0.4):
    """Görseli w x h alanı tamamen kaplayacak şekilde ölçekler ve kırpar (yüz genelde üst-ortada)."""
    o = max(w / im.width, h / im.height)
    im = im.resize((max(w, round(im.width * o)), max(h, round(im.height * o))), Image.LANCZOS)
    x0 = (im.width - w) // 2
    y0 = int((im.height - h) * dikey_kay)
    return im.crop((x0, y0, x0 + w, y0 + h))


def _degrade(w, h, c1, c2, yatay=True):
    a = Image.new("RGB", (2, 1) if yatay else (1, 2))
    a.putpixel((0, 0), c1)
    a.putpixel((1, 0) if yatay else (0, 1), c2)
    return a.resize((w, h), Image.BILINEAR)


def _maske_cizgisel(w, h, bas, son, yon="sag"):
    """yon='sag': x<bas tam opak(255) -> x>son tam saydam; 'sol' tersini yapar. 'asagi' dikey."""
    m = Image.new("L", (w, h))
    d = ImageDraw.Draw(m)
    eksen = h if yon in ("asagi", "yukari") else w
    for i in range(eksen):
        t = 0 if i <= bas else (1 if i >= son else (i - bas) / (son - bas))
        t = t * t * (3 - 2 * t)                           # yumuşak geçiş
        v = int(255 * (1 - t)) if yon in ("sag", "yukari") else int(255 * t)
        if yon in ("asagi", "yukari"):
            d.line([(0, i), (w, i)], fill=v)
        else:
            d.line([(i, 0), (i, h)], fill=v)
    return m


def _vinyet(img, guc=0.55):
    w, h = img.size
    m = Image.new("L", (w // 8, h // 8), 0)
    ImageDraw.Draw(m).ellipse((-w // 40, -h // 40, w // 8 + w // 40, h // 8 + h // 40), fill=255)
    m = m.filter(ImageFilter.GaussianBlur(w // 60)).resize((w, h), Image.BILINEAR)
    koyu = Image.new("RGB", (w, h), (0, 0, 0))
    karisim = Image.composite(img, koyu, m)
    return Image.blend(img, karisim, guc)


def _golgeli_yazi(img, xy, metin, font, renk, golge=0.65, bulanik=10, kaydir=(0, 6)):
    w, h = img.size
    katman = Image.new("L", (w, h), 0)
    ImageDraw.Draw(katman).text((xy[0] + kaydir[0], xy[1] + kaydir[1]), metin, font=font, fill=int(255 * golge))
    katman = katman.filter(ImageFilter.GaussianBlur(bulanik))
    img.paste((0, 0, 0), (0, 0), katman)
    ImageDraw.Draw(img).text(xy, metin, font=font, fill=renk)


def _bas_ve_alt(baslik):
    t = baslik_temizle(baslik)
    t = re.sub(r"[\U0001F000-\U0001FAFF☀-➿️]", "", t).strip()   # emoji kapakta kutu çıkarır
    parca = [p.strip(" -–:") for p in re.split(r"\s*[|｜]\s*", t) if p.strip(" -–:")]
    ana = parca[0] if parca else t
    alt = parca[1] if len(parca) > 1 else ""
    if len(ana) > 70:                                     # çok uzun: noktalama ya da kelime sınırından kes
        m = re.match(r"(.{25,70}?[?!.:,])\s", ana + " ")
        ana = m.group(1).rstrip(",:") if m else ana[:70].rsplit(" ", 1)[0] + "…"
    return ana, alt[:60]


def _vurgu_indeksi(kelimeler):
    for i, w in enumerate(kelimeler):
        if VURGU_KELIME.search(w):
            return i
    uz = max(range(len(kelimeler)), key=lambda i: len(kelimeler[i])) if kelimeler else -1
    return uz


def _baslik_yerlesim(d, metin, gen, boylar, max_satir):
    kel = tr_upper(metin).split()
    for boy in boylar:
        f = _font("Poppins-Black.ttf", boy)
        sat = satirla(d, " ".join(kel), f, gen)
        if len(sat) <= max_satir:
            return f, boy, sat
    f = _font("Poppins-Black.ttf", boylar[-1])
    sat = satirla(d, " ".join(kel), f, gen)[:max_satir]
    sat[-1] = sat[-1].rstrip(" ,.") + "…"
    return f, boylar[-1], sat


def _baslik_ciz(img, x, y, satirlar, font, boy, st, hiza="sol", gen=None):
    """Satırları çizer; vurgu kelimesi altın (gidersiz) ya da magenta bant (anahtar) olur."""
    d = ImageDraw.Draw(img)
    tum = " ".join(satirlar).split()
    vi = _vurgu_indeksi(tum)
    adim = int(boy * 1.08)
    sayac = 0
    for s in satirlar:
        kel = s.split()
        bosluk = d.textlength(" ", font=font)
        toplam = d.textlength(s, font=font)
        cx = x if hiza == "sol" else (x + gen - toplam if hiza == "sag" else x + (gen - toplam) / 2)
        for w in kel:
            ww = d.textlength(w, font=font)
            vurgulu = sayac == vi
            if vurgulu and st["bant"]:
                pad = int(boy * 0.16)
                ust = y + int(boy * 0.12)
                d.rounded_rectangle((cx - pad, ust, cx + ww + pad, ust + int(boy * 1.02)), radius=int(boy * 0.16),
                                    fill=st["vurgu"])
                d.text((cx, y), w, font=font, fill=st["vurgu_yazi"])
            elif vurgulu:
                _golgeli_yazi(img, (cx, y), w, font, st["vurgu"])
            else:
                _golgeli_yazi(img, (cx, y), w, font, (255, 255, 255))
            d = ImageDraw.Draw(img)
            cx += ww + bosluk
            sayac += 1
        y += adim
    return y


def _rozet(img, x, y, metin, st, boy, sag_hiza=False):
    d = ImageDraw.Draw(img)
    f = _font("Poppins-SemiBold.ttf", boy)
    tw = d.textlength(metin, font=f)
    ph, pw = int(boy * 0.55), int(boy * 0.9)
    nokta = int(boy * 0.36)
    yazi_x = pw * 0.6 + nokta + boy * 0.45
    gen, yuk = int(yazi_x + tw + pw), boy + 2 * ph
    if sag_hiza:
        x = x - gen
    # cam efekti: arkası hafif bulanık + yarı saydam koyu, ince vurgu kenarlığı
    bolge = img.crop((int(x), int(y), int(x + gen), int(y + yuk))).filter(ImageFilter.GaussianBlur(12))
    koyu = Image.new("RGB", bolge.size, st["koyu"])
    bolge = Image.blend(bolge, koyu, 0.55)
    m = Image.new("L", bolge.size, 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, gen - 1, yuk - 1), radius=yuk // 2, fill=255)
    img.paste(bolge, (int(x), int(y)), m)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((x, y, x + gen, y + yuk), radius=yuk // 2, outline=st["vurgu"], width=max(2, boy // 12))
    d.ellipse((x + pw * 0.6, y + yuk / 2 - nokta / 2, x + pw * 0.6 + nokta, y + yuk / 2 + nokta / 2), fill=st["vurgu"])
    d.text((x + yazi_x, y + ph - boy * 0.12), metin, font=f, fill=(255, 255, 255))
    return gen, yuk


def _kaydet(img, hedef):
    for q in (93, 90, 86, 82):
        img.save(hedef, "JPEG", quality=q, optimize=True, progressive=True, subsampling=0)
        if os.path.getsize(hedef) < 1_900_000:          # YouTube kapak sınırı 2 MB
            break
    return hedef


def _kapak_yatay(kare, baslik, kanal):
    st, k = KAPAK_STIL[kanal], KANALLAR[kanal]
    W, H = 1920, 1080
    gorsel_w = 1180
    foto = _rotus(_kapla(kare, gorsel_w, H, 0.35))
    zemin = _degrade(W, H, st["koyu"], st["orta"]) if st["gorsel"] == "sag" else _degrade(W, H, st["orta"], st["koyu"])
    # zemine fotoğrafın bulanık hâli: panel düz renk görünmesin, derinlik kazansın
    bul = _kapla(kare, W, H, 0.35).filter(ImageFilter.GaussianBlur(40))
    zemin = Image.blend(zemin, bul, 0.18)
    img = zemin.copy()
    if st["gorsel"] == "sag":
        gx = W - gorsel_w
        maske = _maske_cizgisel(gorsel_w, H, 0, 360, "sol")      # sol kenarı yumuşak eriyor
        metin_x, metin_gen, hiza = 96, 860, "sol"
    else:
        gx = 0
        maske = _maske_cizgisel(gorsel_w, H, gorsel_w - 360, gorsel_w, "sag")
        metin_x, metin_gen, hiza = W - 96 - 860, 860, "sag"
    img.paste(foto, (gx, 0), maske)
    # yazı tarafına ek koyu panel: videodaki alt yazı / logo kalıntıları başlığa karışmasın
    if st["gorsel"] == "sag":
        panel = _maske_cizgisel(W, H, 900, 1320, "sag")
    else:
        panel = _maske_cizgisel(W, H, W - 1320, W - 900, "sol")
    img.paste(st["koyu"], (0, 0), panel.point(lambda v: int(v * 0.94)))
    img = _vinyet(img, 0.5)
    # altta koyuluk: yazı/slogan okunaklı kalsın, videodaki alt yazılar silikleşsin
    alt = _maske_cizgisel(W, H, int(H * 0.66), H, "asagi")
    img.paste(st["koyu"], (0, 0), alt.point(lambda v: int(v * 0.88)))
    d = ImageDraw.Draw(img)
    ana, alt_baslik = _bas_ve_alt(baslik)
    font, boy, satirlar = _baslik_yerlesim(d, ana, metin_gen, (124, 112, 102, 94, 86, 78, 70), 4)
    blok = len(satirlar) * int(boy * 1.08) + (70 if alt_baslik else 0)
    y = max(190, (H - blok) // 2 - 10)
    y = _baslik_ciz(img, metin_x, y, satirlar, font, boy, st, hiza, metin_gen)
    d = ImageDraw.Draw(img)
    cizgi_x = metin_x if hiza == "sol" else metin_x + metin_gen - 180
    d.rounded_rectangle((cizgi_x, y + 18, cizgi_x + 180, y + 30), radius=6, fill=st["vurgu"])
    if alt_baslik:
        af = _font("Poppins-SemiBold.ttf", 46)
        alt_baslik = satirla(d, alt_baslik, af, metin_gen)[0]
        aw = d.textlength(alt_baslik, font=af)
        ax = metin_x if hiza == "sol" else metin_x + metin_gen - aw
        _golgeli_yazi(img, (ax, y + 52), alt_baslik, af, (235, 235, 245), 0.6, 8, (0, 3))
    # rozet: kanal adı
    if hiza == "sol":
        _rozet(img, metin_x, 78, tr_upper(k["ad"]), st, 38)
    else:
        _rozet(img, W - 96, 78, tr_upper(k["ad"]), st, 38, sag_hiza=True)
    # slogan
    d = ImageDraw.Draw(img)
    sf = _font("Poppins-SemiBold.ttf", 30)
    sw = d.textlength(st["slogan"], font=sf)
    sx = metin_x if hiza == "sol" else W - 96 - sw
    d.text((sx, H - 92), st["slogan"], font=sf, fill=(*st["vurgu"],) if kanal == "gidersiz" else (255, 255, 255))
    return img


def _kapak_dikey(kare, baslik, kanal):
    st, k = KAPAK_STIL[kanal], KANALLAR[kanal]
    W, H = 1080, 1920
    img = _rotus(_kapla(kare, W, H, 0.3))
    img = _vinyet(img, 0.45)
    # alt yarı: kanal renginde koyu degrade (yazı alanı)
    alt = _maske_cizgisel(W, H, int(H * 0.40), int(H * 0.78), "asagi")
    img.paste(st["koyu"], (0, 0), alt.point(lambda v: int(v * 0.94)))
    ust = _maske_cizgisel(W, H, 0, int(H * 0.16), "yukari")
    img.paste(st["koyu"], (0, 0), ust.point(lambda v: int(v * 0.55)))
    d = ImageDraw.Draw(img)
    ana, alt_baslik = _bas_ve_alt(baslik)
    gen = W - 2 * 80
    font, boy, satirlar = _baslik_yerlesim(d, ana, gen, (118, 106, 96, 88, 80, 72), 5)
    blok = len(satirlar) * int(boy * 1.08)
    y = H - 330 - blok
    hiza = "sol" if kanal == "gidersiz" else "orta"
    y = _baslik_ciz(img, 80, y, satirlar, font, boy, st, hiza, gen)
    d = ImageDraw.Draw(img)
    cx = 80 if hiza == "sol" else (W - 200) // 2
    d.rounded_rectangle((cx, y + 20, cx + 200, y + 34), radius=7, fill=st["vurgu"])
    sf = _font("Poppins-SemiBold.ttf", 34)
    sw = d.textlength(st["slogan"], font=sf)
    d.text((80 if hiza == "sol" else (W - sw) / 2, H - 170), st["slogan"], font=sf,
           fill=st["vurgu"] if kanal == "gidersiz" else (255, 255, 255))
    rf = 40
    if hiza == "sol":
        _rozet(img, 80, 120, tr_upper(k["ad"]), st, rf)
    else:
        f = _font("Poppins-SemiBold.ttf", rf)
        tw = ImageDraw.Draw(img).textlength(tr_upper(k["ad"]), font=f)
        gen = rf * 0.9 * 0.6 + int(rf * 0.36) + rf * 0.45 + tw + int(rf * 0.9)
        _rozet(img, (W - gen) / 2, 120, tr_upper(k["ad"]), st, rf)
    return img


def kapak(video, baslik, kanal, hedef, dikey=None):
    """Premium kapak üretir. dikey=None ise videonun yönüne göre karar verilir
    (dikey video / Shorts -> 1080x1920, yatay -> 1920x1080)."""
    kare = en_iyi_kare(video, hedef + ".kare")
    if dikey is None:
        dikey = kare.height > kare.width
    img = _kapak_dikey(kare, baslik, kanal) if dikey else _kapak_yatay(kare, baslik, kanal)
    return _kaydet(img, hedef)
