# minimal-rag-chat

End-to-end Retrieval-Augmented Generation CLI. Ingests Markdown / text /
PDF documents, indexes them with hybrid BM25 + vector retrieval, and
answers natural-language questions via OpenAI or Anthropic.

Subdirectory of [freelance-demos](https://github.com/ForeverDreamer/freelance-demos).
Reference implementation for "chat over my docs" briefs on Upwork.

## Why this is interesting

Most "ChatGPT over your docs" scripts use pure vector similarity and
quietly fail on exact-match queries (product codes, SKU numbers, error
codes, person names). This demo fuses two rankers at query time:

- **BM25** on tokenized chunk text, strong at rare-keyword matches
- **Cosine similarity** over OpenAI embeddings, strong at paraphrase and
  intent matches

The two rank lists are combined via **Reciprocal Rank Fusion**
(`score = Σ 1 / (k + rank_i)`, k=60) which needs no score normalization
and is the fusion method used in systems like Elastic and Vespa.

See `retrieve.py:Store.search` for the ~15 lines that do the work.

## Quick start

This project uses [uv](https://docs.astral.sh/uv/) for dependency management.

```bash
uv sync
cp rag.example.yaml rag.yaml
export OPENAI_API_KEY=sk-...      # or ANTHROPIC_API_KEY for the Claude path

# Index the synthetic sample docs (or point at your own folder)
uv run python ragchat.py ingest ./sample_data

# Ask a question
uv run python ragchat.py ask "What does the Team plan cost?"

# Inspect retrieval without calling the LLM
uv run python ragchat.py ask "What does the Team plan cost?" --retrieve-only
```

### No API key? Run the whole pipeline offline

Set `provider: fake` for both `embeddings` and `llm` in `rag.yaml`.
The fake embedder is deterministic (hash-based, non-semantic) and the
fake LLM echoes prompt metadata. Useful for evaluating chunking and
retrieval plumbing without spending on API calls.

## What this demo shows

| Capability | Where | Proof |
|---|---|---|
| Markdown / TXT / PDF loading | `loaders.py` | `tests/test_loaders.py` |
| Paragraph-aware chunker with overlap | `ingest.py:split_text` | `tests/test_ingest.py` |
| JSONL-backed vector store | `ingest.py` + `retrieve.py:Store` | `tests/test_ingest.py::test_ingest_writes_jsonl` |
| Hybrid BM25 + vector retrieval via RRF | `retrieve.py:Store.search` | `tests/test_retrieve.py` |
| Pluggable providers (OpenAI / Anthropic / fake) | `providers.py` | `tests/test_integration.py` |
| Runnable offline (fake provider path) | `providers.py:FakeEmbedder`, `FakeChat` | whole test suite runs with no network |
| Source-cited answers | `ragchat.py:SYSTEM_PROMPT` + `build_user_prompt` | `tests/test_integration.py::test_build_user_prompt_formats_citations` |

## What this demo does NOT do

This is a capability demo, not a production deployment. A full paid
delivery adds:

- **Incremental ingest**: only re-embed changed files (this demo
  rewrites the whole store every run)
- **Re-ranker stage**: cross-encoder or `cohere.rerank` on top-k from
  retrieval to boost precision on ambiguous queries
- **Query rewriting and decomposition**: multi-hop questions, HyDE,
  step-back prompting
- **Streaming token output** to the terminal or a web UI
- **Production vector store**: pgvector, Qdrant, or Pinecone with
  metadata filters, per-tenant namespaces, and connection pooling
  (this demo uses a flat JSONL file, fine for up to ~10k chunks)
- **Evaluation harness**: labeled Q/A sets, groundedness scoring,
  retrieval hit-rate and MRR tracking across versions
- **Document-format coverage beyond MD / TXT / PDF**: DOCX, HTML,
  XLSX, CSV, Confluence, Notion, Google Drive connectors
- **Auth and multi-tenant isolation**, API rate limits, token usage
  accounting, and request-level audit logs
- **Chunking strategies beyond paragraph+char**: semantic chunking,
  layout-aware splitting, table extraction, image OCR
- **Observability**: retrieval traces, LLM cost dashboards, drift
  detection on embeddings

If any of these matter for your project, that is the paid work.

## Running the tests

```bash
uv sync
uv run pytest tests/
```

Expected: 21 tests pass in under a second. The suite uses only the
`fake` provider so **no API key or network is required**.

## Design notes

- `vector_store.jsonl` is a single-file, newline-delimited JSON store.
  Fine up to ~10k chunks on a single machine. For larger corpora swap
  `retrieve.py:Store` for pgvector or Qdrant, keeping the same
  `search` signature.
- Chunking is paragraph-first, then hard-split if a single paragraph
  exceeds `chunk_size`. Overlap is appended as a tail-prefix on every
  non-first chunk to preserve boundary context.
- `text-embedding-3-small` is the default because it is cheap (1536-d,
  USD 0.02 per 1M tokens as of 2026-04) and strong enough for
  docs-scale corpora. Swap via config for `text-embedding-3-large` if
  retrieval quality matters more than cost.

## License

MIT. Fork, read, learn freely.

## Custom builds

For your specific corpus, retrieval quality targets, production
deployment, or ongoing maintenance, reach out on Upwork: <https://www.upwork.com/freelancers/~0140562708001afd27>
