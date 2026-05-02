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
| [docx-standardizer](docx-standardizer/) | Inconsistent .docx batch normalized via OpenAI strict structured outputs and rebuilt from a master Word template | Python, python-docx, OpenAI structured outputs, Pydantic | 🟡 code ready |
| [minimal-rag-chat](minimal-rag-chat/) | End-to-end RAG CLI with hybrid BM25 + vector retrieval | Python, OpenAI / Anthropic, rank-bm25 | 🟡 code ready |
| [social-crawler](social-crawler/) | 6 spiders × 4 platforms (Facebook / Twitter (X) / Instagram / TikTok) using pure asyncio + Playwright with CDP attach and click-flow navigation; 0.9–5 s per spider on real logged-in profiles | Python, asyncio, Playwright, click | 🟡 code ready |
| [mna-extractor-demo](mna-extractor-demo/) | LLM extraction across PE / search-fund / family-office websites; multi-page fetch + 33-column Buyer Database `.xlsx` with `[REQUIRES EXTERNAL]` flagging for PitchBook-grade fields | Python, httpx, selectolax, DeepSeek V3, Pydantic, openpyxl | 🟡 code ready |
| [doc-extractor-preview](doc-extractor-preview/) | Local-only document AI sketch: PDF / image / DOCX → JSON aligned to EN 16931, designed for EU multilingual + GDPR / Latvia 2026-2028 e-invoicing mandate briefs; sketch-form (architecture docs + stub code) | Python, FastAPI, Docling, Ollama, Pydantic | 🟡 sketch |
| [sapphire-studios-promo](sapphire-studios-promo/) | 20s 9:16 brand promo rendered via Claude Code + Hyperframes — HTML/GSAP to deterministic MP4, procedural audio | Hyperframes, GSAP, FFmpeg | 🟢 full deliverable |
| [video-creation-pipeline](video-creation-pipeline/) | Agentic code-to-video pipeline. Claude Code drives Blender (3D procedural) and Adobe CEP (2D programmatic) as long-lived TCP services. Heavier-stack counterpart to sapphire-studios-promo | Blender Python API, Adobe CEP + ExtendScript, FFmpeg, MCP | 🟡 architecture + demo |

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
or ongoing maintenance, reach out on Upwork: <https://www.upwork.com/freelancers/~0140562708001afd27>

## License

MIT on every subfolder unless otherwise noted. See `LICENSE` at repo
root for the default terms.
