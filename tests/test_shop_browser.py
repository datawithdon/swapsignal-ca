"""Drives a real headless browser against a local fixture page."""
import json
import os
from pathlib import Path

import pytest

from swapsignal import __main__ as cli

pytest.importorskip("playwright")
FIXTURE = (Path(__file__).parent / "fixtures" / "shop.html").resolve().as_uri()
CHANNEL = os.environ.get("PLAYWRIGHT_CHANNEL") or None


def check(tmp_path, monkeypatch, slots):
    cfg = {"shops": [{"name": "Test Garage", "url": f"{FIXTURE}?slots={slots}",
                      "clicks": ["#svc"], "slot_selector": "li.slot.available", "timeout_ms": 8000}]}
    monkeypatch.setenv("SWAPSIGNAL_CONFIG", json.dumps(cfg))
    monkeypatch.setenv("NTFY_TOPIC", "swapsignal-Q7mX2pL9vR4tK8wN3bZ6cJ1h")
    monkeypatch.setenv("SWAPSIGNAL_ALLOW_FILE_URLS", "1")
    monkeypatch.setenv("SWAPSIGNAL_CONFIG_FILE", str(tmp_path / "none.json"))
    pushed = []
    monkeypatch.setattr(cli.notify.requests, "post", lambda url, json, timeout, headers=None: pushed.append(json) or type("R", (), {"raise_for_status": lambda s: None})())
    st = tmp_path / "state.json"
    code = cli.main(["shops", "--state", str(st)] + (["--channel", CHANNEL] if CHANNEL else []))
    return code, pushed, json.loads(st.read_text())


def test_new_slots_alert_then_quiet_then_cancellation(tmp_path, monkeypatch):
    code, pushed, st = check(tmp_path, monkeypatch, "Sat Nov 21 9:00|Tue Nov 24 14:00")
    assert code == 0 and len(pushed) == 1 and "2 open slots" in pushed[0]["title"]
    assert "full" not in pushed[0]["message"]
    (key, saved), = st["shops"].items()
    raw = json.dumps(st)
    assert "Test Garage" not in raw and "Nov 21" not in raw   # no plaintext in saved state
    assert len(saved["seen"]) == 2

    _, pushed, _ = check(tmp_path, monkeypatch, "Sat Nov 21 9:00|Tue Nov 24 14:00")
    assert pushed == []

    _, pushed, _ = check(tmp_path, monkeypatch, "Tue Nov 24 14:00|Wed Nov 18 10:30")
    assert len(pushed) == 1 and pushed[0]["message"] == "• Wed Nov 18 10:30" and pushed[0]["priority"] == 5


def test_broken_page_alerts_after_three_failures(tmp_path, monkeypatch):
    def broken(tmp_path, monkeypatch):
        cfg = {"shops": [{"name": "Gone", "url": FIXTURE, "clicks": ["#does-not-exist"],
                          "slot_selector": "li", "timeout_ms": 1500}]}
        monkeypatch.setenv("SWAPSIGNAL_CONFIG", json.dumps(cfg))
        monkeypatch.setenv("NTFY_TOPIC", "swapsignal-Q7mX2pL9vR4tK8wN3bZ6cJ1h")
        monkeypatch.setenv("SWAPSIGNAL_ALLOW_FILE_URLS", "1")
        monkeypatch.setenv("SWAPSIGNAL_CONFIG_FILE", str(tmp_path / "none.json"))
        pushed = []
        monkeypatch.setattr(cli.notify.requests, "post", lambda url, json, timeout, headers=None: pushed.append(json) or type("R", (), {"raise_for_status": lambda s: None})())
        code = cli.main(["shops", "--state", str(tmp_path / "s.json")] + (["--channel", CHANNEL] if CHANNEL else []))
        return code, pushed
    results = [broken(tmp_path, monkeypatch) for _ in range(4)]
    assert all(code == 1 for code, _ in results)
    assert [len(p) for _, p in results] == [0, 0, 1, 0]
    assert "can't read Gone" in results[2][1][0]["title"]
