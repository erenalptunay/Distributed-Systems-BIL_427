"""hello-cluster düğümü -- BİL 427 Dağıtık Sistemler, Hafta 1 (Lab 0).

A deliberately tiny service that shows the anatomy of a distributed-system node:

    inbound adapter   -> Handler.do_GET      (receives HTTP requests)
    business logic    -> status()            (decides what to answer)
    outbound adapter  -> probe()             (calls other nodes over HTTP)

Standard library only: no pip install is needed to run it.

Configuration (environment variables):
    NODE_ID       name of this node                        (default: host name)
    PORT          TCP port to listen on                    (default: 8000)
    PEERS         comma-separated "host:port" list         (default: none)
    PEER_TIMEOUT  seconds to wait for a peer's answer      (default: 1.0)
"""
import json
import os
import signal
import socket
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

STARTED = time.monotonic()


# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------
def load_config(env=None):
    """Read the node configuration from environment variables."""
    env = os.environ if env is None else env
    peers = [p.strip() for p in env.get("PEERS", "").split(",") if p.strip()]
    return {
        "node_id": env.get("NODE_ID", socket.gethostname()),
        "port": int(env.get("PORT", "8000")),
        "peers": peers,
        "timeout": float(env.get("PEER_TIMEOUT", "1.0")),
    }


# --------------------------------------------------------------------------
# Business logic (knows nothing about HTTP)
# --------------------------------------------------------------------------
def status(node_id, started=STARTED):
    """The node's answer to 'are you alive?'."""
    return {"node": node_id, "status": "ok", "uptime_s": round(time.monotonic() - started, 1)}


# --------------------------------------------------------------------------
# Outbound adapter: talking to other nodes
# --------------------------------------------------------------------------
def classify_error(exc):
    """Turn a low-level exception into a short label that a human can compare."""
    reason = getattr(exc, "reason", exc)  # urllib wraps the real error in .reason
    if isinstance(reason, TimeoutError):  # socket.timeout is TimeoutError (Python >= 3.10)
        return "timeout"
    if isinstance(reason, ConnectionRefusedError):
        return "connection refused"
    if isinstance(reason, socket.gaierror):
        return "name not resolved"
    if isinstance(reason, ConnectionError):
        return "connection reset"
    return type(reason).__name__


def _ms(t0):
    return round((time.monotonic() - t0) * 1000, 1)


def probe(peer, timeout=1.0):
    """Ask one peer 'GET /health' and report what happened, including how it failed."""
    t0 = time.monotonic()
    try:
        with urllib.request.urlopen(f"http://{peer}/health", timeout=timeout) as resp:
            reply = json.load(resp)
        return {"peer": peer, "reachable": True, "rtt_ms": _ms(t0), "reply": reply}
    except Exception as exc:  # noqa: BLE001 - we want to report *any* failure
        return {"peer": peer, "reachable": False, "rtt_ms": _ms(t0), "error": classify_error(exc)}


def probe_all(peers, timeout=1.0):
    """Probe all peers concurrently, so one slow peer does not delay the others."""
    if not peers:
        return []
    with ThreadPoolExecutor(max_workers=len(peers)) as pool:
        return list(pool.map(lambda p: probe(p, timeout), peers))


# --------------------------------------------------------------------------
# Inbound adapter: HTTP
# --------------------------------------------------------------------------
class Handler(BaseHTTPRequestHandler):
    config = None  # filled in by make_server()

    def _send(self, code, body):
        data = json.dumps(body, indent=2).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):  # noqa: N802 - name required by BaseHTTPRequestHandler
        cfg = self.config
        if self.path == "/":
            self._send(200, {"node": cfg["node_id"], "endpoints": ["/health", "/peers"]})
        elif self.path == "/health":
            self._send(200, status(cfg["node_id"]))
        elif self.path == "/peers":
            self._send(200, {"node": cfg["node_id"], "peers": probe_all(cfg["peers"], cfg["timeout"])})
        else:
            self._send(404, {"error": "not found", "path": self.path})

    def log_message(self, fmt, *args):  # one log line per request, tagged with the node name
        print(f"[{self.config['node_id']}] {self.address_string()} {fmt % args}", flush=True)


def make_server(config, host="0.0.0.0"):
    """Build (but do not start) the HTTP server. Port 0 picks a free port (handy for tests)."""
    handler = type("BoundHandler", (Handler,), {"config": config})
    server = ThreadingHTTPServer((host, config["port"]), handler)
    server.daemon_threads = True
    return server


def main():
    config = load_config()
    server = make_server(config)

    def _stop(signum, frame):  # lets `docker stop` (SIGTERM) end the process quickly
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, _stop)
    print(f"[{config['node_id']}] listening on port {config['port']}, peers={config['peers']}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        print(f"[{config['node_id']}] stopped", flush=True)


if __name__ == "__main__":
    main()
