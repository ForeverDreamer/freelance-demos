"""Ingestion: read docs, chunk, embed, and persist to a JSONL vector store.

Store format (one record per line):
    {"doc": "...", "chunk_id": 0, "text": "...", "embedding": [...]}
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Union

from loaders import iter_files, load
from providers import Embedder


@dataclass
class Chunk:
    doc: str
    chunk_id: int
    text: str
    embedding: list[float]


def split_text(text: str, chunk_size: int, chunk_overlap: int) -> list[str]:
    """Paragraph-aware greedy splitter with tail overlap on every non-first chunk.

    Paragraphs larger than chunk_size are hard-split. The first chunk has no
    prefix; each subsequent chunk is prefixed by the last chunk_overlap chars
    of the previous chunk to preserve context across boundaries.
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if chunk_overlap < 0:
        raise ValueError("chunk_overlap must be non-negative")

    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for p in paras:
        if len(p) > chunk_size:
            if current:
                chunks.append("\n\n".join(current))
                current, current_len = [], 0
            for i in range(0, len(p), chunk_size):
                chunks.append(p[i : i + chunk_size])
            continue
        added_len = len(p) + (2 if current else 0)
        if current_len + added_len > chunk_size:
            chunks.append("\n\n".join(current))
            current, current_len = [p], len(p)
        else:
            current.append(p)
            current_len += added_len
    if current:
        chunks.append("\n\n".join(current))

    if chunk_overlap == 0 or len(chunks) < 2:
        return chunks

    out = [chunks[0]]
    for i in range(1, len(chunks)):
        prev_tail = chunks[i - 1][-chunk_overlap:]
        out.append(prev_tail + "\n\n" + chunks[i])
    return out


def ingest(
    source: Union[str, Path],
    store_path: Union[str, Path],
    embedder: Embedder,
    chunk_size: int,
    chunk_overlap: int,
) -> int:
    """Load files under source, chunk, embed, and write the JSONL store."""
    src = Path(source)
    paths = [src] if src.is_file() else list(iter_files(src))
    if not paths:
        raise FileNotFoundError(f"No supported files found under {src}")

    items: list[tuple[str, int, str]] = []
    for p in paths:
        text = load(p)
        for i, chunk_text in enumerate(split_text(text, chunk_size, chunk_overlap)):
            items.append((str(p), i, chunk_text))

    texts = [t for _, _, t in items]
    vectors = embedder.embed(texts) if texts else []

    store = Path(store_path)
    store.parent.mkdir(parents=True, exist_ok=True)
    with store.open("w", encoding="utf-8") as f:
        for (doc, cid, text), vec in zip(items, vectors):
            record = Chunk(doc=doc, chunk_id=cid, text=text, embedding=vec)
            f.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")
    return len(items)
