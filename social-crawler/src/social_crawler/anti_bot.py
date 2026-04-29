"""Anti-bot detection: shared constants + Playwright page event listener.

Public demo scope: a minimal pattern set covering the two demo platforms
(Twitter / TikTok) plus generic challenge fragments. The paid version
ships an extended pattern catalog covering Facebook checkpoint flows,
Instagram suspended-account / login-wall variants, datacenter-IP soft
blocks, regional CAPTCHA variants, and HTTP-status edge cases tuned per
platform. Extend `STOP_SIGNAL_FRAGMENTS` per platform in production.

Mechanism:

- `framenavigated` — the SPA pushed history to a challenge URL
- `response`       — main document returned 401 / 403 / 429 / 451 / 503

When triggered, `PageChallengeWatcher.triggered` is set to True with a reason
string. The spider checks this flag in its scroll/extract loop and exits
gracefully.
"""
from __future__ import annotations

import logging
from typing import Iterable, Optional

logger = logging.getLogger(__name__)

# URL fragments that indicate a challenge or login wall (demo subset).
# Production catalog is platform-specific and tuned per engagement.
STOP_SIGNAL_FRAGMENTS: tuple[str, ...] = (
    # Generic
    "challenge",
    "captcha",
    "/login",
    "verify",
    "blocked",
    # Twitter (X) — single representative pattern
    "/i/flow/login",
    # TikTok — single representative pattern
    "/captcha-verify",
)

# HTTP status codes on the main document that indicate stop conditions.
STOP_STATUS_CODES: frozenset[int] = frozenset({401, 403, 429, 451, 502, 503, 504})


def url_hits_stop_fragment(
    url: str, fragments: Iterable[str] = STOP_SIGNAL_FRAGMENTS
) -> Optional[str]:
    """Return the first matching fragment, or None."""
    if not url:
        return None
    for frag in fragments:
        if frag in url:
            return frag
    return None


class PageChallengeWatcher:
    """Listens to Playwright Page events and flags anti-bot triggers.

    Usage:
        watcher = PageChallengeWatcher(page)
        try:
            for ... :
                if watcher.triggered:
                    break
        finally:
            watcher.detach()
    """

    def __init__(
        self,
        page,
        *,
        stop_fragments: Iterable[str] = STOP_SIGNAL_FRAGMENTS,
        stop_status_codes: Iterable[int] = STOP_STATUS_CODES,
        spider_logger: Optional[logging.Logger] = None,
    ) -> None:
        self.page = page
        self.stop_fragments = tuple(stop_fragments)
        self.stop_status_codes = frozenset(stop_status_codes)
        self.logger = spider_logger or logger

        self.triggered: bool = False
        self.reason: Optional[str] = None

        page.on("framenavigated", self._on_framenavigated)
        page.on("response", self._on_response)

    def _on_framenavigated(self, frame) -> None:
        try:
            if frame is not self.page.main_frame:
                return
        except Exception:
            return
        try:
            url = frame.url or ""
        except Exception:
            return
        hit = url_hits_stop_fragment(url, self.stop_fragments)
        if hit:
            self._mark(f"url_redirect:{hit}", detail=url)

    def _on_response(self, response) -> None:
        try:
            if response.frame is not self.page.main_frame:
                return
            if response.request.resource_type != "document":
                return
        except Exception:
            return
        status = getattr(response, "status", None)
        if status in self.stop_status_codes:
            self._mark(f"http_{status}", detail=getattr(response, "url", ""))

    def _mark(self, reason: str, *, detail: str = "") -> None:
        if self.triggered:
            return
        self.triggered = True
        self.reason = reason
        self.logger.warning(
            "Anti-bot signal triggered: %s | url=%s | detail=%s",
            reason,
            getattr(self.page, "url", "<unknown>"),
            detail,
        )

    def detach(self) -> None:
        try:
            self.page.remove_listener("framenavigated", self._on_framenavigated)
            self.page.remove_listener("response", self._on_response)
        except Exception:
            pass
