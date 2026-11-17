# @gecirgenbagirsak günlük içerik kuralları

Bu dosya, her gün otomatik çalışan içerik görevinin uyduğu kurallardır. Kullanıcı (Ege Işık) bunları 17.11.2026'da onayladı.

## Hesap
- Instagram botId: `01a1caef-0eda-7327-b1c8-4ff3afb8f256` (@gecirgenbagirsak)
- YouTube: `python motor/youtube.py yukle ...` (yalnızca youtube.upload izni; **herkese açık** yüklenir — kilit yok, test edildi)
- TikTok: henüz bağlı değil, atla.
- Kitle: çoğu Türkiye'den kadın, 25–55 yaş. En çok ilgi gören konular: demir eksikliği/ferritin, halsizlik, şişkinlik, cilt, reflü, Candida, bağırsak florası.
- Bilgi: yalnızca genel kabul görmüş, iyi bilinen bilgileri kullan. Emin olmadığın rakam, çalışma veya iddiayı yazma.

## Dosya düzeni (depo: github.com/gecirgenbagirsak/icerik)
- `motor/` kod (uret.py, medya.py, yayinla.py, youtube.py, fonts/)
- `durum/` bu kurallar, konu-havuzu.md, yayin-gunlugu.json — her yayından sonra güncellenir ve yayinla.py ile GitHub'a gönderilir (kalıcı hafıza budur).
- `medya/<YYYY-MM-DD>-<ogle|aksam>/` her içeriğin klasörü (icerik.json + üretilen dosyalar). Site: https://gecirgenbagirsak.github.io/icerik/medya/<klasör>/...
- Komutlar depo kökünden çalıştırılır: `python motor/uret.py medya/<klasör>`, `python motor/yayinla.py medya/<klasör>` (Windows'ta `py`).

## Token tasarrufu (kullanıcı istedi: etkileşim düşmesin ama limit de bitmesin)
- Her slayt/sahne için TEK Pixabay araması yap; önizlemede uygun yoksa en fazla 1 farklı sorgu daha dene.
- Gereksiz dosya okuma yok: sadece KURALLAR.md, konu-havuzu.md, yayin-gunlugu.json ve örnek icerik.json.
- Kalite kontrolünde tek birleşik görsel aç (karusel için tüm slaytlar bir görselde, reel için tüm kareler bir görselde).
- Kısa düşün, kısa raporla.

## Kredi kuralı (KESİN)
ChatPlace/Virale AI üretim araçları (virale_*_generate, montage, carousel_generate, image_generate vb.) **asla** kullanılmaz. Sadece: Pixabay (medya.py), uret.py, youtube.py, virale_publish_content, virale_publication_status, virale_ai_balance (kontrol için).

## Görsel stil
- Rahatsızlığı yaşayan **gerçek insanlar**: karnını tutan, halsiz, aynada cildine bakan, yorgun vb. İzleyen "bu benim" demeli.
- Pixabay araması İngilizce yapılır: `python motor/medya.py ara foto "woman stomach pain" /tmp/onizleme.jpg` / `ara video ...`. Önizleme görselini aç, en uygun, gerçekçi, kaliteli olanı seç. Karikatür, 3D figür, çizgi film, aşırı yapay görünen AI görsel, kan/iğrenç görüntü, çıplaklık seçme.
- Aynı Pixabay ID'sini son 14 günde kullanma (yayin-gunlugu.json'a bak).
- Videoda yüz kırpılıyorsa sahneye `"x": 0..1` ver (yatay kırpma noktası); karuselde `"odak": 0..1` (dikey).

## Metin ve ton
- Türkçe, samimi, "sen" dili. Korkutma yok, vaat yok.
- Sağlık dili temkinli: "olabilir", "destekler", "araştırmalar gösteriyor". "Tedavi eder, iyileştirir, garanti" YASAK. Hastalık teşhisi koyma.
- Ürün adı (Lactofermin, Butyera) içerikte geçebilir ama sağlık iddiasıyla birlikte değil; satış DM'de yapılır.
- **CTA:** "DM'den yaz" KULLANMA. Kullan: "Detaylı bilgi için DM üzerinden bize ulaşın" / "Detaylı bilgi almak istersen DM üzerinden bize ulaşabilirsin".
- Karusel son slayt: `tip: cta`, `buton: "Detaylı bilgi için DM'den ulaşın"`, `not: "Bu içerik bilgilendirme amaçlıdır."`
- Reel son sahne: `kapanis: {"ust": "Detaylı bilgi için", "ana": "DM üzerinden bize ulaşın"}` (altyazı otomatik kapanır).
- Açıklama (caption): kanca cümle + 2-3 kısa paragraf + "Detaylı bilgi için DM üzerinden bize ulaşabilirsiniz 💬" + 8-10 Türkçe hashtag. Emoji ölçülü.

## Karusel (öğlen)
- 6-8 slayt, 1080×1350. Kapak (`tip: kapak`, güçlü kanca) → maddeler → (opsiyonel "Peki ne yapmalı?") → CTA.
- **Sayfa numarası yok.** Madde numarası (`no`) sadece başlıktaki listeyle birebir (ör. "5 işaret" → 1..5). Kapak/öneri/CTA slaytlarında `no` yok.
- Madde metni en fazla ~140 karakter; başlık kısa.

## Reels (akşam)
- 6-8 sahne, toplam 30-45 sn. İlk sahne kanca + `baslik` (üstte turuncu kutu, kısa soru). Her sahne 1 cümle seslendirme.
- Her sahneye konuya uyan 1-2 Pixabay video klibi (`video: id` veya `[id, id]`).
- Dosya ≤ 20 MB (uret.py zaten sınırlıyor).
- YouTube başlığı: ≤ 90 karakter, sonunda ` #Shorts`. Açıklama = reel_aciklama.txt.

## Kalite kontrolü (yayından önce zorunlu)
- Karusel: tüm slaytları birleştirip bak (ffmpeg hstack/vstack) — yazı yüzü kapatıyor mu, Türkçe karakterler doğru mu, numaralar doğru mu.
- Reels: 4-5 kare çıkarıp bak (ffmpeg -ss). Siyah kare, yanlış kırpma, okunmayan altyazı varsa düzelt ve yeniden üret.
- Sorun düzeltilemiyorsa YAYINLAMA; raporla.
