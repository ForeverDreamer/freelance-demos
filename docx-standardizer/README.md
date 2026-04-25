# docx-standardizer

Pipeline that takes inconsistent .docx files, normalizes the structure
via OpenAI structured outputs, and rebuilds clean .docx files from a
master Word template.

Subdirectory of [freelance-demos](https://github.com/ForeverDreamer/freelance-demos).
Reference implementation for management-system document standardization
briefs on Upwork.

## Why this is interesting

OpenAI handles the part it is good at (extracting structure from messy
prose). python-docx handles the part Python should own (applying styles
deterministically from a master template). The boundary stays clean:
the model never touches Word formatting, and the rebuild step never
guesses at section names.

The schema is enforced at the token-generation level using
`response_format={"type": "json_schema", "strict": true}`. The API
literally cannot return a non-conforming JSON, so the rebuild step
has guaranteed inputs.

## Quick start

```bash
cd docx-standardizer
uv sync
cp .env.example .env  # then edit and add your OPENAI_API_KEY

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

## What this demo shows

| Capability | Where | Proof |
|---|---|---|
| .docx extraction | `extract.py` | `tests/test_extract.py` |
| Pydantic schema for canonical doc shape | `schema.py` | type-checked at import |
| OpenAI strict structured outputs | `normalize.py` | `tests/test_normalize.py` (mocked) |
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

## How the OpenAI part works

Schema-first. `schema.py` defines a Pydantic v2 model
(`StandardizedDocument`) covering ten canonical sections. Its
`model_json_schema()` is passed to the API via:

```python
response = client.chat.completions.create(
    model="gpt-4o-2024-08-06",
    messages=[
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": json.dumps(extracted)},
    ],
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

Strict mode constrains decoding at the token level, so the result is
guaranteed valid against the schema before the rebuild step ever sees
it. We still validate by running `StandardizedDocument.model_validate`
on the parsed JSON for an extra layer.

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

Expect `7 passed`. Tests mock the OpenAI client so no API key is
required to run them.

## License

MIT. Fork, read, learn freely.

## Custom builds

For your specific master template, custom schema per document type,
200+ document batch, production deployment, or ongoing maintenance,
reach out on Upwork: <YOUR_UPWORK_PROFILE_URL>.
