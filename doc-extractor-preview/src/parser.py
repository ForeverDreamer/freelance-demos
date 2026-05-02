"""Docling-based document parser (CPU-only).

Returns the document text content as Markdown for the LLM extractor.
Docling handles PDF / image / DOCX / PPTX in one API.

This sketch uses the default conversion pipeline. The paid build adds
PaddleOCR-VL (109-language OCR including Latvian / Russian / Arabic /
CJK), MinerU2.5-Pro for tables-heavy documents, and Chandra for
handwriting-heavy briefs as alternate parsers behind the same protocol.

TODO: see private repo for adapter pattern + parser swap by profile.
"""
from __future__ import annotations

from pathlib import Path

from docling.document_converter import DocumentConverter

_converter = DocumentConverter()


def parse_to_text(file_path: str | Path) -> str:
    """Parse a document file and return its text content as Markdown."""
    result = _converter.convert(str(file_path))
    return result.document.export_to_markdown()
