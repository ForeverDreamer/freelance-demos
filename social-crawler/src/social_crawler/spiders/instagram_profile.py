"""Instagram profile spider.

Click-flow:
    instagram.com/ (clean home)
      → click `a[role="link"]:has(svg[aria-label="Search"])` (sidebar Search)
      → wait for `input[aria-label="Search input"]` visible (panel slides out)
      → fill the input
      → wait for typeahead to render an exact `a[href="/<username>/"]` link
      → click that link → SPA navigate to /<username>/
      → wait for `<header>` and at least one `a[href*="/<username>/p/"]` or
        `a[href*="/<username>/reel/"]` to render
      → DOM extract header (InstagramUserItem) + grid (InstagramPostItem)

Two cross-platform quirks
-------------------------
1. **Trusted-vs-JS click reversal**: TikTok requires Playwright trusted CDP
   click to fire its React `onClick`. Instagram is the opposite — the search
   sidebar button doesn't accept Playwright's CDP click reliably; we fall back
   to `page.evaluate(() => ...click())` (a JS-dispatched click). For plain
   anchor navigation it is the same either way.
2. **Search panel is not in `[role="dialog"]`** — Instagram renders the
   search panel as an independent slide-out, not a dialog. Selectors must
   anchor on the input element (`input[aria-label="Search input"]`) and walk
   up to find a panel container that holds typeahead results.

Cross-account contamination filter
----------------------------------
The grid shows "Suggested for you" reels from other accounts mixed into the
profile's own grid (e.g., a `/natgeotv/reel/...` link appears on `/natgeo/`).
The selector must include `/<handle>/` prefix to filter these out.

Alt-text quality varies
-----------------------
For posts, `<img alt>` is usually IG-vision auto-generated ("Photo by X on
date. May be an image of..."). For reels, it is the user-written caption.
The `is_alt_text_auto` flag distinguishes the two.
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
from social_crawler.items import InstagramPostItem, InstagramUserItem
from social_crawler.pipelines import PipelineContext, run_pipelines

logger = logging.getLogger(__name__)


SEARCH_TRIGGER_SEL = 'a[role="link"]:has(svg[aria-label="Search"])'
SEARCH_INPUT_SEL = 'input[aria-label="Search input"]'
PROFILE_HEADER_SEL = 'header'

SOFT_BLOCK_PATTERNS = (
    "something went wrong",
    "try again later",
    "we restrict certain activity",
    "help us confirm",
    "suspicious",
    "too many requests",
    "page not found",
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
    username: str,
    max_posts: int = 5,
    scroll_distance: int = 800,
) -> Stats:
    username = username.lstrip("@").lower()
    stats = Stats()
    t0 = time.monotonic()

    def _t(label: str) -> None:
        logger.info("[ig] [+%6.2fs] %s", time.monotonic() - t0, label)

    _t(f"crawl start (username=@{username})")

    async with PipelineContext(settings, spider_name="instagram_profile") as pctx:
        async with cdp_session("instagram", settings) as page:
            watcher = PageChallengeWatcher(page, spider_logger=logger)
            try:
                async for item in _click_flow(page, username, max_posts, scroll_distance, watcher, _t):
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


async def _click_flow(page, username, max_posts, scroll_distance, watcher, _t):
    body_text = (await page.evaluate("() => document.body.innerText")).lower()
    for pattern in SOFT_BLOCK_PATTERNS:
        if pattern in body_text:
            logger.error("page already in soft-block state: %r at url=%s", pattern, page.url)
            return

    # Step 1: open the search panel via JS-dispatched click.
    # Playwright CDP trusted click does not reliably trigger Instagram's
    # React onClick on the sidebar search button (5s timeout). JS .click()
    # works because the handler doesn't gate on isTrusted.
    try:
        clicked = await page.evaluate(
            r"""() => {
                const svg = document.querySelector('svg[aria-label="Search"]');
                const a = svg ? svg.closest('a, [role="link"], [role="button"]') : null;
                if (!a) return false;
                a.click();
                return true;
            }"""
        )
        if not clicked:
            logger.error("search trigger element not found")
            return
        _t("search trigger JS click dispatched")
    except Exception as exc:
        logger.error("search trigger click failed: %s", exc)
        return

    try:
        await page.wait_for_function(
            """() => {
                const inp = document.querySelector('input[aria-label="Search input"]');
                return inp && inp.offsetParent !== null;
            }""",
            timeout=5_000,
        )
        _t("search input visible")
    except PWTimeout:
        logger.error("search input did not appear after trigger click")
        return

    search_input = page.locator(SEARCH_INPUT_SEL).first
    await search_input.fill(username)
    _t("fill done")

    # Wait for the typeahead to render an exact-match link inside the panel
    # (panel = the closest ancestor of `search_input` that contains the link).
    try:
        await page.wait_for_function(
            """(handle) => {
                const inp = document.querySelector('input[aria-label="Search input"]');
                if (!inp) return false;
                let panel = inp.parentElement;
                while (panel && panel !== document.body) {
                    const candidate = panel.querySelector(`a[href="/${handle}/"]`);
                    if (candidate && candidate.offsetParent !== null) return true;
                    panel = panel.parentElement;
                }
                return false;
            }""",
            arg=username,
            timeout=8_000,
        )
        _t("typeahead exact match visible")
    except PWTimeout:
        logger.error("typeahead exact-match a[href='/%s/'] not found", username)
        return

    if watcher.triggered:
        return

    # Step 4: click the typeahead link via JS (panel-scoped to avoid feed link
    # collisions).
    try:
        clicked = await page.evaluate(
            r"""(handle) => {
                const inp = document.querySelector('input[aria-label="Search input"]');
                if (!inp) return false;
                let panel = inp.parentElement;
                while (panel && panel !== document.body) {
                    const link = panel.querySelector(`a[href="/${handle}/"]`);
                    if (link && link.offsetParent !== null) {
                        link.click();
                        return true;
                    }
                    panel = panel.parentElement;
                }
                return false;
            }""",
            arg=username,
        )
        if not clicked:
            logger.error("typeahead link click failed (not found in panel)")
            return
        _t("typeahead link clicked")
    except Exception as exc:
        logger.error("typeahead click failed: %s", exc)
        return

    try:
        await page.wait_for_url(f"**/{username}/", timeout=15_000)
        _t("profile URL committed")
    except PWTimeout:
        logger.error("profile URL did not commit; current=%s", page.url)
        return

    try:
        await page.wait_for_selector(PROFILE_HEADER_SEL, timeout=10_000)
    except PWTimeout:
        logger.error("header never rendered")
        return

    try:
        await page.wait_for_function(
            """(handle) => {
                const items = document.querySelectorAll(
                    `a[href*="/${handle}/p/"], a[href*="/${handle}/reel/"]`
                );
                return items.length > 0;
            }""",
            arg=username,
            timeout=15_000,
        )
        _t("first grid item visible")
    except PWTimeout:
        logger.error("grid never rendered for /%s/", username)
        return

    body_text = (await page.evaluate("() => document.body.innerText")).lower()
    for pattern in SOFT_BLOCK_PATTERNS:
        if pattern in body_text:
            logger.error("post-navigate soft-block: %r", pattern)
            return

    user_info = await _extract_user_dom(page, username)
    if user_info:
        yield _build_user_item(user_info, username)

    async for item in _extract_grid(page, username, max_posts, scroll_distance, watcher):
        yield item


async def _extract_user_dom(page, username: str) -> Optional[dict]:
    try:
        return await page.evaluate(
            r"""
            (handle) => {
                const parseCount = (s) => {
                    if (!s) return null;
                    const trimmed = s.trim().replace(/,/g, '');
                    const m = trimmed.match(/^([\d.]+)([KMB])?/i);
                    if (!m) return null;
                    let n = parseFloat(m[1]);
                    if (!Number.isFinite(n)) return null;
                    const suf = (m[2] || '').toUpperCase();
                    if (suf === 'K') n *= 1000;
                    else if (suf === 'M') n *= 1_000_000;
                    else if (suf === 'B') n *= 1_000_000_000;
                    return Math.round(n);
                };
                const header = document.querySelector('header');
                if (!header) return null;
                const verified = !!header.querySelector('svg[aria-label="Verified"]');
                const headerText = (header.innerText || '');
                const isPrivate = /this account is private|account is private/i.test(headerText);
                const avatarImg = header.querySelector('img[alt*="profile" i]');
                const avatarUrl = avatarImg ? avatarImg.src : '';
                const followersA = header.querySelector(`a[href$="/${handle}/followers/"]`)
                    || document.querySelector(`a[href$="/${handle}/followers/"]`);
                const followingA = header.querySelector(`a[href$="/${handle}/following/"]`)
                    || document.querySelector(`a[href$="/${handle}/following/"]`);
                const followersStr = followersA ? (followersA.innerText || '').split('\n')[0] : '';
                const followingStr = followingA ? (followingA.innerText || '').split('\n')[0] : '';
                const postsMatch = headerText.match(/([\d,.]+\s*[KMB]?)\s+posts?/i);
                const postsStr = postsMatch ? postsMatch[1] : '';
                const headerLines = headerText.split('\n').map(s => s.trim()).filter(Boolean);
                let displayName = '';
                let bio = '';
                let bioLink = '';
                if (headerLines.length >= 2 && headerLines[0].toLowerCase() === handle.toLowerCase()) {
                    displayName = headerLines[1] || '';
                    const statsKeywords = /^[\d.,]+\s*[KMB]?\s+(posts?|followers?|following)$/i;
                    const buttonLabels = /^(follow|following|message|send message|message…|more options|follow back|requested|share profile|edit profile|view archive)$/i;
                    const bioStartIdx = headerLines.findIndex((l, i) =>
                        i >= 2 && !statsKeywords.test(l)
                    );
                    if (bioStartIdx > -1) {
                        const bioLines = [];
                        for (let i = bioStartIdx; i < headerLines.length; i++) {
                            const l = headerLines[i];
                            if (l === handle || statsKeywords.test(l) || buttonLabels.test(l)) break;
                            if (/^[a-z0-9-]+\.[a-z]{2,}(\/.*)?$/i.test(l) && !bioLink) {
                                bioLink = l;
                            } else {
                                bioLines.push(l);
                            }
                        }
                        bio = bioLines.join('\n');
                    }
                }
                return {
                    handle: handle,
                    display_name: displayName,
                    bio: bio,
                    bio_link: bioLink,
                    avatar_url: avatarUrl,
                    verified: verified,
                    is_private: isPrivate,
                    posts_count: parseCount(postsStr),
                    followers_count: parseCount(followersStr),
                    following_count: parseCount(followingStr),
                };
            }
            """,
            arg=username,
        )
    except Exception as exc:
        logger.warning("DOM user header extract failed: %s", exc)
        return None


async def _extract_grid(page, username, max_posts, scroll_distance, watcher):
    seen: set[str] = set()
    collected = 0
    stall = 0
    js = r"""
    (handle) => {
        const sels = [
            `a[href*="/${handle}/p/"]`,
            `a[href*="/${handle}/reel/"]`,
        ];
        const out = [];
        const seenHrefs = new Set();
        for (const sel of sels) {
            document.querySelectorAll(sel).forEach(a => {
                const href = a.getAttribute('href') || '';
                if (seenHrefs.has(href)) return;
                seenHrefs.add(href);
                const m = href.match(new RegExp(`^/${handle}/(p|reel|tv)/([^/]+)/?$`));
                if (!m) return;
                const postType = m[1];
                const shortcode = m[2];
                const img = a.querySelector('img');
                const altText = img ? (img.alt || '') : '';
                const isAuto = /^(photo by |photo shared by |may be an image of )/i.test(altText);
                const hashtagMatches = (altText.match(/#([\p{L}\p{N}_]+)/gu) || [])
                    .map(s => s.slice(1));
                const mentionMatches = (altText.match(/@([A-Za-z0-9._]+)/g) || [])
                    .map(s => s.slice(1));
                out.push({
                    post_id: shortcode,
                    post_type: postType,
                    url: 'https://www.instagram.com' + href,
                    author_handle: handle,
                    content_text: altText,
                    cover_url: img ? img.src : '',
                    hashtags: hashtagMatches,
                    mentions: mentionMatches,
                    is_alt_text_auto: isAuto,
                });
            });
        }
        return out;
    }
    """

    for _ in range(max_posts * 3):
        if watcher.triggered or collected >= max_posts:
            break

        items = await page.evaluate(js, username)
        new_this_round = 0
        for v in items:
            sid = v.get("post_id")
            if not sid or sid in seen:
                continue
            seen.add(sid)
            new_this_round += 1
            yield _build_post_item(v, source_handle=username)
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
        await page.wait_for_timeout(400)


def _build_user_item(info: dict, username: str) -> InstagramUserItem:
    return InstagramUserItem(
        platform="instagram",
        username=info.get("handle") or username,
        display_name=info.get("display_name") or "",
        bio=info.get("bio") or "",
        bio_link=info.get("bio_link") or "",
        avatar_url=info.get("avatar_url") or "",
        is_verified=bool(info.get("verified")),
        is_private=bool(info.get("is_private")),
        posts_count=info.get("posts_count"),
        followers_count=info.get("followers_count"),
        following_count=info.get("following_count"),
        scraped_at=datetime.now(timezone.utc).isoformat(),
    )


def _build_post_item(v: dict, *, source_handle: str) -> InstagramPostItem:
    return InstagramPostItem(
        platform="instagram",
        post_id=v.get("post_id") or "",
        url=v.get("url") or "",
        author_handle=v.get("author_handle") or source_handle,
        content_text=v.get("content_text") or "",
        cover_url=v.get("cover_url") or "",
        hashtags=v.get("hashtags") or [],
        mentions=v.get("mentions") or [],
        post_type=v.get("post_type") or "",
        is_alt_text_auto=v.get("is_alt_text_auto"),
        scraped_at=datetime.now(timezone.utc).isoformat(),
        source_spider="instagram_profile",
        source_query=source_handle,
    )
