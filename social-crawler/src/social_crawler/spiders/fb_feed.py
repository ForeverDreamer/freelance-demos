"""Facebook Page feed spider.

Click-flow:
    facebook.com/ (clean home)
      → fill input[type="search"](page_handle)
      → press Enter → /search/top/?q=<handle>
      → click `a[href*="/search/pages/"][href*="q=<handle>"]` (Pages filter tab)
      → /search/pages/?q=<handle>
      → wait for [role="feed"] articles
      → find first article link with href = facebook.com/<handle> → click → /<handle>
      → wait for [data-pagelet="ProfileTimeline"]
      → DOM extract loop on [data-pagelet^="TimelineFeedUnit_"] + scroll

Notes
-----
- The Page profile timeline lives in `data-pagelet^="TimelineFeedUnit_"` units,
  not the older `[role="article"]` selector (which would also match
  search-result and sidebar cards).
- Post timestamps live in the permalink anchor's `aria-label` as a relative
  time string (e.g., "18小时", "1天" on Chinese-locale UI; "18h", "1d" on
  English UI). They are not normalized in the demo.
- Reaction breakdowns come from `[aria-label]` strings of the form
  "Like: 200 users" / "赞:200位用户".
"""
from __future__ import annotations

import logging
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Optional

from playwright.async_api import TimeoutError as PWTimeout

from social_crawler.anti_bot import PageChallengeWatcher
from social_crawler.browser import cdp_session
from social_crawler.config import Settings
from social_crawler.items import FacebookPageItem, FacebookPostItem
from social_crawler.pipelines import PipelineContext, run_pipelines

logger = logging.getLogger(__name__)


SEARCH_INPUT_SEL = 'input[type="search"]'
PAGES_FILTER_TAB_SEL_TPL = 'a[href*="/search/pages/"][href*="q={query}"]'
PROFILE_TIMELINE_SEL = '[data-pagelet="ProfileTimeline"]'
TIMELINE_UNIT_SEL = '[data-pagelet^="TimelineFeedUnit_"]'
SOFT_BLOCK_PATTERNS = (
    "something went wrong",
    "try again later",
    "please try again",
    "this content isn't available",
    # Chinese-locale soft-block strings
    "出错了",
    "稍后再试",
)


@dataclass
class Stats:
    items_yielded: int = 0
    items_dropped: int = 0
    watcher_triggered_at: list[str] = field(default_factory=list)
    elapsed_seconds: float = 0.0
    finish_reason: str = "unknown"


async def crawl(
    *,
    settings: Settings,
    page_handle: str,
    max_posts: int = 5,
    scroll_distance: int = 800,
) -> Stats:
    page_handle = page_handle.lstrip("/").rstrip("/")
    stats = Stats()
    t0 = time.monotonic()

    def _t(label: str) -> None:
        logger.info("[fb] [+%6.2fs] %s", time.monotonic() - t0, label)

    _t(f"crawl start (page_handle={page_handle})")

    async with PipelineContext(settings, spider_name="fb_feed") as pctx:
        async with cdp_session("fb", settings) as page:
            watcher = PageChallengeWatcher(page, spider_logger=logger)
            try:
                async for item in _click_flow(page, page_handle, max_posts, scroll_distance, watcher, _t):
                    item_dict = asdict(item)
                    result = await run_pipelines(item_dict, pctx)
                    if result is None:
                        stats.items_dropped += 1
                    else:
                        stats.items_yielded += 1

                if watcher.triggered:
                    stats.watcher_triggered_at.append(watcher.reason or "?")
                    stats.finish_reason = f"watcher:{watcher.reason}"
                else:
                    stats.finish_reason = "finished"
            finally:
                watcher.detach()

    stats.elapsed_seconds = time.monotonic() - t0
    _t(f"crawl done — yielded={stats.items_yielded} dropped={stats.items_dropped} "
       f"finish={stats.finish_reason} elapsed={stats.elapsed_seconds:.2f}s")
    return stats


