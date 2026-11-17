"""对照 docs/02-探测15500与22.md。绑定源端口，不发应用字节。"""
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
from config import load_config


def probe(bind_ip: str, bind_port: int, host: str, port: int, timeout: float) -> dict:
    started = time.monotonic()
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.settimeout(timeout)
        sock.bind((bind_ip, bind_port))
        sock.connect((host, port))
        local, peer = sock.getsockname(), sock.getpeername()
        banner = b""
        try:
            banner = sock.recv(64)
        except socket.timeout:
            banner = b""
        return {
            "ok": True,
            "error": None,
            "local_endpoint": list(local),
            "peer_endpoint": list(peer),
            "banner_text": banner.decode("latin1", errors="replace"),
            "elapsed_seconds": round(time.monotonic() - started, 6),
        }
    except OSError as error:
        return {
            "ok": False,
            "error": str(error),
            "type": type(error).__name__,
            "winerror": getattr(error, "winerror", None),
            "elapsed_seconds": round(time.monotonic() - started, 6),
        }
    finally:
        sock.close()


def main() -> int:
    cfg = load_config()
    parser = argparse.ArgumentParser()
    parser.add_argument("port", type=int, nargs="?", default=cfg["ssh_port"])
    parser.add_argument("--json-output", type=Path)
    args = parser.parse_args()
    report = {
        "bind_ip": cfg["bind_ip"],
        "bind_port": cfg["bind_port"],
        "host": cfg["host"],
        "port": args.port,
        **probe(cfg["bind_ip"], int(cfg["bind_port"]), cfg["host"], args.port, float(cfg["probe_timeout_s"])),
    }
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
