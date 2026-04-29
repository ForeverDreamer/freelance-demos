# Stack

## Runtime

- **Python 3.11+** — required for native `asyncio` task groups and the
  generic `dict[K, V]` syntax used across the codebase.
- **uv** — dependency manager (does not require a separate Python install).

## Direct runtime dependencies

| Package | Why |
| ---- | ---- |
| [`playwright`](https://playwright.dev/python/) | Browser automation via CDP attach. We use `connect_over_cdp` (not `chromium.launch`) so the crawler attaches to a user-launched Chrome instance and inherits its session. |
| [`python-dotenv`](https://pypi.org/project/python-dotenv/) | `.env` file loader for CDP port overrides and data-dir settings. |
| [`click`](https://click.palletsprojects.com/) | CLI framework (`python -m social_crawler.main <subcommand>`). One subcommand per spider. |

The demo deliberately ships **without**:

- Redis (paid version: dedup with TTL)
- MongoDB driver (paid version: warehouse upsert)
- aiohttp / httpx (everything goes through Playwright; no parallel HTTP
  fetch in the demo)
- Loguru / structlog (paid version: structured JSON log lines)

## Why these picks

### Playwright over Selenium

- Native async API → no thread bridge, no GIL contention with Python's event
  loop.
- First-class `connect_over_cdp` for attach-mode (Selenium does have CDP
  support but the abstraction is leakier).
- `page.locator(...)` auto-retries on stale handles, which matters for SPA
  apps that re-mount React subtrees during typing.
- Cross-browser support out of the box (we only use Chromium here, but the
  abstraction makes Firefox/WebKit a small change).

### asyncio over Twisted (Scrapy)

The first iteration was Scrapy + scrapy-playwright. Twisted's reactor runs
its cross-thread emit path on a 5-second tick. Single-step optimizations
inside an `await` chain were absorbed by the reactor tick boundary — the
crawler's wall-clock time was unmoved by 5–10 s of accumulated savings. See
[architecture.md](architecture.md) for the full story.

### click over argparse

argparse can do this too, but click's group-and-subcommand pattern is
clearer for a crawler with one entrypoint per platform.

### `uv` over `pip` + `venv`

- `uv sync` is reproducible (locks in `uv.lock`).
- `uv run` activates the venv on the fly without `source .venv/bin/activate`
  ceremony.
- Parses `pyproject.toml` directly (PEP 621) — no separate `setup.py`.

## Browser

- **Chrome / Chromium** (any recent version). Chrome 136+ silently ignores
  `--remote-debugging-port` if `--user-data-dir` is the OS default; the
  launcher script defaults to `~/.chrome-profiles/<platform>/` which avoids
  this.
- The user logs in manually once per platform; session persists in the
  per-platform user-data-dir. The crawler never sees credentials.

## Tested on

- WSL2 Ubuntu (primary dev environment) with Windows-side Chrome
- macOS (Sonoma) with Homebrew-installed Chrome
- Native Linux (Ubuntu 22.04) with `apt`-installed Chromium

Windows-native Python should work but is not the primary test target. The
WSL2 path (Linux Python attaching to Windows Chrome over `localhost`) is
the maintained one.
