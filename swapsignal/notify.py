"""Phone push through ntfy.sh (install the ntfy app and subscribe to your topic)."""
from __future__ import annotations

import os
from typing import List, Optional

import requests


def build(topic: str, title: str, message: str, click: str = "", tags: Optional[List[str]] = None,
          priority: int = 4) -> dict:
    body = {"topic": topic, "title": title, "message": message, "priority": priority,
            "tags": tags or []}
    if click:
        body["click"] = click
        body["actions"] = [{"action": "view", "label": "Book now", "url": click, "clear": True}]
    return body


def send(server: str, body: dict, dry_run: bool = False, timeout: float = 15) -> None:
    if dry_run or not body.get("topic"):
        why = "dry run" if dry_run else "no NTFY_TOPIC set"
        print(f"[push skipped: {why}] {body['title']}\n{body['message']}")
        return
    # JSON publishing keeps UTF-8 (°C, accents) intact; headers would not.
    # Anyone who knows a public topic can read it; a token locks it down (ntfy access control).
    token = os.environ.get("NTFY_TOKEN", "").strip()
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    r = requests.post(server.rstrip("/"), json=body, headers=headers, timeout=timeout)
    r.raise_for_status()
    print(f"[pushed] {body['title']}")
