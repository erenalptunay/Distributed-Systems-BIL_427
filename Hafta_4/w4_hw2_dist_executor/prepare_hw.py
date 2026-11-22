"""prepare_hw.py — BİL 427 HW2: kişisel deney parametrelerini üretir (VERİLEN KOD).

Kullanım:
    python prepare_hw.py           # ilk kez: bilgileri sorar, hw2_config.json yazar
    python prepare_hw.py           # sonraki çalıştırmalar: yapılandırmayı gösterir
    python prepare_hw.py --force   # bilgileri yeniden girmek için

Parametreler öğrenci numaranızdan türetilir; aynı numara her zaman aynı
değerleri verir. Başka bir öğrencinin parametreleriyle yapılan çalışma
notlandırılmaz.
"""
import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime

CONFIG_FILE = "hw2_config.json"


def derive(student_no):
    h = int(hashlib.sha256(f"BIL427-HW2-{student_no}".encode()).hexdigest(), 16)
    delay_ms = 120 + 20 * ((h >> 16) % 7)                      # 120 … 240 ms
    return {
        "N_TASKS": 40 + h % 21,                                 # 40 … 60 görev
        "LOSE_RATE": [0.20, 0.25, 0.30, 0.35][(h >> 8) % 4],    # yanıt kaybı olasılığı
        "DELAY_MS": delay_ms,                                   # görev yürütme süresi
        "TIMEOUT_SHORT": round(delay_ms * 0.6 / 1000, 3),       # yürütme süresinden kısa
        "SEED": (h >> 32) % 100000,
    }


def show(cfg):
    print("=== HW2 YAPILANDIRMASI ===")
    print(f"Öğrenci          : {cfg['student_name']}")
    print(f"Öğrenci No       : {cfg['student_no']}")
    print(f"Görev sayısı     : N_TASKS = {cfg['N_TASKS']}")
    print(f"Yürütme süresi   : DELAY_MS = {cfg['DELAY_MS']} ms")
    print(f"Yanıt kaybı      : LOSE_RATE = {cfg['LOSE_RATE']}")
    print(f"Kısa zaman aşımı : TIMEOUT_SHORT = {cfg['TIMEOUT_SHORT']} s")
    print(f"Tohum            : SEED = {cfg['SEED']}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--force", action="store_true")
    args = p.parse_args()
    if os.path.exists(CONFIG_FILE) and not args.force:
        with open(CONFIG_FILE, encoding="utf-8") as f:
            show(json.load(f))
        print("(Mevcut yapılandırma. Yeniden oluşturmak için --force kullanın.)")
        return
    name = input("Ad Soyad    : ").strip()
    no = input("Öğrenci No  : ").strip()
    if len(name.split()) < 2 or not re.fullmatch(r"\d{6,12}", no):
        sys.exit("Ad soyad (en az iki sözcük) ve yalnız rakamlardan oluşan öğrenci "
                 "numarası girin.")
    cfg = {"student_name": name, "student_no": no, **derive(no),
           "created": datetime.now().isoformat(timespec="seconds")}
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    show(cfg)
    print(f"Kaydedildi: {CONFIG_FILE}")


if __name__ == "__main__":
    main()
