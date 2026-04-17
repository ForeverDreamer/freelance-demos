from __future__ import annotations

from pathlib import Path

import pytest

from loaders import SUPPORTED_EXTENSIONS, iter_files, load


def test_load_markdown(tmp_path: Path) -> None:
    f = tmp_path / "a.md"
    f.write_text("# Heading\n\nBody.", encoding="utf-8")
    assert load(f).startswith("# Heading")


def test_load_txt(tmp_path: Path) -> None:
    f = tmp_path / "notes.txt"
    f.write_text("plain text", encoding="utf-8")
    assert load(f) == "plain text"


def test_load_unsupported(tmp_path: Path) -> None:
    f = tmp_path / "x.docx"
    f.write_bytes(b"binary")
    with pytest.raises(ValueError):
        load(f)


def test_iter_files_filters_and_sorts(tmp_path: Path) -> None:
    (tmp_path / "b.md").write_text("b", encoding="utf-8")
    (tmp_path / "a.md").write_text("a", encoding="utf-8")
    (tmp_path / "skip.docx").write_bytes(b"skip")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "c.txt").write_text("c", encoding="utf-8")

    names = [p.name for p in iter_files(tmp_path)]
    assert names == ["a.md", "b.md", "c.txt"]


def test_supported_extensions_frozen() -> None:
    assert ".md" in SUPPORTED_EXTENSIONS
    assert ".txt" in SUPPORTED_EXTENSIONS
    assert ".pdf" in SUPPORTED_EXTENSIONS
