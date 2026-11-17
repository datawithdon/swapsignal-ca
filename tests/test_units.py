import json
from datetime import date

import pytest

from swapsignal import config, geo, notify, shop, state


def test_config_layers(tmp_path):
    f = tmp_path / "c.json"
    f.write_text(json.dumps({"threshold_c": 5, "location": "Laval"}))
    env = {"SWAPSIGNAL_CONFIG": '{"streak_days": 4}', "SWAP_LOCATION": "H2X 1Y4", "NTFY_TOPIC": " swapsignal-Q7mX2pL9vR4tK8wN3bZ6cJ1h "}
    c = config.load(str(f), env)
    assert c["threshold_c"] == 5.0 and c["streak_days"] == 4
    assert c["location"] == "H2X 1Y4" and c["ntfy_topic"] == "swapsignal-Q7mX2pL9vR4tK8wN3bZ6cJ1h" and c["metric"] == "mean"


def test_config_bad_metric(tmp_path):
    with pytest.raises(ValueError):
        config.load(str(tmp_path / "none.json"), {"SWAPSIGNAL_CONFIG": '{"metric": "avg"}'})


def test_latlon_and_postal():
    assert geo.parse_latlon("45.5, -73.6") == (45.5, -73.6)
    assert geo.parse_latlon("Montreal") is None
    with pytest.raises(ValueError):
        geo.parse_latlon("95,0")
    assert geo.POSTAL_RE.match("h2x1y4") and geo.normalize_postal("h2x1y4") == "H2X 1Y4"
    assert geo.geocode("45.5,-73.6")[:2] == (45.5, -73.6)
    with pytest.raises(ValueError):
        geo.geocode("  ")


def test_season():
    assert state.season(date(2026, 11, 16)) == "2026-27"
    assert state.season(date(2027, 3, 1)) == "2026-27"
    assert state.season(date(2027, 7, 1)) == "2027-28"


def test_state_roundtrip_and_corrupt(tmp_path):
    p = tmp_path / "s" / "state.json"
    state.save(str(p), {"a": 1})
    assert state.load(str(p)) == {"a": 1}
    p.write_text("{nope")
    assert state.load(str(p)) == {}


def test_slots_clean_and_diff():
    raw = ["  Sat Nov 21\n 9:00 ", "Sat Nov 21 9:00", "Tue Nov 24 14:00", ""]
    assert shop.clean_slots(raw) == ["Sat Nov 21 9:00", "Tue Nov 24 14:00"]
    assert shop.clean_slots(raw, include="sat") == ["Sat Nov 21 9:00"]
    assert shop.diff(["a", "b", "c"], ["b"]) == ["a", "c"]


def test_notify_build_and_skip(capsys):
    b = notify.build("topic", "T", "−3 °C", click="https://x.test/book")
    assert b["actions"][0]["url"] == "https://x.test/book" and b["click"] == "https://x.test/book"
    assert "actions" not in notify.build("t", "T", "m")
    notify.send("https://ntfy.sh", notify.build("", "T", "m"))
    assert "no NTFY_TOPIC" in capsys.readouterr().out


def test_rejects_plain_http_ntfy_and_file_shop_urls(tmp_path):
    none = str(tmp_path / "none.json")
    with pytest.raises(ValueError):
        config.load(none, {"NTFY_SERVER": "http://ntfy.example.com"})
    assert config.load(none, {"NTFY_SERVER": "http://localhost:8080"})
    with pytest.raises(ValueError):
        config.load(none, {"SWAPSIGNAL_CONFIG": '{"shops":[{"url":"file:///etc/passwd","slot_selector":"a"}]}'})


def test_slot_text_is_capped():
    out = shop.clean_slots(["x" * 5000] + [f"s{i}" for i in range(500)])
    assert len(out[0]) == shop.MAX_SLOT_CHARS and len(out) == shop.MAX_SLOTS


def test_ntfy_token_header(monkeypatch):
    sent = {}
    monkeypatch.setenv("NTFY_TOKEN", "tk_abc")
    monkeypatch.setattr(notify.requests, "post", lambda url, json, headers, timeout: sent.update(headers) or type("R", (), {"raise_for_status": lambda s: None})())
    notify.send("https://ntfy.sh", notify.build("t", "T", "m"))
    assert sent == {"Authorization": "Bearer tk_abc"}


def test_topic_must_be_strong(tmp_path):
    none = str(tmp_path / "none.json")
    for weak in ("t", "swapsignal", "my-tires", "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", "<run: python -m swapsignal new-topic>"):
        with pytest.raises(ValueError):
            config.load(none, {"NTFY_TOPIC": weak})
    from swapsignal.__main__ import new_topic
    t1, t2 = new_topic(), new_topic()
    assert t1 != t2 and config.load(none, {"NTFY_TOPIC": t1})["ntfy_topic"] == t1


def test_links_stripped_from_page_text():
    raw = ["Sat 9:00 book at https://evil.example/x", "Sun 10:00 www.phish.io now",
           "Mon 8:00 go to tire-deals.ca/promo", "Tue 14:00 javascript:alert(1)//x", "Wed 9:30"]
    out = shop.clean_slots(raw)
    assert all(bad not in " ".join(out) for bad in ("evil", "phish", "tire-deals", "javascript:"))
    assert out[-1] == "Wed 9:30" and "[link removed]" in out[0]


def test_chrome_launched_with_sandbox_and_no_downloads(monkeypatch):
    import sys, types
    seen = {}

    class Page:
        def set_default_timeout(self, t): pass
        def goto(self, *a, **k): pass
        def wait_for_selector(self, *a, **k): pass
        def locator(self, sel):
            return types.SimpleNamespace(all_inner_texts=lambda: ["Sat 9:00"])

    class Browser:
        def new_page(self, **k): seen["page"] = k; return Page()
        def close(self): pass

    class PW:
        chromium = types.SimpleNamespace(launch=lambda **k: seen.setdefault("launch", k) and Browser())
        def __enter__(self): return self
        def __exit__(self, *a): pass

    fake = types.ModuleType("playwright.sync_api")
    fake.sync_playwright = PW
    fake.TimeoutError = TimeoutError
    monkeypatch.setitem(sys.modules, "playwright.sync_api", fake)
    slots, _ = shop.scrape({"url": "https://x.test", "slot_selector": "li"})
    assert seen["launch"]["chromium_sandbox"] is True
    assert seen["page"] == {"accept_downloads": False}
    assert slots == ["Sat 9:00"]


def test_sandbox_failure_is_refused_not_bypassed(monkeypatch):
    import sys, types

    def boom(**k):
        raise Exception("No usable sandbox! ...")

    class PW:
        chromium = types.SimpleNamespace(launch=boom)
        def __enter__(self): return self
        def __exit__(self, *a): pass

    fake = types.ModuleType("playwright.sync_api")
    fake.sync_playwright, fake.TimeoutError = PW, TimeoutError
    monkeypatch.setitem(sys.modules, "playwright.sync_api", fake)
    with pytest.raises(RuntimeError, match="NOT opened"):
        shop.scrape({"url": "https://x.test", "slot_selector": "li"})