async def _click_flow(page, page_handle, max_posts, scroll_distance, watcher, _t):
    body_text = (await page.evaluate("() => document.body.innerText")).lower()
    for pattern in SOFT_BLOCK_PATTERNS:
        if pattern in body_text:
            logger.error("page already in soft-block state: %r at url=%s", pattern, page.url)
            return
    _t("pre soft-block check OK")

    search_input = page.locator(SEARCH_INPUT_SEL).first
    try:
        await search_input.wait_for(state="visible", timeout=5_000)
        await search_input.fill(page_handle)
        await search_input.press("Enter")
    except (PWTimeout, Exception) as exc:
        logger.error("search fill/submit failed: %s", exc)
        return

    try:
        await page.wait_for_url("**/search/**", timeout=15_000)
        _t("search results URL committed")
    except PWTimeout:
        logger.error("search results URL did not commit")
        return

    if watcher.triggered:
        return

    pages_tab_sel = PAGES_FILTER_TAB_SEL_TPL.format(query=page_handle.lower())
    pages_tab = page.locator(pages_tab_sel).first
    try:
        await pages_tab.wait_for(state="visible", timeout=10_000)
    except PWTimeout:
        # Fall back to less strict selector
        pages_tab = page.locator('a[href*="/search/pages/"]').first
        try:
            await pages_tab.wait_for(state="visible", timeout=3_000)
        except PWTimeout:
            logger.error("Pages filter tab not found")
            return

    await pages_tab.click()
    try:
        await page.wait_for_url(
            lambda url: "/search/pages" in url and "q=" in url,
            timeout=15_000,
        )
        _t("Pages search URL committed")
    except PWTimeout:
        logger.error("Pages search URL did not commit")
        return

    try:
        await page.wait_for_selector('[role="feed"] [role="article"]', timeout=20_000)
        _t("Pages search feed visible")
    except PWTimeout:
        logger.error("Pages search feed never rendered")
        return

    # Find the exact-handle Page link in the search feed.
    profile_url = await page.evaluate(
        """(handle) => {
            const feed = document.querySelector('[role="feed"]');
            if (!feed) return null;
            const links = feed.querySelectorAll('a[href]');
            const target = handle.toLowerCase();
            for (const a of links) {
                const m = (a.getAttribute('href') || '').match(/^https?:\\/\\/(?:www\\.)?facebook\\.com\\/([^?#/]+)/);
                if (m && m[1].toLowerCase() === target) {
                    return a.href;
                }
            }
            return null;
        }""",
        page_handle,
    )
    if not profile_url:
        logger.error("no Page result with handle exactly matching %r", page_handle)
        return

    profile_link = page.locator(f'[role="feed"] a[href="{profile_url}"]').first
    try:
        await profile_link.click()
        await page.wait_for_url(
            lambda url: f"/{page_handle.lower()}" in url.lower() and "/search" not in url.lower(),
            timeout=15_000,
        )
        _t("profile URL committed")
    except (PWTimeout, Exception) as exc:
        logger.error("profile click/navigate failed: %s", exc)
        return

    try:
        await page.wait_for_selector(PROFILE_TIMELINE_SEL, timeout=15_000)
        _t("ProfileTimeline visible")
    except PWTimeout:
        logger.error("ProfileTimeline never rendered for /%s", page_handle)
        return

    body_text = (await page.evaluate("() => document.body.innerText")).lower()
    for pattern in SOFT_BLOCK_PATTERNS:
        if pattern in body_text:
            logger.error("post-navigate soft-block: %r", pattern)
            return

    page_info = await _extract_page_dom(page)
    if page_info:
        yield _build_page_item(page_info, page_handle)

    async for post_item in _extract_posts(page, page_handle, max_posts, scroll_distance, watcher):
        yield post_item


async def _extract_page_dom(page) -> Optional[dict]:
    try:
        return await page.evaluate(
            r"""
            () => {
                const parseCount = (s) => {
                    if (!s) return null;
                    s = s.replace(/[, 位粉丝followers\s]/gi, '').trim();
                    const m = s.match(/^([\d.]+)([万亿KMB])?$/i);
                    if (!m) {
                        const plain = parseInt(s.replace(/[^\d]/g, ''), 10);
                        return Number.isFinite(plain) ? plain : null;
                    }
                    let n = parseFloat(m[1]);
                    if (!Number.isFinite(n)) return null;
                    const suf = (m[2] || '').toUpperCase();
                    if (suf === '万') n *= 10000;
                    else if (suf === '亿') n *= 100000000;
                    else if (suf === 'K') n *= 1000;
                    else if (suf === 'M') n *= 1000000;
                    else if (suf === 'B') n *= 1000000000;
                    return Math.round(n);
                };
                const h1 = document.querySelector('h1');
                const pageName = h1 ? (h1.innerText || '').trim() : '';
                const followerA = Array.from(document.querySelectorAll('a[href*="/followers/"]'))
                    .find(a => (a.innerText || '').match(/(?:粉丝|followers)/i)
                            && (a.innerText || '').match(/\d/));
                const followersText = followerA ? (followerA.innerText || '').trim() : '';
                const verifiedImg = document.querySelector(
                    'img[alt="Verified account"], '
                    + 'svg[role="img"][aria-label*="erified"]'
                );
                return {
                    page_name: pageName,
                    follower_count: parseCount(followersText),
                    verified: !!verifiedImg,
                };
            }
            """
        )
    except Exception as exc:
        logger.warning("DOM Page header extract failed: %s", exc)
        return None


