"""TikTok public profile spider (demo).

Usage:
    scrapy crawl tiktok_public_profile -a username=tiktok -a max_videos=10

Public profile pages do not require login. The spider parses the embedded
`__UNIVERSAL_DATA_FOR_REHYDRATION__` JSON for user info, then scrolls the
video grid and extracts each video card via the `data-e2e="user-post-item"`
attribute.

Demo limits (paid version supplies the rest):
- No request signing (comments / search excluded by design).
- No proxy pool, dedup, or anti-bot challenge watcher.
- DOM selectors and JSON paths can change; treat them as best-effort.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from typing import Any, AsyncGenerator

import scrapy
from scrapy.http import Request, Response

from social_crawler.items import SocialPostItem


TIKTOK_CDP_URL = f"http://localhost:{os.getenv('TIKTOK_CDP_PORT', '9225')}"


class TikTokPublicProfileSpider(scrapy.Spider):
    name = "tiktok_public_profile"
    platform = "tiktok"
    allowed_domains = ["tiktok.com", "www.tiktok.com"]

    custom_settings = {
        "PLAYWRIGHT_CDP_URL": TIKTOK_CDP_URL,
        "PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": 30_000,
    }

    def __init__(
        self,
        username: str | None = None,
        max_videos: int = 10,
        **kwargs,
    ):
        super().__init__(**kwargs)
        if not username:
            raise ValueError("-a username=<account> required")
        self.username = username.lstrip("@")
        self.max_videos = int(max_videos)

    def start_requests(self):
        yield Request(
            url=f"https://www.tiktok.com/@{self.username}",
            callback=self.parse_profile,
            meta={"playwright": True, "playwright_include_page": True},
        )

    async def parse_profile(self, response: Response) -> AsyncGenerator:
        page = response.meta["playwright_page"]
        seen: set[str] = set()
        collected = 0

        try:
            html = await page.content()
            user_info = _extract_user_info(html)
            if user_info:
                yield self._build_user_item(user_info)

            for _ in range(self.max_videos * 3):
                if collected >= self.max_videos:
                    break
                videos = await page.evaluate(_TIKTOK_EXTRACT_JS)
                for v in videos:
                    vid = v.get("id")
                    if not vid or vid in seen:
                        continue
                    seen.add(vid)
                    yield self._build_video_item(v)
                    collected += 1
                    if collected >= self.max_videos:
                        break
                await page.evaluate("window.scrollBy(0, 800)")
                await page.wait_for_timeout(1500)
        finally:
            await page.close()

    def _build_user_item(self, info: dict) -> SocialPostItem:
        """User profile is reported as a SocialPostItem with platform=tiktok and
        post_id='profile' for demo simplicity. Paid version uses TikTokUserItem.
        """
        user = info.get("user", {}) if isinstance(info, dict) else {}
        stats = info.get("stats", {}) if isinstance(info, dict) else {}

        item = SocialPostItem()
        item["platform"] = "tiktok"
        item["post_id"] = f"profile:{user.get('uniqueId') or self.username}"
        item["url"] = f"https://www.tiktok.com/@{self.username}"
        item["author_handle"] = user.get("uniqueId") or self.username
        item["author_display_name"] = user.get("nickname") or ""
        item["content_text"] = user.get("signature") or ""
        item["likes_count"] = stats.get("heartCount") or stats.get("heart")
        item["scraped_at"] = datetime.now(timezone.utc).isoformat()
        item["source_spider"] = self.name
        item["source_query"] = self.username
        return item

    def _build_video_item(self, v: dict) -> SocialPostItem:
        item = SocialPostItem()
        item["platform"] = "tiktok"
        item["post_id"] = v.get("id") or ""
        item["url"] = v.get("url") or ""
        item["author_handle"] = self.username
        item["cover_url"] = v.get("cover_url") or ""
        item["content_text"] = v.get("alt_text") or ""
        item["scraped_at"] = datetime.now(timezone.utc).isoformat()
        item["source_spider"] = self.name
        item["source_query"] = self.username
        return item


_TIKTOK_EXTRACT_JS = r"""
() => {
    const items = document.querySelectorAll('[data-e2e="user-post-item"]');
    const out = [];
    items.forEach(el => {
        const a = el.querySelector('a[href*="/video/"]');
        if (!a) return;
        const m = a.href.match(/\/video\/(\d+)/);
        if (!m) return;
        const img = el.querySelector('img');
        out.push({
            id: m[1],
            url: a.href,
            cover_url: img ? img.src : null,
            alt_text: img ? img.alt : '',
        });
    });
    return out;
}
"""

_RE_UNIVERSAL = re.compile(
    r'<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__"[^>]*>(.*?)</script>',
    re.DOTALL,
)


def _extract_user_info(html: str) -> dict[str, Any] | None:
    m = _RE_UNIVERSAL.search(html)
    if not m:
        return None
    try:
        data = json.loads(m.group(1))
        scope = data.get("__DEFAULT_SCOPE__", {})
        return scope.get("webapp.user-detail", {}).get("userInfo")
    except (json.JSONDecodeError, AttributeError):
        return None
