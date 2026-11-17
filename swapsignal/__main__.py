"""SwapSignal CLI.

  python -m swapsignal forecast     # check for a cold streak, push once per season
  python -m swapsignal shops        # check watched shop pages, push on new slots
  python -m swapsignal test-push    # send a test notification
  python -m swapsignal new-topic    # print a strong random ntfy topic name
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import os
import secrets
import sys
from datetime import date, datetime
from typing import List, Optional

from . import config, forecast, geo, notify, shop, state

BROKEN_AFTER = 3  # consecutive scrape failures before a "watcher broken" push


def _fmt_day(iso: str) -> str:
    d = datetime.strptime(iso, "%Y-%m-%d")
    return f"{d:%a %b} {d.day}"


IN_CI = os.environ.get("GITHUB_ACTIONS") == "true"


def mask(*values) -> None:
    """Hide personal values in GitHub Actions logs (public on public repos)."""
    if not IN_CI:
        return
    for v in values:
        for line in str(v or "").splitlines():
            if line.strip() and len(line.strip()) >= 3:
                print(f"::add-mask::{line.strip()}", flush=True)


def _h(cfg, text: str) -> str:
    """Keyed hash so the saved state holds no shop names or slot text."""
    key = (cfg.get("ntfy_topic") or "swapsignal").encode()
    return hmac.new(key, text.encode(), hashlib.sha256).hexdigest()[:24]


def _coords(cfg, st):
    # Not cached: coordinates would pinpoint you, and the state file can leak (see SECURITY.md).
    st.pop("geo", None)
    lat, lon, label = geo.geocode(cfg["location"])
    mask(label, *label.split(", "), f"{lat}", f"{lon}")
    return lat, lon, label


def cmd_forecast(cfg, st, args, today: date) -> int:
    lat, lon, label = _coords(cfg, st)
    days = forecast.fetch(lat, lon, cfg["metric"], cfg["forecast_days"])
    thr, n = cfg["threshold_c"], cfg["streak_days"]
    print(f"Daily {cfg['metric']} temperature, {label}:")
    for d in days:
        t = "  n/a" if d.temp is None else f"{d.temp:5.1f}"
        print(f"  {d.date}  {t} °C {'❄' if d.temp is not None and d.temp < thr else ''}")
    streak = forecast.find_streak(days, thr, n)
    if not streak:
        print(f"No {n}-day streak under {thr:g} °C in the next {len(days)} days.")
        return 0
    first = f"today ({_fmt_day(streak.start)})" if streak.start == today.isoformat() else _fmt_day(streak.start)
    length = f"{len(streak.days)}+" if streak.open_ended else str(len(streak.days))
    print(f"Cold streak: {length} days under {thr:g} °C starting {first}.")

    season = state.season(today)
    fs = st.setdefault("forecast", {})
    if fs.get("alerted_season") == season and not args.force:
        print(f"Already alerted this season ({season}, streak from {fs.get('streak_start')}); not pushing again.")
        return 0
    temps = ", ".join(f"{d.temp:.0f}" for d in streak.days[:5])
    msg = (f"{length} days in a row under {thr:g} °C starting {first} near {label} "
           f"({cfg['metric']} temps {temps} °C).\n"
           "Shops fill up fast after the first cold snap. Book your winter tire swap this week.")
    notify.send(cfg["ntfy_server"], notify.build(
        cfg["ntfy_topic"], "Time to book your winter tire swap", msg,
        click=cfg["book_url"], tags=["snowflake", "car"]), dry_run=args.dry_run)
    if not args.dry_run:
        fs.update(alerted_season=season, streak_start=streak.start, alerted_on=today.isoformat())
    return 0


def cmd_shops(cfg, st, args, today: date) -> int:
    shops = [s for s in cfg["shops"] if s.get("enabled", True)]
    if not shops:
        print("No shops configured (add one under \"shops\" in your config).")
        return 0
    channel = args.channel or os.environ.get("PLAYWRIGHT_CHANNEL") or None
    failed = 0
    all_state = st.setdefault("shops", {})
    for s in shops:
        name = s.get("name") or s["url"]
        ss = all_state.setdefault(_h(cfg, "shop:" + name), {})
        try:
            slots, status = shop.scrape(s, channel)
        except Exception as e:  # pages change; keep other shops running
            failed += 1
            ss["fail_count"] = ss.get("fail_count", 0) + 1
            print(f"[{name}] scrape failed ({ss['fail_count']}x): {type(e).__name__}: {e}", file=sys.stderr)
            if ss["fail_count"] == BROKEN_AFTER:
                notify.send(cfg["ntfy_server"], notify.build(
                    cfg["ntfy_topic"], f"SwapSignal can't read {name}",
                    f"The booking page failed {BROKEN_AFTER} checks in a row. "
                    "Its layout probably changed; update slot_selector/clicks.",
                    click=s["url"], tags=["warning"], priority=3), dry_run=args.dry_run)
            continue
        ss["fail_count"] = 0
        first_run = "seen" not in ss
        seen = set(ss.get("seen", []))
        new = [x for x in slots if _h(cfg, x) not in seen]
        print(f"[{name}] {status}: {len(slots)} open slot(s), {len(new)} new" + (" (first run)" if first_run else ""))
        for x in ([] if IN_CI else slots[:10]):
            print(f"    {'NEW ' if x in new else '    '}{x}")
        if new:
            shown = "\n".join(f"• {x}" for x in new[:6])
            more = f"\n…and {len(new) - 6} more" if len(new) > 6 else ""
            title = f"{len(new)} open slot{'s' if len(new) != 1 else ''} at {name}"
            notify.send(cfg["ntfy_server"], notify.build(
                cfg["ntfy_topic"], title, shown + more,
                click=s.get("book_url") or s["url"], tags=["calendar", "car"], priority=5 if not first_run else 4),
                dry_run=args.dry_run)
        if not args.dry_run:
            ss["seen"] = [_h(cfg, x) for x in slots]
            ss["checked_at"] = datetime.now().isoformat(timespec="minutes")
    return 1 if failed else 0


def cmd_test_push(cfg, st, args, today: date) -> int:
    notify.send(cfg["ntfy_server"], notify.build(
        cfg["ntfy_topic"], "SwapSignal test", "Push works. You'll hear from me when it's time to swap.",
        click=cfg["book_url"], tags=["white_check_mark"]), dry_run=args.dry_run)
    return 0


def new_topic() -> str:
    return "swapsignal-" + secrets.token_urlsafe(24).replace("_", "x").replace("-", "y")


def main(argv: Optional[List[str]] = None, today: Optional[date] = None) -> int:
    ap = argparse.ArgumentParser(prog="swapsignal", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["forecast", "shops", "test-push", "new-topic"])
    ap.add_argument("--config", help="config JSON (default: config.json if present)")
    ap.add_argument("--state", default=os.environ.get("SWAPSIGNAL_STATE", ".state/state.json"))
    ap.add_argument("--dry-run", action="store_true", help="print instead of pushing; don't update state")
    ap.add_argument("--force", action="store_true", help="forecast: push even if already alerted this season")
    ap.add_argument("--channel", help="shops: browser channel, e.g. 'chrome' to use installed Chrome")
    args = ap.parse_args(argv)
    if args.command == "new-topic":
        print(new_topic())
        return 0

    try:
        cfg = config.load(args.config)
    except ValueError as e:
        print(f"config error: {e}", file=sys.stderr)
        return 2
    mask(cfg["location"], cfg["ntfy_topic"], cfg["book_url"], os.environ.get("NTFY_TOKEN"))
    if geo.POSTAL_RE.match(cfg["location"].strip()):
        mask(geo.normalize_postal(cfg["location"]), cfg["location"].replace(" ", ""))
    for sh in cfg["shops"]:
        mask(sh.get("name"), sh.get("url"), sh.get("book_url"))
    st = state.load(args.state)
    today = today or date.today()
    fn = {"forecast": cmd_forecast, "shops": cmd_shops, "test-push": cmd_test_push}[args.command]
    try:
        code = fn(cfg, st, args, today)
    except (ValueError, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        code = 2
    state.save(args.state, st)
    return code


if __name__ == "__main__":
    sys.exit(main())
