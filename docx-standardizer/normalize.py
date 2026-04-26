"""Send extracted document content to OpenAI with strict structured outputs against the StandardizedDocument schema. Includes 1 retry on timeout or schema-validation failure."""

import json
import os
import time
from typing import Any, Callable, Dict, TypeVar

from openai import APITimeoutError, OpenAI
from pydantic import ValidationError

from schema import StandardizedDocument

T = TypeVar("T")


SYSTEM_PROMPT = (
    "You are a document structure normalizer. You receive raw extracted "
    "content from a Microsoft Word .docx file (paragraphs with style "
    "names, bold flags, max font size in points, tables, and metadata) "
    "and you output a JSON object that strictly conforms to the supplied "
    "schema. Authors often skip Heading styles and instead mark sections "
    "with bold or larger fonts on Normal-styled paragraphs; treat such "
    "paragraphs as likely section headings. Preserve the source content. "
    "Do not invent. If a section is missing in the source, fill with an "
    "empty string or empty list as the schema allows."
)


class NormalizationFailed(Exception):
    pass


def call_with_retry(
    fn: Callable[[], T],
    retries: int = 1,
    backoff: tuple[float, ...] = (1.0, 3.0),
) -> T:
    last_exc: Exception | None = None
    for attempt in range(retries + 1):
        try:
            return fn()
        except (APITimeoutError, ValidationError, json.JSONDecodeError) as e:
            last_exc = e
            if attempt < retries:
                time.sleep(backoff[min(attempt, len(backoff) - 1)])
            continue
    raise NormalizationFailed(
        f"Failed after {retries + 1} attempts: {last_exc}"
    ) from last_exc


def normalize(
    extracted: Dict[str, Any],
    client: OpenAI | None = None,
) -> StandardizedDocument:
    client = client or OpenAI()
    model = os.environ.get("OPENAI_MODEL", "gpt-4o-2024-08-06")

    def _call() -> StandardizedDocument:
        response = client.chat.completions.create(
            model=model,
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
        content = response.choices[0].message.content or ""
        data = json.loads(content)
        return StandardizedDocument.model_validate(data)

    return call_with_retry(_call, retries=1)
