"""TikTok video detail spider — full per-video metadata.

Walks `@username`'s feed via the detail-modal arrow-right button:

    Click-flow:
        / (clean For-You)
          → 5-step click-flow to /@username (search → click profile)
          → click first user-post-item card → detail modal opens
            (URL becomes /@username/video/<id>)
          → DOM extract from `browse-*` selector namespace
          → click [data-e2e="arrow-right"] (aria-label="Go to next video")
          → repeat for max_videos

Detail-page selector namespace (`browse-*`)
-------------------------------------------
- `[data-e2e="browse-video-desc"]` — description DIV with embedded
  `<a href="/tag/...">` and `<a href="/@...">` for hashtags / mentions
- `[data-e2e="browser-nickname"]` — 3-line text "Display Name\\n·\\nM-D"
  (the M-D is a relative date like "4-1"; ISO is not exposed)
- `[data-e2e="browse-user-avatar"]` — anchor whose href is "/<handle>"
- `[data-e2e="browse-music"]` — H4 with music_title (no surrounding anchor,
  music URL not directly extractable)
- `[data-e2e="browse-like-count"]` / `[...="browse-comment-count"]`
- `[data-e2e="undefined-count"]` — bookmark/save count (4th action button)
- `[data-e2e="arrow-right"]` — next-video button (aria-label "Go to next video")
- `[data-e2e="browse-close"]` — close-modal button

Why DOM-only
------------
TikTok's 2026-04 SSR `__UNIVERSAL_DATA_FOR_REHYDRATION__` no longer ships
video data; only `webapp.app-context` / `biz-context` / `i18n-translation` /
`seo.abtest` / `webapp.a-b` are inlined. DOM extraction is the only path.

Why arrow-right (instead of clicking each grid item)
----------------------------------------------------
arrow-right is a SPA URL switch (`pushState`) — fast and no fresh document
fetch. Cleaner than going back to the grid and re-clicking each thumbnail.
"""
from __future__ import annotations

import logging
import re
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Optional

from playwright.async_api import TimeoutError as PWTimeout

from social_crawler.anti_bot import PageChallengeWatcher
from social_crawler.browser import cdp_session
from social_crawler.config import Settings
from social_crawler.items import TikTokVideoItem
from social_crawler.pipelines import PipelineContext, run_pipelines

logger = logging.getLogger(__name__)


SEARCH_TRIGGER_SEL = 'button[data-e2e="nav-search"]'
SEARCH_BOX_SEL = 'input[data-e2e="search-user-input"]'
GRID_ITEM_SEL = '[data-e2e="user-post-item"]'
DETAIL_DESC_SEL = '[data-e2e="browse-video-desc"]'
ARROW_RIGHT_SEL = '[data-e2e="arrow-right"]'

POST_TYPE_RE = re.compile(r"/(video|photo|reel)/(\d+)")
SOFT_BLOCK_PATTERNS = ("something went wrong", "try again later", "please try again")


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
    username: str,
    max_videos: int = 5,
) -> Stats:
    username = username.lstrip("@")
    stats = Stats()
    t0 = time.monotonic()

    def _t(label: str) -> None:
        logger.info("[tk-video] [+%6.2fs] %s", time.monotonic() - t0, label)

    _t(f"crawl start (username=@{username})")

    async with PipelineContext(settings, spider_name="tiktok_video") as pctx:
        async with cdp_session("tiktok", settings) as page:
            watcher = PageChallengeWatcher(page, spider_logger=logger)
            try:
                async for vitem in _full_flow(page, username, max_videos, watcher, _t):
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


