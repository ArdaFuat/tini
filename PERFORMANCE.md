# Performans incelemesi — 15 Ekim 2026

## Güncel animasyon: ayrı ses süreci ve GPU çizimi

Gerçek konuşma çözümlemesi sürerken eski arayüzde kareler arasında 392 ms'ye
ulaşan boşluklar görüldü. Ses motoru artık ayrı bir süreçte çalışıyor; kürenin
sürekli hareketini Qt Quick'in yerel render iş parçacığı ve GPU shader'ları
üretiyor. Her kare için Python geri çağrısı veya QWidget yeniden çizimi yok.
GPU çizimi açılamazsa eski raster çizimine dönülüyor.

Büyüme sırasında pencere maskesini tekrar kurmak 138 ms'ye kadar duraklama
yaratabiliyordu. Bu işlem kaldırıldı; şeffaf pikseller ve ayrı hafif tıklama
yüzeyi sürükleme/tıklama alanını sağlıyor. Ses motoru kapanışta durduruluyor;
iptal edilmiş oturumların sonuçları metin alanına gönderilmiyor. İlk gerçek
çözümlemenin CUDA hazırlığını azaltmak için beam-search ve VAD açılışta ısıtılıyor.
Konuşmayı çözen `transcribe` işlevinin ayarları değişmedi.

İki ayrı beş dakikalık denemede mevcut yerel ses örnekleri kullanıldı; gerçek
mikrofon açılmadı, sonuçlar başka uygulamalara yazılmadı. Her koşuda 299/299
çözümleme tamamlandı; 43 durum geçişi ve beş gizleme/geri getirme çevrimi denendi.
Son koşuda 69.126 görünür render karesinin medyan aralığı 4 ms, yüzde 99 değeri
8 ms idi. Sekiz aralık 50 ms'yi aştı; en büyüğü 80 ms idi. Bu değerler ayrıntılı
Qt günlükleri açıkken alınan render iş parçacığı ölçümleridir; fiziksel ekran
sunumu ölçümü veya bütün takılmaların ortadan kalktığı garantisi değildir.
Normal uygulamada bu yoğun kare günlükleri kapalıdır.

GPU açık ve kapalı ek kontrollerde üç ses örneğinin toplam 18 çözümlemesi
önceki referanslarla birebir aynı metni verdi. 27 otomatik kontrol ile ayrı
çalıştırılan beş Windows/GPU kontrolü geçti. GPU kontrolleri gerçek piksellerde
hareket ve büyüme, ses tepkisi, tıklama geçirgenliği, iki monitör arasında taşıma
ve görünürlüğün geri gelmesini kapsıyor.

Küçük kürede referans videodaki üçgen ağ korunuyor. Beklerken deformasyon ve
derinliğe bağlı kararma yok; küre iki eksende sabit parlaklıkla dönüyor. Büyüyen
küre de turkuaz kalıyor; pembe renk ses seviyesiyle beliriyor, sessizlikte geri
çekiliyor. Konuşma tepkisinin hızlı yükselip yavaş sönmesi korundu. Bu son
görsel ayar, yukarıdaki uzun yük denemelerinden sonra beş Windows/GPU kontrolüyle
yeniden doğrulandı. Bunlardan biri gerçek render piksellerinde sessizlik →
konuşma → sessizlik sırasında turkuaz → pembe → turkuaz geçişini denetliyor.

## Önceki animasyon: düzenli kare aralığı

Takılma incelemesinde ekran dışı Qt olay döngüsünde bekleme karelerinin medyan
aralığı 126,34 ms, konuşma karelerinin aralığı 46,85 ms ölçüldü. Bekleme bilinçli
olarak 8 kare/sn ile sınırlıydı; varsayılan kaba zamanlayıcı da aktif kareleri geciktiriyordu.
`PreciseTimer` ve beklemede 33 / kullanımda 16 ms hedefiyle medyanlar 33,04 / 16,01 ms
oldu; yüzde 95 değerleri 34,56 / 16,77 ms. Ölçüm, gerçek mikrofon veya çıkarım
çalıştırmadan 30 ms aralıklı yapay ses seviyesiyle yapıldı; tam dikte yükü ölçümü değildir.

