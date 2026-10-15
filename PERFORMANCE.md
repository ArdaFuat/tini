# Performans incelemesi — 15 Ekim 2026

**Son durum:** Kullanıcı tercihiyle animasyonun çizim uygulaması optimizasyondan
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
