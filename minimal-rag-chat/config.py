"""YAML config loader for minimal-rag-chat."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Union

import yaml


@dataclass
class EmbeddingsConfig:
    provider: str
    model: str


@dataclass
class LLMConfig:
    provider: str
    model: str
    temperature: float = 0.0
    max_tokens: int = 512


@dataclass
class RetrievalConfig:
    top_k: int = 4
    chunk_size: int = 800
    chunk_overlap: int = 100


@dataclass
class StorageConfig:
    path: str = "./vector_store.jsonl"


@dataclass
class Config:
    embeddings: EmbeddingsConfig
    llm: LLMConfig
    retrieval: RetrievalConfig = field(default_factory=RetrievalConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)


def load_config(path: Union[str, Path]) -> Config:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Config root must be a mapping.")
    return Config(
        embeddings=EmbeddingsConfig(**data["embeddings"]),
        llm=LLMConfig(**data["llm"]),
        retrieval=RetrievalConfig(**data.get("retrieval", {})),
        storage=StorageConfig(**data.get("storage", {})),
    )
