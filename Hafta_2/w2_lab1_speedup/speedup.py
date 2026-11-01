"""speedup.py — BİL 427 Lab 1: paralel hızlanmayı ölçmek.

Kullanım:
    python speedup.py process                  # süreç havuzu (varsayılan)
    python speedup.py thread                   # iş parçacığı havuzu
    python speedup.py process --tpw 1          # işçi başına görev sayısı (tanecik)
    python speedup.py process --repeats 1      # her N için tekrar sayısı
    python speedup.py process --workers 1,2,4  # denenecek işçi sayıları

İş: π = ∫₀¹ 4 / (1 + x²) dx integralinin orta nokta kuralıyla hesaplanması.
İş miktarı (N_SLICES) prepare_lab.py'nin ürettiği lab1_config.json'dan okunur.
Sonuçlar ekrana ve results/ klasöründeki bir CSV dosyasına yazılır.
"""
import argparse
import csv
import json
import math
import os
import platform
import statistics
import sys
import time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
CONFIG = HERE / "lab1_config.json"
RESULTS = HERE / "results"


def partial_pi(task):
    """CPU-yoğun, saf Python iş: [start, stop) dilimlerinin katkısını toplar."""
    start, stop, n_slices = task
    width, s = 1.0 / n_slices, 0.0
    for i in range(start, stop):
        x = width * (i + 0.5)
        s += 4.0 / (1.0 + x * x)
    return s * width


def make_tasks(n_slices, k):
    """[0, n_slices) aralığını k ardışık, örtüşmeyen göreve böler."""
    step = n_slices // k
    return [(i * step, n_slices if i == k - 1 else (i + 1) * step, n_slices)
            for i in range(k)]


def run(workers, pool_cls, tasks_per_worker, n_slices):
    """İşi workers × tasks_per_worker göreve böler, havuzda çalıştırır; (süre, π) döndürür."""
    tasks = make_tasks(n_slices, workers * tasks_per_worker)
    t0 = time.perf_counter()
    with pool_cls(max_workers=workers) as pool:          # havuzun başlatılması da süreye dahildir
        pi = sum(pool.map(partial_pi, tasks))
    return time.perf_counter() - t0, pi


def cgroup_cpu_quota():
    """Konteyner içindeysek cgroups CPU kotasını (çekirdek cinsinden) döndürür; yoksa None."""
    try:                                                    # cgroup v2
        quota, period = Path("/sys/fs/cgroup/cpu.max").read_text().split()
        return None if quota == "max" else int(quota) / int(period)
    except (OSError, ValueError):
        pass
    try:                                                    # cgroup v1
        q = int(Path("/sys/fs/cgroup/cpu/cpu.cfs_quota_us").read_text())
        p = int(Path("/sys/fs/cgroup/cpu/cpu.cfs_period_us").read_text())
        return None if q <= 0 else q / p
    except (OSError, ValueError):
        return None


def default_workers(logical):
    """1, 2, 4, … ; çekirdek sayısını aşan en az bir değeri de içerir (en fazla 32)."""
    limit = min(max(8, 2 * logical), 32)
    ws, n = [], 1
    while n <= limit:
        ws.append(n)
        n *= 2
    return ws


def load_config():
    if not CONFIG.exists():
        sys.exit("lab1_config.json bulunamadı. Önce bu klasörde 'python prepare_lab.py' çalıştırın.")
    return json.loads(CONFIG.read_text(encoding="utf-8"))


def main(argv=None):
    ap = argparse.ArgumentParser(description="BİL 427 Lab 1 — hızlanma ölçümü")
    ap.add_argument("mode", nargs="?", default="process", choices=["process", "thread"])
    ap.add_argument("--tpw", type=int, default=4, help="işçi başına görev sayısı (varsayılan 4)")
    ap.add_argument("--repeats", type=int, default=3, help="her N için tekrar sayısı (varsayılan 3)")
    ap.add_argument("--workers", default=None, help="virgülle ayrılmış işçi sayıları, ör. 1,2,4,8")
    args = ap.parse_args(argv)

    cfg = load_config()
    n_slices = cfg["n_slices"]
    logical = os.cpu_count() or 1
    workers = ([int(w) for w in args.workers.split(",")] if args.workers
               else default_workers(logical))
    if workers[0] != 1:
        workers = [1] + workers                             # S(N) için T(1) gerekir
    pool_cls = ProcessPoolExecutor if args.mode == "process" else ThreadPoolExecutor
    quota = cgroup_cpu_quota()
    gil = getattr(sys, "_is_gil_enabled", lambda: True)()

    print(f"Öğrenci No: {cfg['student_no']}   mod={args.mode}   işçi başına görev={args.tpw}"
          f"   tekrar={args.repeats}")
    print(f"mantıksal işlemci={logical}   cgroup CPU kotası="
          f"{'yok' if quota is None else f'{quota:g} çekirdek'}")
    print(f"Python {platform.python_version()} (GIL {'açık' if gil else 'kapalı'})   "
          f"N_SLICES={n_slices:,}".replace(",", "."))
    print(f"{'N':>3} {'T(s)':>8} {'S':>6} {'E':>6}   π")

    rows, t1 = [], None
    for n in workers:
        times = []
        for _ in range(args.repeats):
            t, pi = run(n, pool_cls, args.tpw, n_slices)
            times.append(t)
        tn = statistics.median(times)
        if t1 is None:
            t1 = tn
        s, e = t1 / tn, t1 / tn / n
        ok = "" if abs(pi - math.pi) < 1e-6 else "  <-- π hatalı!"
        print(f"{n:>3} {tn:8.3f} {s:6.2f} {e:6.2f}   {pi:.8f}{ok}")
        rows.append({"N": n, "T_median_s": f"{tn:.4f}",
                     "T_runs_s": " ".join(f"{t:.4f}" for t in times),
                     "S": f"{s:.3f}", "E": f"{e:.3f}", "pi": f"{pi:.10f}"})

    RESULTS.mkdir(exist_ok=True)
    tag = f"{args.mode}_tpw{args.tpw}" + ("" if quota is None else f"_cpus{quota:g}")
    out = RESULTS / f"{tag}.csv"
    with out.open("w", newline="", encoding="utf-8") as f:
        f.write(f"# student_no={cfg['student_no']} mode={args.mode} tpw={args.tpw} "
                f"repeats={args.repeats} logical_cpus={logical} cgroup_quota={quota} "
                f"python={platform.python_version()} gil={gil} n_slices={n_slices}\n")
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"Kaydedildi: results/{out.name}")


if __name__ == "__main__":
    main()
