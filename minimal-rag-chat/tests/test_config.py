from __future__ import annotations

from pathlib import Path

import pytest

from config import load_config


def _write(tmp: Path, body: str) -> Path:
    p = tmp / "rag.yaml"
    p.write_text(body, encoding="utf-8")
    return p


def test_load_minimal(tmp_path: Path) -> None:
    cfg = load_config(
        _write(
            tmp_path,
            """
embeddings:
  provider: fake
  model: none
llm:
  provider: fake
  model: none
""",
        )
    )
    assert cfg.embeddings.provider == "fake"
    assert cfg.llm.provider == "fake"
    assert cfg.retrieval.top_k == 4
    assert cfg.retrieval.chunk_size == 800


def test_load_full(tmp_path: Path) -> None:
    cfg = load_config(
        _write(
            tmp_path,
            """
embeddings:
  provider: openai
  model: text-embedding-3-small
llm:
  provider: anthropic
  model: claude-haiku-4-5-20251001
  temperature: 0.2
  max_tokens: 256
retrieval:
  top_k: 8
  chunk_size: 500
  chunk_overlap: 50
storage:
  path: ./custom.jsonl
""",
        )
    )
    assert cfg.llm.provider == "anthropic"
    assert cfg.llm.temperature == pytest.approx(0.2)
    assert cfg.retrieval.top_k == 8
    assert cfg.storage.path == "./custom.jsonl"


def test_load_rejects_non_mapping(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        load_config(_write(tmp_path, "- just a list\n- not a mapping\n"))
