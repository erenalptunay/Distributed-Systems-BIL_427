# BİL 427 — Lab 1: Hızlanma Ölçümü

Bu klasör Lab 1 paketidir. **Bağlayıcı çalışma yönergesi, LMS'teki "BİL 427 — Lab 1: Hızlanma Ölçümü"
dokümanıdır**; bu dosya yalnız kısa bir teknik başvuru metnidir.

## Dosyalar

| Dosya | Görevi |
|---|---|
| `prepare_lab.py` | İşlemcinizin tek çekirdek hızını kısa bir ölçümle belirler; bu ölçümden ve öğrenci numaranızdan kişisel deney parametrelerinizi üretir; `lab1_config.json` ve `.env` yazar. Bir kez çalıştırın. |
| `speedup.py` | Ölçüm programı. π integralini 1, 2, 4, … işçiyle hesaplar; T(N), S(N), E(N) değerlerini yazar ve `results/` altına CSV kaydeder. |
| `plot_speedup.py` | `results/` içindeki tüm ölçümlerden `results/speedup.png` grafiğini (logaritmik eksenlerle) çizer. |
| `test_speedup.py` | Başlangıç testleri (`python -m pytest -q`). |
| `requirements-dev.txt` | pytest ve matplotlib. |

## Kısa kullanım

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
python prepare_lab.py
python speedup.py process
python speedup.py thread
python speedup.py process --tpw 1
python speedup.py process --tpw <GRAIN_LARGE> --repeats 1
python plot_speedup.py
```

`speedup.py` seçenekleri: `process|thread`, `--tpw` (işçi başına görev, varsayılan 4),
`--repeats` (her N için tekrar, varsayılan 3; tablodaki süre ortancadır),
`--workers` (ör. `1,2,4,8`).

Konteyner deneyinde program `python:3.12-slim` imajında, `--cpus` ile sınırlanmış olarak çalışır;
yalnız standart kütüphaneyi kullandığı için imaja ek paket kurmak gerekmez.
