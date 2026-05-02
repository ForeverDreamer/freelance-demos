"""Ollama-based LLM extractor (CPU / small model).

Sends parsed text to a local Ollama model and asks it to return strict
JSON matching the Invoice schema. The sketch uses raw `format=json` mode
+ json.loads + Pydantic validation.

The paid build replaces this with one of:

- `instructor` + `pydantic` for retry on validation failure
- `outlines` for grammar-constrained decoding (no malformed JSON ever)
- vLLM logprobs for field-level confidence scoring + HITL routing

TODO: see private repo for confidence-routed extraction with EN 16931
schema (100+ fields) and Peppol BIS Billing 3.0 compliance.
"""
from __future__ import annotations

import json
import os

import ollama
from pydantic import ValidationError

from .schema import Invoice

DEFAULT_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b-instruct-q4_K_M")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")

_PROMPT_TEMPLATE = """You are an invoice data extraction assistant.

Extract the fields below from the invoice text. Return ONLY a single
valid JSON object, no markdown, no commentary.

Required keys: vendor, invoice_number, issue_date, currency, total,
line_items (array of {{description, quantity, unit_price, line_total}}).

Use null for missing optional numbers and an empty string for missing
text fields. Do not fabricate values.

INVOICE TEXT:
---
{text}
---

JSON:
"""


def extract(text: str, model: str = DEFAULT_MODEL) -> Invoice:
    """Call Ollama and return a validated Invoice."""
    client = ollama.Client(host=OLLAMA_URL)
    response = client.generate(
        model=model,
        prompt=_PROMPT_TEMPLATE.format(text=text),
        format="json",
        options={"temperature": 0.0},
    )
    raw = response["response"]

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Model returned non-JSON: {raw[:500]}") from exc

    try:
        return Invoice.model_validate(payload)
    except ValidationError as exc:
        raise ValueError(f"Model JSON failed schema: {exc}\nRaw: {raw[:500]}") from exc
