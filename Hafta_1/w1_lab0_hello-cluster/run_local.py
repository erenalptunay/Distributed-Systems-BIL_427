"""Start three nodes on localhost (ports 8001-8003) WITHOUT Docker.

    python run_local.py

Stop with Ctrl+C. Then try:  curl http://localhost:8001/peers
"""
import os
import subprocess
import sys
import time
from pathlib import Path

PORTS = {"node1": 8001, "node2": 8002, "node3": 8003}


def load_lab_env(path=".env"):
    values = {}
    env_path = Path(path)
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip()
    return values


def main():
    lab_env = load_lab_env()
    peer_timeout = lab_env.get("PEER_TIMEOUT", "1.0")

    procs = {}
    for name, port in PORTS.items():
        peers = ",".join(f"localhost:{p}" for n, p in PORTS.items() if n != name)
        env = dict(os.environ, NODE_ID=name, PORT=str(port), PEERS=peers, PEER_TIMEOUT=peer_timeout, PYTHONUNBUFFERED="1")
        procs[name] = subprocess.Popen([sys.executable, "node.py"], env=env)
        print(f"started {name} (pid {procs[name].pid}) on http://localhost:{port}")
    print("\nCtrl+C to stop all nodes. To 'freeze' a node on Linux/macOS: kill -STOP <pid> ; resume: kill -CONT <pid>")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        for p in procs.values():
            p.terminate()
        for p in procs.values():
            p.wait(timeout=5)


if __name__ == "__main__":
    main()
