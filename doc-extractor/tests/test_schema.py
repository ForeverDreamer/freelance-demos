"""Schema-only smoke test.

The full pipeline (parser + extractor + Ollama) is not run in this
sketch. The paid build ships an integration test suite that hits a real
Ollama / vLLM endpoint and asserts field-level confidence routing.

TODO: see private repo for the full test matrix.
"""
from __future__ import annotations

from decimal import Decimal

from src.schema import Invoice, LineItem


def test_invoice_minimal_payload_validates() -> None:
    payload = {
        "vendor": "Acme Supplies Ltd",
        "invoice_number": "INV-2025-0042",
        "issue_date": "2025-08-15",
        "currency": "EUR",
        "total": "1234.56",
        "line_items": [
            {"description": "Widget", "quantity": "2", "unit_price": "100.00", "line_total": "200.00"},
        ],
    }
    invoice = Invoice.model_validate(payload)
    assert invoice.vendor == "Acme Supplies Ltd"
    assert invoice.total == Decimal("1234.56")
    assert len(invoice.line_items) == 1
    assert isinstance(invoice.line_items[0], LineItem)
