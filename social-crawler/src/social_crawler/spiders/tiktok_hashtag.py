"""TikTok hashtag page spider (`/tag/<name>`).

Click-flow:
    / (clean For-You)
      → click `button[data-e2e="nav-search"]` (open search popup)
      → fill `input[data-e2e="search-user-input"]` (active one)
      → press Enter → /search?q=<hashtag>
      → click `a[data-e2e="search-common-link"][href="/tag/<name>"]`
      → SPA navigate to /tag/<name>
      → wait for `[data-e2e="challenge-item"]` grid
      → DOM extract loop + scroll

Why we click an inline hashtag link instead of a "Hashtag tab"
--------------------------------------------------------------
TikTok's search results page does NOT have a dedicated "Hashtag" tab — only
Top / Users / Videos / LIVE / Photo. However, every video description embeds
its hashtags as `<a data-e2e="search-common-link" href="/tag/<name>">`
elements. Picking the exact-match href is enough; clicking it triggers the
SPA navigation to the hashtag page.

Niche hashtag fallback
----------------------
If no video on the search results page embeds the hashtag (rare; happens for
very obscure tags), the selector times out. The spider exits gracefully.
We deliberately do NOT fall back to `page.goto("/tag/<name>")` because the
goto path triggers anti-bot detection.

Hashtag/mention extraction via regex (NOT anchor)
-------------------------------------------------
Unlike the detail-page (`browse-video-desc`) which is rich text with anchor
elements, the hashtag-page item description (`challenge-item-desc`) is plain
text without anchor children. So we extract `#tag` and `@user` via regex on
the alt-text caption instead of `querySelectorAll('a[href^="/tag/"]')`.
"""
from __future__ import annotations

import logging
import re
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

from playwright.async_api import TimeoutError as PWTimeout

from social_crawler.anti_bot import PageChallengeWatcher
from social_crawler.browser import cdp_session
from social_crawler.config import Settings
from social_crawler.items import TikTokVideoItem
from social_crawler.pipelines import PipelineContext, run_pipelines

logger = logging.getLogger(__name__)


SEARCH_TRIGGER_SEL = 'button[data-e2e="nav-search"]'
SEARCH_BOX_SEL = 'input[data-e2e="search-user-input"]'
CHALLENGE_ITEM_SEL = '[data-e2e="challenge-item"]'

POST_URL_RE = re.compile(r"/(video|photo|reel)/(\d+)")
SOFT_BLOCK_PATTERNS = (
    "something went wrong",
    "try again later",
    "please try again",
    "too many requests",
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
    hashtag: str,
    max_videos: int = 5,
    scroll_distance: int = 800,
) -> Stats:
    hashtag = hashtag.lstrip("#").lower()
    stats = Stats()
    t0 = time.monotonic()

    def _t(label: str) -> None:
        logger.info("[tk-hashtag] [+%6.2fs] %s", time.monotonic() - t0, label)

    _t(f"crawl start (hashtag=#{hashtag})")

    async with PipelineContext(settings, spider_name="tiktok_hashtag") as pctx:
        async with cdp_session("tiktok", settings) as page:
            watcher = PageChallengeWatcher(page, spider_logger=logger)
            try:
                async for vitem in _click_flow(page, hashtag, max_videos, scroll_distance, watcher, _t):
                    item_dict = asdict(vitem)
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


