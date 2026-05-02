# Architecture

Reference architecture for the local-only document AI pipeline. This
sketch documents the four stages and the differentiators that live in
the paid build.

## 1. Pipeline overview

```text
┌────────────┐    ┌────────────┐    ┌─────────────┐    ┌──────────────┐
│  Parser    │───▶│ Extractor  │───▶│ Confidence  │───▶│  Pusher      │
│ (PDF→text) │    │ (LLM→JSON) │    │  + HITL     │    │ (ERP / n8n / │
│            │    │            │    │             │    │  Peppol AP)  │
└────────────┘    └────────────┘    └─────────────┘    └──────────────┘
       ▲                  ▲                  ▲                 ▲
       │                  │                  │                 │
   Docling /         Ollama / vLLM /     vLLM logprobs    n8n / Webhook
   PaddleOCR-VL /    Instructor /         field-level     CSV dump /
   MinerU /          Outlines             confidence      Peppol push
   Chandra
```

Stage protocols live behind plain Python `Protocol` classes so the
implementation behind each box can swap independently. The sketch ships
**Parser** and **Extractor** stages only; **Confidence + HITL** and
**Pusher** are paid-build content.

## 2. What the sketch covers

| Stage | Sketch implementation | File |
|-------|----------------------|------|
| Parser | Docling default pipeline (CPU) | [`src/parser.py`](../src/parser.py) |
| Extractor | Ollama `format=json` + Pydantic validation | [`src/extractor.py`](../src/extractor.py) |
| Schema | 6 fields (vendor / invoice_number / issue_date / currency / total / line_items) | [`src/schema.py`](../src/schema.py) |
| API | FastAPI POST /ingest, sync only | [`src/main.py`](../src/main.py) |

## 3. What the paid build adds

### 3.1 Parsers

- **PaddleOCR-VL** for 109-language OCR including Latvian, Russian,
  Arabic, CJK. Required for EU invoice multilingual coverage.
- **MinerU2.5-Pro** for tables-heavy documents (financial statements,
  tax forms, academic papers).
- **Chandra** for handwriting-heavy briefs (insurance claims, KYC
  forms, medical intake).

Each parser is configured via a profile YAML and routed through the
same `Parser` protocol. One `PROFILE=...` env var swaps the entire
parser at boot.

### 3.2 Extractors

- **Instructor + Pydantic**: validation-failure retry loop, automatic
  reprompt with the validation error context.
- **Outlines**: grammar-constrained decoding so the model literally
  cannot emit malformed JSON.
- **vLLM logprobs**: token-level probability per emitted field, used as
  the basis for the confidence score described in §3.3.

### 3.3 Confidence routing + HITL

Every extracted field carries its own confidence score derived from
vLLM logprobs (not estimated, measured). Three routes:

| Score range | Routing |
|-------------|---------|
| `score >= auto_pass` (default 0.95) | Direct push to downstream |
| `auto_pass > score >= review_queue` (default 0.80) | Human review queue with original image side by side |
| `score < auto_reject` (default 0.40) | Auto-reject, parser quality flagged |

Thresholds are config values, not hardcoded. Reviewer corrections feed
the schema-aligned audit log.

### 3.4 Schema

Sketch carries 6 fields. The paid build aligns to **EN 16931** (EU
e-invoicing standard) and **Peppol BIS Billing 3.0** with the full 100+
field coverage including:

- Supplier / buyer party blocks (name, VAT ID, address, country code)
- VAT lines with rate / category / exemption reason
- Payment terms and bank details (IBAN / BIC / SEPA mandate)
- Invoice references (purchase order, contract, project)
- Document-level allowances and charges

The schema you ingest today is the schema you submit to Latvia's SRS
(2026 mandate, B2G) or the Peppol Access Point (2028 B2B mandate).

### 3.5 Pusher

- **n8n integration** via HTTP Request node (Email / IMAP trigger →
  doc_extractor API → Postgres → Telegram / Slack / Teams /
  Webhook).
- **CSV dump** for spreadsheet-driven reviewers.
- **Peppol AP push** routed through a compliance vendor (out of scope
  for the extractor itself, but the schema is wire-compatible).

## 4. Adapter pattern + 6 preset profiles

The paid build ships 8 protocols (parser, runtime, extractor, embedder,
vectorstore, confidence, matcher, pusher) with 15-20 implementations
across them. Six preset profiles bundle these into named configurations:

| Profile | OCR | LLM | GPU | TTM |
|---------|-----|-----|-----|-----|
| `english-throughput-hybrid` (default) | Mistral OCR API | Claude Sonnet | none | 1-2 days |
| `multilingual-strict-selfhost` | PaddleOCR-VL | Qwen3-VL-8B | 24GB | 1 week |
| `handwriting-heavy` | Chandra | Claude Sonnet | 16GB | 3-5 days |
| `tables-heavy` | MinerU2.5-Pro | Claude Sonnet | 8GB | 3-5 days |
| `privacy-first` | PaddleOCR-VL self-host | Qwen2.5-VL-7B-AWQ | 16GB | 1 week |
| `low-budget-cloud-api` | Mistral OCR Batch | Claude Haiku | none | 1 week |

Switching between them is one env var. The sketch in this directory
runs an even simpler `cpu-fallback`-style profile: Docling parser +
Ollama small model + flat schema, which is the minimum needed to show
"PDF in, JSON out" works end-to-end before committing to a paid build.

## 5. Why this architecture

The motivation thread is in the [portfolio video](#) (link from the
[root README](../README.md)). Short version: most freelance invoice-AI
briefs ship as a single hardcoded model + schema and lock the customer
into one stack. The adapter + profile design lets the same codebase
serve a US SMB on hybrid cloud (1-2 day TTM) and an EU regulated
customer on selfhost (multilingual + GDPR + Peppol) without rewrites.
