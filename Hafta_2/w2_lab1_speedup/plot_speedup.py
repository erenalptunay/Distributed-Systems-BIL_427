"""plot_speedup.py — results/ klasöründeki ölçümlerden hızlanma grafiği çizer.

Kullanım:  python plot_speedup.py
Çıktı:     results/speedup.png  (raporunuzda kullanın)
"""
import csv
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"


def read(path):
    """(N listesi, T listesi, S listesi, mantıksal işlemci sayısı) döndürür."""
    with path.open(encoding="utf-8") as f:
        lines = f.readlines()
    meta = dict(kv.split("=", 1) for kv in lines[0].lstrip("# ").split()) if lines[0].startswith("#") else {}
    rows = list(csv.DictReader(ln for ln in lines if not ln.startswith("#")))
    return ([int(r["N"]) for r in rows], [float(r["T_median_s"]) for r in rows],
            [float(r["S"]) for r in rows], int(meta.get("logical_cpus", 0)), meta)


def label(meta, stem):
    """CSV başlığından okunur bir gösterge etiketi üretir."""
    if "mode" not in meta:
        return stem
    kind = "süreç" if meta["mode"] == "process" else "iş parçacığı"
    text = f"{kind}, işçi başına {meta.get('tpw', '?')} görev"
    if meta.get("cgroup_quota", "None") != "None":
        text += f", --cpus={float(meta['cgroup_quota']):g}"
    return text


def main():
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        sys.exit("matplotlib bulunamadı: python -m pip install -r requirements-dev.txt")

    files = sorted(RESULTS.glob("*.csv"))
    if not files:
        sys.exit("results/ klasöründe ölçüm yok. Önce speedup.py'yi çalıştırın.")

    fig, (ax_s, ax_t) = plt.subplots(1, 2, figsize=(11, 4.5))
    n_max, logical, t_all, s_all = 1, 0, [], []
    for p in files:
        ns, ts, ss, lg, meta = read(p)
        n_max, logical = max(n_max, max(ns)), max(logical, lg)
        t_all += ts
        s_all += ss
        ax_s.plot(ns, ss, marker="o", label=label(meta, p.stem))
        ax_t.plot(ns, ts, marker="o", label=label(meta, p.stem))
    ticks = [2 ** i for i in range(n_max.bit_length())]
    ax_s.plot(ticks, ticks, "k--", lw=1, label="ideal: S(N) = N")
    fmt = matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:g}")
    for ax in (ax_s, ax_t):
        ax.set_xscale("log", base=2)
        ax.set_yscale("log")                    # küçük ve büyük değerler birlikte okunur
        ax.set_xticks(ticks)
        ax.xaxis.set_major_formatter(fmt)
        ax.yaxis.set_major_formatter(fmt)
        ax.yaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())
        ax.set_xlabel("işçi sayısı N")
        ax.grid(alpha=0.3, which="both")
        if logical:
            ax.axvline(logical, color="gray", ls=":", lw=1.5)
    s_lo, s_hi = min(min(s_all), 1) / 1.4, max(max(s_all), n_max) * 1.3
    ax_s.set_ylim(s_lo, s_hi)
    ax_s.set_yticks([t for t in [0.1, 0.15, 0.25, 0.5, 0.75, 1, 1.5, 2, 3, 4, 8, 16, 32] if s_lo <= t <= s_hi])
    lo, hi = min(t_all), max(t_all)
    ax_t.set_ylim(lo / 1.4, hi * 1.4)
    ax_t.set_yticks([t for t in [0.01, 0.02, 0.05, 0.1, 0.2, 0.3, 0.5, 0.75, 1, 1.5, 2, 3, 5, 7.5, 10, 20, 50, 100]
                     if lo / 1.4 <= t <= hi * 1.4])
    ax_s.set_ylabel("hızlanma S(N) = T(1) / T(N)")
    ax_s.set_title("Hızlanma (noktalı dikey çizgi: mantıksal işlemci sayısı)", fontsize=10)
    ax_t.set_ylabel("süre T(N) (s)")
    ax_t.set_title("Süre", fontsize=10)
    ax_s.legend(fontsize=7.5, loc="upper left")
    fig.suptitle("Lab 1 — ölçülen hızlanma ve süre (eksenler logaritmik)")
    fig.tight_layout()
    out = RESULTS / "speedup.png"
    fig.savefig(out, dpi=150)
    print(f"Kaydedildi: results/{out.name}  ({len(files)} ölçüm dosyası)")


if __name__ == "__main__":
    main()
