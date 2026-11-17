# SwapSignal

A tiny alert bot for Canadian drivers. It pushes a notification to your phone when:

1. **It's time to book your winter tire swap.** The forecast shows 3+ days in a row with a mean temperature under 7 °C (the usual rule of thumb). Data comes from [Open-Meteo](https://open-meteo.com), which is free and needs no API key. You get one alert per season.
2. **Your shop has an opening.** A headless browser checks one shop's online booking page and alerts you to new slots, including cancellations that free up a slot again.

Every alert has a **Book now** button. Push goes through [ntfy.sh](https://ntfy.sh), which is free and needs no account.

## Try it in 10 seconds

```bash
python3 first_step.py "H2Y 1C6"    # stdlib only: prints the first day of the 7 °C streak
```

## Set up

```bash
python3.12 -m venv .venv   # Python 3.10+ && .venv/bin/pip install --require-hashes -r requirements-dev.txt
cp config.example.json config.json   # edit it; config.json is git-ignored
.venv/bin/python -m swapsignal forecast --dry-run
.venv/bin/python -m swapsignal shops --dry-run --channel chrome   # uses your installed Chrome
```

Install the **ntfy** app (iOS or Android). Create your topic name with `python -m swapsignal new-topic`, then subscribe to it in the app. Anyone who knows the topic can read your alerts or send you fake ones, so SwapSignal rejects short or guessable names. Then send a test with `python -m swapsignal test-push`.

| Setting | Default | Meaning |
|---|---|---|
| `location` | — | Full postal code (`H2Y 1C6`), city (`Laval`), or `lat,lon` |
| `threshold_c` | `7` | Temperature that counts as "cold" |
| `streak_days` | `3` | Days in a row under the threshold |
| `metric` | `mean` | Daily `mean`, or `max` for a stricter "even afternoons are cold" rule |
| `forecast_days` | `10` | How far ahead to look (max 16) |
| `book_url` | — | Where the forecast alert's Book now button goes |

Environment variables override the file: `SWAP_LOCATION`, `NTFY_TOPIC`, `NTFY_TOKEN`, `BOOK_URL`, and `SWAPSIGNAL_CONFIG` (a whole config as JSON).

## Watching a shop's booking page

Every shop's booking page is different, so you describe yours in `shops`:

- `url`: the booking page
- `clicks`: selectors to click before slots appear, e.g. `"text=Winter tire changeover"` or `"button:has-text('Next')"`
- `slot_selector`: matches **one element per open slot**, e.g. `.time-slot:not(.disabled)`
- `include` (optional): a regex the slot text must match, e.g. `"Sat|Sun"` for weekends only

To find the selectors, open the page in Chrome, right-click an open time slot and choose **Inspect**. Run `shops --dry-run` until it lists the slots you expect. The first run alerts you to everything already open; after that you only hear about new slots. If a page fails 3 checks in a row, you get one "can't read" push. That usually means the layout changed.

Phone- or chat-only booking can't be watched. The forecast alert still works.

## Run it automatically (GitHub Actions)

The included workflow runs the forecast check daily and the shop check every 2 hours. State is kept in the Actions cache, not in the repo. Add these repo **secrets**:

| Secret | Example |
|---|---|
| `SWAP_LOCATION` | `H2Y 1C6` |
| `NTFY_TOPIC` | `swapsignal-x7k2q9…` |
| `NTFY_TOKEN` | optional: an ntfy access token, if your topic is reserved |
| `BOOK_URL` | your shop's booking link |
| `SWAPSIGNAL_CONFIG` | optional: `{"shops":[…]}` as JSON |

Then add the repo **variable** `SWAPSIGNAL_ENABLED` = `true` to turn on the schedule. Until then it stays off, so you won't get daily failure emails. You can also start it by hand from **Actions → SwapSignal → Run workflow**. GitHub pauses scheduled workflows after 60 days without repo activity, and you can disable the workflow after your swap.

## Security

Personal values are hidden in the public Actions logs, and the saved state holds no plaintext. Dependencies and actions are pinned and audited. Details and recommended repo settings are in [SECURITY.md](SECURITY.md).

## Tests

```bash
PLAYWRIGHT_CHANNEL=chrome .venv/bin/python -m pytest -q
```

The browser tests drive real Chromium against a local fixture page with click-to-reveal slots.