async def _click_flow(page, hashtag, max_videos, scroll_distance, watcher, _t):
    body_text = (await page.evaluate("() => document.body.innerText")).lower()
    for pattern in SOFT_BLOCK_PATTERNS:
        if pattern in body_text:
            logger.error("page in soft-block: %r", pattern)
            return

    try:
        await page.locator(SEARCH_TRIGGER_SEL).first.click(timeout=10_000)
    except Exception as exc:
        logger.error("search trigger click failed: %s", exc)
        return

    try:
        await page.wait_for_function(
            """() => {
                const inputs = document.querySelectorAll('input[data-e2e="search-user-input"]');
                return inputs.length >= 2 && inputs[1].offsetParent !== null;
            }""",
            timeout=5_000,
        )
    except PWTimeout:
        logger.error("search popup did not activate")
        return

    active_input = page.locator(SEARCH_BOX_SEL).nth(1)
    await active_input.fill(hashtag)
    await active_input.press("Enter")

    try:
        await page.wait_for_url("**/search?q=*", timeout=15_000)
    except PWTimeout:
        logger.error("search results URL did not commit")
        return

    if watcher.triggered:
        return

    tag_link_sel = f'a[data-e2e="search-common-link"][href="/tag/{hashtag}"]'
    try:
        await page.locator(tag_link_sel).first.wait_for(state="visible", timeout=10_000)
        _t("tag link visible")
    except PWTimeout:
        logger.error(
            "no exact-match search-common-link[/tag/%s] in search results "
            "(may be a niche hashtag with no embedding videos)", hashtag,
        )
        return

    await page.locator(tag_link_sel).first.click()

    try:
        await page.wait_for_url(f"**/tag/{hashtag}", timeout=15_000)
        await page.wait_for_selector(CHALLENGE_ITEM_SEL, timeout=15_000)
        _t("challenge-item grid visible")
    except PWTimeout:
        logger.error("/tag/%s grid never rendered", hashtag)
        return

    body_text = (await page.evaluate("() => document.body.innerText")).lower()
    for pattern in SOFT_BLOCK_PATTERNS:
        if pattern in body_text:
            logger.error("post-navigate soft-block: %r", pattern)
            return

    async for vitem in _extract_grid(page, hashtag, max_videos, scroll_distance, watcher):
        yield vitem


async def _extract_grid(page, hashtag, max_videos, scroll_distance, watcher):
    seen: set[str] = set()
    collected = 0
    stall = 0
    js = r"""
    () => {
        const items = document.querySelectorAll('[data-e2e="challenge-item"]');
        const out = [];
        items.forEach(el => {
            const a = el.querySelector('a[href*="/video/"], a[href*="/photo/"]');
            if (!a) return;
            const href = a.href || '';
            const m = href.match(/\/(video|photo|reel)\/(\d+)/);
            if (!m) return;
            const postType = m[1];
            const postId = m[2];
            const img = el.querySelector('img');
            const userEl = el.querySelector('[data-e2e="challenge-item-username"]');
            const avatarA = el.querySelector('[data-e2e="challenge-item-avatar"]');
            const handle = (userEl ? (userEl.innerText || '').trim()
                : (avatarA ? (avatarA.getAttribute('href') || '')
                    .replace(/^\/@/, '').split('?')[0] : ''));
            const altText = img ? (img.alt || '') : '';
            const hashtagMatches = (altText.match(/#([\p{L}\p{N}_]+)/gu) || [])
                .map(s => s.slice(1));
            const mentionMatches = (altText.match(/@([A-Za-z0-9._]+)/g) || [])
                .map(s => s.slice(1));
            out.push({
                post_id: postId,
                post_type: postType,
                url: href.split('?')[0],
                author_handle: handle,
                content_text: altText,
                cover_url: img ? img.src : '',
                hashtags: hashtagMatches,
                mentions: mentionMatches,
            });
        });
        return out;
    }
    """

    for _ in range(max_videos * 3):
        if watcher.triggered or collected >= max_videos:
            break

        items = await page.evaluate(js)
        new_this_round = 0
        for v in items:
            pid = v.get("post_id")
            if not pid or pid in seen:
                continue
            seen.add(pid)
            new_this_round += 1
            yield _build_video_item(v, source_hashtag=hashtag)
            collected += 1
            if collected >= max_videos:
                break

        if new_this_round == 0:
            stall += 1
            if stall >= 3:
                break
        else:
            stall = 0

        if collected >= max_videos:
            break
        await page.evaluate(f"window.scrollBy(0, {scroll_distance})")
        await page.wait_for_timeout(400)


def _build_video_item(v: dict, *, source_hashtag: str) -> TikTokVideoItem:
    return TikTokVideoItem(
        platform="tiktok",
        post_id=v.get("post_id") or "",
        url=v.get("url") or "",
        author_handle=v.get("author_handle") or "",
        content_text=v.get("content_text") or "",
        description=v.get("content_text") or "",
        cover_url=v.get("cover_url") or "",
        hashtags=v.get("hashtags") or [],
        mentions=v.get("mentions") or [],
        scraped_at=datetime.now(timezone.utc).isoformat(),
        source_spider="tiktok_hashtag",
        source_query=source_hashtag,
        raw_snapshot={"post_type": v.get("post_type", "")},
    )
