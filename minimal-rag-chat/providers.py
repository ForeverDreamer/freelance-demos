"""Embedding and chat provider abstractions.

Three provider families are wired in:
- openai: production path for embeddings and chat
- anthropic: production path for chat (Claude models)
- fake: deterministic, no-network fallback for tests and no-key demo runs
"""
from __future__ import annotations

import hashlib
from typing import Protocol

import numpy as np


class Embedder(Protocol):
    dim: int

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class Chat(Protocol):
    def complete(self, system: str, user: str) -> str: ...


# ---------- Embedders ----------


class FakeEmbedder:
    """Hash-based deterministic embedder. Not semantic, but stable and offline."""

    dim = 128

    def embed(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for t in texts:
            h = hashlib.sha256(t.encode("utf-8")).digest()
            arr = np.frombuffer(h, dtype=np.uint8).astype(np.float32)
            arr = np.tile(arr, 4)[: self.dim] / 127.5 - 1.0
            arr = arr / (np.linalg.norm(arr) + 1e-9)
            out.append(arr.tolist())
        return out


class OpenAIEmbedder:
    def __init__(self, model: str = "text-embedding-3-small") -> None:
        from openai import OpenAI

        self._client = OpenAI()
        self.model = model
        self.dim = 1536

    def embed(self, texts: list[str]) -> list[list[float]]:
        resp = self._client.embeddings.create(model=self.model, input=texts)
        return [d.embedding for d in resp.data]


def get_embedder(provider: str, model: str) -> Embedder:
    if provider == "openai":
        return OpenAIEmbedder(model=model)
    if provider == "fake":
        return FakeEmbedder()
    raise ValueError(f"Unknown embedding provider: {provider}")


# ---------- Chat ----------


class FakeChat:
    """Echoes a short structured reply so integration tests stay deterministic."""

    def complete(self, system: str, user: str) -> str:
        head = user.splitlines()[0] if user else ""
        return f"[fake-llm] sys={len(system)}ch head={head[:80]}"


class OpenAIChat:
    def __init__(self, model: str, temperature: float, max_tokens: int) -> None:
        from openai import OpenAI

        self._client = OpenAI()
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

    def complete(self, system: str, user: str) -> str:
        resp = self._client.chat.completions.create(
            model=self.model,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return resp.choices[0].message.content or ""


class AnthropicChat:
    def __init__(self, model: str, temperature: float, max_tokens: int) -> None:
        from anthropic import Anthropic

        self._client = Anthropic()
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

    def complete(self, system: str, user: str) -> str:
        resp = self._client.messages.create(
            model=self.model,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        parts = [b.text for b in resp.content if hasattr(b, "text")]
        return "".join(parts)


def get_chat(provider: str, model: str, temperature: float, max_tokens: int) -> Chat:
    if provider == "openai":
        return OpenAIChat(model=model, temperature=temperature, max_tokens=max_tokens)
    if provider == "anthropic":
        return AnthropicChat(
            model=model, temperature=temperature, max_tokens=max_tokens
        )
    if provider == "fake":
        return FakeChat()
    raise ValueError(f"Unknown chat provider: {provider}")
