# Tını

Windows için yerel Türkçe dikte. Konuş, metnin seçtiğin alana yazılsın.

![Tını: beklerken küçük turkuaz küre, dinlerken pembe ve yazarken altın animasyon](assets/preview.png)

Sesinle hareket eden, sürükleyebildiğin küçük bir küre. İlk model indirmesinden
sonra çevrimdışı çalışır; ses kaydetmez, abonelik veya API anahtarı istemez.

## Kurulum

**Windows · Python 3.13 · CUDA destekli NVIDIA ekran kartı ve güncel sürücü**

Depoyu indir, klasörde PowerShell aç:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

`Baslat.vbs` dosyasına çift tıkla. İlk açılışta yaklaşık **1,6 GB** model indirilir;
uygulama açıkken model GPU belleğinde hazır tutulur.

## Kullanım

- Yazmak istediğin alana tıkla; **Ctrl + Alt + Boşluk** ile dikteyi başlat / bitir.
- **Esc:** iptal · **Ctrl + Alt + Q:** çıkış.
- Küreyi sürükleyerek taşı; sağ tık menüsünden ayarlara ulaş.
- Küre kaybolursa `Baslat.vbs` dosyasını tekrar aç.

Konuşma bittiğinde metin hedef alana yapıştırılır. Hedef değişirse panoya kopyalanır.

[Performans notları](PERFORMANCE.md) ·
[faster-whisper](https://github.com/SYSTRAN/faster-whisper) ·
[Whisper large-v3-turbo](https://huggingface.co/openai/whisper-large-v3-turbo) ·
[PySide6](https://doc.qt.io/qtforpython-6/)
