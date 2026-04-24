"""WebSocket service (port 8003).

Dedicated raw WebSocket service for real-time events like
notifications and presence. Chat streaming itself lives on the `app`
service via Socket.IO, kept separate so chat can scale independently
from presence.

TODO: see private repo for full impl.
"""
from __future__ import annotations

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

app = FastAPI(title="multi-tenant-rag-saas / ws", version="0.1.0-sketch")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "ws"}


@app.websocket("/ws/events")
async def events(ws: WebSocket) -> None:
    """Per-tenant event stream.

    Real build authenticates via a short-lived token in the
    Sec-WebSocket-Protocol header, resolves tenant_id + user_id, and
    subscribes the connection to the tenant's Redis pub/sub channel.

    TODO: see private repo for auth + subscription wiring.
    """
    await ws.accept()
    try:
        while True:
            msg = await ws.receive_text()
            await ws.send_json({"echo": msg, "note": "sketch only"})
    except WebSocketDisconnect:
        return
