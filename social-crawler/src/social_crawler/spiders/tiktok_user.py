"""TikTok user profile spider — public demo (5-step click-flow showcase).

High-level click-flow:
    / (clean homepage) → search popup → fill query → Enter → /search?q=*
    → click profile card → /@<username> → DOM extract loop + scroll

The selectors and timing waits below produce a working baseline against a
public TikTok profile, but the full battle-tested behavior — selector
fallbacks across UI revisions, popup-activation race recovery, search-page
hero-card vs profile-card disambiguation, login-wall and CAPTCHA-interstitial
recovery, regional locale variants — ships in the paid version. Contact via
Upwork to scope production work.
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
from social_crawler.items import TikTokUserItem, TikTokVideoItem
from social_crawler.pipelines import PipelineContext, run_pipelines

logger = logging.getLogger(__name__)


SEARCH_TRIGGER_SEL = 'button[data-e2e="nav-search"]'
SEARCH_BOX_SEL = 'input[data-e2e="search-user-input"]'
GRID_ITEM_SEL = '[data-e2e="user-post-item"]'
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
    scroll_distance: int = 600,
) -> Stats:
    """End-to-end TikTok user profile crawl. Returns a Stats summary."""
    username = username.lstrip("@")
    stats = Stats()
    t0 = time.monotonic()

    def _t(label: str) -> None:
        elapsed = time.monotonic() - t0
        logger.info("[tk-user] [+%6.2fs] %s", elapsed, label)

    _t("crawl start")

    async with PipelineContext(settings, spider_name="tiktok_user") as pctx:
        async with cdp_session("tiktok", settings) as page:
            _t("CDP attach OK")
            watcher = PageChallengeWatcher(page, spider_logger=logger)

            try:
                async for item in _click_flow(
                    page, username, max_videos, scroll_distance, watcher, _t,
                ):
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


async def _click_flow(page, username, max_videos, scroll_distance, watcher, _t):
    body_text = (await page.evaluate("() => document.body.innerText")).lower()
    for pattern in SOFT_BLOCK_PATTERNS:
        if pattern in body_text:
            logger.error("page already in soft-block state: %r at url=%s", pattern, page.url)
            return
    _t("pre soft-block check OK")

    try:
        await page.locator(SEARCH_TRIGGER_SEL).first.click(timeout=10_000)
        _t("search trigger clicked")
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
        _t("popup active input visible")
    except PWTimeout:
        logger.error("search popup did not activate")
        return

    active_input = page.locator(SEARCH_BOX_SEL).nth(1)
    await active_input.fill(username)
    _t("fill done")

    await active_input.press("Enter")
    try:
        await page.wait_for_url("**/search?q=*", timeout=15_000)
        _t("search results URL committed")
    except PWTimeout:
        logger.error("search results URL did not commit")
        return

    if watcher.triggered:
        return

    profile_link_sel = f'a[data-e2e="search-card-user-link"][href="/@{username}"]'
    try:
        await page.locator(profile_link_sel).first.wait_for(timeout=10_000)
        await page.locator(profile_link_sel).first.click()
        await page.wait_for_url(f"**/@{username}", timeout=15_000)
        _t("profile URL committed")
    except PWTimeout:
        logger.error("profile_link did not appear: %s", profile_link_sel)
        return

    try:
        await page.wait_for_selector(GRID_ITEM_SEL, timeout=15_000)
        _t("grid item visible")
    except PWTimeout:
        logger.error("grid never rendered for @%s", username)
        return

    body_text = (await page.evaluate("() => document.body.innerText")).lower()
    for pattern in SOFT_BLOCK_PATTERNS:
        if pattern in body_text:
            logger.error("post-navigate soft-block: %r at url=%s", pattern, page.url)
            return

    user_info = await _extract_user_dom(page)
    if user_info:
        yield _build_user_item(user_info, username)

    async for vitem in _extract_video_grid(page, username, max_videos, scroll_distance, watcher):
        yield vitem


async def _extract_user_dom(page) -> Optional[dict]:
    """Pull header fields via DOM. Demo extracts a minimal subset."""
    try:
        return await page.evaluate(
            r"""
            () => {
                const q = (sel, attr) => {
                    const el = document.querySelector(sel);
                    if (!el) return '';
                    return attr ? (el.getAttribute(attr) || '') : (el.innerText || '');
                };
                const statsLine = q('h3') || '';
                const m = statsLine.match(/([\d.]+[KMB]?)\s+Following\s+([\d.]+[KMB]?)\s+Followers\s+([\d.]+[KMB]?)\s+Likes/i);
                return {
                    nickname: q('[data-e2e="user-title"]'),
                    unique_id: q('[data-e2e="user-subtitle"]'),
                    bio: q('[data-e2e="user-bio"]'),
                    bio_link: q('[data-e2e="user-link"]'),
                    avatar_url: q('[data-e2e="user-avatar"] img', 'src'),
                    following_str: m ? m[1] : '',
                    followers_str: m ? m[2] : '',
                    likes_str: m ? m[3] : '',
                    verified: !!document.querySelector('[data-e2e="user-subtitle"] + svg circle[fill="#20D5EC"]'),
                };
            }
            """
        )
    except Exception as exc:
        logger.warning("DOM user header extract failed: %s", exc)
        return None


async def _extract_video_grid(page, username, max_videos, scroll_distance, watcher):
    seen: set[str] = set()
    collected = 0
    stall = 0
    js = r"""
    () => {
        const items = document.querySelectorAll('[data-e2e="user-post-item"]');
        const out = [];
        items.forEach(el => {
            const a = el.querySelector('a[href*="/video/"]');
            if (!a) return;
            const m = a.href.match(/\/video\/(\d+)/);
            if (!m) return;
            const img = el.querySelector('img');
            const viewsEl = el.querySelector('[data-e2e="video-views"]');
            out.push({
                id: m[1],
                url: a.href,
                cover_url: img ? img.src : null,
                alt_text: img ? img.alt : '',
                views_text: viewsEl ? viewsEl.innerText : '',
            });
        });
        return out;
    }
    """

    for _ in range(max_videos * 3):
        if watcher.triggered or collected >= max_videos:
            break

        videos = await page.evaluate(js)
        new_this_round = 0
        for v in videos:
            vid = v.get("id")
            if not vid or vid in seen:
                continue
            seen.add(vid)
            new_this_round += 1
            yield _build_video_item(v, username)
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


def _build_user_item(info: dict, username: str) -> TikTokUserItem:
    return TikTokUserItem(
        platform="tiktok",
        unique_id=info.get("unique_id") or username,
        nickname=info.get("nickname") or "",
        bio=info.get("bio") or "",
        bio_link=info.get("bio_link") or "",
        avatar_url=info.get("avatar_url") or "",
        is_verified=bool(info.get("verified")),
        followers_count=_parse_count_suffix(info.get("followers_str", "")),
        following_count=_parse_count_suffix(info.get("following_str", "")),
        hearts_count=_parse_count_suffix(info.get("likes_str", "")),
        scraped_at=datetime.now(timezone.utc).isoformat(),
    )


def _build_video_item(v: dict, username: str) -> TikTokVideoItem:
    return TikTokVideoItem(
        platform="tiktok",
        post_id=v.get("id") or "",
        url=v.get("url") or "",
        author_handle=username,
        cover_url=v.get("cover_url") or "",
        content_text=v.get("alt_text") or "",
        scraped_at=datetime.now(timezone.utc).isoformat(),
        source_spider="tiktok_user",
        source_query=username,
        raw_snapshot={"views_text": v.get("views_text", "")},
    )


def _parse_count_suffix(s: str) -> Optional[int]:
    """'9.5M' → 9_500_000; '50.2M' → 50_200_000; '60' → 60."""
    if not s:
        return None
    s = s.strip()
    multipliers = {"K": 1_000, "M": 1_000_000, "B": 1_000_000_000}
    suffix = s[-1].upper() if s and s[-1].upper() in multipliers else None
    try:
        if suffix:
            return int(float(s[:-1]) * multipliers[suffix])
        return int(float(s))
    except (ValueError, TypeError):
        return None
