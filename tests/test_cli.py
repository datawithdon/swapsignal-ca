import json
from datetime import date

from swapsignal import __main__ as cli
from swapsignal.forecast import Day

TODAY = date(2026, 11, 16)


def run(tmp_path, monkeypatch, temps, *extra):
    monkeypatch.setattr(cli.forecast, "fetch", lambda *a, **k: [Day(f"2026-11-{16 + i}", t) for i, t in enumerate(temps)])
    pushed = []
    monkeypatch.setattr(cli.notify.requests, "post", lambda url, json, timeout, headers=None: pushed.append(json) or type("R", (), {"raise_for_status": lambda s: None})())
    monkeypatch.setenv("SWAP_LOCATION", "45.5,-73.6")
    monkeypatch.setenv("NTFY_TOPIC", "swapsignal-Q7mX2pL9vR4tK8wN3bZ6cJ1h")
    monkeypatch.setenv("SWAPSIGNAL_CONFIG_FILE", str(tmp_path / "none.json"))
    st = tmp_path / "state.json"
    code = cli.main(["forecast", "--state", str(st), *extra], today=TODAY)
    return code, pushed, json.loads(st.read_text())


def test_alerts_once_per_season(tmp_path, monkeypatch):
    code, pushed, st = run(tmp_path, monkeypatch, [1.4, 3.7, 6.9, 8.0])
    assert code == 0 and len(pushed) == 1
    assert "today" in pushed[0]["message"] and st["forecast"]["alerted_season"] == "2026-27"
    _, pushed2, _ = run(tmp_path, monkeypatch, [1.4, 3.7, 6.9, 8.0])
    assert pushed2 == []
    _, pushed3, _ = run(tmp_path, monkeypatch, [1.4, 3.7, 6.9, 8.0], "--force")
    assert len(pushed3) == 1


def test_no_streak_no_push(tmp_path, monkeypatch):
    code, pushed, st = run(tmp_path, monkeypatch, [9, 8, 6, 6, 10])
    assert code == 0 and pushed == [] and "forecast" not in st


def test_dry_run_does_not_record(tmp_path, monkeypatch):
    _, pushed, st = run(tmp_path, monkeypatch, [1, 1, 1], "--dry-run")
    assert pushed == [] and "alerted_season" not in st.get("forecast", {})


def test_missing_location_is_error(tmp_path, monkeypatch):
    monkeypatch.setattr(cli.notify.requests, "post", lambda *a, **k: None)
    monkeypatch.delenv("SWAP_LOCATION", raising=False)
    monkeypatch.setenv("SWAPSIGNAL_CONFIG_FILE", str(tmp_path / "none.json"))
    assert cli.main(["forecast", "--state", str(tmp_path / "s.json")], today=TODAY) == 2


def test_ci_masks_location_and_keeps_no_coordinates(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli, "IN_CI", True)
    monkeypatch.setattr(cli.geo, "geocode", lambda loc: (45.509, -73.569, "H2Y 1C6"))
    monkeypatch.setenv("NTFY_TOKEN", "tk_secret")
    _, _, st = run(tmp_path, monkeypatch, [9, 9, 9])
    out = capsys.readouterr().out
    for v in ("H2Y 1C6", "45.509", "-73.569", "tk_secret", "swapsignal-Q7mX2pL9vR4tK8wN3bZ6cJ1h"):
        assert f"::add-mask::{v}" in out
    assert "geo" not in st and "45.509" not in json.dumps(st)
