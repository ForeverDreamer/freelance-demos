# mna-extractor

LLM-based extraction pipeline for M&A buyer firms. Reads PE / search-fund / family-office websites and produces a 33-column "Buyer Database" `.xlsx` matching the standard analyst template, with PE-internal numerical fields (EV / EBITDA / AUM / hold period / debt-leverage) explicitly flagged `[REQUIRES EXTERNAL]` for follow-on PitchBook / Grata enrichment.

Subdirectory of [freelance-demos](https://github.com/ForeverDreamer/freelance-demos). Reference implementation for "extract structured data from N firms' websites at LLM scale" briefs.

## Why this is interesting

Most "scrape + LLM extract" prototypes fail two ways at scale: (1) single-page fetch leaves the LLM blind to HQ city, leadership names, and portfolio industries that live on `/about` / `/team` / `/contact` / `/portfolio` sub-pages; (2) the extracted JSON shape rarely matches the analyst's actual Excel template, forcing a second cleanup pass.

This demo solves both:

- **Multi-page fetcher** discovers same-domain anchor links by tier (about / team / contact / portfolio), pulls up to three sub-pages alongside the homepage, strips `<script>` / `<style>` / `<svg>` noise, and concatenates with section markers so the LLM can attribute facts to specific pages.
- **33-column schema** mirrors the analyst Excel template exactly (six section groupings: FIRM IDENTITY / INVESTMENT OVERVIEW / PLATFORM SEARCH CRITERIA / ADD-ON SEARCH CRITERIA / DEAL STRUCTURE / META). PE-internal numerical fields stay at the literal `[REQUIRES EXTERNAL]` marker; the writer highlights those cells yellow in the output `.xlsx` so a reviewer can route them to the data-subscription provider in one pass.
- **Confidence-tagged output** (`High` / `Medium` / `Low`) per row, computed from website-stated coverage of HQ + ≥1 platform industry. Rows with weak signal surface for review rather than passing silently.

On a 10-firm pilot against well-known PE buyers, **7/8 fetched firms reach High confidence**, with HQ filled correctly for 7/8 and platform industries for 7/8. The single Medium row is a known seed-data artifact (a portfolio company misclassified as a buyer) and is correctly flagged. Per-firm cost on DeepSeek V3 is ~$0.003; full 10K-firm projection is ~$28 LLM compute including failure-retry buffer.

## Quick demo

### Prerequisites

- A **DeepSeek API key**: get one at <https://platform.deepseek.com>. This is the only required configuration; other settings have safe defaults.
- **uv** (Python project manager). Install once: <https://docs.astral.sh/uv/getting-started/installation/>. uv handles Python 3.11+ automatically.

### Get the code

**Option A (no git required, recommended for non-developers):**

1. Open <https://github.com/ForeverDreamer/freelance-demos> in your browser
2. Click the green **Code** button → **Download ZIP**
3. Extract the ZIP, then navigate into `freelance-demos-main/mna-extractor-demo/`
4. Right-click inside that folder → **Open in Terminal** (Windows 11 / macOS Finder / most Linux file managers support this natively)

**Option B (developer):**

```bash
git clone https://github.com/ForeverDreamer/freelance-demos
cd freelance-demos/mna-extractor-demo
```

### Run

```bash
# Sync deps (creates .venv, installs from uv.lock)
uv sync

# Configure the API key
cp .env.example .env
# Open .env in any text editor (Notepad / TextEdit / VS Code) and fill DEEPSEEK_API_KEY.
# Other variables (provider, model, timeout, UA, output path) have safe defaults
# documented in .env.example.

# Fetch-only smoke (no LLM, sanity-check the network path)
uv run python -m mna_extractor.cli fetch --input data/sample_input.csv --concurrency 5

# Full pilot (fetch + multi-page + LLM + Excel writer)
uv run python -m mna_extractor.cli pilot \
  --input data/sample_input.csv \
  --output data/pilot_output.csv \
  --concurrency 3
# Generates pilot_output.csv + pilot_output.xlsx (33-col, client format)
```

The seed input `data/sample_input.csv` covers ten widely-known PE firms (KKR, Blackstone, Carlyle, Apollo, TPG, Bain Capital, Vista Equity, Thoma Bravo, Alpine Investors, Marmic Fire) so the run is reproducible without supplying your own buyer list.

## Architecture

```
data/sample_input.csv ──┐
                        │
                        ▼
           ┌──────────────────────────────┐
           │  fetcher.fetch_firm_pages()  │   httpx + selectolax
           │  homepage + ≤3 sub-pages     │   tier discovery
           │  noise stripping             │   regex pre-clean
           └──────────────┬───────────────┘
                          │ concat HTML
                          ▼
           ┌──────────────────────────────┐
           │  llm_extractor.extract()     │   DeepSeek V3
           │  33-col JSON schema          │   OpenAI SDK + JSON mode
           │  temperature=0.0             │   ~50K char input cap
           └──────────────┬───────────────┘
                          │ FirmRecord
                          ▼
           ┌──────────────────────────────┐
           │  flagger.post_process()      │   Confidence rubric
           │  pipeline override           │   source_urls truth
           │  source_urls list            │   from fetcher
           └──────────────┬───────────────┘
                          │
                          ▼
           ┌──────────────────────────────┐
           │  excel_writer.write()        │   openpyxl
           │  6 sections + 33 columns     │   merged section headers
           │  yellow [REQUIRES EXTERNAL]  │   frozen panes
           └──────────────┬───────────────┘
                          │
                          ▼
                   pilot_output.xlsx
```

## What this demo does NOT do

- **PE-internal numerical fields** (EV / EBITDA / revenue ranges, AUM, hold period, min ownership %, debt-leverage, preferred EBITDA margin). These are systematically flagged `[REQUIRES EXTERNAL: PitchBook / Grata / 2-Pager PDF]` because they are rarely on public firm websites. A paid engagement adds the merge-from-PitchBook pass.
- **Cloudflare / WAF bypass** for firms that block `httpx` at the edge (~3-5% of buyers based on the pilot — Carlyle and Vista Equity in the 10-firm seed). The `playwright` optional dependency group is wired up in `pyproject.toml` for a headless-browser fallback, but the actual orchestration is part of paid delivery.
- **10K-scale orchestration** (OpenAI Batch API mode, checkpointed restart, concurrency tuning, monitoring dashboards). The current pilot mode is sync-API single-pass for prompt iteration.
- **Vertical Tag Library mapping** to a custom analyst taxonomy. The pipeline emits free-text industry strings; mapping to a controlled vocabulary is a paid add-on.
- **Auto-merge against PitchBook / Grata exports**. The `firm_name` + `website` keys are stable for downstream join; the join itself is paid.

## Tech stack

- **Python 3.11+** managed by [uv](https://docs.astral.sh/uv/) (no system-Python conflicts; `uv.lock` reproduces exactly).
- **httpx + tenacity** for async fetch with retry on transient network errors.
- **selectolax** for fast HTML parsing (anchor discovery + noise tag removal). 10x faster than BeautifulSoup on the homepages tested.
- **DeepSeek V3** (`deepseek-chat`) via `openai` SDK in OpenAI-compatible mode. ~5x cheaper than `gpt-4o-mini` at equivalent extraction quality on this task. Swap to OpenAI by setting `MNA_LLM_PROVIDER=openai`.
- **Pydantic v2** for schema validation; the same `FirmRecord` model is the single source of truth for both LLM JSON parse and Excel output column ordering.
- **openpyxl** for `.xlsx` writer with merged section headers, conditional cell highlighting, and frozen panes.

## Custom builds

If you have a similar M&A buyer database / industry directory / structured-website-extraction brief and want a tailored 10K-scale run with custom schema, [reach out via Upwork](https://www.upwork.com/freelancers/~0140562708001afd27).

## License

MIT. See [LICENSE](../LICENSE).
