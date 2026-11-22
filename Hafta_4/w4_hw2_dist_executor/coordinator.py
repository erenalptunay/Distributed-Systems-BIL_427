"""coordinator.py — BİL 427 HW2: görevleri işçilere dağıtan koordinatör.

Koordinatör, hw2_config.json dosyasındaki kişisel parametrelerinize göre
N_TASKS görev üretir, her göreve bir kimlik (task_id, UUID) verir, görevleri
workers.json dosyasındaki işçilere dağıtır ve her görevi
    PUT /tasks/{task_id}   gövde: {"op": "square", "x": <tamsayı>}
isteğiyle gönderir. Sonuç, PUT isteğinin yanıtında gelir (eşzamanlı çağrı).

Kullanım (işçiler çalışırken, ödev klasöründe):
    python coordinator.py --label d1b_uc_isci
    python coordinator.py --label d2_tekrarsiz --lossy --retries 0
    python coordinator.py --help

Seçenekler:
    --label L        sonuç dosyasının adı: results/L.csv (zorunlu)
    --use K          workers.json'daki ilk K işçiyi kullan (varsayılan: hepsi)
    --lossy          işçiler yanıtları kişisel LOSE_RATE olasılığıyla düşürür
    --no-dedup       işçilerde tekrar ayıklamayı kapat
    --retries R      bir görev için en fazla R tekrar (varsayılan 4)
    --short-timeout  zaman aşımı olarak kişisel TIMEOUT_SHORT değerini kullan

ÖĞRENCİ KODU yalnızca "TODO 2", "TODO 3" ve "TODO 4" ile işaretli bölgelere
yazılır. Dosyanın geri kalanı VERİLEN KODDUR; değiştirmeyin.
"""
import argparse
import csv
import json
import os
import platform
import random
import sys
import threading
import time
import uuid
from dataclasses import dataclass
from typing import Optional

import transport

CONFIG_FILE = "hw2_config.json"
WORKERS_FILE = "workers.json"
RESULTS_DIR = "results"

DEFAULT_TIMEOUT = 1.0     # saniye; bir denemenin yanıtı en fazla bu kadar beklenir
DEFAULT_RETRIES = 4       # ilk denemeye EK olarak en fazla 4 tekrar
BACKOFF_BASE = 0.1        # saniye; ilk tekrar öncesi bekleme üst sınırı
BACKOFF_CAP = 2.0         # saniye; bekleme hiçbir zaman bunu aşmaz
LOSE_DELAY = 3.0          # saniye; düşürülen yanıtta işçinin bekleme süresi
RETRYABLE_STATUS = {503}  # yeniden denenebilecek durum kodları


@dataclass
class Outcome:
    """Bir görevin bütün denemelerinden sonraki sonucu."""
    status: Optional[int]   # son yanıtın durum kodu; yanıt hiç gelmediyse None
    data: Optional[dict]    # son yanıtın gövdesi
    attempts: int           # toplam deneme sayısı (ilk deneme + tekrarlar)
    error: Optional[str]    # vazgeçildiyse son hatanın kısa adı, yoksa None

    @property
    def ok(self):
        return self.status in (200, 201)


# ---------- TODO 2 (ÖĞRENCİ KODU): üstel geri çekilme ----------
def backoff_delay(attempt, base=BACKOFF_BASE, cap=BACKOFF_CAP, rng=random):
    """attempt numaralı tekrardan önce beklenecek süreyi (saniye) döndürür.

    attempt = 0 ilk tekrardır (yani ikinci deneme), attempt = 1 ikinci tekrar...
    Üst sınır her tekrarda iki katına çıkar ama cap'i aşmaz:
        üst = min(cap, base * 2 ** attempt)
    Bekleme süresi [0, üst] aralığından rng.uniform ile rastgele seçilir
    ("tam rastgelelik", full jitter). rng parametresini kullanın; testler
    kendi rng nesnelerini verir.
    """
    # >>> ÖĞRENCİ KODU BAŞLANGICI (TODO 2)
    upper = min(cap, base * 2 ** attempt)
    return rng.uniform(0, upper)
    # <<< ÖĞRENCİ KODU SONU (TODO 2)


# ---------- TODO 3 (ÖĞRENCİ KODU): görev dağıtımı ----------
def assign_workers(n_tasks, workers):
    """Her görev için bir işçi adresi seçer; n_tasks uzunluğunda liste döndürür.

    Sıralı dağıtım (round-robin) kullanın: i numaralı görev
    workers[i % len(workers)] işçisine gider. Böylece işçilerin görev
    sayıları arasındaki fark en fazla 1 olur.
    """
    # >>> ÖĞRENCİ KODU BAŞLANGICI (TODO 3)
    return [workers[i % len(workers)] for i in range(n_tasks)]
    # <<< ÖĞRENCİ KODU SONU (TODO 3)


