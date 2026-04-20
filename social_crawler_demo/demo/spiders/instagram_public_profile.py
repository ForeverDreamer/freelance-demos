"""Instagram public profile spider (demo).

Usage:
    scrapy crawl instagram_public_profile -a username=anthropic.ai -a max_posts=10

Note: Instagram aggressively blocks datacenter IPs. The demo does not ship
proxy pool infrastructure; add residential proxies in production.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import AsyncGenerator

import scrapy
from scrapy.http import Request, Response

from demo.items import SocialPostItem

IG_CDP_URL = f"http://localhost:{os.getenv('INSTAGRAM_CDP_PORT', '9224')}"


class InstagramPublicProfileSpider(scrapy.Spider):
    name = "instagram_public_profile"
    platform = "instagram"
    allowed_domains = ["instagram.com", "www.instagram.com"]

    custom_settings = {
        "PLAYWRIGHT_CDP_URL": IG_CDP_URL,
        "PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": 30_000,
    }

    def __init__(self, username: str | None = None, max_posts: int = 10, **kwargs):
        super().__init__(**kwargs)
        if not username:
            raise ValueError("-a username=<account> required")
        self.username = username
        self.max_posts = int(max_posts)

    def start_requests(self):
        yield Request(
            url=f"https://www.instagram.com/{self.username}/",
            callback=self.parse,
            meta={"playwright": True, "playwright_include_page": True},
        )

    async def parse(self, response: Response) -> AsyncGenerator:
        page = response.meta["playwright_page"]
        seen: set[str] = set()
        collected = 0
        try:
            for _ in range(self.max_posts * 3):
                if collected >= self.max_posts:
                    break
                posts = await page.evaluate(_IG_EXTRACT_JS)
                for p in posts:
                    sc = p.get("shortcode")
                    if not sc or sc in seen:
                        continue
                    seen.add(sc)
                    yield self._build_item(p)
                    collected += 1
                    if collected >= self.max_posts:
                        break
                await page.evaluate("window.scrollBy(0, 800)")
                await page.wait_for_timeout(1500)
        finally:
            await page.close()

    def _build_item(self, p: dict) -> SocialPostItem:
        item = SocialPostItem()
        item["platform"] = "instagram"
        item["post_id"] = p.get("shortcode") or ""
        item["shortcode"] = p.get("shortcode") or ""
        item["url"] = p.get("url") or ""
        item["author_handle"] = self.username
        item["media_type"] = p.get("media_type") or "image"
        item["media_urls"] = [p["thumbnail_url"]] if p.get("thumbnail_url") else []
        item["content_text"] = p.get("alt_text") or ""
        item["scraped_at"] = datetime.now(timezone.utc).isoformat()
        item["source_spider"] = self.name
        item["source_query"] = self.username
        return item


_IG_EXTRACT_JS = r"""
() => {
    const anchors = document.querySelectorAll('a[href*="/p/"], a[href*="/reel/"]');
    const seen = new Set();
    const out = [];
    anchors.forEach(a => {
        const m = a.href.match(/\/(?:p|reel)\/([^\/?#]+)/);
        if (!m) return;
        const sc = m[1];
        if (seen.has(sc)) return;
        seen.add(sc);
        const img = a.querySelector('img');
        const video = a.querySelector('video');
        const isReel = a.href.includes('/reel/');
        out.push({
            shortcode: sc,
            url: a.href,
            thumbnail_url: img ? img.src : null,
            media_type: isReel ? 'reel' : (video ? 'video' : 'image'),
            alt_text: img ? img.alt : '',
        });
    });
    return out;
}
"""
