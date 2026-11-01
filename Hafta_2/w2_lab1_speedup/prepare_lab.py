"""prepare_lab.py — BİL 427 Lab 1: kişisel yapılandırmayı hazırlar.

Bir kez çalıştırın:  python prepare_lab.py
Program ad soyadınızı ve öğrenci numaranızı sorar, bilgisayarınızın tek
çekirdekteki hızını kısa bir ölçümle belirler, öğrenci numaranızdan ve bu
ölçümden size özgü deney parametrelerini üretir ve bunları lab1_config.json
ile .env dosyalarına yazar.
"""
import hashlib
import json
import os
import platform
import sys
import time
from pathlib import Path

from speedup import partial_pi

HERE = Path(__file__).resolve().parent
CONFIG = HERE / "lab1_config.json"
ENV = HERE / ".env"

TARGET_T1 = 2.0                                          # hedef T(1), saniye
WORK_FACTORS = [0.8, 0.9, 1.0, 1.1, 1.2]                 # öğrenciye özgü ±%20
N_SLICES_MIN, N_SLICES_MAX = 4, 80                       # milyon dilim
GRAIN_LARGE_CHOICES = [500, 1000, 1500, 2000]            # işçi başına görev
CPU_LIMIT_CHOICES = [1.0, 1.5, 2.0, 2.5, 3.0]            # çekirdek


def _digest(student_no: str) -> bytes:
    return hashlib.sha256(f"BIL427-LAB1-{student_no}".encode()).digest()


def calibrate(n=2_000_000, repeats=3):
    """Tek çekirdekte 1 milyon dilimin kaç saniye sürdüğünü ölçer (en iyi ölçüm)."""
    partial_pi((0, n // 10, n))                           # ısınma
    best = min(_timed(n) for _ in range(repeats))
    return best / (n / 1_000_000)


def _timed(n):
    t0 = time.perf_counter()
    partial_pi((0, n, n))
    return time.perf_counter() - t0


def make_params(student_no: str, logical_cpus: int, sec_per_million: float) -> dict:
    """Öğrenci numarasından ve makinenin hızından belirlenimci parametreler üretir.

    Toplam iş, tek işçiyle yaklaşık TARGET_T1 saniye sürecek şekilde seçilir ve
    öğrenci numarasına göre ±%20 değiştirilir.
    """
    h = _digest(student_no)
    factor = WORK_FACTORS[h[0] % len(WORK_FACTORS)]
    millions = round(TARGET_T1 * factor / sec_per_million)
    n_slices = min(max(millions, N_SLICES_MIN), N_SLICES_MAX) * 1_000_000
    grain_large = GRAIN_LARGE_CHOICES[h[1] % len(GRAIN_LARGE_CHOICES)]
    limits = [c for c in CPU_LIMIT_CHOICES if c < logical_cpus] or [0.5]
    cpu_limit = limits[h[2] % len(limits)]
    return {"n_slices": n_slices, "grain_large": grain_large, "cpu_limit": cpu_limit}


def valid_student_no(s: str) -> bool:
    return s.isdigit() and 5 <= len(s) <= 12


def show(cfg: dict) -> None:
    print()
    print("=== LAB 1 YAPILANDIRMASI ===")
    print(f"Öğrenci           : {cfg['student_name']}")
    print(f"Öğrenci No        : {cfg['student_no']}")
    print(f"Mantıksal işlemci : {cfg['logical_cpus']}")
    print(f"Kalibrasyon       : 1 milyon dilim ≈ {cfg['sec_per_million']:.3f} s (tek çekirdek)")
    n = f"{cfg['n_slices']:_}".replace("_", ".")
    print(f"İş miktarı        : N_SLICES = {n} dilim")
    print(f"Büyük parça sayısı: GRAIN_LARGE = işçi başına {cfg['grain_large']} görev")
    print(f"CPU sınırı        : CPU_LIMIT = {cfg['cpu_limit']} çekirdek")
    print()


def main() -> None:
    force = "--force" in sys.argv
    if CONFIG.exists() and not force:
        cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
        print("Bu klasörde zaten bir Lab 1 yapılandırması var:")
        show(cfg)
        print("Yeniden oluşturmanız gerekmiyor. Bilgileriniz yanlışsa: python prepare_lab.py --force")
        return

    name = input("Ad Soyad       : ").strip()
    while not name:
        name = input("Ad Soyad (boş olamaz): ").strip()
    no = input("Öğrenci No     : ").strip()
    while not valid_student_no(no):
        no = input("Öğrenci No (yalnız rakam): ").strip()

    logical = os.cpu_count() or 1
    print("İşlemci hızı ölçülüyor...")
    spm = calibrate()
    cfg = {"student_name": name, "student_no": no, "logical_cpus": logical,
           "sec_per_million": round(spm, 4),
           "platform": platform.platform(), "python": platform.python_version()}
    cfg.update(make_params(no, logical, spm))

    CONFIG.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    ENV.write_text(
        f"LAB1_STUDENT_NO={no}\n"
        f"N_SLICES={cfg['n_slices']}\n"
        f"GRAIN_LARGE={cfg['grain_large']}\n"
        f"CPU_LIMIT={cfg['cpu_limit']}\n",
        encoding="utf-8")
    show(cfg)
    print(f"Yazıldı: {CONFIG.name} ve {ENV.name}")


if __name__ == "__main__":
    main()
