"""Watch one shop's booking page for open slots with Playwright.

Each shop's page is different, so you describe it in config:
  url            page that lists slots
  slot_selector  CSS selector matching one element per open slot
  clicks         optional selectors to click first (e.g. "Winter tire changeover", "Next")
  wait_for       optional selector to wait for before reading (defaults to slot_selector)
  include        optional regex a slot's text must match (e.g. "Sat|Sun")
"""
from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional, Tuple


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


# Push apps turn URLs in message text into tappable links; a hacked booking page must
# not be able to put a phishing link in your notification. Only your configured
# Book now URL is ever clickable.
LINK_RE = re.compile(
    r"(?:[a-z][a-z0-9+.-]*://\S+|\b(?:javascript|data|vbscript|file|intent|mailto|tel|sms):\S*|www\.\S+|"
    r"\b[a-z0-9-]+(?:\.[a-z0-9-]+)*\.(?:com|ca|net|org|io|co|app|xyz|info|biz|me|ly|link|"
    r"site|online|top|ru|cn|tk|us|uk|gg|sh|to|cc|dev|page|click|live|shop|store)\b\S*)",
    re.I)
MAX_SLOT_CHARS = 120   # page text is untrusted; keep pushes and logs small
MAX_SLOTS = 200


def clean_slots(raw: Iterable[str], include: Optional[str] = None) -> List[str]:
    pat = re.compile(include, re.I) if include else None
    out: List[str] = []
    for t in raw:
        if len(out) >= MAX_SLOTS:
            break
        t = _norm(LINK_RE.sub("[link removed]", t))[:MAX_SLOT_CHARS]
        if t and t not in out and (pat is None or pat.search(t)):
            out.append(t)
    return out


def diff(current: List[str], seen: List[str]) -> List[str]:
    """Slots that are open now but weren't last time (includes cancellations reopening)."""
    old = set(seen)
    return [s for s in current if s not in old]


def scrape(shop: Dict[str, Any], browser_channel: Optional[str] = None) -> Tuple[List[str], str]:
    """Returns (slots, status). status is 'ok' or 'no-slots-element'."""
    from playwright.sync_api import TimeoutError as PWTimeout, sync_playwright

    timeout = int(shop.get("timeout_ms", 30000))
    with sync_playwright() as p:
        # Playwright disables Chrome's sandbox by default (--no-sandbox). Keep it ON so a
        # hostile or hacked booking page can't escape the browser onto your machine.
        launch = {"headless": True, "chromium_sandbox": True}
        if browser_channel:
            launch["channel"] = browser_channel
        try:
            browser = p.chromium.launch(**launch)
        except Exception as e:
            if "sandbox" in str(e).lower():
                raise RuntimeError(
                    "Chrome's sandbox couldn't start, so the page was NOT opened (SwapSignal never "
                    "runs Chrome without it). On Ubuntu 24.04 allow unprivileged user namespaces: "
                    "sudo sysctl -w kernel.apparmor_restrict_unprivileged_userns=0") from e
            raise
        try:
            # Fresh throwaway profile (no cookies/logins from your real Chrome), no downloads.
            page = browser.new_page(accept_downloads=False)
            page.set_default_timeout(timeout)
            page.goto(shop["url"], wait_until="domcontentloaded")
            for sel in shop.get("clicks", []):
                page.locator(sel).first.click()
                page.wait_for_load_state("networkidle")
            try:
                page.wait_for_selector(shop.get("wait_for") or shop["slot_selector"], state="attached")
            except PWTimeout:
                return [], "no-slots-element"
            texts = page.locator(shop["slot_selector"]).all_inner_texts()
            return clean_slots(texts, shop.get("include")), "ok"
        finally:
            browser.close()
