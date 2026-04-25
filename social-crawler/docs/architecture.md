# Architecture

Demo version of the multi-platform social crawler, drawn at the level of evidence rather than production scope. The internal repo carries the Redis proxy pool, dedup, multi-store pipelines, and cleaning middleware that this public sketch deliberately omits.

## Data flow

```text
┌───────────────────────────────────────────────────────────────┐
│  User-launched Chrome (one window per platform)               │
│                                                               │
│   profile=fb        port=9222   ~/.chrome-profiles/fb         │
│   profile=twitter   port=9223   ~/.chrome-profiles/twitter    │
│   profile=instagram port=9224   ~/.chrome-profiles/instagram  │
└──────────────┬─────────────┬─────────────┬────────────────────┘
               │             │             │
               ▼             ▼             ▼
       ┌────────────────────────────────────────┐
       │  Scrapy spiders (one per platform)     │
       │  - facebook_public_page                │
       │  - twitter_public_profile              │
       │  - instagram_public_profile            │
       └──────────────┬─────────────────────────┘
                      │
                      ▼
       ┌────────────────────────────────────────┐
       │  CDP attach middleware                 │
       │  - reads spider.platform → CDP port    │
       │  - playwright.connect_over_cdp(...)    │
       └──────────────┬─────────────────────────┘
                      │
                      ▼
       ┌────────────────────────────────────────┐
       │  JSONL pipeline (demo only)            │
       │  - data/{platform}/YYYY-MM-DD.jsonl    │
       └────────────────────────────────────────┘
```

## Why CDP attach instead of fresh headless

Three observations drove the architecture:

1. Fresh headless Chromium triggers basic bot detection on all three platforms within minutes, even on public pages. Real Chrome with a persistent profile and manual login goes further on a single account before rate limits kick in.
2. Cookie cross-contamination is a real failure mode: if one Chrome instance holds three logged-in accounts, the platform sees the unusual fingerprint and downgrades trust. Per-platform profiles plus per-platform user-data-dir keep each session looking like an ordinary user.
3. CDP attach lets Scrapy reuse the network stack and rendered DOM of a Chrome the user already trusts, instead of trying to reproduce that trust from scratch each crawl.

## Profile and port isolation

Each platform binds to a fixed user-data-dir and a fixed CDP port. Switching platforms means starting a different Chrome process, not a different tab inside the same browser. This is intentional:

- Cookies, localStorage, and IndexedDB are scoped per user-data-dir, so a Facebook session never leaks into the Instagram crawl
- The CDP port is the integration boundary the spider sees; the spider does not know or care what is logged in
- Replacing the proxy attached to one Chrome profile does not perturb the other two

## What the paid version adds (omitted here by design)

| Layer | Demo | Paid version |
| ---- | ---- | ---- |
| Storage | JSONL only | JSON + MongoDB + PostgreSQL + Google Sheets |
| Dedup | None | Redis SET with TTL, keyed on `(platform, post_id)` |
| Proxy pool | None | Redis-backed pool with validator, sticky-per-profile binding |
| Cleaning pipeline | None | Time normalization, zero-width char strip, required-field guards |
| Rate limiting | Scrapy default `DOWNLOAD_DELAY=2` | Per-spider token bucket, behavior-aware |
| Residential proxy integration | None | Bright Data / Smartproxy provider plug-ins |
| User-agent rotation | None | Rotating UA middleware tied to proxy provider |

The paid version's Redis proxy pool with sticky-per-profile binding is the layer Instagram and X actually require in production. Datacenter IPs get banned within hours on those two platforms regardless of browser type.

## TODO: see private repo for full implementation

- `proxy/pool.py` Redis store with downgrade on failure
- `proxy/validator.py` async aiohttp liveness checker
- `pipelines/dedup.py` Redis SET-based dedup with TTL
- `pipelines/clean.py` field normalization and zero-width strip
- `proxy/providers/<vendor>.py` Bright Data / Smartproxy adapters
- `middlewares/user_agent.py` rotating UA tied to proxy
- `middlewares/rate_limit.py` per-spider token bucket
