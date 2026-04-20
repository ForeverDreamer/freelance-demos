"""Twitter/X public profile spider (demo).

Usage:
    scrapy crawl twitter_public_profile -a handle=anthropicai -a max_tweets=10
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import AsyncGenerator

import scrapy
from scrapy.http import Request, Response

from demo.items import SocialPostItem

TWITTER_CDP_URL = f"http://localhost:{os.getenv('TWITTER_CDP_PORT', '9223')}"


class TwitterPublicProfileSpider(scrapy.Spider):
    name = "twitter_public_profile"
    platform = "twitter"
    allowed_domains = ["x.com", "twitter.com"]

    custom_settings = {
        "PLAYWRIGHT_CDP_URL": TWITTER_CDP_URL,
        "PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": 30_000,
    }

    def __init__(self, handle: str | None = None, max_tweets: int = 10, **kwargs):
        super().__init__(**kwargs)
        if not handle:
            raise ValueError("-a handle=<screen_name> required")
        self.handle = handle.lstrip("@")
        self.max_tweets = int(max_tweets)

    def start_requests(self):
        yield Request(
            url=f"https://x.com/{self.handle}",
            callback=self.parse,
            meta={"playwright": True, "playwright_include_page": True},
        )

    async def parse(self, response: Response) -> AsyncGenerator:
        page = response.meta["playwright_page"]
        seen: set[str] = set()
        collected = 0
        try:
            for _ in range(self.max_tweets * 3):
                if collected >= self.max_tweets:
                    break
                tweets = await page.evaluate(_TW_EXTRACT_JS)
                for t in tweets:
                    tid = t.get("id")
                    if not tid or tid in seen:
                        continue
                    seen.add(tid)
                    yield self._build_item(t)
                    collected += 1
                    if collected >= self.max_tweets:
                        break
                await page.evaluate("window.scrollBy(0, 800)")
                await page.wait_for_timeout(1500)
        finally:
            await page.close()

    def _build_item(self, t: dict) -> SocialPostItem:
        item = SocialPostItem()
        item["platform"] = "twitter"
        item["post_id"] = t.get("id") or ""
        item["url"] = t.get("url") or ""
        item["author_handle"] = t.get("handle") or self.handle
        item["content_text"] = t.get("text") or ""
        item["created_at"] = t.get("datetime") or None
        item["scraped_at"] = datetime.now(timezone.utc).isoformat()
        item["likes_count"] = t.get("likes")
        item["comments_count"] = t.get("replies")
        item["retweets_count"] = t.get("retweets")
        item["source_spider"] = self.name
        item["source_query"] = self.handle
        return item


_TW_EXTRACT_JS = """
() => {
    const parseCount = (s) => {
        if (!s) return null;
        const n = s.trim().replace(/,/g, '');
        if (n.endsWith('K')) return Math.round(parseFloat(n) * 1000);
        if (n.endsWith('M')) return Math.round(parseFloat(n) * 1000000);
        return parseInt(n, 10) || null;
    };
    const arts = document.querySelectorAll('article[data-testid="tweet"]');
    return Array.from(arts).map(el => {
        const text = el.querySelector('[data-testid="tweetText"]');
        const time = el.querySelector('time');
        const link = time && time.closest('a[href*="/status/"]');
        const url = link ? link.href : '';
        const id = url ? url.split('/status/')[1]?.split('?')[0] : '';
        const h = el.querySelector('[data-testid="User-Name"] a[href^="/"]');
        const handle = h ? h.getAttribute('href').replace('/', '') : '';
        return {
            id, url,
            text: text ? text.innerText : '',
            datetime: time ? time.getAttribute('datetime') : '',
            handle,
            replies: parseCount(el.querySelector('[data-testid="reply"]')?.innerText),
            retweets: parseCount(el.querySelector('[data-testid="retweet"]')?.innerText),
            likes: parseCount(el.querySelector('[data-testid="like"]')?.innerText),
        };
    }).filter(t => t.id);
}
"""
