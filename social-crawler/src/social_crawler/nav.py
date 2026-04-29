"""Sidebar Home reset — return to the platform's clean homepage via a real
DOM click (CDP trusted), not via `page.goto(homepage_url)`.

Public demo scope: TikTok + Twitter (X). The paid version adds Facebook
top-nav and Instagram sidebar resets, plus modal/dialog cleanup heuristics
tuned per platform.

Why
---
Each spider expects to start from the platform homepage and triggers the
search popup → fills query → clicks typeahead. If the user-launched Chrome
tab is on a sub-route, the spider needs to navigate back without using
`page.goto(...)` — programmatic navigation servers can detect.

Each platform's sidebar / top nav has a Home button that fires a SPA
`pushState` (URL becomes `/` or `/home`) without a fresh document fetch.
Clicking it via `page.locator(...).click()` goes through CDP
`Input.dispatchMouseEvent` with `isTrusted=true`.
"""
from __future__ import annotations

import logging
from typing import Optional

from playwright.async_api import Page, TimeoutError as PWTimeout

logger = logging.getLogger(__name__)


# TikTok sidebar nav selectors (data-e2e attribute is stable across UI changes).
TIKTOK_SIDEBAR_NAV: dict[str, str] = {
    "logo": 'a[data-e2e="tiktok-logo"]',
    "foryou": 'a[data-e2e="nav-foryou"]',
    "explore": 'a[data-e2e="nav-explore"]',
    "following": 'a[data-e2e="nav-following"]',
    "messages": 'a[data-e2e="nav-messages"]',
    "profile": 'a[data-e2e="nav-profile"]',
}

# Twitter (X) sidebar selectors (data-testid is stable).
TWITTER_SIDEBAR_NAV: dict[str, str] = {
    "logo": 'header[role="banner"] a[href="/home"][aria-label="X"]',
    "home": '[data-testid="AppTabBar_Home_Link"]',
    "explore": '[data-testid="AppTabBar_Explore_Link"]',
    "notifications": '[data-testid="AppTabBar_Notifications_Link"]',
    "messages": '[data-testid="AppTabBar_DirectMessage_Link"]',
    "profile": '[data-testid="AppTabBar_Profile_Link"]',
}


async def reset_tiktok_to_home(page: Page, *, timeout_ms: int = 10_000) -> bool:
    """SPA-navigate to tiktok.com/ via sidebar For You click."""
    if "tiktok.com" not in page.url:
        logger.warning("Not on tiktok.com (url=%s); skipping reset", page.url)
        return False

    sel = TIKTOK_SIDEBAR_NAV["foryou"]
    try:
        await page.locator(sel).first.click(timeout=timeout_ms)
        await page.wait_for_url("**/", timeout=5_000)
        logger.info("Reset to TikTok / OK: %s", page.url)
        return True
    except (PWTimeout, Exception) as exc:
        u = page.url.rstrip("/")
        if u in ("https://www.tiktok.com", "http://www.tiktok.com"):
            return True
        logger.warning("TikTok sidebar click failed: %s", exc)
        return False


async def reset_twitter_to_home(page: Page, *, timeout_ms: int = 10_000) -> bool:
    """SPA-navigate to x.com/home via sidebar Home click."""
    if "x.com" not in page.url and "twitter.com" not in page.url:
        logger.warning("Not on x.com/twitter.com (url=%s); skipping reset", page.url)
        return False

    sel = TWITTER_SIDEBAR_NAV["home"]
    try:
        await page.locator(sel).first.click(timeout=timeout_ms)
        await page.wait_for_url("**/home", timeout=5_000)
        logger.info("Reset to X /home OK: %s", page.url)
        return True
    except (PWTimeout, Exception) as exc:
        if page.url.endswith("/home") or "/home?" in page.url:
            return True
        logger.warning("X sidebar Home click failed: %s", exc)
        return False


def is_clean_homepage(url: str, platform: str) -> bool:
    """Strict check: URL is the platform's canonical homepage."""
    if platform == "twitter":
        u = url.split("?")[0].rstrip("/")
        return u in ("https://x.com/home", "https://twitter.com/home")
    if platform == "tiktok":
        u = url.rstrip("/")
        return u in ("https://www.tiktok.com", "http://www.tiktok.com")
    return False


async def find_or_reset_homepage_page(ctx, platform: str) -> Optional[Page]:
    """Find a Chrome tab on this platform; reset to homepage if needed.

    1. If any tab is already on the canonical homepage URL → return it
    2. Else if any tab is on the platform domain → click sidebar Home
    3. Else → return None (caller raises with a helpful message)
    """
    for p in ctx.pages:
        if is_clean_homepage(p.url, platform):
            return p

    domain_match = {
        "tiktok": "tiktok.com",
        "twitter": ("x.com", "twitter.com"),
    }.get(platform)
    if domain_match is None:
        return None
    domains = (domain_match,) if isinstance(domain_match, str) else domain_match

    for p in ctx.pages:
        if any(d in p.url for d in domains):
            ok = False
            if platform == "tiktok":
                ok = await reset_tiktok_to_home(p)
            elif platform == "twitter":
                ok = await reset_twitter_to_home(p)
            if ok and is_clean_homepage(p.url, platform):
                return p

    return None
