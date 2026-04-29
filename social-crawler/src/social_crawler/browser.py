"""Playwright CDP attach + page reuse (attach mode).

The crawler does NOT launch its own browser. Instead, the user runs
`scripts/start_chrome_cdp.py` first, which starts Chrome with
`--remote-debugging-port=<port>` and a per-platform `--user-data-dir`.

This module's `cdp_session` async context manager:

1. Calls `playwright.connect_over_cdp(<cdp_url>)` to attach
2. Reuses `browser.contexts[0]` (the user's persistent context with cookies)
3. Picks a tab on the platform domain via `nav.find_or_reset_homepage_page`
4. Yields that page to the spider

On exit: only `playwright.stop()` is called. The user's Chrome window stays
open. The spider does not close any tabs.

Why
---
Servers can fingerprint Playwright-launched browsers via:

- `navigator.webdriver === true`
- `--enable-automation` Chrome flag → user agent fragment "HeadlessChrome"
- Missing `Notification.permission` quirks
- Chrome window "automation control" infobar

By attaching to a user-launched Chrome the crawler inherits a real human
session. The user logs in manually (if needed) once; profile dir persists.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from playwright.async_api import BrowserContext, Page, async_playwright

from social_crawler.config import Settings
from social_crawler.nav import find_or_reset_homepage_page

logger = logging.getLogger(__name__)


@asynccontextmanager
async def cdp_session(platform: str, settings: Settings):
    """Async context manager: yields the user's clean homepage Page.

    Caller runs the click-flow on the yielded page. On exit only the
    Playwright connection is torn down; Chrome stays running.
    """
    port = settings.cdp_port_for(platform)
    cdp_url = f"http://localhost:{port}"

    pw = await async_playwright().start()
    try:
        browser = await pw.chromium.connect_over_cdp(cdp_url)
        contexts = browser.contexts
        if not contexts:
            raise RuntimeError(
                f"Chrome at {cdp_url} has 0 browser contexts. "
                f"Run scripts/start_chrome_cdp.py --platform {platform} first."
            )
        ctx = contexts[0]
        page = await _acquire_homepage(ctx, platform, port)
        yield page
    finally:
        try:
            await pw.stop()
        except Exception as exc:
            logger.warning("playwright.stop() failed (ignored): %s", exc)


async def _acquire_homepage(ctx: BrowserContext, platform: str, port: int) -> Page:
    target = await find_or_reset_homepage_page(ctx, platform)
    if target is None:
        current_urls = [p.url for p in ctx.pages]
        raise RuntimeError(
            f"No usable {platform} tab found in Chrome (port {port}). "
            f"Existing pages: {current_urls!r}. "
            f"In Chrome: Ctrl+T, type the platform homepage URL in the address "
            f"bar, press Enter, wait for the page to settle, then retry."
        )

    # Match dark color scheme to avoid a light-flash during automation.
    try:
        await target.emulate_media(color_scheme="dark")
    except Exception as exc:
        logger.warning("emulate_media dark failed (ignored): %s", exc)

    logger.info("Reusing %s page url=%s", platform, target.url)
    return target
