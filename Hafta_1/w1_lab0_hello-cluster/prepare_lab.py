"""Lab 0 başlangıç yapılandırmasını hazırlar."""

import hashlib
from pathlib import Path

TIMEOUTS = (
    0.45, 0.55, 0.65, 0.75, 0.85,
    0.95, 1.05, 1.15, 1.25, 1.35,
)

NODE_PAIRS = (
    ("node1", "node2"),
    ("node1", "node3"),
    ("node2", "node1"),
    ("node2", "node3"),
    ("node3", "node1"),
    ("node3", "node2"),
)

NODE_PORTS = {
    "node1": 8001,
    "node2": 8002,
    "node3": 8003,
}


def derive_parameters(student_id):
    digest = hashlib.sha256(student_id.encode("utf-8")).digest()

    pair_value = int.from_bytes(digest[0:8], "big")
    timeout_value = int.from_bytes(digest[8:16], "big")

    observation_node, experiment_node = NODE_PAIRS[
        pair_value % len(NODE_PAIRS)
    ]
    peer_timeout = TIMEOUTS[
        timeout_value % len(TIMEOUTS)
    ]

    return observation_node, experiment_node, peer_timeout


def read_nonempty(prompt):
    while True:
        value = input(prompt).strip()
        if value:
            return value
        print("Bu alan boş bırakılamaz.")


def read_student_id():
    while True:
        value = read_nonempty("Öğrenci numaranız: ")
        if value.isdigit():
            return value
        print("Öğrenci numarası yalnızca rakamlardan oluşmalıdır.")


def main():
    full_name = read_nonempty("Ad Soyad: ")
    student_id = read_student_id()

    observation_node, experiment_node, peer_timeout = derive_parameters(student_id)
    observation_port = NODE_PORTS[observation_node]

    env_text = (
        f"STUDENT_ID={student_id}\n"
        f"OBSERVATION_NODE={observation_node}\n"
        f"OBSERVATION_PORT={observation_port}\n"
        f"EXPERIMENT_NODE={experiment_node}\n"
        f"PEER_TIMEOUT={peer_timeout:.2f}\n"
    )
    Path(".env").write_text(env_text, encoding="utf-8")

    print()
    print("=== LAB 0 YAPILANDIRMASI ===")
    print(f"Öğrenci       : {full_name}")
    print(f"Öğrenci No    : {student_id}")
    print(f"Gözlem düğümü : {observation_node}")
    print(f"Deney düğümü  : {experiment_node}")
    print(f"PEER_TIMEOUT   : {peer_timeout:.2f} s")
    print(f"Gözlem adresi : http://localhost:{observation_port}/peers")
    print()
    print("Lab 0 yapılandırması hazır.")


if __name__ == "__main__":
    main()
