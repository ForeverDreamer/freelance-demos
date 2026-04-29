"""Twitter (X) user timeline spider.

Click-flow:
    /home (clean)
      → fill `[data-testid="SearchBox_Search_Input"]` (always visible, no popup)
      → wait for typeahead listbox to render >= 2 buttons
      → click typeahead button with text "Go to @<handle>"
      → SPA navigate to /<handle>
      → wait for `article[data-testid="tweet"]`
      → DOM extract loop + scroll

Note on the typeahead structure
-------------------------------
The "Go to @<handle>" button is rendered inside a `<div data-testid=
"typeaheadResult">` wrapper, NOT as a direct child of the listbox. The locator
must use `[role="listbox"] button` (descendant) plus `has_text=`, not a child
selector like `> button`.
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
from social_crawler.items import TwitterPostItem, TwitterUserItem
from social_crawler.pipelines import PipelineContext, run_pipelines

logger = logging.getLogger(__name__)


SEARCH_BOX_SEL = '[data-testid="SearchBox_Search_Input"]'
TYPEAHEAD_LISTBOX_SEL = '[role="listbox"]'
TWEET_ARTICLE_SEL = 'article[data-testid="tweet"]'
USER_NAME_SEL = '[data-testid="UserName"]'
USER_DESC_SEL = '[data-testid="UserDescription"]'
SOFT_BLOCK_PATTERNS = (
    "something went wrong",
    "try again later",
    "please try again",
    "rate limit exceeded",
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
    handle: str,
    max_tweets: int = 5,
    scroll_distance: int = 800,
) -> Stats:
    handle = handle.lstrip("@")
    stats = Stats()
    t0 = time.monotonic()

    def _t(label: str) -> None:
        logger.info("[tw-user] [+%6.2fs] %s", time.monotonic() - t0, label)

    _t("crawl start")

    async with PipelineContext(settings, spider_name="twitter_user") as pctx:
        async with cdp_session("twitter", settings) as page:
            watcher = PageChallengeWatcher(page, spider_logger=logger)
            try:
                async for item in _click_flow(page, handle, max_tweets, scroll_distance, watcher, _t):
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


async def _click_flow(page, handle, max_tweets, scroll_distance, watcher, _t):
    body_text = (await page.evaluate("() => document.body.innerText")).lower()
    for pattern in SOFT_BLOCK_PATTERNS:
        if pattern in body_text:
            logger.error("page already in soft-block state: %r at url=%s", pattern, page.url)
            return

    search_box = page.locator(SEARCH_BOX_SEL).first
    try:
        await search_box.wait_for(state="visible", timeout=5_000)
        await search_box.fill(handle)
        _t("fill done")
    except (PWTimeout, Exception) as exc:
        logger.error("search box fill failed: %s", exc)
        return

    # Typeahead is async; wait for at least 2 buttons in the listbox.
    try:
        await page.wait_for_function(
            """() => {
                const lb = document.querySelector('[role="listbox"]');
                if (!lb) return false;
                return lb.querySelectorAll('button').length >= 2;
            }""",
            timeout=5_000,
        )
        _t("typeahead listbox rendered")
    except PWTimeout:
        logger.error("typeahead listbox did not render")
        return

    if watcher.triggered:
        return

    # The "Go to @<handle>" button uses lowercase handle in its text.
    go_to = page.locator(
        f'{TYPEAHEAD_LISTBOX_SEL} button',
        has_text=f"Go to @{handle.lower()}",
    ).first
    try:
        await go_to.wait_for(state="visible", timeout=5_000)
        await go_to.click()
        _t("'Go to' clicked")
    except PWTimeout:
        logger.error("'Go to @%s' button not in typeahead", handle)
        return

    # X may redirect /lower → /Cased; match case-insensitively and exclude /search.
    try:
        await page.wait_for_url(
            lambda url: f"/{handle.lower()}" in url.lower() and "/search" not in url.lower(),
            timeout=15_000,
        )
        _t("profile URL committed")
    except PWTimeout:
        logger.error("profile URL did not commit; current url=%s", page.url)
        return

    try:
        await page.wait_for_selector(TWEET_ARTICLE_SEL, timeout=15_000)
        _t("tweet article visible")
    except PWTimeout:
        logger.error("timeline never rendered for @%s", handle)
        return

    body_text = (await page.evaluate("() => document.body.innerText")).lower()
    for pattern in SOFT_BLOCK_PATTERNS:
        if pattern in body_text:
            logger.error("post-navigate soft-block: %r at url=%s", pattern, page.url)
            return

    user_info = await _extract_user_dom(page)
    if user_info:
        yield _build_user_item(user_info, handle)

    async for tweet in _extract_tweets(page, handle, max_tweets, scroll_distance, watcher):
        yield tweet


async def _extract_user_dom(page) -> Optional[dict]:
    try:
        return await page.evaluate(
            r"""
            () => {
                const parseCount = (s) => {
                    if (!s) return null;
                    const m = s.match(/([\d,.]+)\s*([KMB])?/);
                    if (!m) return null;
                    let n = parseFloat(m[1].replace(/,/g, ''));
                    if (!Number.isFinite(n)) return null;
                    const suf = (m[2] || '').toUpperCase();
                    if (suf === 'K') n *= 1000;
                    else if (suf === 'M') n *= 1_000_000;
                    else if (suf === 'B') n *= 1_000_000_000;
                    return Math.round(n);
                };
                const nameEl = document.querySelector('[data-testid="UserName"]');
                const descEl = document.querySelector('[data-testid="UserDescription"]');
                const verifiedSvg = !!document.querySelector(
                    '[data-testid="UserName"] svg[aria-label*="erified"]'
                );
                let displayName = '', handle = '';
                if (nameEl) {
                    const lines = (nameEl.innerText || '').split('\n').filter(s => s.trim());
                    if (lines.length >= 2) {
                        displayName = lines[0];
                        const hLine = lines.find(l => l.startsWith('@'));
                        handle = hLine ? hLine.slice(1) : '';
                    } else if (lines.length === 1) {
                        displayName = lines[0];
                    }
                }
                const followersA = document.querySelector('a[href$="/verified_followers"]')
                    || document.querySelector('a[href$="/followers"]');
                const followingA = document.querySelector('a[href$="/following"]');
                const avatarImg = document.querySelector(
                    '[data-testid^="UserAvatar-Container-"] img'
                );
                return {
                    handle: handle,
                    display_name: displayName,
                    bio: descEl ? (descEl.innerText || '') : '',
                    verified: verifiedSvg,
                    profile_image_url: avatarImg ? avatarImg.src : '',
                    followers_count: parseCount(
                        followersA ? (followersA.innerText || '').split('\n')[0] : ''
                    ),
                    following_count: parseCount(
                        followingA ? (followingA.innerText || '').split('\n')[0] : ''
                    ),
                };
            }
            """
        )
    except Exception as exc:
        logger.warning("DOM user header extract failed: %s", exc)
        return None


async def _extract_tweets(page, handle, max_tweets, scroll_distance, watcher):
    seen: set[str] = set()
    collected = 0
    stall = 0
    js = r"""
    () => {
        const parseCount = (s) => {
            if (!s) return null;
            const trimmed = s.trim().replace(/,/g, '');
            const m = trimmed.match(/^([\d.]+)([KMB])?$/i);
            if (!m) return null;
            let n = parseFloat(m[1]);
            if (!Number.isFinite(n)) return null;
            const suf = (m[2] || '').toUpperCase();
            if (suf === 'K') n *= 1000;
            else if (suf === 'M') n *= 1_000_000;
            else if (suf === 'B') n *= 1_000_000_000;
            return Math.round(n);
        };
        const articles = document.querySelectorAll('article[data-testid="tweet"]');
        return Array.from(articles).map(el => {
            const promoted = (el.innerText || '').toLowerCase();
            const isAd = promoted.includes('\nad\n') || promoted.startsWith('ad\n');
            const textEl = el.querySelector('[data-testid="tweetText"]');
            const timeEl = el.querySelector('time');
            const linkEl = timeEl && timeEl.closest('a[href*="/status/"]');
            const url = linkEl ? linkEl.href : '';
            const id = url ? (url.split('/status/')[1] || '').split('?')[0].split('/')[0] : '';
            const handleEl = el.querySelector('[data-testid="User-Name"] a[href^="/"]');
            const tweetHandle = handleEl
                ? handleEl.getAttribute('href').replace(/^\//, '').split('/')[0]
                : '';
            const replyEl = el.querySelector('[data-testid="reply"]');
            const retweetEl = el.querySelector('[data-testid="retweet"]');
            const likeEl = el.querySelector('[data-testid="like"]');
            const viewsLink = el.querySelector('a[href*="/analytics"]');
            return {
                id: id,
                url: url,
                text: textEl ? textEl.innerText : '',
                datetime: timeEl ? timeEl.getAttribute('datetime') : '',
                handle: tweetHandle,
                replies: replyEl ? parseCount(replyEl.innerText) : null,
                retweets: retweetEl ? parseCount(retweetEl.innerText) : null,
                likes: likeEl ? parseCount(likeEl.innerText) : null,
                views: viewsLink ? parseCount(viewsLink.innerText) : null,
                is_ad: isAd,
            };
        }).filter(t => t.id && !t.is_ad);
    }
    """

    for _ in range(max_tweets * 3):
        if watcher.triggered or collected >= max_tweets:
            break

        tweets = await page.evaluate(js)
        new_this_round = 0
        for t in tweets:
            tid = t.get("id")
            if not tid or tid in seen:
                continue
            seen.add(tid)
            new_this_round += 1
            yield _build_tweet_item(t, handle)
            collected += 1
            if collected >= max_tweets:
                break

        if new_this_round == 0:
            stall += 1
            if stall >= 3:
                break
        else:
            stall = 0

        if collected >= max_tweets:
            break
        await page.evaluate(f"window.scrollBy(0, {scroll_distance})")
        await page.wait_for_timeout(400)


def _build_user_item(info: dict, handle: str) -> TwitterUserItem:
    return TwitterUserItem(
        platform="twitter",
        handle=info.get("handle") or handle,
        display_name=info.get("display_name") or "",
        bio=info.get("bio") or "",
        verified=bool(info.get("verified")),
        followers_count=info.get("followers_count"),
        following_count=info.get("following_count"),
        profile_image_url=info.get("profile_image_url") or "",
        scraped_at=datetime.now(timezone.utc).isoformat(),
    )


def _build_tweet_item(t: dict, source_handle: str) -> TwitterPostItem:
    return TwitterPostItem(
        platform="twitter",
        post_id=t.get("id") or "",
        url=t.get("url") or "",
        author_handle=t.get("handle") or source_handle,
        content_text=t.get("text") or "",
        created_at=t.get("datetime") or None,
        scraped_at=datetime.now(timezone.utc).isoformat(),
        likes_count=t.get("likes"),
        comments_count=t.get("replies"),
        retweets_count=t.get("retweets"),
        views_count=t.get("views"),
        source_spider="twitter_user",
        source_query=source_handle,
    )
