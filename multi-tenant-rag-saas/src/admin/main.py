"""Admin service (port 8002).

Tenants, users, roles, billing, token usage tracking, document
ingestion, embedding tracker.

TODO: see private repo for full impl.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI

from ..share.models import User
from .auth import require_role  # TODO: see private repo
from .services.token_tracker import UsageEvent, record_usage

app = FastAPI(title="multi-tenant-rag-saas / admin", version="0.1.0-sketch")

billing_router = APIRouter(prefix="/api/v1/billing", tags=["billing"])
tenants_router = APIRouter(prefix="/api/v1/tenants", tags=["tenants"])
users_router = APIRouter(prefix="/api/v1/users", tags=["users"])
documents_router = APIRouter(prefix="/api/v1/documents", tags=["documents"])
internal_router = APIRouter(prefix="/api/v1/internal", tags=["internal"])


@internal_router.post("/token-usage")
async def ingest_token_usage(event: UsageEvent) -> dict[str, str]:
    """Called by the `app` service after every LLM or embedding call.

    Not exposed publicly. Bound to the internal Docker network only,
    protected by a shared secret header in the real build.
    TODO: see private repo for shared-secret middleware.
    """
    await record_usage(event)
    return {"status": "recorded"}


@billing_router.get("/plans")
async def list_billing_plans(
    _: User = Depends(require_role("tenant_admin")),
) -> list[dict[str, object]]:
    """Three billing models available to tenants.

    - pay_per_use: no cap, accrued cost billed monthly
    - prepaid: balance debited per call, zero stops service
    - monthly_limit: hard token cap, resets first of month

    TODO: see private repo for the real price table per model.
    """
    return [
        {"model": "pay_per_use", "hard_cap": False, "upfront": False},
        {"model": "prepaid", "hard_cap": True, "upfront": True},
        {"model": "monthly_limit", "hard_cap": True, "upfront": False},
    ]


app.include_router(billing_router)
app.include_router(tenants_router)
app.include_router(users_router)
app.include_router(documents_router)
app.include_router(internal_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "admin"}
