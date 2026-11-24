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


def kapak(video, baslik, kanal, hedef):
    """1280x720 özgün kapak: solda videodan kare, sağda kanal renginde başlık paneli."""
    k = KANALLAR[kanal]
    W, H = 1280, 720
    kare = hedef + ".kare.jpg"
    kare_al(video, kare)
    src = Image.open(kare).convert("RGB")
    os.remove(kare)
    # kareyi sola yerleştir (dikey videolarda yüz ortada kalır)
    sol_w = 620
    oran = max(sol_w / src.width, H / src.height)
    src = src.resize((int(src.width * oran), int(src.height * oran)))
    x0 = (src.width - sol_w) // 2
    y0 = max(0, (src.height - H) // 3)
    src = src.crop((x0, y0, x0 + sol_w, y0 + H))
    img = Image.new("RGB", (W, H), k["renk1"])
    # sağ panel degrade
    px = img.load()
    for x in range(W):
        t = x / W
        r = int(k["renk1"][0] + (k["renk2"][0] - k["renk1"][0]) * t)
        g = int(k["renk1"][1] + (k["renk2"][1] - k["renk1"][1]) * t)
        b = int(k["renk1"][2] + (k["renk2"][2] - k["renk1"][2]) * t)
        for y in range(H):
            px[x, y] = (r, g, b)
    # kareyi yumuşak kenarla bindir
    maske = Image.new("L", (sol_w, H), 255)
    md = ImageDraw.Draw(maske)
    for i in range(120):
        md.line([(sol_w - 120 + i, 0), (sol_w - 120 + i, H)], fill=int(255 * (1 - i / 120)))
    img.paste(src, (0, 0), maske)
    d = ImageDraw.Draw(img)
    # başlık
    x, gen = 600, W - 600 - 50
    metin = baslik_temizle(baslik)
    for boy in (78, 70, 62, 54, 48, 42):
        f = _font("Poppins-Black.ttf", boy)
        sat = satirla(d, metin, f, gen)
        if len(sat) <= 4:
            break
    sat = sat[:4]
    yuk = len(sat) * int(boy * 1.15)
    y = (H - yuk) // 2 - 20
    for s in sat:
        d.text((x + 3, y + 3), s, font=f, fill=(0, 0, 0))
        d.text((x, y), s, font=f, fill=(255, 255, 255))
        y += int(boy * 1.15)
    # vurgu çizgisi ve kanal etiketi
    d.rectangle((x, y + 14, x + 140, y + 24), fill=k["vurgu"])
    ef = _font("Poppins-SemiBold.ttf", 30)
    etiket = tr_upper(k["ad"])
    tw = d.textlength(etiket, font=ef)
    d.rounded_rectangle((W - tw - 70, 30, W - 30, 86), radius=28, fill=k["vurgu"])
    d.text((W - tw - 50, 37), etiket, font=ef, fill=k["renk1"] if k["vurgu"] != (255, 255, 255) else k["renk1"])
    img.save(hedef, quality=90)
    return hedef