async def _full_flow(page, username, max_videos, watcher, _t):
    if not await _navigate_to_user_grid(page, username, watcher, _t):
        return

    first_card = page.locator(
        f'{GRID_ITEM_SEL} a[href*="/video/"], {GRID_ITEM_SEL} a[href*="/photo/"]'
    ).first
    try:
        await first_card.wait_for(state="visible", timeout=10_000)
        await first_card.click()
    except (PWTimeout, Exception) as exc:
        logger.error("first video card click failed: %s", exc)
        return

    try:
        await page.wait_for_url(
            lambda url: "/video/" in url or "/photo/" in url,
            timeout=15_000,
        )
    except PWTimeout:
        logger.error("detail URL did not commit")
        return

    try:
        await page.wait_for_selector(DETAIL_DESC_SEL, timeout=15_000)
        _t("detail modal ready")
    except PWTimeout:
        logger.error("detail desc never rendered")
        return

    body_text = (await page.evaluate("() => document.body.innerText")).lower()
    for pattern in SOFT_BLOCK_PATTERNS:
        if pattern in body_text:
            logger.error("post-navigate soft-block: %r", pattern)
            return

    seen_post_ids: set[str] = set()
    for i in range(max_videos):
        if watcher.triggered:
            break

        info = await _extract_detail_dom(page)
        _t(f"detail #{i+1} extracted")

        if info and info.get("post_id") and info["post_id"] not in seen_post_ids:
            seen_post_ids.add(info["post_id"])
            yield _build_video_item(info, source_handle=username)

        if i + 1 >= max_videos:
            break
        if not await _advance_arrow_right(page, _t):
            break


async def _navigate_to_user_grid(page, username, watcher, _t) -> bool:
    """5-step click-flow: clean fyp → search → profile → /@username grid."""
    body_text = (await page.evaluate("() => document.body.innerText")).lower()
    for pattern in SOFT_BLOCK_PATTERNS:
        if pattern in body_text:
            logger.error("page in soft-block: %r", pattern)
            return False

    try:
        await page.locator(SEARCH_TRIGGER_SEL).first.click(timeout=10_000)
    except Exception as exc:
        logger.error("search trigger click failed: %s", exc)
        return False

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
        return False

    active_input = page.locator(SEARCH_BOX_SEL).nth(1)
    await active_input.fill(username)
    await active_input.press("Enter")

    try:
        await page.wait_for_url("**/search?q=*", timeout=15_000)
    except PWTimeout:
        logger.error("search results URL did not commit")
        return False

    if watcher.triggered:
        return False

    profile_sel = f'a[data-e2e="search-card-user-link"][href="/@{username}"]'
    try:
        await page.locator(profile_sel).first.wait_for(timeout=10_000)
        await page.locator(profile_sel).first.click()
        await page.wait_for_url(f"**/@{username}", timeout=15_000)
        await page.wait_for_selector(GRID_ITEM_SEL, timeout=15_000)
        _t("user grid visible")
        return True
    except (PWTimeout, Exception) as exc:
        logger.error("profile/grid step failed: %s", exc)
        return False


async def _advance_arrow_right(page, _t) -> bool:
    arrow = page.locator(ARROW_RIGHT_SEL).first
    try:
        await arrow.wait_for(state="visible", timeout=5_000)
    except PWTimeout:
        return False

    prev_url = page.url
    try:
        await arrow.click(timeout=5_000)
        await page.wait_for_url(
            lambda url: url != prev_url and ("/video/" in url or "/photo/" in url),
            timeout=10_000,
        )
        await page.wait_for_selector(DETAIL_DESC_SEL, timeout=10_000)
        return True
    except (PWTimeout, Exception):
        return False


