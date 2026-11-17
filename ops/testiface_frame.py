"""Build a static-model testiface frame; send only with --send. No runtime identity claim.

The 2047-byte cap is a receiver-buffer necessary condition, not a proven accepted
command limit. TCP segmentation is not controlled by sendall. The firmware's
automation readiness check can dispatch after only nine bytes (see offline report).
"""
from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import socket
import threading
import time

PREAMBLE = b"\x83\x87\xab\xcd"
HEADER = PREAMBLE + b"\0" * 4 + bytes([2, 0xE3, 0x32, 0])
MAX_FRAME_BYTES = 2047
DEFAULT_HOST, DEFAULT_PORT = None, 15500


def checksum(prefix: bytes) -> int:
    if not prefix:
        raise ValueError("checksum requires a nonempty prefix")
    value = 0
    for byte in prefix:
        value ^= byte
    return 0x1C if value == 0x1B else value


def build_frame_bytes(cmd_b: bytes, wire: str = "y", pad: str = "auto") -> bytes:
    if not isinstance(cmd_b, bytes) or not cmd_b or b"\0" in cmd_b:
        raise ValueError("command must be nonempty bytes without NUL")
    if wire not in ("x", "y") or pad not in ("auto", "always", "never"):
        raise ValueError("invalid wire/pad mode")
    prefix = HEADER + cmd_b
    if wire == "x":
        prefix += b"\0"
    elif pad == "always" or (pad == "auto" and checksum(prefix) == 0):
        prefix += b" "
    frame = prefix + bytes([checksum(prefix)])
    if len(frame) > MAX_FRAME_BYTES:
        raise ValueError("frame exceeds the 2047-byte host cap; smaller target limits remain unverified")
    return frame


def build_frame(cmd: str, wire: str = "y", pad: str = "auto") -> bytes:
    return build_frame_bytes(cmd.encode("utf-8"), wire, pad)


def device_would_run(frame: bytes) -> bytes:
    """Only model make_RUN_COMMAND's string slicing, NOT full target validation."""
    region = (frame + b"\0")[12:]
    if not region:
        return b""
    length = region.index(0)
    return region[:length - 1] if length >= 2 else b""


def receive_response(sock, timeout: float, max_bytes: int = 65536):
    """Accumulate stream fragments within one absolute deadline, O(max_bytes).

    No ACK length/preamble is assumed: the wire envelope is not fully established.
    Returned termination distinguishes timeout, EOF, truncation and receive errors.
    """
    deadline = time.monotonic() + timeout
    chunks, length = [], 0
    while length < max_bytes:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return b"".join(chunks), "timeout", None
        sock.settimeout(remaining)
        try:
            chunk = sock.recv(min(4096, max_bytes - length))
        except socket.timeout:
            return b"".join(chunks), "timeout", None
        except OSError as error:
            return b"".join(chunks), "receive_error", str(error)
        if not chunk:
            return b"".join(chunks), "eof", None
        chunks.append(chunk)
        length += len(chunk)
    return b"".join(chunks), "limit_reached", None


def exchange_frame(frame: bytes, host: str, port: int, timeout: float,
                   bind_ip: str = "", bind_port: int = 0,
                   max_response_bytes: int = 65536):
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("timeout must be finite and positive")
    if not 1 <= port <= 65535 or not 0 <= bind_port <= 65535:
        raise ValueError("invalid TCP port")
    if not frame or len(frame) > MAX_FRAME_BYTES or max_response_bytes < 1:
        raise ValueError("invalid frame/response size")
    started = time.monotonic()
    # An explicit source port must fail visibly if occupied, never silently fall
    # back to an ephemeral port (which would invalidate the 7878 comparison).
    if bind_ip or bind_port:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.settimeout(timeout)
            try:
                sock.bind((bind_ip or "0.0.0.0", bind_port))
            except OSError as error:
                raise OSError(f"bind {bind_ip or '0.0.0.0'}:{bind_port}: {error}") from error
            sock.connect((host, port))
        except BaseException:
            sock.close()
            raise
    else:
        sock = socket.create_connection((host, port), timeout=timeout)
    with sock:
        local, peer = sock.getsockname(), sock.getpeername()
        sock.sendall(frame)
        reply, termination, error = receive_response(sock, timeout, max_response_bytes)
    return {
        "local_endpoint": list(local), "peer_endpoint": list(peer),
        "request_hex": frame.hex(), "response_hex": reply.hex(),
        "response_bytes": len(reply), "receive_termination": termination,
        "receive_error": error, "elapsed_seconds": round(time.monotonic() - started, 6),
        "application_payload_sent": True, "execution_verified": False,
        "identity_verified": False,
    }


