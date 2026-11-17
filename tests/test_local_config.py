"""Offline checks: refuse unconfigured devices and unknown SSH hosts."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

OPS = Path(__file__).resolve().parents[1] / "ops"
sys.path.insert(0, str(OPS))
import config

spec = importlib.util.spec_from_file_location("ssh_login", OPS / "04-ssh-login.py")
login = importlib.util.module_from_spec(spec)
spec.loader.exec_module(login)


class ConfigTests(unittest.TestCase):
    def test_template_cannot_connect(self):
        with self.assertRaises(ValueError):
            config.load_config(config.EXAMPLE_PATH)

    def test_missing_local_config_does_not_use_template(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(config, "CONFIG_PATH", Path(temp) / "missing.json"):
                with self.assertRaises(ValueError):
                    config.load_config()

    def test_explicit_local_settings_load(self):
        data = json.loads(config.EXAMPLE_PATH.read_text(encoding="utf-8"))
        data.update(ssid="offline-test", bind_ip="127.0.0.1", host="127.0.0.1")
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "config.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            self.assertEqual(config.load_config(path)["host"], "127.0.0.1")
            data["host"] = "::1"
            path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaises(ValueError):
                config.load_config(path)


class SSHTests(unittest.TestCase):
    def make_config(self, temp):
        identity, known = Path(temp) / "identity", Path(temp) / "known_hosts"
        identity.touch()
        return dict(identity_path=identity, known_hosts_path=known, root=OPS.parent,
                    ssh_user="root", host="127.0.0.1", ssh_port=2222,
                    ssh_timeout_s=1, verify_remote="id", verify_uid_needle="uid=0(root)")

    def test_missing_trusted_hosts_rejected_before_network(self):
        with tempfile.TemporaryDirectory() as temp:
            cfg = self.make_config(temp)
            with patch.object(login, "load_config", return_value=cfg), patch.object(sys, "argv", ["ssh-login"]), patch.object(login, "wait_free") as wait, patch.object(login.subprocess, "run") as run:
                self.assertEqual(login.main(), 2)
                wait.assert_not_called()
                run.assert_not_called()

    def test_strict_hosts_and_configured_port_used(self):
        with tempfile.TemporaryDirectory() as temp:
            cfg = self.make_config(temp)
            cfg["known_hosts_path"].touch()
            with patch.object(login, "load_config", return_value=cfg), patch.object(sys, "argv", ["ssh-login", "--skip-wait"]), patch.object(login.subprocess, "run", return_value=subprocess.CompletedProcess([], 255, "", "Host key verification failed")) as run:
                self.assertEqual(login.main(), 1)
                args = run.call_args.args[0]
                self.assertIn("StrictHostKeyChecking=yes", args)
                self.assertIn("PreferredAuthentications=publickey", args)
                self.assertEqual(args[args.index("-p") + 1], "2222")
                self.assertIn(f"UserKnownHostsFile={cfg['known_hosts_path']}", args)


if __name__ == "__main__":
    unittest.main(verbosity=2)
