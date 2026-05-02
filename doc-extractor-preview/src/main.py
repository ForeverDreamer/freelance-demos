"""FastAPI entry point (port 8100).

Single endpoint: POST /ingest accepts a PDF / image / DOCX upload, calls
the parser + extractor, and returns a validated Invoice JSON.

TODO: see private repo for full impl (auth, rate limit, async worker
queue, multi-doctype routing, observability hooks).
"""
from __future__ import annotations

from fastapi import FastAPI, File, HTTPException, UploadFile

from .extractor import extract  # TODO: see private repo for retry + Outlines fallback
from .parser import parse_to_text
from .schema import Invoice

app = FastAPI(title="doc-extractor-preview", version="0.1.0-sketch")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/ingest", response_model=Invoice)
async def ingest(file: UploadFile = File(...)) -> Invoice:
    """Parse a document and extract invoice fields.

    Sketch behavior: synchronous parse + LLM call. Production runs the
    parse stage in a Celery worker pool, the LLM stage on a separate
    queue with logprobs-based confidence routing, and pushes
    low-confidence records to a HITL review queue. See
    `docs/architecture.md` §3 for the full pipeline.

    TODO: see private repo for async pipeline + confidence routing.
    """
    if not file.filename:
        raise HTTPException(400, "filename missing")

    contents = await file.read()
    tmp_path = f"/tmp/{file.filename}"
    with open(tmp_path, "wb") as fh:
        fh.write(contents)

    try:
        text = parse_to_text(tmp_path)
        return extract(text)
    except Exception as exc:
        raise HTTPException(500, f"extraction failed: {exc}") from exc