Çizgi koordinatları ve derinlik ayrımı NumPy ile topluca hazırlanıyor. Aynı tel
kafes ve QPainter yolları korunuyor: üç durum, dört ses seviyesi ve üç fazdan
36 kare önceki çizimle piksel piksel aynı. Profilsiz çizim medyanı beklemede
0,878 → 0,418 ms, konuşurken 2,909 → 1,392 ms oldu. Daha sık kare çizildiğinden bu
kazanım toplam CPU kullanımının yarıya düştüğü anlamına gelmez. Model, mikrofon
ve dikte ayarları değişmedi.

## Önceki değişiklik: daha seyrek geometri

Kullanıcı isteğiyle tel kafes 25×48 yerine 18×34 örnekten oluşturuluyor.
Çizgi sayısı 3.504 → 1.768 (%49,5 azalma); nokta sayısı 1.200 → 612.
Renkler, ses kazancı, dalgalanma ve kare hızları aynı kaldı.
Aynı ekran dışı çizim ölçümünde medyan süre beklerken 1,582 → 0,884 ms,
konuşurken 5,358 → 2,941 ms oldu (yaklaşık %44–45 daha kısa).
Bu sonuç yalnızca animasyon çizimine aittir; toplam RAM/GPU tüketimi ölçülmedi.

**Önceki optimizasyonun durumu:** Kullanıcı tercihiyle animasyonun çizim uygulaması optimizasyondan
önceki sürümüne geri alındı. Aşağıdaki çizim süreleri denenen optimizasyonun
arşiv ölçümleridir; çizim kazancı artık geçerli sürümün özelliği değildir.
Hafif başlatıcı, ayarların sonradan oluşturulması, ses tamponlarının bırakılması
ve boşta çalışan işlerin azaltılması korunmuştur. Geri alma sonrasındaki toplam
RAM/CPU tüketimi bu tablodan doğrudan çıkarılamaz.

Ölçüm ortamı: Windows, Core Ultra 9 185H, 16 GB RAM, RTX 4070 Laptop 8 GB.
Whisper large-v3-turbo, CUDA float16. Konuşma modelinin ağırlıkları, beam size,
VAD eşikleri, dil ayarı, token sınırı ve doğruluk filtreleri değiştirilmedi.

## Önce / sonra

| İş | Önce | Sonra | Fark |
|---|---:|---:|---:|
| Bekleyen kürenin çizimi, medyan | 1,761 ms/kare | 0,650 ms/kare | %63 daha az süre |
| Konuşan kürenin çizimi, medyan | 5,662 ms/kare | 2,425 ms/kare | %57 daha az süre |
| Ses bölümü işleme, ortalama | 4,703 µs/blok | 1,419 µs/blok | %70 daha az süre |
| Açık uygulamayı simgeden geri getirme, medyan | 473 ms | 167 ms | %65 daha az süre |
| Bekleme RAM'i, çalışma kümesi | 738,9 MB | 646,0 MB | Yaklaşık 93 MB daha az |
| Bekleme ekran kartı belleği | 2.274,9 MB | 2.274,9 MB | Aynı |
| Ayrılmış özel bellek (private bytes) | 3.815,5 MB | 3.815,4 MB | Ölçümde hemen hemen aynı |

Çizim sonuçları gerçek Qt widget'ının ekran dışında çizildiği 120 ölçüm karesinin
medyanıdır. 8 kare/sn bekleme ve 30 kare/sn konuşma hızı, ağ yoğunluğu ve görünüm
korundu. Çizim hızlanması, bütün bilgisayarın CPU kullanımının aynı oranda düştüğü
anlamına gelmez. Beklemede toplam CPU tüketimi zaten çok düşüktü; 12 saniyelik
örneklerde ölçülebilir fark görülmedi.

