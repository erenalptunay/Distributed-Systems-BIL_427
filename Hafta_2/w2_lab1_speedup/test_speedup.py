"""Lab 1 başlangıç testleri:  python -m pytest -q"""
import math
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor

import prepare_lab
import speedup


def test_tasks_cover_range_without_overlap():
    tasks = speedup.make_tasks(1003, 7)
    assert len(tasks) == 7
    assert tasks[0][0] == 0 and tasks[-1][1] == 1003
    for (a, b, _), (c, d, _) in zip(tasks, tasks[1:]):
        assert b == c                      # boşluk ya da örtüşme yok


def test_sequential_pi():
    n = 100_000
    pi = sum(speedup.partial_pi(t) for t in speedup.make_tasks(n, 5))
    assert abs(pi - math.pi) < 1e-8


def test_process_pool_matches_sequential():
    n = 200_000
    seq = speedup.partial_pi((0, n, n))
    _, par = speedup.run(2, ProcessPoolExecutor, 3, n)
    assert abs(par - seq) < 1e-9


def test_thread_pool_matches_sequential():
    n = 200_000
    seq = speedup.partial_pi((0, n, n))
    _, par = speedup.run(2, ThreadPoolExecutor, 3, n)
    assert abs(par - seq) < 1e-9


def test_default_workers_exceed_core_count():
    assert speedup.default_workers(2) == [1, 2, 4, 8]
    assert speedup.default_workers(8)[-1] == 16
    assert speedup.default_workers(64)[-1] == 32


def test_params_are_deterministic_and_in_range():
    a = prepare_lab.make_params("250000001", 8, 0.1)
    assert a == prepare_lab.make_params("250000001", 8, 0.1)
    assert 16_000_000 <= a["n_slices"] <= 24_000_000      # 2 s / 0,1 s × (0,8 … 1,2)
    assert a["n_slices"] % 1_000_000 == 0
    assert a["grain_large"] in prepare_lab.GRAIN_LARGE_CHOICES
    assert a["cpu_limit"] < 8


def test_work_scales_with_machine_speed_and_is_clamped():
    fast = prepare_lab.make_params("250000001", 8, 0.05)["n_slices"]
    slow = prepare_lab.make_params("250000001", 8, 0.2)["n_slices"]
    assert fast > slow
    assert prepare_lab.make_params("250000001", 8, 10.0)["n_slices"] == 4_000_000
    assert prepare_lab.make_params("250000001", 8, 0.001)["n_slices"] == 80_000_000


def test_cpu_limit_below_logical_cpus():
    for no in range(250000000, 250000050):
        assert prepare_lab.make_params(str(no), 2, 0.1)["cpu_limit"] < 2


def test_calibration_is_positive():
    assert prepare_lab.calibrate(n=200_000, repeats=1) > 0


def test_student_number_validation():
    assert prepare_lab.valid_student_no("250000001")
    assert not prepare_lab.valid_student_no("25abc")
    assert not prepare_lab.valid_student_no("")
