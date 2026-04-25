from pathlib import Path

import pytest
from docx import Document

from extract import extract


@pytest.fixture
def sample_docx(tmp_path: Path) -> Path:
    p = tmp_path / "sample.docx"
    doc = Document()
    doc.core_properties.author = "Test Author"
    doc.core_properties.title = "Test Title"
    doc.add_paragraph("My Title", style="Title")
    doc.add_paragraph("First Section", style="Heading 1")
    doc.add_paragraph("Body text here.", style="Normal")
    table = doc.add_table(rows=2, cols=2)
    table.rows[0].cells[0].text = "k1"
    table.rows[0].cells[1].text = "v1"
    table.rows[1].cells[0].text = "k2"
    table.rows[1].cells[1].text = "v2"
    doc.save(str(p))
    return p


def test_extract_returns_title(sample_docx: Path) -> None:
    out = extract(sample_docx)
    assert out["title"] == "My Title"


def test_extract_paragraph_styles(sample_docx: Path) -> None:
    out = extract(sample_docx)
    styles = {p["style"] for p in out["paragraphs"]}
    assert "Title" in styles
    assert "Heading 1" in styles
    assert "Normal" in styles


def test_extract_tables(sample_docx: Path) -> None:
    out = extract(sample_docx)
    assert len(out["tables"]) == 1
    assert out["tables"][0] == [["k1", "v1"], ["k2", "v2"]]


def test_extract_metadata(sample_docx: Path) -> None:
    out = extract(sample_docx)
    assert out["metadata"]["author"] == "Test Author"
