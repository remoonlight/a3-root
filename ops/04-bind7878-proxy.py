"""对照 docs/04-公钥登录.md。OpenSSH ProxyCommand：绑源端口后拷贝 stdio。"""
from __future__ import annotations

import os
import socket
import sys
import threading
import time

from pathlib import Path

OPS = Path(__file__).resolve().parent
if str(OPS) not in sys.path:
    sys.path.insert(0, str(OPS))
from config import load_config


def write_all(write_fn, data: bytes) -> None:
    offset = 0
    while offset < len(data):
        try:
            written = write_fn(data[offset:])
        except BlockingIOError:
            time.sleep(0.01)
            continue
        if not written:
            return
        offset += written


def stdin_to_sock(sock: socket.socket) -> None:
    while True:
        try:
            data = os.read(0, 16384)
        except BlockingIOError:
            time.sleep(0.01)
            continue
        if not data:
            try:
                sock.shutdown(socket.SHUT_WR)
            except OSError:
                pass
            return
        try:
            sock.sendall(data)
        except OSError:
            return


def sock_to_stdout(sock: socket.socket) -> None:
    while True:
        try:
            data = sock.recv(16384)
        except OSError:
            return
        if not data:
            return
        try:
            write_all(lambda chunk: os.write(1, chunk), data)
        except OSError:
            return


def main() -> int:
    cfg = load_config()
    host, port = sys.argv[1], int(sys.argv[2])
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(float(cfg["ssh_timeout_s"]))
    sock.bind((cfg["bind_ip"], int(cfg["bind_port"])))
    sock.connect((host, port))
    sock.settimeout(None)
    out = threading.Thread(target=sock_to_stdout, args=(sock,), daemon=True)
    out.start()
    stdin_to_sock(sock)
    out.join(timeout=30)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
