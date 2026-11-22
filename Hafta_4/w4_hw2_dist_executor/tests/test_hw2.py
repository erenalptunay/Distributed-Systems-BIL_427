"""test_hw2.py — BİL 427 HW2 testleri (VERİLEN DOSYA, değiştirmeyin).

Çalıştırma (ödev klasöründe):  python -m pytest -q
İşçiler testlerde aynı süreç içinde, rastgele boş portlarda başlatılır;
Docker konteynerlerinin çalışıyor olması gerekmez.
"""
import random
import threading
import time
import uuid

import pytest

import coordinator
import transport
import worker


# ---------- yardımcılar ----------
class MaxRng:
    """uniform(a, b) için hep b döndürür: üst sınırı görmemizi sağlar."""
    def uniform(self, a, b):
        return b


class FakeSend:
    """Sırayla verilen sonuçları döndüren (ya da yükselten) sahte send."""
    def __init__(self, *results):
        self.results = list(results)
        self.calls = []

    def __call__(self, url, body, timeout):
        self.calls.append((url, body, timeout))
        r = self.results.pop(0)
        if isinstance(r, BaseException):
            raise r
        return r


@pytest.fixture
def server():
    """Aynı süreçte bir işçi başlatır; adresini döndürür."""
    worker.TABLE.reset(**worker.DEFAULT_CONFIG)
    srv = worker.make_server("127.0.0.1", 0)
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()
    srv.server_close()


def configure(url, **settings):
    status, _ = transport.put_json(f"{url}/config", settings, 2.0)
    assert status == 200


# ---------- TODO 2: backoff_delay ----------
def test_backoff_upper_bound_doubles():
    got = [coordinator.backoff_delay(k, base=0.1, cap=100, rng=MaxRng()) for k in range(4)]
    assert got == pytest.approx([0.1, 0.2, 0.4, 0.8])


def test_backoff_respects_cap():
    assert coordinator.backoff_delay(10, base=0.1, cap=2.0, rng=MaxRng()) == pytest.approx(2.0)


def test_backoff_is_random_within_bounds():
    rng = random.Random(1)
    values = [coordinator.backoff_delay(3, base=0.1, cap=2.0, rng=rng) for _ in range(200)]
    assert all(0 <= v <= 0.8 for v in values)
    assert len(set(values)) > 100          # sabit bir değer değil


# ---------- TODO 3: assign_workers ----------
def test_assign_round_robin():
    ws = ["a", "b", "c"]
    got = coordinator.assign_workers(7, ws)
    assert got == ["a", "b", "c", "a", "b", "c", "a"]


def test_assign_balanced():
    ws = ["w1", "w2", "w3", "w4"]
    got = coordinator.assign_workers(43, ws)
    counts = [got.count(w) for w in ws]
    assert len(got) == 43 and max(counts) - min(counts) <= 1


# ---------- TODO 4: send_with_retry ----------
def test_retry_success_first_try():
    send = FakeSend((201, {"result": 4}))
    out = coordinator.send_with_retry(send, "u", {"x": 2}, retries=3, sleep=lambda s: None)
    assert out.ok and out.status == 201 and out.attempts == 1 and out.error is None


def test_retry_after_timeout_and_503():
    send = FakeSend(TimeoutError(), (503, {}), (200, {"result": 4}))
    slept = []
    out = coordinator.send_with_retry(send, "u", {"x": 2}, retries=3, timeout=0.5,
                                      base=0.1, cap=10, rng=MaxRng(), sleep=slept.append)
    assert out.ok and out.attempts == 3
    assert slept == pytest.approx([0.1, 0.2])            # backoff_delay(0), (1)
    assert all(c == ("u", {"x": 2}, 0.5) for c in send.calls)   # aynı istek, aynı süre


