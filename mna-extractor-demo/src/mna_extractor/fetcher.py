"""Website fetcher: httpx primary, Playwright fallback (optional). Multi-page firm fetch (Module 1.5).

Module 1.5 (v0.3): per-firm multi-page fetch. Homepage + up to N sub-pages
(about / team / contact / portfolio tiers) concatenated, to give LLM more context
for HQ + industries + key contacts extraction. Lifts source_urls from 1 to 2-4 per firm,
unblocks confidence ceiling Medium → High.
"""

from __future__ import annotations

import asyncio
import os
import re
import time
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)


_NOISE_PATTERNS = [
    re.compile(r"<script[^>]*>.*?</script>", re.DOTALL | re.IGNORECASE),
    re.compile(r"<style[^>]*>.*?</style>", re.DOTALL | re.IGNORECASE),
    re.compile(r"<noscript[^>]*>.*?</noscript>", re.DOTALL | re.IGNORECASE),
    re.compile(r"<!--.*?-->", re.DOTALL),
    re.compile(r"<svg[^>]*>.*?</svg>", re.DOTALL | re.IGNORECASE),
]


def _strip_noise(html: str) -> str:
    """Remove script / style / svg / HTML comments. Reduces page size 40-70% for LLM context."""
    for pat in _NOISE_PATTERNS:
        html = pat.sub("", html)
    html = re.sub(r"\n\s*\n+", "\n\n", html)
    return html


@dataclass
class FetchResult:
    url: str
    status_code: int | None
    html: str | None
    error: str | None = None
    elapsed_ms: int = 0
    used_fallback: bool = False


@dataclass
class FirmPagesResult:
    """Multi-page fetch result for one firm. Module 1.5 (v0.3)."""

    homepage_url: str
    homepage_status: int | None
    fetched_urls: list[str] = field(default_factory=list)
    concatenated_html: str | None = None
    sub_page_failures: list[tuple[str, str]] = field(default_factory=list)
    total_elapsed_ms: int = 0
    homepage_error: str | None = None


# Sub-page discovery keywords. Tiered by extraction value:
# - about: firm history / type / segment description (firm_type, notes)
# - team: leadership names + titles (key_contacts)
# - contact: HQ city / office addresses (hq_location)
# - portfolio: industries + investments (industries_verticals, transaction_types)
SUBPAGE_KEYWORDS: dict[str, list[str]] = {
    "about": [
        "about", "about-us", "aboutus", "our-firm", "thefirm", "the-firm",
        "who-we-are", "whoweare", "company", "overview", "our-story",
    ],
    "team": [
        "team", "our-team", "ourteam", "people", "leadership", "partners-page",
        "our-people", "professionals",
    ],
    "contact": [
        "contact", "contact-us", "contactus", "offices", "locations", "office",
    ],
    "portfolio": [
        "portfolio", "investments", "companies", "our-companies", "ourcompanies",
        "portfolio-companies", "our-portfolio", "ourportfolio", "current-investments",
    ],
}


class HttpxFetcher:
    """Primary fetcher: async httpx with retry."""

    def __init__(
        self,
        timeout_seconds: int | None = None,
        user_agent: str | None = None,
        max_retries: int = 3,
    ):
        self.timeout = timeout_seconds or int(
            os.getenv("MNA_HTTP_TIMEOUT_SECONDS", "30")
        )
        self.user_agent = user_agent or os.getenv(
            "MNA_USER_AGENT",
            "Mozilla/5.0 (compatible; mna-extractor/0.1; research)",
        )
        self.max_retries = max_retries

    async def fetch(self, url: str) -> FetchResult:
        return await self._fetch_with_retry(url)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(
            (httpx.TimeoutException, httpx.NetworkError)
        ),
        reraise=True,
    )
    async def _fetch_with_retry(self, url: str) -> FetchResult:
        start = time.monotonic()
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout,
                follow_redirects=True,
                headers={"User-Agent": self.user_agent},
            ) as client:
                resp = await client.get(url)
                elapsed_ms = int((time.monotonic() - start) * 1000)
                if resp.status_code >= 400:
                    return FetchResult(
                        url=url,
                        status_code=resp.status_code,
                        html=None,
                        error=f"HTTP {resp.status_code}",
                        elapsed_ms=elapsed_ms,
                    )
                return FetchResult(
                    url=url,
                    status_code=resp.status_code,
                    html=resp.text,
                    elapsed_ms=elapsed_ms,
                )
        except Exception as exc:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            return FetchResult(
                url=url,
                status_code=None,
                html=None,
                error=f"{type(exc).__name__}: {exc}",
                elapsed_ms=elapsed_ms,
            )


