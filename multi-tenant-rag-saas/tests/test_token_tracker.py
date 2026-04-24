"""Representative test for the token tracker shape.

The real suite covers billing model dispatch, Redis rollup math,
cap enforcement edge cases, and concurrent-write ordering. This
file shows the shape and leaves the full behavior as a stub.

TODO: see private repo for full impl.
"""
from __future__ import annotations

import pytest

from src.admin.services.token_tracker import (
    BillingCapExceeded,
    InsufficientBalance,
    UsageEvent,
    cost_of,
    record_usage,
)


def _event(**overrides: object) -> UsageEvent:
    base = dict(
        tenant_id="11111111-1111-1111-1111-111111111111",
        user_id="22222222-2222-2222-2222-222222222222",
        model_name="gpt-4o",
        input_tokens=100,
        output_tokens=50,
        op="chat",
    )
    base.update(overrides)
    return UsageEvent(**base)  # type: ignore[arg-type]


def test_usage_event_defaults_to_chat_op() -> None:
    event = _event()
    assert event.op == "chat"


@pytest.mark.xfail(reason="sketch only, see private repo", strict=True)
def test_cost_of_matches_price_table() -> None:
    event = _event(input_tokens=1_000_000, output_tokens=0)
    cost_of(event)


@pytest.mark.xfail(reason="sketch only, see private repo", strict=True)
@pytest.mark.asyncio
async def test_record_usage_monthly_limit_enforced() -> None:
    event = _event()
    with pytest.raises(BillingCapExceeded):
        await record_usage(event)


@pytest.mark.xfail(reason="sketch only, see private repo", strict=True)
@pytest.mark.asyncio
async def test_record_usage_prepaid_debits_balance() -> None:
    event = _event()
    with pytest.raises(InsufficientBalance):
        await record_usage(event)
