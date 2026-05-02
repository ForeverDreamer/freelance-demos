# Stack

The sketch in this directory uses the simplest combination that
demonstrates "PDF in, JSON out" end-to-end. The paid build expands
across the matrix below.

## Sketch (this directory)

| Component | Choice | Why |
|-----------|--------|-----|
| Document parser | [Docling](https://github.com/DS4SD/docling) (CPU) | One API for PDF / image / DOCX / PPTX. No GPU required. |
| LLM runtime | [Ollama](https://ollama.com) | Local-only, single binary, runs anywhere. Removes "do you have an API key" friction for a 5-minute walkthrough. |
| LLM model | `qwen2.5:7b-instruct-q4_K_M` | 4-bit quantized 7B, ~4.7GB on disk, ~6GB RAM at runtime. Multilingual baseline good enough for English / European Latin scripts. |
| Schema validation | [Pydantic v2](https://docs.pydantic.dev) | De facto standard for typed Python data + JSON schema export. |
| API | [FastAPI](https://fastapi.tiangolo.com) | One-file POST endpoint, OpenAPI docs free. |

## Paid build expansions

### Parser tier

| Need | Choice |
|------|--------|
| 109-language OCR (Latvian / Russian / Arabic / CJK) | PaddleOCR-VL |
| Tables-heavy (financials, tax forms) | MinerU2.5-Pro |
| Handwriting-heavy (insurance, KYC) | Chandra |

### LLM tier

| Need | Choice |
|------|--------|
| Cloud, fast TTM, no GPU | Mistral OCR + Claude Sonnet |
| Selfhost, GDPR / privacy | vLLM serving Qwen2.5-VL-7B-AWQ or Qwen3-VL-8B |
| Cheapest cloud | Mistral OCR Batch + Claude Haiku |

### Extraction tier

| Need | Choice |
|------|--------|
| Validation retry on schema fail | [Instructor](https://github.com/jxnl/instructor) |
| Grammar-constrained decoding (zero malformed JSON) | [Outlines](https://github.com/dottxt-ai/outlines) |
| Field-level confidence from logprobs | vLLM logprobs + custom router |

### Storage + queue tier

| Need | Choice |
|------|--------|
| Persistence | PostgreSQL |
| Vector store for product catalog matching | [pgvector](https://github.com/pgvector/pgvector) + BGE-M3 embeddings |
| Async pipeline | Celery + Redis |
| Workflow orchestration | n8n self-host (HTTP Request node) |

## Verified vs extension

The sketch ships with Docling + Ollama (the `cpu-fallback` profile of
the paid build). The other five preset profiles in [§4 of
architecture.md](./architecture.md#4-adapter-pattern--6-preset-profiles)
are configured (YAML present, protocol contract met) but require model
download / API key setup before they run. None of the paid-build
runtimes are exercised in this sketch.
