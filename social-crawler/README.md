# social-crawler

Multi-platform social media scraper built on **pure asyncio + Playwright with
Chrome DevTools Protocol attach**. Each platform runs its own Chrome profile
and CDP port, isolating cookies and surviving basic bot detection without
headless browsers or rotating datacenter proxies.

This subdirectory is the **public capability demo**. It ships **2 spiders**
(Twitter user timeline + TikTok user profile) so you can verify the
architecture end-to-end in a few minutes. The full production build ships
**6 spiders × 4 platforms** (Facebook Page feed, Instagram profile, TikTok
hashtag page, TikTok video detail metadata) plus Redis dedup, MongoDB
warehouse, residential-proxy integration, humanized typing/clicking, retry
middleware, and structured observability — delivered through paid engagement.

Custom builds → [Upwork profile](https://www.upwork.com/freelancers/~0140562708001afd27)

## Compliance notice (important)

- Demonstration code only; targets **public, login-free content**
- No cookie / credential / session persistence code is bundled
- Respect platform ToS + robots.txt + rate limits in your use
- This demo does not provide techniques to bypass anti-bot measures, paywalls,
  or authentication gates

## What this demo does

- **Pure asyncio + Playwright** crawler (no Scrapy, no Twisted)
- **Click-flow navigation** — the crawler never calls `page.goto(url)` directly;
  it triggers SPA navigation by clicking real DOM elements (search button,
  typeahead result, sidebar link). This matches how a real user reaches a
  profile page and avoids `sec-fetch-user=?0` server-side detection
- **CDP attach reuse** to a user-launched Chrome instance (`connect_over_cdp` +
  reuse `browser.contexts[0].pages[0]`); the crawler does not spawn its own
  browser
- 2 spiders × 2 platforms (Twitter user timeline, TikTok user profile) — the
  rest of the suite ships in the paid version
- Per-platform Chrome profile + CDP port isolation (no cookie cross-contamination)
- Anti-bot watcher — Playwright `page.on('framenavigated')` + `page.on('response')`
  listeners detect challenge URL fragments and HTTP 401/403/429 on the main
  document; the spider exits gracefully on trigger
- Single pipeline: daily-sharded JSONL output (`data/<platform>/YYYY-MM-DD.jsonl`)
- Cross-platform Chrome launcher (WSL2 / Linux / macOS / Windows)

## Architecture

See [docs/architecture.md](docs/architecture.md) for the full diagram and
rationale. TL;DR:

```text
User-launched Chrome (per-platform profile, dedicated CDP port, logged-in tab)
       │
       ▼
asyncio spider ──► click-flow (real DOM clicks, SPA pushState)
       │
       ▼
DOM extract via page.evaluate ──► JSONL pipeline ──► data/<platform>/YYYY-MM-DD.jsonl
       │
       ▼
PageChallengeWatcher (Playwright event listeners) ──► graceful exit on anti-bot signal
```

## Why click-flow instead of `page.goto(url)`

When a server sees `page.goto(url)` it observes:

- `sec-fetch-user: ?0` (programmatic navigation, no user gesture)
- A "stale background tab + jump-to-URL" pattern that automation telemetry can fingerprint

Real users navigate via:

- Click search button → fill query → click typeahead result → SPA `pushState`
- All three steps are inside an existing logged-in tab; the request headers
  show `sec-fetch-user: ?1` and the navigation does not even fire a fresh
  document fetch

The crawler reproduces this by:

1. Connecting via CDP to a Chrome window the user opened manually
2. Reusing `browser.contexts[0].pages[0]` (already on the platform homepage)
3. Triggering each step with `page.locator(...).click()` (CDP
   `Input.dispatchMouseEvent`, `isTrusted=true`)

End-to-end timing measured on real logged-in profiles: ~1.7 s for Twitter,
~5 s for TikTok user profile (warm runs).

## What this demo does NOT do (and the paid version does)

| Feature | Demo | Paid version |
| ---- | ---- | ---- |
| Spider coverage | 2 spiders × 2 platforms (twitter user, tiktok user) | 6 spiders × 4 platforms (+ Facebook Page feed, Instagram profile, TikTok hashtag, TikTok video detail) |
| Storage backends | JSONL only | JSONL + MongoDB upsert + Redis dedup + PostgreSQL warehouse + Google Sheets |
| Dedup | ⬜ None | ✅ Redis SET with 30-day TTL keyed by `dedup:<platform>:<post_id>` |
| Field cleaning pipeline | Basic time normalization | Time normalization, zero-width char stripping, required-field guards, language detection |
| Humanized typing/clicking | ⬜ Not bundled | ✅ `--humanize` flag adds 80–180 ms per-character keystroke jitter + 400–1500 ms pre-click delays |
| Rate-limit middleware | ⬜ None | ✅ Per-spider token bucket, configurable burst/sustain |
| Retry on transient failures | ⬜ None | ✅ Exponential backoff with jitter |
| Residential proxy integration | ⬜ None | ✅ Sticky-per-profile binding for Instagram / Twitter |
| Selector fallbacks across UI revisions | ⬜ Single selector path | ✅ Multi-tier fallback chain per platform, regional locale variants |
| Anti-bot URL pattern catalog | ⬜ Minimal subset | ✅ Platform-tuned challenge / suspended-account / login-wall / regional CAPTCHA patterns |
| Login / session persistence | ⬜ Not bundled | ⬜ Still not bundled (by design — user logs in manually once, profile dir persists) |
| Structured observability | ⬜ stdlib logging | ✅ JSON log lines + per-spider metrics |
| Production CLI | `python -m social_crawler.main` | `crawlctl` umbrella tool with `chrome` / `crawl` / `info` / `infra` subcommands |

**Login flow is deliberately excluded** from both demo and paid version. Users
launch Chrome manually, log in manually if needed, and the scraper attaches via
CDP. This keeps credentials out of code and respects platform ToS by leaving
authentication to the human operator.

## Quick start

### 1. Install

```bash
uv sync
uv run playwright install chromium
```

### 2. Launch Chrome in CDP mode

Each platform runs in its own profile so cookies don't cross-contaminate.

```bash
# Choose one platform (the script picks a default port + user-data-dir)
uv run python scripts/start_chrome_cdp.py --platform twitter
```

The Chrome window opens on a blank New Tab Page. **Open a new tab manually**
(`Ctrl+T`), type the platform homepage URL, press Enter, and let it load. If
the platform requires login, log in manually once — the session persists in
`~/.chrome-profiles/<platform>/`.

### 3. Run a spider

In another terminal:

```bash
# Twitter user timeline (~1.7 s end-to-end on a warm profile)
uv run python -m social_crawler.main tw-user --handle anthropicai --max 10

# TikTok user profile (~5 s, 5-step click-flow)
uv run python -m social_crawler.main tk-user --username natgeo --max 5
```

Output is written to `data/<platform>/YYYY-MM-DD.jsonl` (one JSON record per
line, daily sharded).

For the rest of the spider catalog (Facebook Page feed, Instagram profile,
TikTok hashtag, TikTok video detail) and the production-grade features in
the table above, contact via the [Upwork profile](https://www.upwork.com/freelancers/~0140562708001afd27).

### 4. Check the output

```bash
ls data/twitter/
# 2026-04-29.jsonl

head -1 data/twitter/2026-04-29.jsonl | python -m json.tool
```

See [examples/sample_output.jsonl](examples/sample_output.jsonl) for what the
records look like.

## Default ports

Two CDP ports (one per demo platform, independent `user-data-dir`). The paid
version registers `fb=9222` and `instagram=9224` in addition.

| Platform | Default port | Chrome profile dir | CLI subcommand |
| ---- | ---- | ---- | ---- |
| `twitter` | 9223 | `~/.chrome-profiles/twitter` | `tw-user` |
| `tiktok` | 9225 | `~/.chrome-profiles/tiktok` | `tk-user` |

Override via env vars (`TWITTER_CDP_PORT`, `TIKTOK_CDP_PORT`) or `--port`
flag on `start_chrome_cdp.py`.

## Project layout

```text
social-crawler/
├── pyproject.toml             # uv-managed
├── README.md                  # this file
├── .env.example               # CDP port + data dir overrides
├── .gitignore
├── docs/
│   ├── architecture.md        # Click-flow rationale + per-platform notes
│   └── stack.md               # Stack decisions (why asyncio over Scrapy)
├── examples/
│   └── sample_output.jsonl    # Example records
├── scripts/
│   └── start_chrome_cdp.py    # Cross-platform Chrome launcher with CDP port
├── src/social_crawler/
│   ├── __init__.py
│   ├── main.py                # click CLI entrypoint (2 subcommands in the demo)
│   ├── config.py              # Settings dataclass loaded from .env
│   ├── browser.py             # connect_over_cdp + page reuse (attach mode)
│   ├── nav.py                 # Sidebar Home reset (returns to clean homepage)
│   ├── anti_bot.py            # PageChallengeWatcher (event-based detection)
│   ├── items.py               # @dataclass items per platform
│   ├── pipelines.py           # Async JSONL pipeline (clean → write_jsonl)
│   └── spiders/
│       ├── tiktok_user.py     # 5-step click-flow showcase
│       └── twitter_user.py    # Fastest spider (~1.7 s)
└── tests/
    └── test_items.py          # Item dataclass round-trip
```

## FAQ

**Q: Why not just `requests` + signed-out HTML scraping?**

Most platforms ship 80% of the timeline content behind JavaScript-rendered
SPA components. Even logged-out HTML on TikTok shows only a header and
"follow to see more". You need a real browser.

**Q: Why not Scrapy + scrapy-playwright?**

Scrapy's Twisted reactor runs on a 5-second tick on the event loop's
cross-thread emit path. In an earlier build of this crawler, single-step
optimizations (e.g., reducing a popup-wait from 10 s to 5 s) were absorbed
by the reactor tick boundary — the spider's total click-flow time stayed at
~50 s regardless. Switching to pure asyncio eliminated this overhead and
brought the same crawler down to seconds-range per run.

**Q: Why CDP attach instead of Playwright launching its own browser?**

Two reasons: (a) the user logs in manually once, the session persists in
the profile dir, and the crawler never sees credentials; (b) Playwright-
launched browsers carry distinguishing automation fingerprints (the
`navigator.webdriver = true` flag, `--enable-automation` Chrome flag,
`HeadlessChrome` user agent fragment) that several of these platforms detect.

**Q: Will this work on private/login-required content?**

Public profile content only. The CDP attach pattern means whatever the
logged-in user can see, the crawler can extract — but the crawler never
performs the login itself. For client engagements that need account-bound
content, the user grants their own session; for fully anonymous public data,
no login is needed at all.

**Q: How do I get the rest of the spiders / the production features?**

Contact via the [Upwork profile](https://www.upwork.com/freelancers/~0140562708001afd27)
to scope a paid engagement. The production build is delivered as a private
repo or a containerized deployment, depending on what fits your team.

## License

MIT (see [LICENSE](../LICENSE) at the monorepo root).
