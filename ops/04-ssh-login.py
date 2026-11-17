"""对照 docs/04-公钥登录.md。经 7878 ProxyCommand 公钥登录并核对 uid＝0。"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

OPS = Path(__file__).resolve().parent
if str(OPS) not in sys.path:
    sys.path.insert(0, str(OPS))
from config import load_config
from wait_7878 import wait_free


def main() -> int:
    cfg = load_config()
    parser = argparse.ArgumentParser()
    parser.add_argument("remote", nargs="?", default=cfg["verify_remote"])
    parser.add_argument("--json-output", type=Path)
    parser.add_argument("--skip-wait", action="store_true")
    args = parser.parse_args()
    if not cfg["identity_path"].exists():
        report = {"error": f"missing private key {cfg['identity_path']}", "identity_verified": False}
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 2
    if not cfg["known_hosts_path"].is_file():
        report = {"error": "Configure a trusted known_hosts file before connecting; see ssh/README.md", "identity_verified": False}
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 2
    if not args.skip_wait:
        waited = wait_free(cfg["bind_ip"], int(cfg["bind_port"]), float(cfg["time_wait_s"]))
        if not waited["free"]:
            report = {"error": "bind_port still occupied", "wait": waited, "identity_verified": False}
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 2
    python = sys.executable
    proxy = cfg["root"] / "ops" / "04-bind7878-proxy.py"
    cmd = [
        "ssh.exe",
        "-i",
        str(cfg["identity_path"]),
        "-o",
        "IdentitiesOnly=yes",
        "-o",
        "BatchMode=yes",
        "-o",
        "PreferredAuthentications=publickey",
        "-p",
        str(cfg["ssh_port"]),
        "-o",
        f"ConnectTimeout={int(cfg['ssh_timeout_s'])}",
        "-o",
        "StrictHostKeyChecking=yes",
        "-o",
        f"UserKnownHostsFile={cfg['known_hosts_path']}",
        "-o",
        "GlobalKnownHostsFile=NUL",
        "-o",
        f"ProxyCommand={python} {proxy} %h %p",
        f"{cfg['ssh_user']}@{cfg['host']}",
        args.remote,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    report = {
        "rc": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "identity_verified": cfg["verify_uid_needle"] in proc.stdout and proc.returncode == 0,
    }
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if report["identity_verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
