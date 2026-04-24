"""Token accounting for LLM calls across tenants and users.

Exposes a tracked-LLM wrapper (for completions) and a tracked-embedder
wrapper (for vector ingest). Both record token usage per call into
the admin service's `token_usage` table via an internal HTTP endpoint,
so the `app` service does not share the database directly with admin.

This is a public architecture sketch.
TODO: see private repo for full impl.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

BillingModel = Literal["pay_per_use", "prepaid", "monthly_limit"]
UsageOp = Literal["chat", "embed"]


@dataclass
class UsageEvent:
    tenant_id: str
    user_id: str
    model_name: str
    input_tokens: int
    output_tokens: int
    op: UsageOp = "chat"


class BillingCapExceeded(Exception):
    """Raised when a monthly_limit tenant would cross their cap."""


class InsufficientBalance(Exception):
    """Raised when a prepaid tenant has run out of balance."""


async def record_usage(event: UsageEvent) -> None:
    """Persist a usage event and enforce the tenant's billing model.

    Sketch of the real behavior:
      - Insert a row into token_usage (tenant, user, model, in, out,
        op, ts).
      - Update per-tenant daily / monthly rollups in Redis (fast
        read for the chat path, which must decide before each call
        whether to serve).
      - Dispatch on the tenant's billing_model:
          pay_per_use   : accrue cost from the model price table,
                          no block.
          prepaid       : debit balance, raise InsufficientBalance
                          if it would go negative.
          monthly_limit : raise BillingCapExceeded if month-to-date
                          tokens would cross the cap.

    TODO: see private repo for the full implementation.
    """
    raise NotImplementedError("see private repo")


def cost_of(event: UsageEvent) -> float:
    """Compute USD cost for a usage event from the model price table.

    Sketch:
      price_table keyed by (provider, model_name), each entry has
      input_price and output_price per 1M tokens. Return:

          (in * input_price + out * output_price) / 1_000_000

    TODO: see private repo for the price table and provider resolution.
    """
    raise NotImplementedError("see private repo")
