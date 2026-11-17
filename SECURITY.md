# Security notes

## What's protected and how

| Risk | Mitigation |
|---|---|
| **Actions logs are public on a public repo**, and would show your area, shop and slots | Postal code, place name, coordinates, ntfy topic/token, shop names and URLs are hidden with `::add-mask::`. In CI, slot lists aren't printed, only counts. |
| **The state cache could be read** by a workflow added in a pull request from a fork | State holds no coordinates (geocoded each run) and no plaintext shop or slot names, only HMAC hashes keyed by your ntfy topic. |
| Install steps (pip, Playwright) running code while secrets are in the environment | Secrets are only given to the single `Run` step. |
| A moved or hijacked action tag | Every action is pinned to a full commit SHA; Dependabot updates them. |
| Vulnerable or tampered dependencies | All packages hash-locked (`--require-hashes`), including pip-audit, which runs in its own venv and fails the job on any known vulnerability. Weekly Dependabot updates. CI uses the runner's preinstalled Google Chrome, so there's no browser download. |
| The checkout token being reused by later steps | `persist-credentials: false`, `permissions: contents: read`. |
| Someone reading or spoofing your ntfy topic | Use a long random topic. For full lock-down, use an ntfy account with an access token (`NTFY_TOKEN`). The server must be `https://`. |
| Hostile text on a booking page | Slot text is capped at 120 characters and 200 slots, and is sent as plain text. |
| Local files read through the shop watcher | `file://` shop URLs are rejected (they're only allowed in tests). |

## Your own computer

- **No open ports and no background process.** SwapSignal runs only when you start it, and the schedule runs on GitHub's servers, not your Mac.
- **No shell commands, `eval`, pickle or YAML loading.** Config and state are plain JSON.
- **Browser isolation:** the shop watcher starts Chrome with its **sandbox on** (Playwright turns it off by default). It uses a **throwaway profile**, never your real Chrome cookies or logins, and **downloads are disabled**.
- **The Book now button only opens URLs from your own config**, never links taken from a web page.
- **Hash-locked dependencies:** `pip install --require-hashes` refuses any package file that doesn't match the hash pinned in `requirements.txt`.
- **Fake pushes:** anyone who knows your ntfy topic can send you a notification. SwapSignal refuses weak topic names; `python -m swapsignal new-topic` generates a 32-character random one, which can't practically be guessed. Before tapping a link, check that it goes to your shop's real website.
- **No links from web pages:** web addresses in slot text (`https://…`, `www…`, `name.ca/…`, `javascript:`…) are replaced with `[link removed]`, so a hacked booking page can't put a tappable link in your push.
- **The sandbox is never skipped:** if Chrome's sandbox can't start, SwapSignal refuses to open the page rather than falling back to `--no-sandbox`.

## Recommended repo settings (public repo)

- Settings → Actions → General → **Fork pull request workflows**: "Require approval for all external contributors".
- Settings → Code security: enable **secret scanning + push protection**, **Dependabot alerts**, and **private vulnerability reporting**.

## Reporting

Please use GitHub's private vulnerability reporting on this repo rather than a public issue.