Bellek ölçümleri her sürüm yeniden başlatılıp model hazır olduktan sonra 12 saniyelik
beklemede, uygulama süreçleri üzerinden alındı. Windows çalışma kümesini dinamik
yönettiğinden RAM farkı her açılışta aynı olmayabilir. Private bytes değeri fiziksel
RAM'de duran sayfa miktarı değildir. Ekran kartı belleği ayrı GPU süreç sayacından
alındı; diğer uygulamaların kullanımı bu sayıya eklenmedi.

## Değişiklikler

- Çizgilerin koordinatları ve ön/arka yüzleri NumPy ile topluca hazırlanıyor.
  Python içinde her çizgi için tekrar tekrar sayısal diziye erişilmiyor.
- Sabit geometri hesapları yeniden kullanılabiliyor; beklerken etkisiz deformasyon
  hesabı yapılmıyor. Pencere tıklama maskesi yalnızca boyut değiştiğinde güncelleniyor.
- Ayarlar paneli ve mikrofon listesi ilk açılışta oluşturulmuyor. Gizli metin alanı
  her konuşma parçasında yeniden çizilmiyor; son metin gerektiğinde gösteriliyor.
- Çıkarım kuyruğu boşken iş parçacığı tamamen bekliyor. Kapanış sinyaliyle uyanıyor.
- Bitmiş veya iptal edilmiş sesin uygulamadaki gereksiz referansları bırakılıyor.
- Ses seviyesi ara çarpım dizisi oluşturmadan hesaplanıyor.
- Zaten açık olan uygulamayı geri getiren başlatıcı, tam arayüzü, NumPy'ı veya
  mikrofon kitaplığını yüklemiyor.
- Hedef pencere değiştiğinde, metni panoya bırakmak için eski panodaki büyük
  resim veya dosya verileri gereksiz yere kopyalanmıyor. Normal yapıştırmada eski
  pano içeriğini geri getiren davranış korunuyor.
- CUDA dizini hazırlığı tekrarlandığında işlem tekrarlanmıyor. Normal kullanımda
  her ses parçası için gereksiz bilgi kayıtları yazılmıyor; uygulama logları sınırlı boyutta dönüyor.

## Doğrulama

- Beş durum ve farklı konuşma seviyelerinden 30 kare, eski çizimle piksel piksel aynı.
- Verilen videodan yerelde çıkarılan 6, 8 ve 7 saniyelik üç ses örneğinin dörder
  çözümlemesi karşılaştırıldı: 12 metin çıktısının tamamı aynı.
- Kod karşılaştırması: konuşmayı çözen `transcribe` fonksiyonu değişmedi.
- Ayrı çalıştırmalarda küçük zaman farkları görüldüğü için, aynı sıcak model
  üzerinde eski/yeni çözümleme sırası dönüşümlü çalıştırıldı. Üç örneğin medyanları
  önce 226,5 / 285,4 / 313,7 ms, sonra 225,5 / 287,7 / 312,5 ms oldu.
  Her örnekte fark %1'in altında; belirgin bir hız kaybı görülmedi. Bu eşleştirilmiş
  ölçümdeki 60 çözümlemede de metinler aynı. Konuşma motorunu sıkıştırmak bu
  değişikliğin parçası değildir.
- 701 ses bloğunun bölümlemesi karşılaştırıldı: dört nihai ses parçası örnek örnek aynı.
- Başlatma, durdurma, iptal, pencerenin sonradan oluşturulması, çıkış ve yeniden
  açma kontrolleri uygulandı. Kullanıcının gerçek ortamındaki her uygulama için
  doğruluk veya gecikme garantisi verilmez.

Ham ölçümler, kaynak anlık görüntüsü ve yerel ses örnekleri yalnızca `runtime`
dizinindedir; Git'e dahil edilmez. Model belleğini boşaltma veya daha düşük
hassasiyet kullanma, ilk yanıt süresini ya da sayısal sonuçları değiştirebileceği
için uygulanmadı.