async def _extract_posts(page, page_handle, max_posts, scroll_distance, watcher):
    seen: set[str] = set()
    collected = 0
    stall = 0
    js = r"""
    () => {
        const units = document.querySelectorAll('[data-pagelet^="TimelineFeedUnit_"]');
        return Array.from(units).map(u => {
            const textEl = u.querySelector(
                '[data-ad-preview="message"], [data-ad-comet-preview="message"]'
            );
            const permalinkSelectors = [
                'a[href*="/posts/"]',
                'a[href*="/reel/"]',
                'a[href*="/videos/"]',
                'a[href*="/permalink/"]',
                'a[href*="story_fbid="]',
                'a[href*="fbid="]',
            ];
            let permalinkA = null;
            for (const sel of permalinkSelectors) {
                permalinkA = u.querySelector(sel);
                if (permalinkA) break;
            }
            if (!permalinkA) return { id: '' };
            const url = permalinkA.href;
            let id = '';
            let postType = 'post';
            const m1 = url.match(/\/(posts|reel|videos|permalink)\/((?:pfbid)?[\w.]+)/);
            const m2 = url.match(/(?:fbid|story_fbid)=([\w.]+)/);
            if (m1) { id = m1[2]; postType = m1[1]; }
            else if (m2) { id = m2[1]; postType = 'photo'; }
            const time_rel = permalinkA.getAttribute('aria-label')
                || (permalinkA.innerText || '').slice(0, 30);
            const reactionCounts = {};
            let reactionsTotal = 0;
            u.querySelectorAll('[aria-label]').forEach(el => {
                const al = el.getAttribute('aria-label') || '';
                const m = al.match(/^(.+?)：(\d+(?:[,，.]\d+)*)位用户$/) ||
                          al.match(/^(.+?):\s*(\d+(?:,\d+)*)\s+(?:reactions?|likes?|users?|people)/i);
                if (m) {
                    const cnt = parseInt(m[2].replace(/[,，.]/g, ''), 10);
                    if (Number.isFinite(cnt)) {
                        reactionCounts[m[1].trim()] = cnt;
                        reactionsTotal += cnt;
                    }
                }
            });
            const mediaImgs = Array.from(u.querySelectorAll('img')).filter(i => {
                const src = i.src || '';
                return src.includes('scontent') && i.naturalWidth > 200;
            });
            return {
                id: id,
                url: url,
                post_type: postType,
                text: textEl ? (textEl.innerText || '') : '',
                time_relative: time_rel,
                reactions_breakdown: reactionCounts,
                reactions_total: reactionsTotal || null,
                media_urls: mediaImgs.map(i => i.src),
                media_alts: mediaImgs.map(i => i.alt || ''),
            };
        }).filter(p => p.id);
    }
    """

    for _ in range(max_posts * 3):
        if watcher.triggered or collected >= max_posts:
            break

        posts = await page.evaluate(js)
        new_this_round = 0
        for p in posts:
            pid = p.get("id")
            if not pid or pid in seen:
                continue
            seen.add(pid)
            new_this_round += 1
            yield _build_post_item(p, page_handle)
            collected += 1
            if collected >= max_posts:
                break

        if new_this_round == 0:
            stall += 1
            if stall >= 3:
                break
        else:
            stall = 0

        if collected >= max_posts:
            break
        await page.evaluate(f"window.scrollBy(0, {scroll_distance})")
        await page.wait_for_timeout(800)


def _build_page_item(info: dict, page_handle: str) -> FacebookPageItem:
    return FacebookPageItem(
        platform="fb",
        page_handle=page_handle,
        page_name=info.get("page_name") or "",
        page_url=f"https://www.facebook.com/{page_handle}",
        verified=bool(info.get("verified")),
        follower_count=info.get("follower_count"),
        scraped_at=datetime.now(timezone.utc).isoformat(),
    )


def _build_post_item(p: dict, page_handle: str) -> FacebookPostItem:
    media_urls = p.get("media_urls") or []
    return FacebookPostItem(
        platform="fb",
        post_id=p.get("id") or "",
        url=p.get("url") or "",
        author_handle=page_handle,
        content_text=p.get("text") or "",
        created_at=p.get("time_relative") or None,
        scraped_at=datetime.now(timezone.utc).isoformat(),
        media_urls=media_urls,
        media_types=["image"] * len(media_urls),
        media_alts=p.get("media_alts") or [],
        reactions_total=p.get("reactions_total"),
        reactions_breakdown=p.get("reactions_breakdown") or {},
        post_type=p.get("post_type") or "",
        source_spider="fb_feed",
        source_query=page_handle,
    )