# ---------- TODO 4 (ÖĞRENCİ KODU): zaman aşımı ve sınırlı tekrar ----------
def send_with_retry(send, url, body, *, retries=DEFAULT_RETRIES,
                    timeout=DEFAULT_TIMEOUT, base=BACKOFF_BASE, cap=BACKOFF_CAP,
                    rng=random, sleep=time.sleep):
    """Görevi gönderir; gerekirse sınırlı sayıda yeniden dener. Outcome döndürür.

    send(url, body, timeout) çağrısı (durum, gövde) döndürür ya da
    TimeoutError / ConnectionError yükseltir (bkz. transport.py).

    İstenen davranış:
      * En fazla 1 + retries deneme yapın. Her denemede send'e timeout verin.
      * TimeoutError ya da ConnectionError: deneme başarısız, yeniden denenebilir.
      * Durum kodu RETRYABLE_STATUS içindeyse (503): yeniden denenebilir.
      * Başka her durum kodunda (200, 201, 400, 409, ...) yeniden DENEMEYİN;
        Outcome(durum, gövde, deneme_sayısı, None) döndürün.
      * İki deneme arasında sleep(backoff_delay(k, base, cap, rng)) çağırın;
        k, kaçıncı tekrar olduğunu gösterir (0, 1, 2, ...). Son denemeden
        sonra beklemeyin.
      * Bütün denemeler başarısızsa vazgeçin:
        Outcome(None, None, deneme_sayısı, hata_adı) döndürün. hata_adı,
        son hatanın kısa adıdır: "TimeoutError", "ConnectionResetError",
        "HTTP 503" gibi (istisnalar için type(e).__name__).
      * Aynı görevi her denemede AYNI url ve AYNI body ile gönderin: task_id
        URL'nin içindedir, işçi tekrarı bu kimlikle tanır.
    """
    # >>> ÖĞRENCİ KODU BAŞLANGICI (TODO 4)
    raise NotImplementedError("TODO 4: send_with_retry")
    # <<< ÖĞRENCİ KODU SONU (TODO 4)


# =====================================================================
# VERİLEN KOD: bundan sonrasını değiştirmeyin.
# =====================================================================
def load_json(path, hint):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        sys.exit(f"{path} bulunamadı. {hint}")


def configure_workers(workers, settings, seed):
    for i, w in enumerate(workers):
        try:
            status, _ = transport.put_json(f"{w}/config", {**settings, "seed": seed + i}, 2.0)
        except (TimeoutError, ConnectionError) as e:
            sys.exit(f"{w} işçisine ulaşılamadı ({type(e).__name__}). "
                     "İşçiler çalışıyor mu? (docker compose ps)")
        if status != 200:
            sys.exit(f"{w} ayarları kabul etmedi (HTTP {status}).")


def worker_stats(workers):
    stats = {}
    for w in workers:
        _, data = transport.get_json(f"{w}/stats", 2.0)
        stats[w] = data
    return stats


