"""Tiny JSON state so you get one alert per event, not one per run."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any, Dict


def load(path: str) -> Dict[str, Any]:
    p = Path(path)
    if p.is_file():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except ValueError:
            pass
    return {}


def save(path: str, data: Dict[str, Any]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


def season(today: date) -> str:
    """Tire season label: July–June, e.g. '2026-27'."""
    y = today.year if today.month >= 7 else today.year - 1
    return f"{y}-{str(y + 1)[2:]}"
