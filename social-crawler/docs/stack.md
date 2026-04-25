# Stack

| Layer | Tech | Why |
| ---- | ---- | ---- |
| Crawl framework | Scrapy 2.x | Battle-tested project structure: items / spiders / middlewares / pipelines pattern; built-in concurrency control |
| Browser automation | Playwright + Chrome DevTools Protocol attach | Real Chrome plus real login profile is harder to fingerprint than headless; CDP attach reuses an already-trusted browser instance |
| Async HTTP | httpx, asyncpg | Used in the production version's Postgres pipeline (omitted from demo) |
| Storage (paid version) | PostgreSQL via SQLAlchemy 2 + asyncpg, MongoDB via Motor, Redis | Pluggable; per-customer choice |
| Proxy infra (paid version) | Redis pool, validator loop, sticky-per-profile binding | Avoids the "profile sees IP jumping → flagged" failure mode |
| Process control | psutil | Cross-platform Chrome process detection and health checks |
| Cross-platform launchers | bash + PowerShell + macOS .command | One repo, three OS environments |
| Dependency management | uv | Fast resolution, lockfile-driven reproducibility |

## Versions in this demo

The demo's `pyproject.toml` pins:

- `scrapy >= 2.11`
- `scrapy-playwright >= 0.0.34`
- `playwright >= 1.45`

Production version pins extra:

- `redis >= 5.0` for proxy pool and dedup
- `asyncpg >= 0.29` plus `SQLAlchemy >= 2.0` for the Postgres pipeline
- `motor >= 3.3` for the MongoDB pipeline
- `gspread >= 6.0` for the Google Sheets pipeline
- `psutil >= 5.9` for cross-platform Chrome process control

## Why these choices

- **Scrapy over a hand-rolled aiohttp loop**: Scrapy's middleware chain, retry semantics, and concurrency knobs would have to be re-implemented anyway. The Playwright integration via `scrapy-playwright` is the cleanest path
- **CDP attach over Playwright launch**: a freshly launched Playwright Chromium fails basic bot detection on all three platforms in under a minute. Attaching to a user-launched Chrome reuses real session trust
- **Per-platform profiles over a single shared profile**: keeps each platform's fingerprint stable and prevents cookie cross-contamination
- **uv over pip + venv**: lockfile reproducibility and faster cold starts; matches the rest of the freelance-demos monorepo