def run(args):
    cfg = load_json(CONFIG_FILE, "Önce python prepare_hw.py çalıştırın.")
    workers = load_json(WORKERS_FILE, "Ödev paketini yeniden açın.")["workers"]
    workers = workers[: args.use] if args.use else workers
    n = cfg["N_TASKS"]
    lose_rate = cfg["LOSE_RATE"] if args.lossy else 0.0
    timeout = cfg["TIMEOUT_SHORT"] if args.short_timeout else DEFAULT_TIMEOUT
    dedup = not args.no_dedup

    configure_workers(workers, {"delay_ms": cfg["DELAY_MS"], "lose_rate": lose_rate,
                                "lose_delay": LOSE_DELAY, "fail_rate": 0.0,
                                "dedup": dedup}, cfg["SEED"])

    rng_x = random.Random(cfg["SEED"])
    tasks = [{"task_id": str(uuid.uuid4()), "op": "square",
              "x": rng_x.randint(1, 10 ** 6)} for _ in range(n)]
    assignment = assign_workers(n, workers)
    if len(assignment) != n or any(w not in workers for w in assignment):
        sys.exit("assign_workers geçersiz bir liste döndürdü (TODO 3).")

    rows, rows_lock = [], threading.Lock()

    def drive(worker_url, my_tasks, seed):
        """Bir işçinin görevlerini sırayla gönderir (işçi başına tek iş parçacığı)."""
        rng = random.Random(seed)
        for t in my_tasks:
            url = f"{worker_url}/tasks/{t['task_id']}"
            body = {"op": t["op"], "x": t["x"]}
            t0 = time.perf_counter()
            out = send_with_retry(transport.put_json, url, body, retries=args.retries,
                                  timeout=timeout, rng=rng)
            elapsed = time.perf_counter() - t0
            result = out.data.get("result") if out.ok and out.data else None
            if out.ok:
                outcome = "ok" if result == t["x"] ** 2 else "wrong"
            elif out.status is None:
                outcome = "gave_up"
            else:
                outcome = "rejected"
            with rows_lock:
                rows.append({"task_id": t["task_id"], "worker": worker_url, "x": t["x"],
                             "outcome": outcome, "status": out.status or "",
                             "attempts": out.attempts, "error": out.error or "",
                             "result": "" if result is None else result,
                             "elapsed_s": f"{elapsed:.3f}"})

    print(f"Öğrenci No: {cfg['student_no']}  N_TASKS={n}  işçi={len(workers)}  "
          f"LOSE_RATE={lose_rate}  dedup={'açık' if dedup else 'kapalı'}")
    print(f"tekrar={args.retries}  zaman aşımı={timeout} s  DELAY_MS={cfg['DELAY_MS']}  "
          f"Python {platform.python_version()}")

    t_start = time.perf_counter()
    threads = []
    for i, w in enumerate(workers):
        mine = [t for t, a in zip(tasks, assignment) if a == w]
        th = threading.Thread(target=drive, args=(w, mine, cfg["SEED"] * 100 + i))
        th.start()
        threads.append(th)
    for th in threads:
        th.join()
    wall = time.perf_counter() - t_start
    stats = worker_stats(workers)

    print(f"{'işçi':24} {'atanan':>6} {'alınan':>6} {'yürütülen':>9} "
          f"{'ayıklanan':>9} {'düşürülen':>9}")
    tot = {"assigned": 0, "received": 0, "executed": 0, "deduplicated": 0, "lost": 0}
    for w in workers:
        s = stats[w]
        a = assignment.count(w)
        print(f"{w:24} {a:6} {s['received']:6} {s['executed']:9} "
              f"{s['deduplicated']:9} {s['lost']:9}")
        tot["assigned"] += a
        for k in ("received", "executed", "deduplicated", "lost"):
            tot[k] += s[k]
    print(f"{'TOPLAM':24} {tot['assigned']:6} {tot['received']:6} {tot['executed']:9} "
          f"{tot['deduplicated']:9} {tot['lost']:9}")

    count = {k: sum(r["outcome"] == k for r in rows)
             for k in ("ok", "gave_up", "rejected", "wrong")}
    attempts = sum(r["attempts"] for r in rows)
    print(f"görev={n}  başarılı={count['ok']}  vazgeçilen={count['gave_up']}  "
          f"reddedilen={count['rejected']}  yanlış={count['wrong']}  deneme={attempts}")
    print(f"süre={wall:.2f} s")

    os.makedirs(RESULTS_DIR, exist_ok=True)
    path = os.path.join(RESULTS_DIR, f"{args.label}.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0]))
        wr.writeheader()
        wr.writerows(sorted(rows, key=lambda r: (r["worker"], r["task_id"])))
    summary = os.path.join(RESULTS_DIR, "summary.csv")
    new = not os.path.exists(summary)
    with open(summary, "a", newline="", encoding="utf-8") as f:
        wr = csv.writer(f)
        if new:
            wr.writerow(["label", "student_no", "n_tasks", "workers", "lose_rate", "dedup",
                         "retries", "timeout_s", "ok", "gave_up", "rejected", "wrong",
                         "attempts", "received", "executed", "deduplicated", "lost",
                         "wall_s"])
        wr.writerow([args.label, cfg["student_no"], n, len(workers), lose_rate, int(dedup),
                     args.retries, timeout, count["ok"], count["gave_up"],
                     count["rejected"], count["wrong"], attempts, tot["received"],
                     tot["executed"], tot["deduplicated"], tot["lost"], f"{wall:.2f}"])
    print(f"Kaydedildi: {path}")


def main(argv=None):
    p = argparse.ArgumentParser(description="BİL 427 HW2 koordinatörü")
    p.add_argument("--label", required=True)
    p.add_argument("--use", type=int, default=0)
    p.add_argument("--lossy", action="store_true")
    p.add_argument("--no-dedup", action="store_true")
    p.add_argument("--retries", type=int, default=DEFAULT_RETRIES)
    p.add_argument("--short-timeout", action="store_true")
    run(p.parse_args(argv))


if __name__ == "__main__":
    main()
