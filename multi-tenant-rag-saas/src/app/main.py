"""Core application service (port 8001).

Chat endpoints, RAG retrieval, JWT auth, SocketIO streaming.

This is a public architecture sketch. Keep the structure, the full
implementation lives in the private repo.
TODO: see private repo for full impl.
"""
from __future__ import annotations

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from ..share.models import User
from .auth import require_user  # TODO: see private repo
from .routers import chat, rag, sessions  # TODO: see private repo

app = FastAPI(title="multi-tenant-rag-saas / app", version="0.1.0-sketch")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["<YOUR_FRONTEND_ORIGIN>"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router, prefix="/api/v1/chat", tags=["chat"])
app.include_router(rag.router, prefix="/api/v1/rag", tags=["rag"])
app.include_router(sessions.router, prefix="/api/v1/sessions", tags=["sessions"])


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "app"}


@app.get("/api/v1/me")
async def me(user: User = Depends(require_user)) -> dict[str, object]:
    """Who am I, with tenant scope embedded. Used by the frontend to
    hydrate the session bar and to gate admin-only routes.

    TODO: see private repo for the full user shape (billing plan,
    token budget remaining, feature flags).
    """
    return {
        "user_id": str(user.id),
        "tenant_id": str(user.tenant_id),
        "effective_role": user.effective_role,
    }


# Socket.IO server is attached in a sibling module and mounted here in
# the real build, so WebSocket streaming shares auth with HTTP routes.
# TODO: see private repo for full impl of socketio_server.
