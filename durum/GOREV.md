# Günlük içerik görevi (bulut ve yerel ortak talimat)

Sen @gecirgenbagirsak ("Bağırsaklarınıza Doğal Çözümler", Ege Işık) hesabının günlük içerik görevisin. Kullanıcı 17.11.2026'da **TAM OTOMATİK** yayına açık onay verdi: kalite kontrolünü geçen içeriği sormadan paylaş. Raporları **Türkçe** yaz.

Çalışma yeri: `github.com/gecirgenbagirsak/icerik` deposunun kökü. Python komutu Linux'ta `python3`, Windows'ta `py`.

**SLOT**: Görevi başlatan mesaj hangi slotu söylüyorsa o: `ogle` = KARUSEL (sadece Instagram), `aksam` = REELS (Instagram Reels + YouTube Shorts).

## 0. Hazırlık
- `git pull -q` (yerelde) — en güncel durum dosyalarını al. Bulutta depo zaten güncel klonlanır.
- Bulutta araçlar eksikse kur: `which ffmpeg || (sudo apt-get update -qq && sudo apt-get install -y -qq ffmpeg)`; `python3 -c "import PIL, edge_tts, googleapiclient, google_auth_oauthlib" || pip install -q pillow edge-tts google-api-python-client google-auth-oauthlib`.
- Gerekli ortam değişkenleri (bulut): PIXABAY_KEY, GH_TOKEN, YOUTUBE_TOKEN_JSON. Eksikse hangi değişkenin eksik olduğunu raporla ve DUR.

## 1. Oku
`durum/KURALLAR.md` (KESİNLİKLE uy), `durum/konu-havuzu.md`, `durum/yayin-gunlugu.json`. Örnek yapı: `medya/2026-11-18-ornek-v2/` yoksa KURALLAR.md'deki şemayı kullan.

## 2. Tekrar kontrolü
Günlükte bugünün tarihi (Europe/Istanbul) + bu slot + instagram linki varsa DUR — zaten paylaşılmış.

## 3. Konu ve içerik
- Son 30 günde kullanılmamış konu seç (ogle → K, aksam → R; akşam konusu öğlenle aynı olmasın).
- Klasör: `medya/<YYYY-MM-DD>-<slot>/icerik.json`. ogle: sadece "hesap" + "karusel"; aksam: sadece "hesap" + "reel".
- Pixabay: `python3 motor/medya.py ara foto|video "<ingilizce sorgu>" /tmp/onizleme.jpg` → önizlemeyi aç → ID seç. Son 14 günün ID'lerini kullanma.

### icerik.json şeması
```json
{"hesap": "gecirgenbagirsak",
 "karusel": {"slides": [
    {"tip": "kapak", "foto": 123, "odak": 0.2, "baslik": "...", "alt": "..."},
    {"no": 1, "foto": 123, "odak": 0.3, "baslik": "...", "metin": "..."},
    {"foto": 123, "baslik": "Peki nereden başlamalı?", "metin": "A · B · C"},
    {"tip": "cta", "foto": 123, "odak": 0.15, "baslik": "...", "metin": "...", "buton": "Detaylı bilgi için DM'den ulaşın", "not": "Bu içerik bilgilendirme amaçlıdır."}],
   "aciklama": "..."},
 "reel": {"sahneler": [
    {"video": [111, 222], "baslik": "Kısa kanca sorusu?", "ses": "..."},
    {"video": 333, "x": 0.7, "ses": "..."},
    {"video": 444, "kapanis": {"ust": "Detaylı bilgi için", "ana": "DM üzerinden bize ulaşın"}, "ses": "Detaylı bilgi almak istersen DM üzerinden bize ulaşabilirsin. ..."}],
   "aciklama": "..."}}
```

## 4. Üret ve kontrol et
- `python3 motor/uret.py medya/<klasör>`
- Karusel: tüm slaytları ffmpeg ile tek görselde birleştir, aç, kontrol et. Reels: her sahneden 1 kare çıkar, tek görselde birleştir, aç, kontrol et.
- Sorun varsa düzelt ve tekrar üret. 2 denemede düzelmezse YAYINLAMA, günlüğe "hata" kaydı yaz, raporla.

## 5. Kaydet ve yayınla
1. `durum/yayin-gunlugu.json`'a kaydı ekle (tarih, slot, format, konu, klasor, pixabay ID'leri; linkler boş) ve `durum/konu-havuzu.md`'de konuyu ✅ (tarih) ile işaretle.
2. `python3 motor/yayinla.py medya/<klasör>` → son satırdaki JSON'dan URL'leri al. (Medya + durum GitHub'a gider.)
3. Instagram: ChatPlace aracı `virale_publish_content` — botId `01a1caef-0eda-7327-b1c8-4ff3afb8f256`, idempotencyKey `ig-<klasör>`.
   - ogle: publishType "carousel", carouselItems = karusel URL'leri sırayla, caption = karusel_aciklama.txt.
   - aksam: publishType "reel", videoUrl = reel URL, coverUrl = kapak URL, caption = reel_aciklama.txt.
   - `virale_publication_status` ile "published" olana kadar 30-60 sn aralıkla kontrol et. failed + submittedAt boş → AYNI key ile tekrar dene. timeout → ASLA tekrar deneme, raporla.
4. aksam ise YouTube: `python3 motor/youtube.py yukle medya/<klasör>/reel.mp4 --baslik "<≤90 karakter> #Shorts" --aciklama-dosyasi medya/<klasör>/reel_aciklama.txt --etiketler "<5-8 etiket>" --gizlilik public`. Oturum hatası olursa YouTube'u atla ve raporla. Instagram başarısız olsa bile YouTube'u dene (ve tersi).
5. Günlükteki kayda instagram permalink ve youtube linkini yaz, sonra tekrar `python3 motor/yayinla.py medya/<klasör>` çalıştır (durum dosyası GitHub'a gider).

## 6. Rapor
3-4 satır Türkçe: konu, linkler, varsa sorun.

## Yasaklar
- ChatPlace/Virale AI üretim araçları (virale_*_generate, montage, carousel_generate vb.) ASLA — kredi DM botu için.
- Gizli değerleri (token, anahtar) asla dosyaya yazma, commit etme veya rapora koyma.
