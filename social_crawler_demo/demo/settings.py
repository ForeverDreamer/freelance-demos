"""Minimal Scrapy settings for public demo."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

BOT_NAME = "demo"
SPIDER_MODULES = ["demo.spiders"]
NEWSPIDER_MODULE = "demo.spiders"

ROBOTSTXT_OBEY = False  # Respected per-spider via explicit public-only targeting
DOWNLOAD_DELAY = 2
CONCURRENT_REQUESTS = 2
RANDOMIZE_DOWNLOAD_DELAY = True

TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"
REQUEST_FINGERPRINTER_IMPLEMENTATION = "2.7"
FEED_EXPORT_ENCODING = "utf-8"

DOWNLOAD_HANDLERS = {
    "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
    "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
}
PLAYWRIGHT_BROWSER_TYPE = "chromium"

PLATFORM_CDP_PORTS = {
    "fb": int(os.getenv("FB_CDP_PORT", "9222")),
    "twitter": int(os.getenv("TWITTER_CDP_PORT", "9223")),
    "instagram": int(os.getenv("INSTAGRAM_CDP_PORT", "9224")),
}

DOWNLOADER_MIDDLEWARES = {
    "demo.middlewares.PlaywrightCDPAttachMiddleware": 120,
}

ITEM_PIPELINES = {
    "demo.pipelines.JsonLinesPipeline": 300,
}

DATA_DIR = os.getenv("DATA_DIR", "./data")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
