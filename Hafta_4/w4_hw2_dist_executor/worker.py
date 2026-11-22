"""worker.py — BİL 427 HW2: görevleri yürüten işçi (worker) servisi.

Yalnızca Python standart kütüphanesini kullanır. Docker Compose bu dosyayı üç
ayrı konteynerde (worker1, worker2, worker3) çalıştırır; isterseniz yerel
olarak da çalıştırabilirsiniz:
    python worker.py                 # 0.0.0.0:8000
    PORT=8001 WORKER_ID=w1 python worker.py

Kaynaklar ve uç noktalar:
    GET  /health           sağlık denetimi                         → 200
    PUT  /tasks/{task_id}  görevi bu kimlikle yürüt (eşzamanlı)     → 201 / 200 / 409
    GET  /tasks/{task_id}  görevin kaydını getir                    → 200 / 404
    GET  /stats            sayaçlar ve geçerli ayarlar              → 200
    PUT  /config           deney ayarlarını değiştir, sayaçları sıfırla → 200

PUT /tasks/{task_id} gövdesi:  {"op": "square", "x": 7}
Yanıt gövdesi:                 {"task_id": "...", "op": "square", "x": 7,
                                "result": 49, "worker": "worker1", "replayed": false}

Görev kimliğini (task_id) koordinatör seçer; bu yüzden yöntem PUT'tur ve aynı
kimlikle gelen tekrar, işlemi yeniden yaptırmamalıdır (ders notları Bölüm 6).

Deney ayarları (PUT /config ile koordinatör gönderir):
    delay_ms   : bir görevin yürütme süresi (iş yükünün benzetimi)
    lose_rate  : 0..1 olasılıkla, görev YÜRÜTÜLDÜKTEN SONRA yanıt gönderilmez;
                 bağlantı lose_delay saniye sonra kapatılır ("işlendi ama yanıt
                 gelmedi", ders notları Şekil 4.6 b)
    lose_delay : yanıtı düşürmeden önce beklenen süre (saniye)
    fail_rate  : 0..1 olasılıkla, görev YÜRÜTÜLMEDEN 503 döner
    dedup      : true ise aynı task_id ile gelen tekrarlar ayıklanır (TODO 1)
    seed       : rastgele sayı üretecinin tohumu

ÖĞRENCİ KODU yalnızca "TODO 1" ile işaretli bölgeye yazılır. Dosyanın geri
kalanı VERİLEN KODDUR; değiştirmeyin.
"""
import json
import os
import random
import re
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "8000"))
WORKER_ID = os.environ.get("WORKER_ID", socket.gethostname())

OPS = {"square": lambda x: x * x}
TASK_PATH = re.compile(r"^/tasks/([A-Za-z0-9-]{1,64})$")

DEFAULT_CONFIG = {"delay_ms": 150, "lose_rate": 0.0, "lose_delay": 3.0,
                  "fail_rate": 0.0, "dedup": True, "seed": None}


class TaskTable:
    """Görev kayıtlarını, sayaçları ve deney ayarlarını bellekte tutar.

    self.lock tek bir kilittir. Kilidi tutan iş parçacığı "kaydı denetle +
    görevi yürüt + kaydı sakla" adımlarını bölünmeden (atomik olarak) yapar.
    Bunun iki sonucu vardır:
      1. Aynı task_id ile aynı anda gelen iki istekten yalnızca biri görevi
         yürütür; diğeri kilidi bekler ve sonra hazır kaydı bulur.
      2. Bir işçi aynı anda yalnızca bir görev yürütür (tek çekirdekli bir
         makine gibi). Deney 1'de işçi sayısının etkisini bu sayede görürüz.
    """

    def __init__(self):
        self.lock = threading.Lock()          # kayıtlar ve yürütme için
        self.stats_lock = threading.Lock()    # yalnızca sayaçlar için
        self.config = dict(DEFAULT_CONFIG)
        self.rng = random.Random()
        self.records = {}                     # task_id -> kayıt sözlüğü
        self.stats = {}
        self.reset()

    # ---------- VERİLEN KOD: değiştirmeyin ----------
    def reset(self, **changes):
        """Ayarları günceller; kayıtları ve sayaçları sıfırlar."""
        with self.lock:
            self.config.update(changes)
            self.rng = random.Random(self.config["seed"])
            self.records = {}
            with self.stats_lock:
                self.stats = {"received": 0, "executed": 0, "deduplicated": 0,
                              "conflicts": 0, "lost": 0, "failed": 0}

    def count(self, name):
        with self.stats_lock:
            self.stats[name] += 1

    def snapshot(self):
        with self.stats_lock:
            return dict(self.stats)

    def compute(self, op, x):
        """Görevi GERÇEKTEN yürütür. Her çağrı "executed" sayacını artırır.

        Gerçek bir sistemde burada bir yan etki olurdu (ödeme, e-posta, dosya).
        Bu yüzden aynı görev için compute() iki kez çağrılmamalıdır.
        """
        time.sleep(self.config["delay_ms"] / 1000)
        self.count("executed")
        return OPS[op](x)

    def get(self, task_id):
        with self.lock:
            return self.records.get(task_id)

    # ---------- TODO 1 (ÖĞRENCİ KODU): tekrar ayıklama ----------
    def put(self, task_id, op, x):
        """PUT /tasks/{task_id} isteğini uygular.

        Dönüş değeri: (durum_kodu, gövde_sözlüğü, tekrar_mı)

        İstenen davranış:
          * Bütün adımları self.lock kilidini tutarak yapın.
          * self.config["dedup"] True ve bu task_id için kayıt VARSA:
              - kayıttaki op ve x istekle aynıysa: compute() ÇAĞIRMAYIN;
                "deduplicated" sayacını artırın; (200, kayıt, True) döndürün.
              - farklıysa: "conflicts" sayacını artırın;
                (409, {"error": "..."}, False) döndürün.
          * Aksi hâlde görevi compute(op, x) ile yürütün ve şu kaydı saklayın:
                {"task_id": task_id, "op": op, "x": x,
                 "result": <sonuç>, "worker": WORKER_ID}
            Bu task_id için daha önce kayıt yoksa 201, varsa 200 döndürün;
            tekrar_mı değeri False olur.
          * dedup False iken her istek görevi yeniden yürütür (Deney 3a).
        """
        # >>> ÖĞRENCİ KODU BAŞLANGICI (TODO 1)
        raise NotImplementedError("TODO 1: TaskTable.put")
        # <<< ÖĞRENCİ KODU SONU (TODO 1)


