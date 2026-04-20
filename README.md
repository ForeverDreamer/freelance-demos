# freelance-demos

Public monorepo of capability demos backing my Upwork profile.

Each subdirectory is a self-contained demo with its own README, tests,
and MIT license. Demos are written to showcase the core technique for
a common automation brief at 60-70% scope, not as production
deployments.

## Demos

| Demo | One-line | Stack | Status |
|---|---|---|:---:|
| [file-organizer](file-organizer/) | Folder watcher with sub-2s detection and YAML rules | Python, watchdog | 🟡 code ready |
| [minimal-rag-chat](minimal-rag-chat/) | End-to-end RAG CLI with hybrid BM25 + vector retrieval | Python, OpenAI / Anthropic, rank-bm25 | 🟡 code ready |
| [social_crawler_demo](social_crawler_demo/) | Scrapy + Playwright CDP attach across Facebook / Twitter / Instagram public profiles | Python, Scrapy, scrapy-playwright | 🟡 code ready |

## About these demos

These are capability demos at 60-70% scope, not production deployments.
Each one shows the core technique for a common automation brief. Full
production delivery (complete action sets, platform-specific install,
monitoring, edge-case testing against your environment) is scoped
separately in paid engagement.

Each demo's README has a "What this demo does NOT do" section that
makes the gap between demo and paid delivery explicit.

## How to use

Each subfolder is self-contained. For example:

```bash
cd file-organizer
uv sync
uv run python organizer.py --config rules.example.yaml --watch ./sample_data
```

Follow the subfolder README for setup specifics. Python demos in this
repo use [uv](https://docs.astral.sh/uv/) for dependency management.

## Repo conventions

- Each demo subfolder has its own `README.md`, dependency manifest
  (`pyproject.toml` for Python demos), `tests/`, and a runnable entry point.
  Top-level `LICENSE` (MIT) applies unless a subfolder overrides it
- Demos are independent: no cross-subfolder imports. Shared utilities
  do not belong here (they live in my private component library)
- Sample data under `sample_data/` is synthetic only. No real client
  data ever lands in this monorepo
- Every demo publishes only 60-70% of the full scope it would cover in
  a paid engagement. The gap is listed in the subfolder README

## Custom builds

For your specific project, folder map, rule set, production deployment,
or ongoing maintenance, reach out on Upwork: `<YOUR_UPWORK_PROFILE_URL>`

## License

MIT on every subfolder unless otherwise noted. See `LICENSE` at repo
root for the default terms.
