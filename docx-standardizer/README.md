# docx-standardizer

Pipeline that takes inconsistent .docx files, normalizes the structure
via a pluggable LLM, and rebuilds clean .docx files from a master Word
template.

Subdirectory of [freelance-demos](https://github.com/ForeverDreamer/freelance-demos).
Reference implementation for management-system document standardization
briefs on Upwork.

## Why this is interesting

The LLM handles the part it is good at (extracting structure from messy
prose). python-docx handles the part Python should own (applying styles
deterministically from a master template). The boundary stays clean:
the model never touches Word formatting, and the rebuild step never
guesses at section names.

The schema is enforced per provider. OpenAI uses strict json_schema (the
API literally cannot return a non-conforming JSON). Claude uses tool_use
with input_schema for the same effect. DeepSeek, Kimi, MiniMax, and
Gemini use JSON mode with the schema embedded in the system prompt and
Pydantic validation as the gate. Either way the rebuild step receives a
validated `StandardizedDocument`.

## Providers

Pick one with `LLM_PROVIDER` in `.env` (default in `.env.example` is
`deepseek`). Six are wired up out of the box:

| Provider | `LLM_PROVIDER` | Default model | Mode | API key env |
| --- | --- | --- | --- | --- |
| DeepSeek | `deepseek` | `deepseek-chat` | JSON mode + Pydantic | `DEEPSEEK_API_KEY` |
| Kimi (Moonshot) | `kimi` | `moonshot-v1-32k` | JSON mode + Pydantic | `MOONSHOT_API_KEY` |
| MiniMax | `minimax` | `abab6.5s-chat` | JSON mode + Pydantic | `MINIMAX_API_KEY` |
| Gemini | `gemini` | `gemini-2.0-flash` | JSON mode + Pydantic | `GEMINI_API_KEY` |
| OpenAI | `openai` | `gpt-4o-2024-08-06` | strict json_schema | `OPENAI_API_KEY` |
| Claude | `claude` | `claude-sonnet-4-5` | tool_use input_schema | `ANTHROPIC_API_KEY` |

Override the default model per provider with `<PROVIDER>_MODEL=...` (for
example `DEEPSEEK_MODEL=deepseek-reasoner`) or apply one model to
whichever provider you pick with `LLM_MODEL=...`.

To plug in a seventh provider, add a `ProviderConfig` to
[`providers.py`](providers.py) and pick one of the three modes
(`OPENAI_STRICT`, `JSON_OBJECT`, `ANTHROPIC_TOOL`). No code changes in
`normalize.py` are required.

## Quick start

```bash
cd docx-standardizer
uv sync
cp .env.example .env  # then edit: pick LLM_PROVIDER and fill its API key

# one-time bootstrap: generate the 3 sample inputs and master.docx
uv run python scripts/generate_samples.py

# run the pipeline
uv run python standardize.py \
    --input ./input \
    --output ./output \
    --master ./master.docx \
    --log ./logs/standardize.log
```

Three sample files in `input/` get rewritten into `output/` with
consistent Title / Heading 1 / Heading 2 / Normal / Table Grid styles
copied from `master.docx`.

To preview `.docx` files in VS Code (and to verify input vs output
structurally), see [docs/preview-tools.md](docs/preview-tools.md).

## What this demo shows

| Capability | Where | Proof |
|---|---|---|
| .docx extraction | `extract.py` | `tests/test_extract.py` |
| Pydantic schema for canonical doc shape | `schema.py` | type-checked at import |
| Six-provider LLM dispatch | `providers.py`, `normalize.py` | `tests/test_normalize.py` (mocked, all 3 modes covered) |
| Strict structured output (OpenAI / Claude) | `normalize.py` | json_schema strict / tool_use input_schema |
| JSON mode + Pydantic gate (DeepSeek / Kimi / MiniMax / Gemini) | `normalize.py` | schema injected in system prompt, validated post-call |
| Master template style copy | `rebuild.py::copy_styles` | `tests/test_rebuild.py` |
| Style-aware rebuild (Title / H1 / H2 / Normal / Table Grid) | `rebuild.py` | open `output/*.docx` in Word |
| Per-file logging (success / partial / failed) | `standardize.py` | `logs/standardize.log` after a run |
| Retry on API or schema-validation failure | `normalize.py::call_with_retry` | covered in `tests/test_normalize.py` |
| Full pipeline run | `standardize.py` orchestrator | `tests/test_pipeline.py` (mocked) |

## What this demo does NOT do

This is a capability demo, not a production deployment. A full paid
delivery adds:

- **Full batch processing** at production scale (this demo runs 3 files;
  the typical brief is 100-500 files with progress checkpointing,
  resumable runs, and parallel workers)
- **Custom schemas per document type** (this demo uses one generic
  schema; SOPs vs Forms vs Manuals usually each get their own)
- **Multi-master template selection** routed by document type
- **Image, equation, footnote, OLE object preservation** (this demo
  drops embedded objects)
- **Track changes, comments, revision marks** (this demo drops them)
- **FastAPI service wrapper** for HTTP-driven runs
- **n8n workflow integration** for ingestion / queueing / notifications
- **Dry-run, diff preview, rollback** before destructive overwrites
- **Production logging** with rotation, structured JSON, and external
  sinks (CloudWatch, Datadog, ELK)
- **Test coverage against your specific document corpus** and edge cases
- **Deployment**: Docker image, scheduled runs, IAM / KMS for API keys,
  monitoring and alerting

If any of these matter for your project, that is the paid work.

## How structured output is enforced

Schema-first. [`schema.py`](schema.py) defines a Pydantic v2 model
(`StandardizedDocument`) covering ten canonical sections. Its
`model_json_schema()` is fed to the LLM in one of three ways depending
on the provider:

**OpenAI strict json_schema** — token-level constraint. The API cannot
emit a non-conforming JSON.

```python
client.chat.completions.create(
    model=model,
    messages=[...],
    response_format={
        "type": "json_schema",
        "json_schema": {
            "name": "StandardizedDocument",
            "schema": StandardizedDocument.model_json_schema(),
            "strict": True,
        },
    },
)
```

**JSON mode + schema in prompt** — DeepSeek, Kimi, MiniMax, Gemini.
`response_format={"type": "json_object"}` keeps the response
syntactically JSON, the schema lives in the system message as a
contract, and `StandardizedDocument.model_validate` is the gate. On
failure the call is retried once (see `call_with_retry`).

**Claude tool_use** — equivalent strictness via `input_schema`:

```python
client.messages.create(
    model=model,
    tools=[{
        "name": "emit_standardized_document",
        "input_schema": StandardizedDocument.model_json_schema(),
    }],
    tool_choice={"type": "tool", "name": "emit_standardized_document"},
    messages=[...],
)
```

Pydantic `model_validate` runs on the parsed payload regardless of mode,
so `rebuild.py` always receives a validated object.

## How the master-template part works

Word's paragraph styles (Title, Heading 1, Heading 2, Normal,
Table Grid) live in the document's `styles.xml`. We open `master.docx`,
copy the relevant `<w:style>` elements onto a fresh document's styles
collection, then write paragraphs and tables with the matching style
names. python-docx's `paragraph.style = "Heading 1"` does the rest.

See `rebuild.py::copy_styles` for the implementation, based on the
StackOverflow pattern by python-docx maintainer
[@scanny](https://stackoverflow.com/questions/49512204).

## Running tests

```bash
uv run pytest tests/ -v
```

Tests mock all three provider modes, so no API key is required to run
them.

## License

MIT. Fork, read, learn freely.

## Custom builds

For your specific master template, custom schema per document type,
200+ document batch, production deployment, or ongoing maintenance,
reach out on Upwork: <YOUR_UPWORK_PROFILE_URL>.