def test_retry_does_not_retry_client_errors():
    for status in (400, 409):
        send = FakeSend((status, {"error": "x"}))
        out = coordinator.send_with_retry(send, "u", {}, retries=3, sleep=lambda s: None)
        assert out.status == status and out.attempts == 1 and not out.ok


def test_retry_gives_up_after_limit():
    send = FakeSend(*[ConnectionResetError()] * 3)
    slept = []
    out = coordinator.send_with_retry(send, "u", {}, retries=2, rng=MaxRng(),
                                      sleep=slept.append)
    assert out.status is None and out.attempts == 3
    assert out.error == "ConnectionResetError"
    assert len(slept) == 2                                # son denemeden sonra bekleme yok


# ---------- VERİLEN KOD: işçinin temel davranışı ----------
def test_worker_rejects_bad_request(server):
    status, _ = transport.put_json(f"{server}/tasks/abc", {"op": "cube", "x": 2}, 2.0)
    assert status == 400
    status, _ = transport.get_json(f"{server}/nothing", 2.0)
    assert status == 404


# ---------- TODO 1: tekrar ayıklama ----------
def test_worker_put_creates_then_replays(server):
    configure(server, delay_ms=0)
    url = f"{server}/tasks/{uuid.uuid4()}"
    s1, b1 = transport.put_json(url, {"op": "square", "x": 7}, 2.0)
    s2, b2 = transport.put_json(url, {"op": "square", "x": 7}, 2.0)
    assert (s1, s2) == (201, 200)
    assert b1["result"] == b2["result"] == 49
    assert (b1["replayed"], b2["replayed"]) == (False, True)
    _, st = transport.get_json(f"{server}/stats", 2.0)
    assert st["executed"] == 1 and st["deduplicated"] == 1


def test_worker_conflicting_body(server):
    configure(server, delay_ms=0)
    url = f"{server}/tasks/t-1"
    transport.put_json(url, {"op": "square", "x": 7}, 2.0)
    status, _ = transport.put_json(url, {"op": "square", "x": 8}, 2.0)
    assert status == 409


def test_worker_without_dedup_executes_again(server):
    configure(server, delay_ms=0, dedup=False)
    url = f"{server}/tasks/t-2"
    s1, _ = transport.put_json(url, {"op": "square", "x": 3}, 2.0)
    s2, b2 = transport.put_json(url, {"op": "square", "x": 3}, 2.0)
    assert (s1, s2) == (201, 200) and b2["replayed"] is False
    _, st = transport.get_json(f"{server}/stats", 2.0)
    assert st["executed"] == 2 and st["deduplicated"] == 0


def test_worker_concurrent_duplicates_execute_once(server):
    configure(server, delay_ms=200)
    url = f"{server}/tasks/t-3"
    results = []
    ths = [threading.Thread(target=lambda: results.append(
        transport.put_json(url, {"op": "square", "x": 5}, 3.0))) for _ in range(4)]
    for t in ths:
        t.start()
    for t in ths:
        t.join()
    assert sorted(s for s, _ in results) == [200, 200, 200, 201]
    _, st = transport.get_json(f"{server}/stats", 2.0)
    assert st["executed"] == 1


# ---------- uçtan uca: kayıp yanıtlar + tekrar + ayıklama ----------
def test_end_to_end_lost_responses(server):
    configure(server, delay_ms=10, lose_rate=0.4, lose_delay=0.6, seed=7)
    rng = random.Random(3)
    outs = []
    for i in range(15):
        url = f"{server}/tasks/e2e-{i}"
        outs.append(coordinator.send_with_retry(
            transport.put_json, url, {"op": "square", "x": i}, retries=8,
            timeout=0.3, base=0.01, cap=0.05, rng=rng))
    assert all(o.ok and o.data["result"] == i * i for i, o in enumerate(outs))
    assert sum(o.attempts for o in outs) > 15              # bazı yanıtlar kayboldu
    _, st = transport.get_json(f"{server}/stats", 2.0)
    assert st["executed"] == 15                             # yine de her görev bir kez
