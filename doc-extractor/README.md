# doc-extractor

A public architecture sketch of a local-first document AI pipeline:
PDF / image / DOCX → structured JSON, no cloud calls required, with a
schema designed to align to the EU e-invoicing standard (EN 16931 /
Peppol BIS Billing 3.0).

Subdirectory of [freelance-demos](https://github.com/ForeverDreamer/freelance-demos).
Reference architecture for "extract structured data from invoices /
receipts / contracts" briefs on Upwork, especially briefs with EU
multilingual or local-only requirements.

## Why this is interesting

Most freelance invoice-AI briefs ship as a single hardcoded model + a
single fixed schema, which locks the customer into one stack. Three
things production briefs actually need.

- **Local-only path that holds up under GDPR / privacy review**: the
  EU e-invoicing mandate (Latvia 2026 B2G, 2028 B2B) and HIPAA / KYC
  briefs in general both rule out third-party LLM APIs for the data
  plane.
- **Multilingual OCR that includes Latvian, Russian, Arabic, CJK**:
  most OSS document parsers stop at English + a handful of major
  European languages. PaddleOCR-VL covers 109 languages out of the
  box, which is a hard differentiator on Eastern Europe and Middle
  East briefs.
- **Field-level confidence routing**: production extraction is
  auto-pass / human-review / auto-reject per field, not per document.
  Logprob-derived confidence scores let a small reviewer team handle
  thousands of invoices without rubber-stamping the easy cases.

See [`docs/architecture.md`](docs/architecture.md) for the full
four-stage pipeline and [`docs/stack.md`](docs/stack.md) for the
technology-choice matrix.

## What this sketch shows

| Capability | Where |
|---|---|
| Four-stage pipeline (parse → extract → confidence → push) | [`docs/architecture.md`](docs/architecture.md) §1 |
| Adapter pattern + 6 preset profiles | [`docs/architecture.md`](docs/architecture.md) §4 |
| Pydantic invoice schema (6 core fields, EN 16931 subset) | [`src/schema.py`](src/schema.py) |
| Docling-based parser (CPU, multi-format) | [`src/parser.py`](src/parser.py) |
| Ollama-based extractor with Pydantic validation | [`src/extractor.py`](src/extractor.py) |
| Single-endpoint FastAPI surface | [`src/main.py`](src/main.py) |
| EU e-invoicing alignment (Latvia 2026 / 2028 mandate) | [`docs/architecture.md`](docs/architecture.md) §3.4 |

## What this sketch does NOT include

This is a capability sketch, not a deployable system. The stubs under
`src/` are skeletons with `TODO: see private repo` markers, no docker
compose, no sample PDFs in the tree. The paid build adds.

- **Multilingual OCR**: PaddleOCR-VL (109 languages: Latvian / Russian
  / Arabic / CJK), MinerU2.5-Pro (tables-heavy), Chandra (handwriting).
- **Production LLM runtime**: vLLM with logprobs-derived field-level
  confidence scoring, plus Instructor / Outlines for retry + grammar-
  constrained decoding.
- **HITL review queue**: side-by-side image + extracted fields,
  approve / edit workflow, reviewer corrections feed the schema-
  aligned audit log.
- **Full EN 16931 / Peppol BIS Billing 3.0 schema** (100+ fields):
  supplier / buyer party blocks with VAT IDs, VAT lines per rate
  category, payment terms with IBAN / BIC, document references,
  document-level allowances and charges.
- **n8n self-host integration**: Email / IMAP trigger →
  doc_extractor API → Postgres → Telegram / Slack / Teams / Webhook
  notification, all on-prem.
- **Async pipeline + scaling**: Celery + Redis worker pool, separate
  queues for parse / extract / push, Prometheus + Grafana
  observability.
- **Six preset profiles**: `english-throughput-hybrid` (default,
  cloud-API, 1-2 day TTM), `multilingual-strict-selfhost`,
  `handwriting-heavy`, `tables-heavy`, `privacy-first`,
  `low-budget-cloud-api`. One env var swaps the entire stack.
- **Curated golden test set**: 6 EU languages × 3 quality tiers × 4
  doctypes, hand-checked expected JSON for regression.
- **Peppol Access Point integration**: routed through a compliance
  vendor (the schema is wire-compatible).

If any of those matter for your project, that is the paid work.

## Stack

Sketch: Python 3.11+, FastAPI, Docling (CPU), Ollama (local LLM
runtime), Pydantic v2.

Paid build adds: PaddleOCR-VL, vLLM, Instructor / Outlines, PostgreSQL
+ pgvector, BGE-M3 embeddings, Celery + Redis, n8n self-host. See
[`docs/stack.md`](docs/stack.md) for the full matrix.

## Tested baseline (when you wire it up)

The sketch is designed to run as Docling + Ollama on CPU. Tested
locally with `qwen2.5:7b-instruct-q4_K_M` (~4.7GB on disk, ~6GB RAM at
runtime). To exercise it you would:

1. Install Ollama from <https://ollama.com>.
2. `ollama pull qwen2.5:7b-instruct-q4_K_M`.
3. Add a `pyproject.toml` and `uv sync` (the sketch omits both; see
   the paid build for the runnable layout).
4. Run `uvicorn src.main:app --port 8100`.
5. POST a PDF to `http://localhost:8100/ingest` and parse the JSON.

Sample PDFs are not bundled. See
[`data/samples/README.md`](data/samples/README.md) for public dataset
sources (DocILE, CORD) and license notes.

## License

MIT. Fork, read, learn freely.

## Custom builds

For your specific document types, multilingual coverage (Latvian /
Russian / Arabic / CJK), local-only deployment, EN 16931 / Peppol
schema alignment, n8n integration, or production HITL queue, reach out
on Upwork: <https://www.upwork.com/freelancers/~0140562708001afd27>