TABLE = TaskTable()


class Handler(BaseHTTPRequestHandler):
    """VERİLEN KOD: değiştirmeyin."""
    protocol_version = "HTTP/1.1"
    server_version = "BIL427-Worker/1.0"

    def send_json(self, status, body, headers=None):
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        try:
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            for name, value in (headers or {}).items():
                self.send_header(name, value)
            self.end_headers()
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            # İstemci zaman aşımıyla gitmiş: görev yürütüldü, yanıt ulaşmadı.
            print(f"[{WORKER_ID}] {status} yanıtı gönderilemedi: istemci gitmiş",
                  flush=True)
            self.close_connection = True

    def read_body(self):
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length)
        try:
            return json.loads(raw or b"null")
        except ValueError:
            return None

    def log_message(self, fmt, *args):   # her isteği yazdırma; olaylar aşağıda
        pass

    def do_GET(self):
        if self.path == "/health":
            return self.send_json(200, {"status": "ok", "worker": WORKER_ID})
        if self.path == "/stats":
            return self.send_json(200, {"worker": WORKER_ID, **TABLE.snapshot(),
                                        "config": TABLE.config})
        m = TASK_PATH.match(self.path)
        if m:
            rec = TABLE.get(m.group(1))
            if rec:
                return self.send_json(200, rec)
            return self.send_json(404, {"error": "görev yok"})
        self.send_json(404, {"error": "böyle bir kaynak yok"})

    def do_PUT(self):
        data = self.read_body()
        if self.path == "/config":
            if not isinstance(data, dict) or not set(data) <= set(DEFAULT_CONFIG):
                return self.send_json(400, {"error": "geçersiz ayar"})
            TABLE.reset(**data)
            print(f"[{WORKER_ID}] yeni ayarlar: {TABLE.config}", flush=True)
            return self.send_json(200, {"worker": WORKER_ID, "config": TABLE.config})
        m = TASK_PATH.match(self.path)
        if not m:
            return self.send_json(404, {"error": "böyle bir kaynak yok"})
        if (not isinstance(data, dict) or data.get("op") not in OPS
                or not isinstance(data.get("x"), int)):
            return self.send_json(400, {"error": 'beklenen: {"op": "square", "x": <tamsayı>}'})
        task_id = m.group(1)
        TABLE.count("received")
        cfg = TABLE.config
        if cfg["fail_rate"] and TABLE.rng.random() < cfg["fail_rate"]:
            TABLE.count("failed")
            return self.send_json(503, {"error": "geçici olarak hizmet verilemiyor"})
        status, body, replayed = TABLE.put(task_id, data["op"], data["x"])
        if replayed:
            print(f"[{WORKER_ID}] tekrar ayıklandı: {task_id}", flush=True)
        if status in (200, 201) and cfg["lose_rate"] and TABLE.rng.random() < cfg["lose_rate"]:
            TABLE.count("lost")
            print(f"[{WORKER_ID}] yanıt düşürüldü: {task_id}", flush=True)
            time.sleep(cfg["lose_delay"])
            self.close_connection = True      # yanıt hiç gönderilmez
            return
        if status in (200, 201):
            body = {**body, "replayed": replayed}
        self.send_json(status, body)

    def do_POST(self):
        allow = "GET, PUT" if TASK_PATH.match(self.path) else "GET"
        self.send_json(405, {"error": "yöntem desteklenmiyor"}, {"Allow": allow})


def make_server(host=HOST, port=PORT):
    return ThreadingHTTPServer((host, port), Handler)


def main():
    srv = make_server()
    print(f"[{WORKER_ID}] http://{HOST}:{PORT} dinleniyor", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()


if __name__ == "__main__":
    main()
