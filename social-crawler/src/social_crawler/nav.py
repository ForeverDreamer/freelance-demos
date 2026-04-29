"""Sidebar Home reset — return to the platform's clean homepage via a real
DOM click (CDP trusted), not via `page.goto(homepage_url)`.

Why this matters
----------------
Each spider expects to start from a known-good page state (the platform
homepage) and from there triggers the search popup → fills query → clicks
typeahead. If the user-launched Chrome tab is already on a sub-route (e.g.,
`/@someuser`), the spider needs to navigate back without using
`page.goto(...)`, which programmatic navigation servers can detect.

The trick: every platform's sidebar / top nav has a Home button that fires a
SPA `pushState` → URL becomes `/` (or `/home` for Twitter) without firing a
fresh document fetch. Clicking it via `page.locator(...).click()` goes through
CDP `Input.dispatchMouseEvent` with `isTrusted=true`, which servers see as a
real user gesture.

Per-platform selectors (verified 2026-04 against logged-in profiles):

- TikTok: `a[data-e2e="nav-foryou"]` (sidebar For You link)
- Twitter (X): `[data-testid="AppTabBar_Home_Link"]` (sidebar Home link)
- Facebook: `[role="navigation"][aria-label="Facebook"] a[href="/"]`
  (top nav Home link inside the Facebook-labelled nav region)
- Instagram: `a[role="link"]:has(svg[aria-label="Home"])` (sidebar Home link)
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

# Facebook top nav selectors. The aria-label "Facebook" on the navigation
# container is locale-stable (the Chinese Facebook UI still has the English
# aria-label).
FB_TOP_NAV: dict[str, str] = {
    "home": '[role="navigation"][aria-label="Facebook"] a[href="/"]',
    "reels": '[role="navigation"][aria-label="Facebook"] a[href*="/reel/"]',
    "marketplace": '[role="navigation"][aria-label="Facebook"] a[href*="/marketplace"]',
}


async def reset_tiktok_to_home(page: Page, *, timeout_ms: int = 10_000) -> bool:
    """SPA-navigate to tiktok.com/ via sidebar For You click.

    Special case: if the page is on a video detail modal (URL contains
    `/video/` or `/photo/`), the video player overlay intercepts pointer
    events on the sidebar. Click the modal close button first, then click
    the sidebar.
    """
    if "tiktok.com" not in page.url:
        logger.warning("Not on tiktok.com (url=%s); skipping reset", page.url)
        return False

    if "/video/" in page.url or "/photo/" in page.url:
        try:
            await page.locator('[data-e2e="browse-close"]').first.click(timeout=3_000)
            await page.wait_for_url(
                lambda u: "/video/" not in u and "/photo/" not in u,
                timeout=5_000,
            )
            logger.info("Closed TikTok detail modal before sidebar reset")
        except (PWTimeout, Exception) as exc:
            logger.debug("No detail modal to close (or close failed): %s", exc)

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


async def reset_fb_to_home(page: Page, *, timeout_ms: int = 10_000) -> bool:
    """SPA-navigate to facebook.com/ via top-nav Home click."""
    if "facebook.com" not in page.url:
        logger.warning("Not on facebook.com (url=%s); skipping reset", page.url)
        return False

    sel = FB_TOP_NAV["home"]
    try:
        await page.locator(sel).first.click(timeout=timeout_ms)
        await page.wait_for_url(
            lambda url: url.rstrip("/").split("?")[0]
            in ("https://www.facebook.com", "http://www.facebook.com"),
            timeout=5_000,
        )
        logger.info("Reset to FB / OK: %s", page.url)
        return True
    except (PWTimeout, Exception) as exc:
        u = page.url.rstrip("/").split("?")[0]
        if u in ("https://www.facebook.com", "http://www.facebook.com"):
            return True
        logger.warning("FB top-nav Home click failed: %s", exc)
        return False


async def reset_instagram_to_home(page: Page, *, timeout_ms: int = 10_000) -> bool:
    """SPA-navigate to instagram.com/ via sidebar Home click.

    Special case: if a search panel or modal is already open from a prior
    session, click the Close button first (Escape is not reliably bound).
    """
    if "instagram.com" not in page.url:
        logger.warning("Not on instagram.com (url=%s); skipping reset", page.url)
        return False

    # Close any open dialog (search panel / login prompt). Safe no-op if
    # nothing is open.
    try:
        close_btn = (
            page.locator('svg[aria-label="Close"]')
            .first.locator('xpath=ancestor::button | ancestor::a | ancestor::div[@role="button"]')
            .first
        )
        if await close_btn.count() > 0:
            await close_btn.click(timeout=2_000)
            await page.wait_for_function(
                """() => !document.querySelector('[role="dialog"]')""",
                timeout=3_000,
            )
            logger.info("Closed lingering IG dialog before reset")
    except (PWTimeout, Exception) as exc:
        logger.debug("No dialog to close (or close failed): %s", exc)

    home_sel = (
        'a[role="link"]:has(svg[aria-label="Home"]), '
        'a[href="/"]:has(svg[aria-label="Home"])'
    )
    try:
        await page.locator(home_sel).first.click(timeout=timeout_ms)
        await page.wait_for_url(
            lambda url: url.rstrip("/").split("?")[0]
            in ("https://www.instagram.com", "http://www.instagram.com"),
            timeout=5_000,
        )
        logger.info("Reset to IG / OK: %s", page.url)
        return True
    except (PWTimeout, Exception) as exc:
        u = page.url.rstrip("/").split("?")[0]
        if u in ("https://www.instagram.com", "http://www.instagram.com"):
            return True
        logger.warning("IG sidebar Home click failed: %s", exc)
        return False


def is_clean_homepage(url: str, platform: str) -> bool:
    """Strict check: URL is the platform's canonical homepage."""
    if platform == "twitter":
        u = url.split("?")[0].rstrip("/")
        return u in ("https://x.com/home", "https://twitter.com/home")
    u = url.rstrip("/")
    targets = {
        "tiktok": ("https://www.tiktok.com", "http://www.tiktok.com"),
        "fb": ("https://www.facebook.com", "http://www.facebook.com"),
        "instagram": ("https://www.instagram.com", "http://www.instagram.com"),
    }.get(platform, ())
    return u in targets


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
        "fb": "facebook.com",
        "twitter": ("x.com", "twitter.com"),
        "instagram": "instagram.com",
    }.get(platform)
    domains = (domain_match,) if isinstance(domain_match, str) else (domain_match or ())

    for p in ctx.pages:
        if any(d in p.url for d in domains):
            ok = False
            if platform == "tiktok":
                ok = await reset_tiktok_to_home(p)
            elif platform == "twitter":
                ok = await reset_twitter_to_home(p)
            elif platform == "fb":
                ok = await reset_fb_to_home(p)
            elif platform == "instagram":
                ok = await reset_instagram_to_home(p)
            if ok and is_clean_homepage(p.url, platform):
                return p

    return None
