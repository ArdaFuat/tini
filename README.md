# Tını — kişisel Windows dikte uygulaması

Türkçe dikte için yerel Whisper large-v3-turbo, faster-whisper ve NVIDIA CUDA.
Uygulama bir model eğitmez; açık kaynak konuşma modelini kişisel arayüzle kullanır.

## Kurulum

Windows, Python 3.13 ve güncel sürücüsü olan CUDA destekli NVIDIA ekran kartı gerekir.
Mevcut sürüm CPU modu veya macOS/Linux desteği sunmaz. Model yaklaşık 1,6 GB
indirilir; uygulama açıkken GPU belleğinde tutulur. Kurulum ve ilk model indirmesi
internet gerektirir, sonraki dikte işlemleri yereldir.

Depoyu indir veya klonla, klasörde PowerShell aç ve çalıştır:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Ardından `Baslat.vbs` dosyasına çift tıkla. Masaüstünden açmak için bu dosyanın
kısayolunu oluşturup adını **Tını** yapabilirsin; simge için `assets/ses.ico` kullanılır.
Sanal ortam, model ağırlıkları ve kişisel çalışma dosyaları depoya dahil değildir.

## Açma ve kullanım

Masaüstündeki **Tını** simgesiyle veya `Baslat.vbs` dosyasına çift tıklayarak aç.
Hafif başlatıcı, uygulama açıksa mevcut küreyi geri getirir; ikinci model yüklemez.
İlk hazırlık bitip **Hazır** görünmesini bekle.
Yazmak istediğin uygulamadaki metin alanına tıkla.
**Ctrl + Alt + Boşluk** ile başlat, tekrar basarak bitir. **Esc** iptal eder.
**Ctrl + Alt + Q** uygulamadan tamamen çıkar. Kürenin sağ tık menüsünde de **Çıkış** vardır.
Ekranda küçük, turkuaz bir tel kafes küre görünür; panel açılmaz.
Kısayola basınca küre yumuşakça büyür; konuşurken pembeleşir ve sesle dalgalanır.
Düğmeyi tutup sürükleyebilirsin; konumu hatırlanır. Tek tıklama başlatır / bitirir.
Ayarlar ve çıkış, düğmenin sağ tık menüsünde ve bildirim alanındaki **s** simgesindedir.
Beklerken turkuaz, dinlerken pembe, işlerken altın, hazırlanırken mavi renktedir.
Animasyon ses seviyesiyle hızlanıp büyür; sessizlikte yumuşakça yavaşlar.
Görsel ses hassasiyeti düşük sesle konuşmada da belirgin tepki verecek şekilde ayarlanmıştır;
bu kazanç yalnızca animasyonu etkiler, mikrofondaki ses veya yazıya çevirme eşikleri değişmez.
Masaüstündeki Tını kısayolunu yeniden açmak veya bildirim alanından
**Animasyonu geri getir** seçmek küreyi ana ekranın sol altına geri getirir.
Ekran dışında kalan kayıtlı konumlar açılışta düzeltilir.

Yuvarlak düğmede metin gösterilmez. Nihai metin konuşma bittiğinde hedef alana
Ctrl+V ile aktarılır. Hedef pencere değişirse veya erişim engellenirse metin
panoya kopyalanır. Otomatik Enter veya mesaj gönderme yoktur. Normal yapıştırmadan
sonra eski pano içeriği geri yüklenir; son metin ayarlar ekranından kopyalanabilir.

## İşleyiş

- Model uygulama açıkken GPU belleğinde sıcak tutulur.
- Konuşma duraklamalarda kısa parçalara ayrılır ve konuşma sürerken işlenir.
- Konuşma duraklamalarında işlenen parçalar korunur; ekranda önizleme hesaplanmaz.
- Sessizlik VAD ile filtrelenir. Mikrofon seviyesi çok düşükse bölümleme sesi kaçırabilir.
- Kesintisiz dikte için beş dakika sınırı vardır; durunca tekrar başlatılabilir.
- Ses dosyası kaydedilmez. Son metin yalnızca uygulama belleğinde tutulur.
- Kelime ipuçları ve çubuk konumu yerel Windows kullanıcı ayarlarında saklanır.
- Model ilk indirmeden sonra çevrimdışı çalışır; bulut API anahtarı veya abonelik yoktur.
- Oyunlar gibi GPU kullanan işler hızını etkileyebilir.
- Beklerken ses işleme zamanlayıcısı durur; animasyon 8 kare/sn, kullanım sırasında 30 kare/sn çalışır.
- Hızlı dikte için konuşma modeli GPU belleğinde hazır tutulur; bu optimizasyon model belleğini boşaltmaz.
- Ayarlar paneli yalnızca istendiğinde oluşturulur; kapalıyken metin arayüzü güncellenmez.
- İşlem kuyruğu boşken çıkarım iş parçacığı uyur; zaman aşımıyla tekrar tekrar uyanmaz.
- İşlenen veya iptal edilen ses tamponları boşta beklerken tutulmaz.

## Performans ölçümleri

Önce/sonra ölçümleri ve doğrulama sınırları için [PERFORMANCE.md](PERFORMANCE.md).

## Geliştirme

Kurulumdan sonra geliştirme ve kontroller için:

```powershell
.\.venv\Scripts\python.exe app.py
.\.venv\Scripts\python.exe -m unittest test_pipeline test_lifecycle test_visual_audio
```

`engine.py --audio dosya.wav` yerel ses dosyasında üç sıcak CUDA ölçümü yapar;
rapor metin içeriğini içermez. Başlangıç hataları `runtime/app.log` dosyasındadır.
`benchmark_perf.py` çizim veya yerel ses karşılaştırması yapar. Ses karşılaştırmasının
ham çıktıları yalnızca Git'e dahil edilmeyen `runtime` dizininde tutulur.

Bu bir ilk sürümdür. Gerçek Türkçe doğruluk ve mikrofon deneyimi kullanıcıyla
denenmelidir; genel model kıyaslamaları bu bilgisayar için hız garantisi değildir.

## Kaynaklar

- https://github.com/SYSTRAN/faster-whisper (MIT)
- https://huggingface.co/openai/whisper-large-v3-turbo (MIT)
- https://doc.qt.io/qtforpython-6/ (PySide6, LGPLv3/GPLv3/commercial)
- https://python-sounddevice.readthedocs.io/
