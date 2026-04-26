import json
from typing import Any
from unittest.mock import MagicMock

import pytest

from normalize import NormalizationFailed, normalize
from providers import resolve
from schema import StandardizedDocument


@pytest.fixture
def fixture_normalized_payload() -> dict[str, Any]:
    return {
        "title": "Test SOP",
        "document_control": {
            "doc_id": "SOP-001",
            "owner": "Ops",
            "approval": "CTO",
            "effective_date": "2026-01-01",
        },
        "purpose": "Define a thing.",
        "scope": "All staff.",
        "definitions": [{"term": "Staff", "meaning": "All hired persons."}],
        "responsibilities": [{"role": "Ops", "duties": "Run SOP."}],
        "procedure": [{"step_number": 1, "action": "Start."}],
        "records": ["audit-log"],
        "references": ["NIST 800-53"],
        "revision_history": [
            {
                "version": "1.0",
                "date": "2026-01-01",
                "author": "A",
                "summary": "Initial.",
            }
        ],
    }


def _mock_client(contents: list[str]) -> MagicMock:
    """Each entry in `contents` is the string returned by one mocked API call."""
    client = MagicMock()
    responses = []
    for c in contents:
        response = MagicMock()
        response.choices = [MagicMock(message=MagicMock(content=c))]
        responses.append(response)
    client.chat.completions.create.side_effect = responses
    return client


def test_normalize_happy_path(fixture_normalized_payload: dict[str, Any]) -> None:
    client = _mock_client([json.dumps(fixture_normalized_payload)])
    out = normalize(
        {"title": "x", "paragraphs": [], "tables": [], "metadata": {}},
        client=client,
    )
    assert isinstance(out, StandardizedDocument)
    assert out.title == "Test SOP"
    assert out.procedure[0].action == "Start."


def test_normalize_retries_once_on_validation_error(
    fixture_normalized_payload: dict[str, Any],
) -> None:
    invalid = json.dumps({"title": "missing required fields"})
    valid = json.dumps(fixture_normalized_payload)
    client = _mock_client([invalid, valid])
    out = normalize(
        {"title": "x", "paragraphs": [], "tables": [], "metadata": {}},
        client=client,
    )
    assert out.title == "Test SOP"
    assert client.chat.completions.create.call_count == 2


def test_normalize_fails_after_retry_exhausted() -> None:
    invalid = json.dumps({"title": "missing required fields"})
    client = _mock_client([invalid, invalid])
    with pytest.raises(NormalizationFailed):
        normalize(
            {"title": "x", "paragraphs": [], "tables": [], "metadata": {}},
            client=client,
        )
    assert client.chat.completions.create.call_count == 2


def test_normalize_deepseek_uses_json_object_mode_with_schema_in_prompt(
    fixture_normalized_payload: dict[str, Any],
) -> None:
    """DeepSeek (and other JSON_OBJECT-mode providers) get the schema
    embedded in the system prompt and ask for response_format json_object.
    Pydantic is the validation gate."""
    client = _mock_client([json.dumps(fixture_normalized_payload)])
    out = normalize(
        {"title": "x", "paragraphs": [], "tables": [], "metadata": {}},
        client=client,
        provider=resolve("deepseek"),
    )
    assert isinstance(out, StandardizedDocument)
    assert out.title == "Test SOP"

    call_kwargs = client.chat.completions.create.call_args.kwargs
    assert call_kwargs["response_format"] == {"type": "json_object"}
    assert call_kwargs["model"] == "deepseek-chat"
    system_msg = call_kwargs["messages"][0]["content"]
    assert "JSON Schema" in system_msg
    assert "StandardizedDocument" in system_msg


def test_normalize_claude_uses_tool_use_with_input_schema(
    fixture_normalized_payload: dict[str, Any],
) -> None:
    """Claude returns the structured payload as a tool_use block; the
    normalizer pulls `input` off it and validates with Pydantic."""
    client = MagicMock()
    tool_use_block = MagicMock(type="tool_use", input=fixture_normalized_payload)
    response = MagicMock(content=[tool_use_block])
    client.messages.create.return_value = response

    out = normalize(
        {"title": "x", "paragraphs": [], "tables": [], "metadata": {}},
        client=client,
        provider=resolve("claude"),
    )
    assert isinstance(out, StandardizedDocument)
    assert out.title == "Test SOP"

    call_kwargs = client.messages.create.call_args.kwargs
    assert call_kwargs["model"] == "claude-sonnet-4-5"
    assert call_kwargs["tool_choice"] == {
        "type": "tool",
        "name": "emit_standardized_document",
    }
    assert call_kwargs["tools"][0]["input_schema"]["title"] == "StandardizedDocument"