async def _discover_subpages(homepage_url: str, html: str) -> dict[str, list[str]]:
    """Parse homepage HTML to find candidate sub-page URLs grouped by tier.

    Returns mapping of tier (about / team / contact / portfolio) to list of absolute URLs
    found within the same domain. Caller picks at most one per tier.
    """
    from selectolax.parser import HTMLParser

    homepage_domain = urlparse(homepage_url).netloc.lower()
    tree = HTMLParser(html)
    candidates: dict[str, list[str]] = {tier: [] for tier in SUBPAGE_KEYWORDS}
    seen: set[str] = {homepage_url.rstrip("/")}

    for anchor in tree.css("a[href]"):
        href = (anchor.attributes.get("href") or "").strip()
        text = (anchor.text() or "").lower().strip()
        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue
        absolute = urljoin(homepage_url, href).split("#")[0].rstrip("/")
        if urlparse(absolute).netloc.lower() != homepage_domain:
            continue
        if absolute in seen:
            continue

        absolute_lower = absolute.lower()
        for tier, keywords in SUBPAGE_KEYWORDS.items():
            for kw in keywords:
                if kw in text or f"/{kw}" in absolute_lower:
                    candidates[tier].append(absolute)
                    seen.add(absolute)
                    break
            else:
                continue
            break

    return candidates


async def fetch_firm_pages(
    homepage_url: str,
    max_subpages: int = 3,
    fetcher: HttpxFetcher | None = None,
) -> FirmPagesResult:
    """Fetch homepage + up to max_subpages sub-pages, concatenate HTML.

    Sub-page selection: take 1 from each tier (about, team, contact, portfolio) in priority
    order, capped at max_subpages. Failures on sub-pages are recorded but do not abort.

    HTML format: each section prefixed with `<!-- ===== SECTION_LABEL: URL ===== -->`
    so the LLM can attribute facts to specific pages.
    """
    fetcher = fetcher or HttpxFetcher()
    start = time.monotonic()

    home = await fetcher.fetch(homepage_url)
    if home.html is None:
        return FirmPagesResult(
            homepage_url=homepage_url,
            homepage_status=home.status_code,
            homepage_error=home.error,
            total_elapsed_ms=int((time.monotonic() - start) * 1000),
        )

    candidates = await _discover_subpages(homepage_url, home.html)

    selected: list[tuple[str, str]] = []
    for tier in ("about", "team", "contact", "portfolio"):
        if candidates[tier] and len(selected) < max_subpages:
            selected.append((tier, candidates[tier][0]))

    sub_results: list[FetchResult] = []
    if selected:
        sub_results = await asyncio.gather(
            *[fetcher.fetch(u) for _, u in selected]
        )

    fetched_urls = [homepage_url]
    sub_failures: list[tuple[str, str]] = []
    home_clean = _strip_noise(home.html)
    parts: list[str] = [f"<!-- ===== HOMEPAGE: {homepage_url} ===== -->\n{home_clean}"]

    for (tier, _expected_url), result in zip(selected, sub_results, strict=True):
        if result.html:
            fetched_urls.append(result.url)
            label = tier.upper()
            sub_clean = _strip_noise(result.html)
            parts.append(f"\n\n<!-- ===== {label}: {result.url} ===== -->\n{sub_clean}")
        else:
            sub_failures.append((result.url, result.error or "unknown"))

    return FirmPagesResult(
        homepage_url=homepage_url,
        homepage_status=home.status_code,
        fetched_urls=fetched_urls,
        concatenated_html="".join(parts),
        sub_page_failures=sub_failures,
        total_elapsed_ms=int((time.monotonic() - start) * 1000),
    )


async def fetch_batch(urls: list[str], concurrency: int = 10) -> list[FetchResult]:
    """Fetch a list of URLs concurrently. Used by Module 1 fetch-only smoke test."""
    fetcher = HttpxFetcher()
    sem = asyncio.Semaphore(concurrency)

    async def _bounded(url: str) -> FetchResult:
        async with sem:
            return await fetcher.fetch(url)

    return await asyncio.gather(*[_bounded(u) for u in urls])
