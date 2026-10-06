# Air Cargo Haberleri → WhatsApp (Meta resmi API)

Air cargo haber sitelerine düşen her yeni haber, kısa süre içinde WhatsApp'ına mesaj olarak gelir.
Mesajlar Meta'nın resmi WhatsApp API'sinin ücretsiz test numarasından gelir: ikinci numara gerekmez, engellenme riski yoktur.
Bilgisayarının açık olması gerekmez: GitHub Actions üzerinde, ücretsiz ve 7/24 çalışır.

**Takip edilen 9 site**

| Site | Odak |
|---|---|
| Air Cargo News | Genel hava kargo, havayolları, forwarderlar |
| Air Cargo Week | Genel hava kargo, pazar verileri |
| Payload Asia | Asya-Pasifik |
| The Loadstar | Sadece *Air* kategorisi |
| CargoForwarder Global | Avrupa, Almanya pazarı, röportajlar |
| Cargo Facts | Freighter filoları, siparişler, kiralama, P2F |
| Air Cargo World | ABD ağırlıklı genel haberler |
| FreightWaves (Air Cargo) | ABD, entegratörler, siparişler |
| Lojiport | Türkçe; sadece kargo/havayolu/THY/Orta Koridor geçen haberler |

Aynı haber birden fazla sitede çıkarsa sadece bir kez gönderilir.

**Mesaj örneği**
```
New air cargo news from Air Cargo News | 🎯 Qatar, Almaty:

🔴 Qatar Airways Cargo adds Almaty freighter

Read the full story: https://www.aircargonews.net/...

You receive this because you subscribed to the Air Cargo News Bot.
```
🔴 = başlıkta/özette takip listendeki bir rakip, ortak ya da konu geçiyor. ✈️ = diğer haberler.

> **Neden bu formatta?** WhatsApp, bir işletme hesabının sana kendiliğinden yazmasına sadece Meta'nın onayladığı
> **mesaj şablonlarıyla** izin verir. Her haber, onaylı `aircargo_news` şablonunun içine yerleştirilerek gönderilir.
> Sabit cümleler bu yüzden İngilizce ve değiştirilemez; değişen kısımlar kaynak, başlık ve link.

---

## Kurulum (~40 dakika)

### 1. Meta geliştirici uygulaması oluştur
1. <https://developers.facebook.com> → Facebook hesabınla giriş yap → gerekirse geliştirici olarak kaydol.
2. **My Apps → Create App**.
3. Kullanım amacı olarak **WhatsApp ile müşterilere bağlan** ("Connect with customers through WhatsApp") seçeneğini seç.
4. Bir isim ver (örn. `Air Cargo News Bot`). Senden bir **business portfolio** (işletme portföyü) istenirse yeni bir tane oluştur; adı önemli değil.
5. Uygulama açılınca sol menüden **WhatsApp → API Setup** (bazı hesaplarda "Quickstart / API Setup") sayfasına git.

### 2. Test numarasını ve kendi numaranı ayarla
**API Setup** sayfasında:
1. **From** alanında Meta'nın verdiği **test numarası** görünür. Altındaki iki ID'yi not al:
   - **Phone number ID** → `META_PHONE_ID`
   - **WhatsApp Business Account ID** → `META_WABA_ID`
2. **To** alanında **Manage phone number list** → kendi WhatsApp numaranı ekle → WhatsApp'ına gelen kodu gir.
   (Test numarası en fazla 5 alıcıya mesaj gönderebilir; ekip arkadaşlarını da ekleyebilirsin.)
3. İstersen sayfadaki **Send message** butonuyla hemen "Hello World" test mesajı gönderebilirsin.

### 3. Kalıcı erişim anahtarı (token) al
API Setup sayfasındaki geçici token **24 saatte** geçersiz olur; bot için kalıcı token gerekir.

1. <https://business.facebook.com/settings> → sol menü **Users → System users → Add**.
2. İsim ver (örn. `aircargo-bot`), rol **Admin** → oluştur.
3. Sistem kullanıcısını seç → **Assign assets** (Varlık ata):
   - **Apps** → oluşturduğun uygulama → **Full control** (Tam kontrol)
   - **WhatsApp accounts** → test hesabı → **Full control**
4. **Generate new token** → uygulamanı seç → süre: **Never** (Hiçbir zaman) → izinler:
   `whatsapp_business_messaging` ve `whatsapp_business_management` → **Generate**.
5. Çıkan uzun metni kopyala → `META_TOKEN`. Bu token gizlidir, kimseyle paylaşma; sayfayı kapatınca bir daha gösterilmez.

> Menü adları Meta'nın arayüz güncellemelerine göre biraz farklı olabilir. Takılırsan ekran görüntüsünü Claude'a gönder.

