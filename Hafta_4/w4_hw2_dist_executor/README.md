# BİL 427 · HW2 — Dağıtık Görev Yürütücüsü (iskelet paket)

Bağlayıcı yönerge, LMS'deki **HW2 ödev dokümanıdır**; bu dosya yalnızca kısa
teknik başvuru metnidir.

## Dosyalar

| Dosya | Ne işe yarar? | Değiştirilir mi? |
|---|---|---|
| `worker.py` | İşçi servisi: `PUT /tasks/{task_id}` ile görevi yürütür | Yalnızca **TODO 1** |
| `coordinator.py` | Görevleri üretir, işçilere dağıtır, sonuçları toplar | Yalnızca **TODO 2, 3, 4** |
| `transport.py` | Koordinatörün HTTP istemcisi (`put_json`, `get_json`) | Hayır |
| `prepare_hw.py` | Kişisel parametreleri üretir → `hw2_config.json` | Hayır |
| `workers.json` | Koordinatörün kullandığı işçi adresleri | Hayır |
| `compose.yaml` | Üç işçi konteyneri (`worker1..3`, portlar 8001–8003) | Hayır |
| `tests/` | Verilen testler | **Hayır** |

## Hızlı başvuru

```bash
python -m pip install -r requirements-dev.txt
python prepare_hw.py
python -m pytest -q              # başlangıçta 14 test başarısız olur
docker compose up -d             # üç işçiyi başlat
python coordinator.py --label deneme
docker compose restart           # worker.py değişince
docker compose down              # iş bitince
```

Koordinatör seçenekleri: `--use K`, `--lossy`, `--no-dedup`, `--retries R`,
`--short-timeout` (bkz. `python coordinator.py --help`).
Sonuçlar: `results/<label>.csv` (görev başına) ve `results/summary.csv` (çalıştırma başına).
