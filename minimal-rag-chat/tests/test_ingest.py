from __future__ import annotations

import json
from pathlib import Path

import pytest

from ingest import ingest, split_text
from providers import FakeEmbedder


def test_split_small_text_is_one_chunk() -> None:
    chunks = split_text("Short doc.", chunk_size=800, chunk_overlap=100)
    assert chunks == ["Short doc."]


def test_split_respects_chunk_size() -> None:
    body = "\n\n".join([f"Para {i} " + "x" * 200 for i in range(5)])
    chunks = split_text(body, chunk_size=250, chunk_overlap=0)
    # Each paragraph is ~208 chars so each becomes its own chunk.
    assert len(chunks) == 5
    assert all(len(c) <= 260 for c in chunks)


def test_split_overlap_prefixes_tail() -> None:
    body = "AAAA\n\nBBBB\n\nCCCC"
    # chunk_size=4 forces one paragraph per chunk.
    chunks = split_text(body, chunk_size=4, chunk_overlap=2)
    assert chunks[0] == "AAAA"
    assert chunks[1].startswith("AA")
    assert "BBBB" in chunks[1]


def test_split_rejects_bad_args() -> None:
    with pytest.raises(ValueError):
        split_text("x", chunk_size=0, chunk_overlap=0)
    with pytest.raises(ValueError):
        split_text("x", chunk_size=10, chunk_overlap=-1)


def test_ingest_writes_jsonl(tmp_path: Path) -> None:
    doc = tmp_path / "a.md"
    doc.write_text("Alpha paragraph.\n\nBeta paragraph.", encoding="utf-8")
    store = tmp_path / "store.jsonl"

    n = ingest(
        source=tmp_path,
        store_path=store,
        embedder=FakeEmbedder(),
        chunk_size=800,
        chunk_overlap=0,
    )

    assert n == 1  # two short paras pack into a single chunk
    records = [json.loads(l) for l in store.read_text().splitlines()]
    assert len(records) == 1
    rec = records[0]
    assert rec["doc"].endswith("a.md")
    assert rec["chunk_id"] == 0
    assert "Alpha" in rec["text"] and "Beta" in rec["text"]
    assert len(rec["embedding"]) == FakeEmbedder.dim


def test_ingest_empty_dir_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        ingest(
            source=tmp_path,
            store_path=tmp_path / "s.jsonl",
            embedder=FakeEmbedder(),
            chunk_size=100,
            chunk_overlap=0,
        )
