"""Single-file merged items for public demo."""
from __future__ import annotations

import scrapy


class SocialPostItem(scrapy.Item):
    platform = scrapy.Field()            # "fb" | "twitter" | "instagram" | "tiktok"
    post_id = scrapy.Field()
    url = scrapy.Field()
    author_handle = scrapy.Field()
    author_display_name = scrapy.Field()
    content_text = scrapy.Field()
    created_at = scrapy.Field()
    scraped_at = scrapy.Field()
    likes_count = scrapy.Field()
    comments_count = scrapy.Field()
    media_urls = scrapy.Field()
    source_spider = scrapy.Field()
    source_query = scrapy.Field()
    # Platform-specific optional fields (loose schema for demo simplicity)
    shares_count = scrapy.Field()        # FB / TikTok
    retweets_count = scrapy.Field()      # Twitter
    shortcode = scrapy.Field()           # IG
    media_type = scrapy.Field()          # IG
    # TikTok-specific
    plays_count = scrapy.Field()         # TikTok playCount
    cover_url = scrapy.Field()           # TikTok video cover thumbnail
    hashtags = scrapy.Field()            # TikTok textExtra hashtags