def send_frame(frame: bytes, host: str, port: int, timeout: float,
               bind_ip: str = "", bind_port: int = 0) -> bytes:
    """Compatibility byte-return API. Use exchange_frame for evidence/error status."""
    result = exchange_frame(frame, host, port, timeout, bind_ip, bind_port)
    if result["receive_error"]:
        raise OSError(result["receive_error"])
    return bytes.fromhex(result["response_hex"])


def hx(data: bytes) -> str:
    return data.hex(" ") if data else "(empty)"


def _find_zero_checksum_cmd():
    return next((b"id" + bytes([x]) for x in range(1, 256)
                 if checksum(HEADER + b"id" + bytes([x])) == 0), None)


def selftest():
    zero = _find_zero_checksum_cmd()
    cases = {
        "id-checksum": checksum(HEADER + b"id") == 0xBC,
        "escape-checksum": checksum(b"\0\x1b") == 0x1C,
        "string-model": device_would_run(build_frame("id")) == b"id",
        "legacy-truncation": device_would_run(build_frame("id", "x")) == b"i",
        "zero-checksum-padding": zero is not None and
            device_would_run(build_frame_bytes(zero)) == zero + b" ",
    }
    for name, ok in cases.items():
        print(f"[selftest] {name}: {'OK' if ok else 'FAIL'}")
    return 0 if all(cases.values()) else 1


def loopback_selftest(port: int = 0):
    received, failures = {}, []
    frame = build_frame("id")
    with socket.socket() as server:
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        server.settimeout(3)

        def serve():
            try:
                conn, peer = server.accept()
                with conn:
                    conn.settimeout(3)
                    data = bytearray()
                    while len(data) < len(frame):
                        chunk = conn.recv(len(frame) - len(data))
                        if not chunk:
                            break
                        data.extend(chunk)
                    received.update(peer=list(peer), data=bytes(data))
                    conn.sendall(b"LOOPBACK-OK")
            except Exception as error:
                failures.append(repr(error))

        worker = threading.Thread(target=serve, daemon=True)
        worker.start()
        result = exchange_frame(frame, "127.0.0.1", server.getsockname()[1], 2,
                                "127.0.0.1", port)
        worker.join(4)
    ok = (not worker.is_alive() and not failures and received.get("data") == frame and
          result["response_hex"] == b"LOOPBACK-OK".hex() and
          (not port or received["peer"][1] == port))
    print(json.dumps({"loopback_passed": ok, "server_peer": received.get("peer"),
                      "failures": failures, "exchange": result}))
    return 0 if ok else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cmd", nargs="?", default="id")
    parser.add_argument("--send", action="store_true")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--timeout", type=float, default=3)
    parser.add_argument("--wire", choices=("x", "y"), default="y")
    parser.add_argument("--pad", choices=("auto", "always", "never"), default="auto")
    parser.add_argument("--raw", metavar="HEX")
    parser.add_argument("--bind-ip", default="")
    parser.add_argument("--bind-port", type=int, default=0)
    parser.add_argument("--max-response-bytes", type=int, default=65536)
    parser.add_argument("--json-output", type=Path)
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--loopback-selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        return selftest()
    if args.loopback_selftest:
        return loopback_selftest(args.bind_port)
    try:
        frame = bytes.fromhex(args.raw) if args.raw is not None else build_frame(args.cmd, args.wire, args.pad)
        if not frame or len(frame) > MAX_FRAME_BYTES:
            raise ValueError("raw frame must contain 1..2047 bytes")
        report = {"frame_hex": frame.hex(), "frame_bytes": len(frame),
                  "command_slice_model_hex": device_would_run(frame).hex(),
                  "model_is_not_full_receiver": True, "application_payload_sent": False,
                  "execution_verified": False, "identity_verified": False}
        code = 0
        if args.send:
            if not args.host:
                raise ValueError("--send requires an explicit --host")
            report.update(exchange_frame(frame, args.host, args.port, args.timeout,
                                         args.bind_ip, args.bind_port, args.max_response_bytes))
            code = 0 if report["response_bytes"] and report["receive_termination"] == "eof" else 3
    except (ValueError, UnicodeError, OSError) as error:
        report = {"error": str(error), "type": type(error).__name__,
                  "execution_verified": False, "identity_verified": False}
        code = 2
    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        temporary = args.json_output.with_name(args.json_output.name + ".tmp")
        temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(temporary, args.json_output)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
