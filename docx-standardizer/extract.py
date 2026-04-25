"""Extract title, paragraphs (with style names), tables, and metadata from a .docx file using python-docx. Output is a dict suitable for serialization to OpenAI."""

from pathlib import Path
from typing import Any, Dict, List

from docx import Document


def extract(path: Path) -> Dict[str, Any]:
    doc = Document(str(path))
    paragraphs: List[Dict[str, str]] = []
    for p in doc.paragraphs:
        if not p.text.strip():
            continue
        paragraphs.append(
            {
                "style": p.style.name if p.style else "Normal",
                "text": p.text,
            }
        )
    tables: List[List[List[str]]] = []
    for t in doc.tables:
        rows: List[List[str]] = []
        for row in t.rows:
            rows.append([cell.text for cell in row.cells])
        tables.append(rows)
    cp = doc.core_properties
    metadata = {
        "author": cp.author or "",
        "created": cp.created.isoformat() if cp.created else "",
        "modified": cp.modified.isoformat() if cp.modified else "",
        "title": cp.title or "",
    }
    title = paragraphs[0]["text"] if paragraphs else metadata["title"]
    return {
        "title": title,
        "paragraphs": paragraphs,
        "tables": tables,
        "metadata": metadata,
    }
