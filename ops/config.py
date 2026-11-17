"""Load ops/config.json (copy of config.example.json). Paths relative to repo root."""
from __future__ import annotations

import json
import ipaddress
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OPS = Path(__file__).resolve().parent
CONFIG_PATH = OPS / "config.json"
EXAMPLE_PATH = OPS / "config.example.json"


def load_config(path: Path | None = None) -> dict:
    target = path or CONFIG_PATH
    if not target.is_file():
        raise ValueError("Copy ops/config.example.json to ops/config.json and fill in ssid, bind_ip and host before connecting")
    data = json.loads(target.read_text(encoding="utf-8"))
    for field in ("ssid", "bind_ip", "host"):
        if not isinstance(data.get(field), str) or not data[field].strip():
            raise ValueError(f"Fill in {field} in ops/config.json before connecting")
    for field in ("bind_ip", "host"):
        if ipaddress.ip_address(data[field]).version != 4:
            raise ValueError(f"{field} must be an IPv4 address")
    identity = ROOT / data["identity_file"]
    known = ROOT / data["known_hosts"]
    data["root"] = ROOT
    data["config_path"] = target
    data["identity_path"] = identity
    data["known_hosts_path"] = known
    return data
