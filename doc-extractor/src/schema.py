"""Minimal invoice schema (5 core fields + line items).

This baseline ships only the fields a non-technical reviewer can sanity-check
on first run. The full pipeline aligns to EN 16931 / Peppol BIS Billing 3.0
with 100+ fields, VAT lines, payment terms, supplier/buyer party blocks, etc.
See README "What this preview does NOT do" for the gap.
"""
from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field


class LineItem(BaseModel):
    description: str = Field(description="Item description as printed on the invoice")
    quantity: Decimal = Field(default=Decimal("1"), description="Quantity")
    unit_price: Decimal | None = Field(default=None, description="Unit price excl. tax")
    line_total: Decimal | None = Field(default=None, description="Line subtotal")


class Invoice(BaseModel):
    vendor: str = Field(description="Supplier / vendor name")
    invoice_number: str = Field(description="Invoice number as printed")
    issue_date: str = Field(description="Issue date in YYYY-MM-DD if recognizable, otherwise raw text")
    currency: str = Field(description="ISO 4217 currency code (EUR, USD, etc.) or raw symbol")
    total: Decimal = Field(description="Grand total including tax")
    line_items: list[LineItem] = Field(default_factory=list)