async def _extract_detail_dom(page) -> Optional[dict]:
    try:
        return await page.evaluate(
            r"""
            () => {
                const url = location.href;
                const m = url.match(/\/(video|photo|reel)\/(\d+)/);
                const postType = m ? m[1] : '';
                const postId = m ? m[2] : '';

                const txt = (sel) => {
                    const el = document.querySelector(sel);
                    return el ? (el.innerText || '').trim() : '';
                };
                const attr = (sel, name) => {
                    const el = document.querySelector(sel);
                    return el ? (el.getAttribute(name) || '') : '';
                };

                const descEl = document.querySelector('[data-e2e="browse-video-desc"]');
                const desc = descEl ? (descEl.innerText || '').trim() : '';
                const hashtags = descEl
                    ? Array.from(descEl.querySelectorAll('a[href^="/tag/"]'))
                        .map(a => (a.innerText || '').replace(/^#/, '').trim())
                        .filter(Boolean)
                    : [];
                const mentions = descEl
                    ? Array.from(descEl.querySelectorAll('a[href^="/@"]'))
                        .map(a => (a.getAttribute('href') || '').replace(/^\/@/, '').trim())
                        .filter(Boolean)
                    : [];

                const nicknameRaw = txt('[data-e2e="browser-nickname"]');
                const lines = nicknameRaw.split('\n').map(s => s.trim()).filter(Boolean);
                const displayName = lines[0] || '';
                const relativeDate = lines[lines.length - 1] || '';
                const authorHandleHref = attr('[data-e2e="browse-user-avatar"]', 'href');
                const authorHandle = (authorHandleHref || '').replace(/^\/@/, '').trim();

                const likesStr = txt('[data-e2e="browse-like-count"]');
                const commentsStr = txt('[data-e2e="browse-comment-count"]');
                const collectsStr = txt('[data-e2e="undefined-count"]');
                const musicTitle = txt('[data-e2e="browse-music"]');

                let duration = null;
                const videos = Array.from(document.querySelectorAll('video'));
                if (videos.length) {
                    let best = null, bestArea = 0;
                    for (const v of videos) {
                        const r = v.getBoundingClientRect();
                        const area = Math.max(0, r.width) * Math.max(0, r.height);
                        if (area > bestArea) { bestArea = area; best = v; }
                    }
                    if (best && Number.isFinite(best.duration) && best.duration > 0) {
                        duration = best.duration;
                    }
                }

                return {
                    post_type: postType,
                    post_id: postId,
                    url: url.split('?')[0],
                    desc,
                    hashtags,
                    mentions,
                    display_name: displayName,
                    author_handle: authorHandle,
                    relative_date: relativeDate,
                    music_title: musicTitle,
                    likes_str: likesStr,
                    comments_str: commentsStr,
                    collects_str: collectsStr,
                    duration_s: duration,
                };
            }
            """
        )
    except Exception as exc:
        logger.warning("DOM extract failed: %s", exc)
        return None


def _build_video_item(info: dict, *, source_handle: str) -> TikTokVideoItem:
    duration_s = info.get("duration_s")
    duration_ms = int(duration_s * 1000) if duration_s else None
    return TikTokVideoItem(
        platform="tiktok",
        post_id=info.get("post_id") or "",
        url=info.get("url") or "",
        author_handle=info.get("author_handle") or source_handle,
        author_display_name=info.get("display_name") or "",
        content_text=info.get("desc") or "",
        description=info.get("desc") or "",
        hashtags=info.get("hashtags") or [],
        mentions=info.get("mentions") or [],
        music_title=info.get("music_title") or "",
        likes_count=_parse_count_suffix(info.get("likes_str", "")),
        comments_count=_parse_count_suffix(info.get("comments_str", "")),
        collects_count=_parse_count_suffix(info.get("collects_str", "")),
        duration_ms=duration_ms,
        scraped_at=datetime.now(timezone.utc).isoformat(),
        source_spider="tiktok_video",
        source_query=source_handle,
        raw_snapshot={
            "relative_date": info.get("relative_date", ""),
            "post_type": info.get("post_type", ""),
        },
    )


def _parse_count_suffix(s: str) -> Optional[int]:
    if not s:
        return None
    s = s.strip().replace(",", "")
    multipliers = {"K": 1_000, "M": 1_000_000, "B": 1_000_000_000}
    suffix = s[-1].upper() if s and s[-1].upper() in multipliers else None
    try:
        if suffix:
            return int(float(s[:-1]) * multipliers[suffix])
        return int(float(s))
    except (ValueError, TypeError):
        return None