### 4. GitHub reposu oluştur
1. <https://github.com/new> → repo adı örn. `aircargo-news`. **Public** seç (aşağıdaki "Maliyet" notuna bak). Token ve numaralar repoda görünmez.
2. `Add file → Upload files` ile `monitor.py`, `setup_meta.py`, `requirements.txt`, `README.md` dosyalarını yükle.
3. `Add file → Create new file` ile iki dosya oluştur ve içeriklerini yapıştır:
   - `.github/workflows/news.yml`
   - `.github/workflows/meta-setup.yml`

### 5. Gizli bilgileri ekle
Repo → **Settings → Secrets and variables → Actions → New repository secret**

| Ad | Değer |
|---|---|
| `META_TOKEN` | 3. adımdaki kalıcı token |
| `META_PHONE_ID` | Phone number ID |
| `META_WABA_ID` | WhatsApp Business Account ID |
| `WA_PHONE` | Mesajların geleceği kendi numaran, + ile: `+4915112345678` |

### 6. Meta kurulumunu çalıştır
Repo → **Actions** → (istenirse "enable" onayı) → **Meta kurulum → Run workflow**.

Bu iş sırayla:
1. Token'ı ve test numarasını kontrol eder,
2. Sana "Hello World" mesajı gönderir,
3. Haber şablonunu (`aircargo_news`) oluşturup Meta onayına gönderir.

Şablon onayı genelde birkaç dakika, bazen birkaç saat sürer. **15–30 dakika sonra "Meta kurulum"u tekrar çalıştır.**
Log'da `Durum: APPROVED` ve "🎉 Her şey hazır" görünce WhatsApp'ına örnek bir haber mesajı gelir.

Hata çıkarsa log'daki ❌ satırı ne yapman gerektiğini söyler. Çözemezsen o satırı Claude'a yapıştır.

### 7. Haber botunu başlat
**Actions → Air Cargo News Alerts → Run workflow**.

İlk çalıştırmada "✅ Air cargo haber botu aktif" mesajı gelir. Mevcut haberler sessizce kaydedilir;
bundan sonra yayınlanan her yeni haber sana gelir. Sistem her 10 dakikada bir kendiliğinden kontrol eder.
Gönderen numarayı telefonuna "Air Cargo Haberleri" diye kaydet.

---

## Ayarlar (`monitor.py` dosyasının başında)

- **`WATCHLIST`**: 🔴 ile işaretlenecek rakip/ortak/konu listesi. GitHub'da dosyayı açıp kalem ikonuyla düzenleyebilirsin.
- **`ONLY_WATCHLIST = True`**: sadece listedekilerle ilgili haberler gelsin (gürültüyü azaltır).
- **`FEEDS`**: site ekle/çıkar. Yeni eklenen sitenin eski haberleri gönderilmez, sadece eklendikten sonrakiler gelir.
- **Kontrol sıklığı**: `.github/workflows/news.yml` içindeki `*/10` (dakika).

## Bilmen gerekenler

- **Ücret:** Meta, test numarasından gönderilen mesajlar için ücret almaz. GitHub Actions public repoda ücretsiz ve sınırsızdır. Private repo istersen ücretsiz kota ayda ~2.000 dakikadır; o durumda `*/10`'u `*/30` yap.
- **Hacim:** 9 site birlikte günde onlarca haber yayınlıyor. Fazla gelirse `ONLY_WATCHLIST = True` yap ya da sohbeti sessize alıp düzenli göz at.
- **Gecikme:** GitHub zamanlanmış görevleri yoğunlukta 5–15 dk gecikebilir. Pratikte haber yayından ~10–20 dk sonra gelir.
- **Şablon kategorisi:** Şablon "UTILITY" (bilgilendirme) olarak gönderilir. Meta bunu "MARKETING" olarak sınıflandırırsa kurulum log'u uyarır; bu durumda Meta kişi başı günlük sınır uygulayabildiği için bazı haberler teslim edilmeyebilir.
- **Gönderim başarısız olursa** haber kaybolmaz, bir sonraki turda tekrar denenir. Bir site geçici olarak açılmazsa bot diğerlerine devam eder.
- **Kendi işletme numarana geçmek** istersen (gönderen adı "Test Number" yerine kendi adın görünür) Meta'da gerçek bir numara ekleyip işletme doğrulaması yapman gerekir; bu durumda mesajlar ücretli olur.
- **Alternatif kanallar:** Kod GREEN-API (ikinci numarayla WhatsApp), CallMeBot, Twilio ve Telegram'ı da destekliyor; sadece secret'ları değiştirmek yeterli.
