"""Configuration: defaults < config.json < SWAPSIGNAL_CONFIG env JSON < single env vars.

Personal values (postal code, ntfy topic, your shop's URL) belong in env vars /
GitHub secrets, not in a committed file.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, Optional

DEFAULTS: Dict[str, Any] = {
    "location": "",            # "H2X 1Y4", "Montreal", or "45.51,-73.57"
    "threshold_c": 7.0,        # rule of thumb: swap once temps stay below 7 °C
    "streak_days": 3,          # how many days in a row must stay under it
    "metric": "mean",          # daily "mean", "max" (conservative) or "min"
    "forecast_days": 10,       # Open-Meteo allows up to 16
    "ntfy_server": "https://ntfy.sh",
    "ntfy_topic": "",
    "book_url": "",            # where the "Book now" button goes
    "shops": [],               # see config.example.json
}

ENV_MAP = {
    "SWAP_LOCATION": "location",
    "NTFY_TOPIC": "ntfy_topic",
    "NTFY_SERVER": "ntfy_server",
    "BOOK_URL": "book_url",
}


def load(path: Optional[str] = None, env: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    env = dict(os.environ) if env is None else env
    cfg = dict(DEFAULTS)
    file = Path(path or env.get("SWAPSIGNAL_CONFIG_FILE", "config.json"))
    if file.is_file():
        cfg.update(json.loads(file.read_text(encoding="utf-8")))
    if env.get("SWAPSIGNAL_CONFIG", "").strip():
        cfg.update(json.loads(env["SWAPSIGNAL_CONFIG"]))
    for var, key in ENV_MAP.items():
        if env.get(var, "").strip():
            cfg[key] = env[var].strip()
    cfg["threshold_c"] = float(cfg["threshold_c"])
    cfg["streak_days"] = int(cfg["streak_days"])
    cfg["forecast_days"] = max(1, min(16, int(cfg["forecast_days"])))
    server = str(cfg["ntfy_server"]).rstrip("/")
    if not (server.startswith("https://") or re.match(r"^http://(localhost|127\.0\.0\.1)(:\d+)?$", server)):
        raise ValueError("ntfy_server must use https:// (your topic and token are sent to it)")
    for sh in cfg["shops"]:
        schemes = ("https://", "http://") + (("file://",) if env.get("SWAPSIGNAL_ALLOW_FILE_URLS") == "1" else ())
        if not str(sh.get("url", "")).startswith(schemes):
            raise ValueError(f"shop url must be http(s): {sh.get('url')!r}")
    check_topic(cfg["ntfy_topic"])
    if cfg["metric"] not in ("mean", "max", "min"):
        raise ValueError("metric must be mean, max or min")
    return cfg


def check_topic(topic: str) -> None:
    """A public ntfy topic is effectively a password: anyone who knows it can send you
    (fake) alerts with phishing links, or read yours. Require a long random one."""
    if not topic:
        return
    if not re.fullmatch(r"[A-Za-z0-9_-]{24,64}", topic) or len(set(topic)) < 12:
        raise ValueError(
            "ntfy topic is too guessable: use 24+ random letters/digits "
            "(run `python -m swapsignal new-topic` to generate one)")
