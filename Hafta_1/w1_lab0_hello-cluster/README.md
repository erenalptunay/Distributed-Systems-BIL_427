# BİL 427 - Dağıtık Sistemler
## Lab 0: İlk Küme Deneyi

Bu klasör, Lab 0 uygulamasında kullanılacak program ve yapılandırma dosyalarını içerir.

Lab 0'ın ana uygulama talimatı LMS'de verilen **“BİL 427 - Lab 0: İlk Küme Deneyi”** dokümanıdır. Çalışma adımları, deneyler, sorular, rapor ve teslim kuralları için bu dokümanı esas alın. Bu README dosyası yalnızca klasördeki teknik dosyaları kısaca açıklayan ek bir başvuru kaynağıdır.

## Önkoşul

Lab 0'a başlamadan önce **“BİL 427 - Çalışma Ortamı Hazırlığı”** dokümanındaki adımları tamamlamış olmalısınız.

Ders boyunca tek Git deposu ve tek Python sanal ortamı kullanılır:

- `.git` yalnızca `BIL_427_Dagitik_Sistemler` ders kökünde bulunur.
- `.venv` yalnızca ders kökünde bulunur.
- Bu laboratuvar klasöründe yeniden `git init` çalıştırmayın.
- Yeni bir terminal açtığınızda ders kökündeki `.venv` ortamını yeniden etkinleştirin.

## Dosyalar

- `prepare_lab.py`: Lab 0 için kullanılacak çalışma yapılandırmasını hazırlar.
- `node.py`: Kümedeki bir düğümün davranışını gerçekleştirir.
- `compose.yaml`: Üç düğümlü yapının Docker Compose tanımıdır.
- `Dockerfile`: Düğüm konteynerinin oluşturulmasını tanımlar.
- `run_local.py`: Düğümleri gerektiğinde yerel Python süreçleri olarak çalıştırır.
- `test_node.py`: Lab 0 kodunun otomatik testlerini içerir.
- `requirements-dev.txt`: Test için gerekli Python paketlerini belirtir.
- `.gitignore`: Laboratuvar sırasında oluşabilecek geçici Python dosyalarının Git'e eklenmesini önleyen ek kuralları içerir.

## Yapılandırma

Lab 0 dokümanındaki ilgili adımda şu program çalıştırılır:

```text
python prepare_lab.py
```

Program sizden ad soyadınızı ve öğrenci numaranızı ister. Ardından deneyde kullanacağınız:

- gözlem düğümünü,
- deney düğümünü,
- `PEER_TIMEOUT` değerini,
- gözlem adresini

gösterir.

Programın verdiği değerleri Lab 0 boyunca aynen kullanın.

## Test

Gerekli paketler kurulduktan sonra kodun başlangıç durumunu şu komutla doğrulayabilirsiniz:

```text
python -m pytest -q
```

Bütün testlerin başarılı olması beklenir.

## Kümenin çalıştırılması

Üç düğümlü yapı Lab 0 dokümanındaki deneyler sırasında Docker Compose ile çalıştırılır. Başlatma, gözlem, düğüm durdurma/dondurma ve temizleme komutları ana Lab 0 dokümanında verilmiştir.

Komutları uygularken `prepare_lab.py` tarafından size gösterilen gözlem düğümünü, deney düğümünü ve gözlem adresini kullanın.

## Rapor ve teslim

Lab 0 için hazırlanacak teknik rapor, Git çalışma geçmişi ve teslim dosyalarının biçimi ana Lab 0 dokümanında açıklanmıştır.

Terminal çıktıları ve program çıktıları teknik raporun kendisi değildir; raporda yapılan deneyleri destekleyen kanıtlar olarak kullanılmalıdır.
