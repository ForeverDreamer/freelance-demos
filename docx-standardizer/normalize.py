"""Normalize extracted .docx content into a StandardizedDocument via one of six
LLM providers. Structured output is enforced per-provider: OpenAI uses strict
json_schema, OpenAI-compatible Chinese providers (DeepSeek / Kimi / MiniMax) and
Gemini's OpenAI-compatible endpoint use JSON mode with the schema injected into
the system prompt, and Claude uses tool_use with input_schema. All paths are
validated by Pydantic and retried once on timeout / parse / validation error."""

import json
import os
import time
from typing import Any, Callable, Dict, TypeVar

from openai import APITimeoutError, OpenAI
from pydantic import ValidationError

from providers import PROVIDERS, ProviderConfig, StructuredOutputMode, resolve
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


def _resolve_provider() -> ProviderConfig:
    return resolve(os.environ.get("LLM_PROVIDER", "openai"))


def _resolve_model(cfg: ProviderConfig) -> str:
    per_provider = os.environ.get(f"{cfg.name.upper()}_MODEL")
    return per_provider or os.environ.get("LLM_MODEL") or cfg.default_model


def _build_openai_client(cfg: ProviderConfig) -> OpenAI:
    kwargs: Dict[str, Any] = {}
    if cfg.base_url:
        kwargs["base_url"] = cfg.base_url
    api_key = os.environ.get(cfg.api_key_env)
    if api_key:
        kwargs["api_key"] = api_key
    return OpenAI(**kwargs)


def _call_openai_compatible(
    extracted: Dict[str, Any],
    *,
    cfg: ProviderConfig,
    client: Any,
    model: str,
) -> Dict[str, Any]:
    schema = StandardizedDocument.model_json_schema()
    user_content = json.dumps(extracted)
    if cfg.mode is StructuredOutputMode.OPENAI_STRICT:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "StandardizedDocument",
                    "schema": schema,
                    "strict": True,
                },
            },
        )
    else:
        system_with_schema = (
            SYSTEM_PROMPT
            + "\n\nReturn one JSON object that conforms to this JSON Schema. "
            + "No prose, no markdown fences:\n"
            + json.dumps(schema)
        )
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_with_schema},
                {"role": "user", "content": user_content},
            ],
            response_format={"type": "json_object"},
        )
    content = response.choices[0].message.content or ""
    return json.loads(content)


def _call_anthropic(
    extracted: Dict[str, Any],
    *,
    client: Any,
    model: str,
) -> Dict[str, Any]:
    schema = StandardizedDocument.model_json_schema()
    response = client.messages.create(
        model=model,
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        tools=[
            {
                "name": "emit_standardized_document",
                "description": "Emit the normalized document as a JSON object.",
                "input_schema": schema,
            }
        ],
        tool_choice={"type": "tool", "name": "emit_standardized_document"},
        messages=[{"role": "user", "content": json.dumps(extracted)}],
    )
    for block in response.content:
        if getattr(block, "type", None) == "tool_use":
            return block.input
    raise NormalizationFailed("Anthropic response did not include a tool_use block")


def _build_anthropic_client() -> Any:
    from anthropic import Anthropic

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    return Anthropic(api_key=api_key) if api_key else Anthropic()


def normalize(
    extracted: Dict[str, Any],
    client: Any | None = None,
    provider: ProviderConfig | None = None,
) -> StandardizedDocument:
    cfg = provider or _resolve_provider()
    model = _resolve_model(cfg)

    def _call() -> StandardizedDocument:
        if cfg.mode is StructuredOutputMode.ANTHROPIC_TOOL:
            c = client or _build_anthropic_client()
            data = _call_anthropic(extracted, client=c, model=model)
        else:
            c = client or _build_openai_client(cfg)
            data = _call_openai_compatible(
                extracted, cfg=cfg, client=c, model=model
            )
        return StandardizedDocument.model_validate(data)

    return call_with_retry(_call, retries=1)
