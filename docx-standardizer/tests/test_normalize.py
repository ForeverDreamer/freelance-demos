import json
from typing import Any
from unittest.mock import MagicMock

import pytest

from normalize import NormalizationFailed, normalize
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
