"""Facebook public Page spider (demo).

Usage:
    scrapy crawl facebook_public_page -a page_url=https://www.facebook.com/<public-page>
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import AsyncGenerator

import scrapy
from scrapy.http import Request, Response

from demo.items import SocialPostItem

FB_CDP_URL = f"http://localhost:{os.getenv('FB_CDP_PORT', '9222')}"


class FacebookPublicPageSpider(scrapy.Spider):
    name = "facebook_public_page"
    platform = "fb"
    allowed_domains = ["facebook.com", "www.facebook.com"]

    custom_settings = {
        "PLAYWRIGHT_CDP_URL": FB_CDP_URL,
        "PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": 30_000,
    }

    def __init__(self, page_url: str | None = None, max_posts: int = 10, **kwargs):
        super().__init__(**kwargs)
        if not page_url:
            raise ValueError("-a page_url=<url> required")
        self.page_url = page_url
        self.max_posts = int(max_posts)

    def start_requests(self):
        yield Request(
            url=self.page_url,
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
                posts = await page.evaluate(_FB_EXTRACT_JS)
                for p in posts:
                    url = p.get("url")
                    if not url or url in seen:
                        continue
                    seen.add(url)
                    yield _build_item(p, self.name, self.page_url)
                    collected += 1
                    if collected >= self.max_posts:
                        break
                await page.evaluate("window.scrollBy(0, 600)")
                await page.wait_for_timeout(1500)
        finally:
            await page.close()


_FB_EXTRACT_JS = """
() => {
    const posts = document.querySelectorAll('[role="article"]');
    return Array.from(posts).map(el => {
        const t = el.querySelector('[data-ad-preview="message"], [data-ad-comet-preview="message"]');
        const a = el.querySelector('a[href*="/posts/"], a[href*="/videos/"], a[href*="/photo"]');
        const h = el.querySelector('h2, h3, h4');
        const tm = el.querySelector('a[role="link"] > span, abbr');
        return {
            text: t ? t.innerText : '',
            url: a ? a.href : '',
            author: h ? h.innerText : '',
            timestamp: tm ? (tm.getAttribute('title') || tm.innerText) : '',
        };
    }).filter(d => d.url);
}
"""


def _build_item(data: dict, spider_name: str, source_query: str) -> SocialPostItem:
    url = data.get("url", "")
    post_id = url.rstrip("/").split("/")[-1].split("?")[0] if url else ""
    item = SocialPostItem()
    item["platform"] = "fb"
    item["post_id"] = post_id
    item["url"] = url
    item["author_display_name"] = data.get("author") or None
    item["content_text"] = data.get("text") or ""
    item["created_at"] = data.get("timestamp") or None
    item["scraped_at"] = datetime.now(timezone.utc).isoformat()
    item["source_spider"] = spider_name
    item["source_query"] = source_query
    return item
