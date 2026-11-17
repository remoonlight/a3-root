"""文档链接的操作文件必须存在；配置字段与脚本读取一致。"""
from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OPS = ROOT / "ops"
DOCS = ROOT / "docs"


class DocsOpsTests(unittest.TestCase):
    def test_readme_table_files_exist(self):
        text = (ROOT / "README.md").read_text(encoding="utf-8")
        missing = []
        for match in re.finditer(r"\((docs/[^)]+|ops/[^)]+|ssh/[^)]+)\)", text):
            path = ROOT / match.group(1)
            if not path.exists():
                missing.append(match.group(1))
        self.assertEqual(missing, [])

    def test_doc_ops_links_exist(self):
        missing = []
        for doc in DOCS.glob("*.md"):
            for match in re.finditer(r"\((?:\.\./)?(ops/[^)]+|ssh/[^)]+|docs/[^)]+)\)", doc.read_text(encoding="utf-8")):
                rel = match.group(1)
                path = ROOT / rel
                if not path.exists():
                    missing.append(f"{doc.name}:{rel}")
        self.assertEqual(missing, [])

    def test_example_config_keys(self):
        cfg = json.loads((OPS / "config.example.json").read_text(encoding="utf-8"))
        required = {
            "ssid", "bind_ip", "bind_port", "host", "testiface_port", "ssh_port",
            "identity_file", "sshd_cmd", "expected_ack_hex", "verify_uid_needle",
        }
        self.assertTrue(required.issubset(cfg))
        self.assertEqual(cfg["bind_port"], 7878)
        self.assertIn("sshd_config_readonly", cfg["sshd_cmd"])
        self.assertIn("82e30101", cfg["expected_ack_hex"].replace(" ", "").lower())


if __name__ == "__main__":
    raise SystemExit(unittest.main(verbosity=2))
