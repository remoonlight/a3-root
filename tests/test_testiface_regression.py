"""Frame/string/readiness models and loopback transport. No vehicle, no shell execution."""
from __future__ import annotations

import sys
from pathlib import Path

OPS = Path(__file__).resolve().parents[1] / "ops"
sys.path.insert(0, str(OPS))

from contextlib import contextmanager
import random
import socket
import threading
import time
import unittest
from unittest.mock import patch

import testiface_frame as frame


def reference_xor(data):
    value = 0
    for byte in data:
        value = value ^ byte
    return 0x1C if value == 27 else value


def reference_command(data):
    body = data[12:]
    end = body.find(b"\0")
    if end < 0:
        end = len(body)
    return body[:end - 1] if end >= 2 else b""


def readiness_model(chunks):
    buffer = b""
    for chunk in chunks:
        if len(buffer) + len(chunk) < 2048:
            buffer += chunk
        if buffer[:2] == b"\x83\x87" and len(buffer) > 8:
            return buffer
    return None


@contextmanager
def local_peer(request, pieces=(), delay=0, hold=0):
    errors, observed = [], {}
    with socket.socket() as server:
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        server.settimeout(3)

        def worker():
            try:
                conn, peer = server.accept()
                with conn:
                    conn.settimeout(2)
                    data = bytearray()
                    while len(data) < len(request):
                        part = conn.recv(len(request) - len(data))
                        if not part:
                            break
                        data.extend(part)
                    observed.update(peer=peer, request=bytes(data))
                    for piece in pieces:
                        conn.sendall(piece)
                        if delay:
                            time.sleep(delay)
                    if hold:
                        time.sleep(hold)
            except Exception as error:
                errors.append(repr(error))

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        try:
            yield server.getsockname()[1], observed
        finally:
            thread.join(4)
            if thread.is_alive() or errors:
                raise AssertionError(f"loopback worker unfinished/errors: {errors}")


class FrameTests(unittest.TestCase):
    def test_known_vector(self):
        self.assertEqual(frame.build_frame("id").hex(), "8387abcd0000000002e332006964bc")

    def test_independent_checksum(self):
        rng = random.Random(8704)
        for length in (1, 2, 12, 64, 1024, 2046):
            data = bytes(rng.randrange(256) for _ in range(length))
            self.assertEqual(frame.checksum(data), reference_xor(data))

    def test_escape_checksum(self):
        self.assertEqual(frame.checksum(b"\0\x1b"), 28)

    def test_empty_checksum(self):
        with self.assertRaises(ValueError):
            frame.checksum(b"")

    def test_legacy_layout_loses_last_byte(self):
        self.assertEqual(reference_command(frame.build_frame("id", "x")), b"i")

    def test_nonempty_commands(self):
        for data in (b"i", b"id", "printf 中文".encode(), b"a" * 2034):
            with self.subTest(length=len(data)):
                built = frame.build_frame_bytes(data)
                self.assertEqual(frame.device_would_run(built), reference_command(built))
                self.assertEqual(reference_command(built).rstrip(b" "), data.rstrip(b" "))

    def test_zero_checksum_variants(self):
        command = b"id\xbc"
        self.assertEqual(reference_xor(frame.HEADER + command), 0)
        self.assertEqual(reference_command(frame.build_frame_bytes(command, pad="auto")), command + b" ")
        self.assertEqual(reference_command(frame.build_frame_bytes(command, pad="never")), command[:-1])

    def test_reject_empty_nul(self):
        for command in (b"", b"id\0extra", b"\0"):
            with self.subTest(command=command), self.assertRaises(ValueError):
                frame.build_frame_bytes(command)

    def test_host_buffer_cap_not_target_acceptance(self):
        self.assertEqual(len(frame.build_frame("a" * 2034)), 2047)
        with self.assertRaises(ValueError):
            frame.build_frame("a" * 2035)

    def test_static_model_split_at_nine_bytes_dispatches_early(self):
        built = frame.build_frame("id")
        dispatched = readiness_model([built[:9], built[9:]])
        self.assertEqual(dispatched, built[:9])
        self.assertNotEqual(reference_command(dispatched), b"id")


class TransportTests(unittest.TestCase):
    request = frame.build_frame("id")

    def test_fragmented_response_accumulates(self):
        with local_peer(self.request, [b"\x82", b"\xe3", b"\x01", b"\x01"], delay=.02) as (port, seen):
            reply = frame.exchange_frame(self.request, "127.0.0.1", port, 1)
        self.assertEqual(reply["response_hex"], "82e30101")
        self.assertEqual(reply["receive_termination"], "eof")
        self.assertFalse(reply["execution_verified"])

    def test_actual_source_port_7878(self):
        with local_peer(self.request, [b"OK"]) as (port, seen):
            reply = frame.exchange_frame(self.request, "127.0.0.1", port, 1, "127.0.0.1", 7878)
        self.assertEqual(seen["peer"], ("127.0.0.1", 7878))
        self.assertEqual(reply["local_endpoint"], ["127.0.0.1", 7878])

    def test_occupied_source_port_no_fallback(self):
        with socket.socket() as reserved:
            reserved.bind(("127.0.0.1", 0))
            reserved.listen(1)
            with self.assertRaisesRegex(OSError, "bind"):
                frame.exchange_frame(self.request, "127.0.0.1", 1, .2,
                                     "127.0.0.1", reserved.getsockname()[1])


if __name__ == "__main__":
    suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromTestCase(case)
                               for case in (FrameTests, TransportTests))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)
