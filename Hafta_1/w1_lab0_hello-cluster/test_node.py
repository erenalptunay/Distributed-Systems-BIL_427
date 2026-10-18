"""Unit and small integration tests for node.py (run with:  pytest -q)."""
import json
import socket
import threading
import urllib.request

import pytest

import node
import prepare_lab


def start_server(peers=(), node_id="test", timeout=0.5):
    """Start a real node on a free port in a background thread."""
    cfg = {"node_id": node_id, "port": 0, "peers": list(peers), "timeout": timeout}
    server = node.make_server(cfg, host="127.0.0.1")
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"127.0.0.1:{server.server_address[1]}"


def get_json(address, path):
    with urllib.request.urlopen(f"http://{address}{path}", timeout=5) as resp:
        return json.load(resp)


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


# ---- pure functions --------------------------------------------------------
def test_load_config_defaults():
    cfg = node.load_config({})
    assert cfg["port"] == 8000 and cfg["peers"] == [] and cfg["timeout"] == 1.0


def test_load_config_parses_peers():
    cfg = node.load_config({"NODE_ID": "n1", "PEERS": "a:1, b:2,", "PEER_TIMEOUT": "0.25"})
    assert cfg["node_id"] == "n1" and cfg["peers"] == ["a:1", "b:2"] and cfg["timeout"] == 0.25


def test_status_shape():
    s = node.status("n1")
    assert s["node"] == "n1" and s["status"] == "ok" and s["uptime_s"] >= 0


def test_classify_error_labels():
    assert node.classify_error(TimeoutError()) == "timeout"
    assert node.classify_error(ConnectionRefusedError()) == "connection refused"
    assert node.classify_error(socket.gaierror()) == "name not resolved"
    assert node.classify_error(ConnectionResetError()) == "connection reset"


# ---- HTTP behaviour --------------------------------------------------------
def test_health_endpoint():
    server, addr = start_server(node_id="alpha")
    try:
        assert get_json(addr, "/health")["node"] == "alpha"
    finally:
        server.shutdown()


def test_unknown_path_returns_404():
    server, addr = start_server()
    try:
        with pytest.raises(urllib.error.HTTPError) as err:
            get_json(addr, "/nope")
        assert err.value.code == 404
    finally:
        server.shutdown()


# ---- failure behaviour (the point of this lab) -------------------------------
def test_crashed_peer_is_refused_quickly():
    """A process that is gone: the connection is refused immediately (fast, unambiguous)."""
    result = node.probe(f"127.0.0.1:{free_port()}", timeout=1.0)
    assert result["reachable"] is False
    assert result["error"] == "connection refused"
    assert result["rtt_ms"] < 500


def test_frozen_peer_looks_like_a_timeout():
    """A peer that accepts connections but never answers (think `docker pause`):
    the caller learns nothing except that time ran out (slow, ambiguous)."""
    frozen = socket.socket()
    frozen.bind(("127.0.0.1", 0))
    frozen.listen(5)  # the kernel completes the TCP handshake; nobody ever replies
    try:
        result = node.probe(f"127.0.0.1:{frozen.getsockname()[1]}", timeout=0.3)
        assert result["reachable"] is False
        assert result["error"] == "timeout"
        assert result["rtt_ms"] >= 250
    finally:
        frozen.close()


def test_peers_endpoint_notices_a_peer_going_away():
    b, addr_b = start_server(node_id="b")
    a, addr_a = start_server(peers=[addr_b], node_id="a")
    try:
        before = get_json(addr_a, "/peers")["peers"][0]
        assert before["reachable"] is True and before["reply"]["node"] == "b"
        b.shutdown()
        b.server_close()
        after = get_json(addr_a, "/peers")["peers"][0]
        assert after["reachable"] is False
    finally:
        a.shutdown()


# ---- Lab 0 student configuration --------------------------------------------

def test_derive_parameters_is_deterministic():
    first = prepare_lab.derive_parameters("250000123")
    second = prepare_lab.derive_parameters("250000123")
    assert first == second


def test_derive_parameters_uses_valid_distinct_nodes():
    for n in range(250000000, 250001000):
        observation_node, experiment_node, _ = (
            prepare_lab.derive_parameters(str(n))
        )
        assert observation_node in {"node1", "node2", "node3"}
        assert experiment_node in {"node1", "node2", "node3"}
        assert observation_node != experiment_node


def test_derive_parameters_uses_allowed_timeout():
    for n in range(250000000, 250001000):
        _, _, timeout = prepare_lab.derive_parameters(str(n))
        assert timeout in prepare_lab.TIMEOUTS


def test_all_node_pairs_are_reachable():
    observed = set()

    for n in range(250000000, 250010000):
        observation_node, experiment_node, _ = (
            prepare_lab.derive_parameters(str(n))
        )
        observed.add((observation_node, experiment_node))

    assert observed == set(prepare_lab.NODE_PAIRS)


def test_all_timeouts_are_reachable():
    observed = set()

    for n in range(250000000, 250010000):
        _, _, timeout = prepare_lab.derive_parameters(str(n))
        observed.add(timeout)

    assert observed == set(prepare_lab.TIMEOUTS)
