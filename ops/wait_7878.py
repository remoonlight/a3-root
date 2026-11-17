"""对照 docs/05-一键开启.md 中的 TIME_WAIT。源端口被占时等待，不改端口。"""
from __future__ import annotations

import json
import socket
import sys
import time
from pathlib import Path

OPS = Path(__file__).resolve().parent
if str(OPS) not in sys.path:
    sys.path.insert(0, str(OPS))
from config import load_config


def wait_free(bind_ip: str, bind_port: int, timeout_s: float) -> dict:
    started = time.monotonic()
    while True:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.bind((bind_ip, bind_port))
            return {"free": True, "elapsed_s": round(time.monotonic() - started, 3)}
        except OSError as error:
            if time.monotonic() - started >= timeout_s:
                return {
                    "free": False,
                    "elapsed_s": round(time.monotonic() - started, 3),
                    "error": str(error),
                }
            time.sleep(1)
        finally:
            sock.close()


def main() -> int:
    cfg = load_config()
    timeout = float(sys.argv[1]) if len(sys.argv) > 1 else cfg["time_wait_s"]
    report = wait_free(cfg["bind_ip"], int(cfg["bind_port"]), timeout)
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["free"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
