"""CDP attach middleware for public demo.

Paid version adds: proxy pool, UA rotation, rate-limit middleware.
"""
from __future__ import annotations

import logging
import socket

from scrapy import signals
from scrapy.crawler import Crawler
from scrapy.http import Request

logger = logging.getLogger(__name__)


class PlaywrightCDPAttachMiddleware:
    def __init__(self, platform_ports: dict[str, int]):
        self.platform_ports = platform_ports

    @classmethod
    def from_crawler(cls, crawler: Crawler) -> "PlaywrightCDPAttachMiddleware":
        instance = cls(platform_ports=crawler.settings.getdict("PLATFORM_CDP_PORTS") or {})
        crawler.signals.connect(instance.spider_opened, signal=signals.spider_opened)
        return instance

    def spider_opened(self, spider) -> None:
        platform = getattr(spider, "platform", None)
        if not platform:
            return
        port = self.platform_ports.get(platform)
        if port and not _port_reachable("127.0.0.1", port):
            spider.logger.warning(
                "CDP port %d unreachable. Run "
                "'python scripts/start_chrome_cdp.py --platform %s' first.",
                port, platform,
            )

    def process_request(self, request: Request, spider):
        platform = getattr(spider, "platform", None)
        if platform:
            request.meta.setdefault("playwright", True)
            request.meta.setdefault("chrome_profile", platform)
        return None


def _port_reachable(host: str, port: int, timeout: float = 1.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False
