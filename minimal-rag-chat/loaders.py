"""File loaders: map a file path to plain text.

Supported extensions: .md, .txt, .pdf. PDF extraction goes through
pymupdf4llm and returns markdown-formatted text.
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterator, Union

SUPPORTED_EXTENSIONS = frozenset({".md", ".txt", ".pdf"})


def load(path: Union[str, Path]) -> str:
    p = Path(path)
    ext = p.suffix.lower()
    if ext in (".md", ".txt"):
        return p.read_text(encoding="utf-8")
    if ext == ".pdf":
        try:
            import pymupdf4llm
        except ImportError as exc:
            raise RuntimeError(
                "PDF loading requires pymupdf4llm. Run `uv sync`."
            ) from exc
        return pymupdf4llm.to_markdown(str(p))
    raise ValueError(
        f"Unsupported file type: {ext}. Supported: {sorted(SUPPORTED_EXTENSIONS)}"
    )


def iter_files(root: Union[str, Path]) -> Iterator[Path]:
    root = Path(root)
    for p in sorted(root.rglob("*")):
        if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS:
            yield p
