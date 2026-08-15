# IlyasVideoDownloaderWeb

Render üzerinde ücretsiz planla çalıştırılmak üzere hazırlanmış Flask + yt-dlp web uygulaması.

## Dosyalar
- app.py
- index.html
- requirements.txt
- render.yaml

## Render
GitHub'a bu 4 dosyayı yükle. Render'da mevcut Web Service'i bu repoya bağla.
`render.yaml` build sırasında bgutil POT provider'ı kurar ve start sırasında 4416 portunda çalıştırır.

## Önemli
POT provider, YouTube'un "Sign in to confirm you're not a bot" kontrollerini azaltmaya yardımcı olur; proje sahibi de bunun her 403/bot kontrolünü garanti etmediğini belirtiyor.
Ayrıca ücretsiz Render servisleri uykuya geçebilir ve büyük dosya indirmelerinde süre/bant genişliği sınırları olabilir.

## Dosya adı
İndirilen dosya, YouTube video başlığından oluşturulur ve mümkün olduğunca aynı ad korunur. İşletim sisteminin yasakladığı karakterler temizlenir.
