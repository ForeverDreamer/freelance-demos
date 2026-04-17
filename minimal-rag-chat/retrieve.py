"""Hybrid retrieval. Fuses BM25 keyword ranks and vector cosine ranks via RRF."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Union

import numpy as np
from rank_bm25 import BM25Okapi

from providers import Embedder


@dataclass
class Hit:
    doc: str
    chunk_id: int
    text: str
    score: float


_TOKEN_RE = re.compile(r"\w+", re.UNICODE)


def tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


class Store:
    """JSONL-backed vector store with an in-memory BM25 index."""

    def __init__(self, path: Union[str, Path]) -> None:
        self.records: list[dict] = []
        with Path(path).open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    self.records.append(json.loads(line))
        if self.records:
            self.vectors = np.array(
                [r["embedding"] for r in self.records], dtype=np.float32
            )
            self._bm25 = BM25Okapi([tokenize(r["text"]) for r in self.records])
        else:
            self.vectors = np.zeros((0, 1), dtype=np.float32)
            self._bm25 = None

    def __len__(self) -> int:
        return len(self.records)

    def search(
        self,
        query: str,
        embedder: Embedder,
        top_k: int,
        rrf_k: int = 60,
    ) -> list[Hit]:
        if not self.records:
            return []

        qvec = np.array(embedder.embed([query])[0], dtype=np.float32)
        vec_norms = np.linalg.norm(self.vectors, axis=1) + 1e-9
        q_norm = float(np.linalg.norm(qvec)) + 1e-9
        cos = (self.vectors @ qvec) / (vec_norms * q_norm)
        vec_ranked = np.argsort(-cos)

        bm25_scores = self._bm25.get_scores(tokenize(query))
        bm25_ranked = np.argsort(-bm25_scores)

        rrf: dict[int, float] = {}
        for rank, idx in enumerate(vec_ranked):
            rrf[int(idx)] = rrf.get(int(idx), 0.0) + 1.0 / (rrf_k + rank + 1)
        for rank, idx in enumerate(bm25_ranked):
            rrf[int(idx)] = rrf.get(int(idx), 0.0) + 1.0 / (rrf_k + rank + 1)

        ordered = sorted(rrf.items(), key=lambda kv: kv[1], reverse=True)[:top_k]
        return [
            Hit(
                doc=self.records[i]["doc"],
                chunk_id=self.records[i]["chunk_id"],
                text=self.records[i]["text"],
                score=float(score),
            )
            for i, score in ordered
        ]
