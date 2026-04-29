# Architecture

## Why pure asyncio + Playwright (and not Scrapy)

The first iteration of this crawler was built on Scrapy + scrapy-playwright.
After many iterations of optimization the spider's end-to-end time stalled
at ~100 s — and the timing log showed every event landing on the 5-second
boundary (e.g., 9.99 s, 14.99 s, 19.99 s). The cause:

> scrapy-playwright runs Playwright in a separate thread and re-emits its
> events through Twisted's reactor. The reactor cross-thread emit path
> processes pending events on a 5-second tick. So no matter how much we
> shaved off any individual `await` (a popup-wait from 10 s to 5 s, a
> wait_for_load_state removal that should have saved 1.5 s), the event
> didn't reach the Python log handler until the next reactor tick boundary.
> Total click-flow time stayed at ~50 s regardless.

Switching to pure asyncio + Playwright eliminated this overhead. The same
crawler now runs in seconds-range per spider on warm profiles.

## Click-flow over `page.goto`

The crawler triggers each navigation via a real DOM click — not via
`page.goto(url)` — because:

| Server-side observation | `page.goto(url)` | Real click |
| ---- | ---- | ---- |
| `sec-fetch-user` header | `?0` (no user gesture) | `?1` (user gesture) |
| Navigation type | Fresh document fetch | SPA `pushState` (no doc fetch) |
| Telemetry pattern | "Stale background tab + jump" | "User clicks button → SPA route change" |
| Likelihood of challenge | Higher | Lower |

The crawler reproduces the real-click pattern by:

1. Connecting via CDP to a Chrome window the user opened manually
2. Reusing `browser.contexts[0].pages[0]` (the user's existing tab)
3. Triggering each step with `page.locator(...).click()`, which goes through
   CDP's `Input.dispatchMouseEvent` with `isTrusted=true`

For each platform the click-flow has a fixed shape:

```text
homepage → search trigger → fill query → typeahead/click → SPA navigate
```

Demo scope ships click-flow implementations for **Twitter (X)** and
**TikTok** user profiles. Per-platform variations (search-popup activation
races, typeahead DOM-tree variants, profile-card vs hero-card disambiguation,
trusted-vs-JS click preference, regional locale handling) are tuned per
platform in the paid version. Contact via Upwork to scope a paid build.

## Anti-bot watcher

`PageChallengeWatcher` (in `anti_bot.py`) listens to two Playwright `page`
events:

- `framenavigated` — main-frame URL changed. If the new URL contains a
  challenge fragment (a generic `challenge` / `captcha` / `/login` / `verify`
  family plus a small per-platform set), set `triggered=True`.
- `response` — main-frame main-document HTTP response. If status is
  401 / 403 / 429 / 451 / 503, set `triggered=True`.

The spider's scroll/extract loop checks `watcher.triggered` each iteration.
On trigger the spider exits gracefully (no exception is raised inside the
async event-loop callback — Playwright callbacks swallow exceptions, so the
spider main loop reads the flag and breaks).

The demo ships a minimal pattern set. The paid version expands it with
platform-tuned challenge / suspended-account / login-wall / regional CAPTCHA
patterns and HTTP-status edge cases.

## Data flow

```text
                    ┌──────────────────────────────┐
                    │  scripts/start_chrome_cdp.py  │
                    │  (cross-platform launcher)    │
                    └──────────────┬───────────────┘
                                   │ launches
                                   ▼
       ┌────────────────────────────────────────────┐
       │  Chrome (user-launched, --remote-debugging) │
       │  Port:    9223 (twitter) / 9225 (tiktok)    │
       │  Profile: ~/.chrome-profiles/<platform>/    │
       │  Tab(s):  user-opened, may be logged in     │
       └─────────────────┬──────────────────────────┘
                         │ CDP attach
                         ▼
           ┌──────────────────────────────┐
           │  src/social_crawler/browser  │
           │  cdp_session(platform):      │
           │    connect_over_cdp()        │
           │    reuse contexts[0].pages   │
           │    nav reset to homepage     │
           └────────────┬────────────────┘
                        │ yields page
                        ▼
        ┌──────────────────────────────────────┐
        │  src/social_crawler/spiders/<name>   │
        │  click-flow → DOM extract via        │
        │  page.evaluate                       │
        │  PageChallengeWatcher attached       │
        └────────────┬─────────────────────────┘
                     │ yield item (dataclass)
                     ▼
            ┌───────────────────────────┐
            │  pipelines.run_pipelines  │
            │  → clean()                │
            │  → write_jsonl()          │
            └────────────┬──────────────┘
                         ▼
            data/<platform>/YYYY-MM-DD.jsonl
```

## Demo scope

| Platform | Spider | CLI subcommand |
| ---- | ---- | ---- |
| TikTok | user profile | `tk-user --username <name>` |
| Twitter (X) | user timeline | `tw-user --handle <name>` |

The paid version adds Facebook Page feed, Instagram profile, TikTok hashtag
page, and TikTok video detail metadata, plus production-grade pipelines
(see [README.md](../README.md) "What this demo does NOT do" table for the
full diff).
