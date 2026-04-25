# social-crawler

Multi-platform social media scraper (Facebook / Twitter(X) / Instagram) built on Scrapy + Playwright with Chrome DevTools Protocol attach. Each platform runs its own Chrome profile and CDP port, isolating cookies and surviving basic bot detection without headless browsers or rotating datacenter proxies.

This subdirectory is the **public capability demo**. The full production build (Redis proxy pool, dedup, multi-store pipelines, residential proxy integration) lives in a private repo and is delivered through paid engagement.

## Compliance notice (Important)

- Demonstration code only; targets **public, login-free content**
- No cookie / credential / session persistence code is bundled
- Respect platform ToS + robots.txt + rate limits in your use
- This demo does not provide techniques to bypass anti-bot measures, paywalls, or authentication gates

## What this demo does

- Scrapy project layout (items / spiders / middlewares / pipelines)
- Playwright CDP attach to a user-launched Chrome instance
- 3 platforms × 1 spider each (Facebook public Page, Twitter(X) public profile, Instagram public profile)
- Per-platform Chrome profile + CDP port isolation (no cookie cross-contamination)
- Single pipeline: daily sharded JSONL output
- Cross-platform Chrome launcher (WSL2 / Linux / macOS / Windows)

## Architecture

See [docs/architecture.md](docs/architecture.md) for the full diagram and rationale. TL;DR:

```text
User-launched Chrome (3 profiles, 3 CDP ports)
       │
       ▼
Scrapy spiders ──► CDP attach middleware ──► JSONL pipeline ──► data/{platform}/YYYY-MM-DD.jsonl
```

Stack details: [docs/stack.md](docs/stack.md).

## What this demo does NOT do (and the paid version does)

| Feature | Demo | Paid version |
| ---- | ---- | ---- |
| Storage backends | JSONL only | JSON + MongoDB + PostgreSQL + Google Sheets |
| Proxy pool | ⬜ None | ✅ Redis-backed with validator, sticky-per-profile binding |
| Dedup | ⬜ None | ✅ Redis SET with TTL |
| Field cleaning pipeline | ⬜ None | ✅ Time normalization, zero-width char stripping, required-field guards |
| User-agent rotation middleware | ⬜ None | ✅ |
| Rate-limit middleware | ⬜ None | ✅ Per-spider token bucket |
| Retry on proxy/IP failure | ⬜ None | ✅ Auto-demote bad proxies |
| Residential proxy integration | ⬜ None | ✅ Instagram / Twitter require it in production |
| Login / session persistence | ⬜ Not bundled | ⬜ Still not bundled (by design) |

**Login flow is deliberately excluded** from both demo and paid version. Users launch Chrome manually, log in manually if needed, and the scraper connects via CDP.

## Quick start

```bash
# 1. Install
uv sync
uv run playwright install chromium

# 2. Launch Chrome in CDP mode (choose one platform)
uv run python scripts/start_chrome_cdp.py --platform twitter
# The Chrome window opens; log in manually if needed (public pages don't require login)

# 3. In another terminal, run the spider
uv run scrapy crawl twitter_public_profile -a handle=anthropicai -a max_tweets=10

# Output: data/twitter/YYYY-MM-DD.jsonl
```

Three CDP ports (one per platform, independent user-data-dir):

| Platform | Default port | Chrome profile dir |
| ---- | ---- | ---- |
| `fb` | 9222 | `~/.chrome-profiles/fb` |
| `twitter` | 9223 | `~/.chrome-profiles/twitter` |
| `instagram` | 9224 | `~/.chrome-profiles/instagram` |

## Project layout

```text
social-crawler/
├── pyproject.toml            # uv-managed
├── scrapy.cfg
├── social_crawler/
│   ├── settings.py
│   ├── items.py              # merged single file
│   ├── pipelines.py          # JsonLines only
│   ├── middlewares.py        # CDP attach middleware only
│   └── spiders/
│       ├── facebook_public_page.py
│       ├── twitter_public_profile.py
│       └── instagram_public_profile.py
├── scripts/
│   └── start_chrome_cdp.py   # Cross-platform Chrome launcher
├── examples/
│   └── sample_output.jsonl   # Example of what output looks like
├── docs/
│   ├── architecture.md       # Data flow + per-platform isolation rationale
│   └── stack.md              # Tier-A stack list and selection notes
└── tests/
    └── test_items.py
```

## Known limitations (honest)

- DOM selectors on FB / IG / X change frequently (2-4 weeks); expect to tune the JS in each spider's `_extract_js()` method
- Instagram aggressively blocks datacenter IPs; the demo doesn't ship proxy infra (paid version does)
- Twitter internal API refactors every 2-4 weeks; DOM-based scrolling is more resilient than GraphQL interception but slower
- Without live Chrome + login, public-only profiles may still rate-limit aggressive scrolling

## Custom builds

For your specific platforms, residential proxy integration, or multi-store pipeline (Postgres / MongoDB / Sheets), reach out on Upwork.

## License

MIT. See repository root [LICENSE](../LICENSE).
