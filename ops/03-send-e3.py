"""对照 docs/03-0xe3-拉起sshd.md。源端口必须是配置里的 bind_port，失败不改临时端口。"""
from __future__ import annotations

import argparse
import json
import socket
import sys
import time
from pathlib import Path

OPS = Path(__file__).resolve().parent
if str(OPS) not in sys.path:
    sys.path.insert(0, str(OPS))
import testiface_frame as frame
from config import load_config
from wait_7878 import wait_free


def exchange(cmd: str, bind_ip: str, bind_port: int, host: str, port: int, timeout: float) -> dict:
    payload = frame.build_frame(cmd)
    started = time.monotonic()
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.settimeout(timeout)
        sock.bind((bind_ip, bind_port))
        sock.connect((host, port))
        local, peer = sock.getsockname(), sock.getpeername()
        if local[1] != bind_port:
            raise OSError(f"bound {local[1]}, expected {bind_port}")
        sock.sendall(payload)
        reply, termination, error = frame.receive_response(sock, timeout)
    finally:
        sock.close()
    return {
        "command": cmd,
        "frame_hex": payload.hex(),
        "local_endpoint": list(local),
        "peer_endpoint": list(peer),
        "response_hex": reply.hex(),
        "response_bytes": len(reply),
        "receive_termination": termination,
        "receive_error": error,
        "elapsed_seconds": round(time.monotonic() - started, 6),
        "application_payload_sent": True,
        "execution_verified": False,
        "identity_verified": False,
        "ack_contains_82e30101": "82e30101" in reply.hex(),
    }


def main() -> int:
    cfg = load_config()
    parser = argparse.ArgumentParser()
    parser.add_argument("--cmd", default=cfg["sshd_cmd"])
    parser.add_argument("--json-output", type=Path)
    parser.add_argument("--skip-wait", action="store_true")
    args = parser.parse_args()
    if not args.skip_wait:
        waited = wait_free(cfg["bind_ip"], int(cfg["bind_port"]), float(cfg["time_wait_s"]))
        if not waited["free"]:
            report = {"error": "bind_port still occupied", "wait": waited}
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 2
    report = exchange(
        args.cmd,
        cfg["bind_ip"],
        int(cfg["bind_port"]),
        cfg["host"],
        int(cfg["testiface_port"]),
        float(cfg["e3_timeout_s"]),
    )
    report["expected_ack_hex"] = cfg["expected_ack_hex"]
    report["ack_matches_expected"] = report["response_hex"] == cfg["expected_ack_hex"]
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if report["ack_contains_82e30101"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
